# -*- coding: utf-8 -*-
"""Automatic texture-root discovery (v3.7 beta 4)."""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from apex_tex import roots            # noqa: E402


class ModelNameTest(unittest.TestCase):
    """The CAST importer names its collection after the .cast file."""

    def test_lod_suffix_is_stripped(self):
        self.assertEqual(roots.clean_model_name("wraith_v20_heist_w_LOD0"),
                         "wraith_v20_heist_w")
        self.assertEqual(roots.clean_model_name("wraith_v20_heist_w_lod12"),
                         "wraith_v20_heist_w")

    def test_datablock_suffix_is_stripped(self):
        self.assertEqual(roots.clean_model_name("wraith_v20_heist_w_LOD0.001"),
                         "wraith_v20_heist_w")

    def test_mesh_index_prefix_is_stripped(self):
        self.assertEqual(
            roots.clean_model_name("body_0_wraith_lgnd_v20_boosted_body"),
            "wraith_lgnd_v20_boosted_body")

    def test_ordinary_names_survive(self):
        self.assertEqual(roots.clean_model_name("alter_lgnd_v24_body"),
                         "alter_lgnd_v24_body")

    def test_candidates_are_deduplicated_in_order(self):
        self.assertEqual(
            roots.model_names(["a_LOD0", "a_LOD1", "b", "a"]), ["a", "b"])


class BookmarksTest(unittest.TestCase):
    """Blender's file browser history is the cold-start anchor."""

    SAMPLE = "\n".join([
        "[Bookmarks]",
        "G:\\Graphics\\3D Art\\Renders\\",
        "G:\\Graphics\\3D Art\\Tools\\RSX\\exported_files\\mdl\\",
        "[Recent]",
        "G:\\Graphics\\3D Art\\Tools\\RSX\\exported_files\\mdl\\wraith_v20_heist_w\\",
        "G:\\Graphics\\3D Art\\Tools\\",
    ])

    def test_sections_are_separated(self):
        recent, bookmarks = roots.parse_bookmarks(self.SAMPLE)
        self.assertEqual(len(recent), 2)
        self.assertEqual(len(bookmarks), 2)
        self.assertTrue(recent[0].endswith("wraith_v20_heist_w\\"))

    def test_empty_and_malformed_input(self):
        self.assertEqual(roots.parse_bookmarks(""), ([], []))
        self.assertEqual(roots.parse_bookmarks(None), ([], []))
        self.assertEqual(roots.parse_bookmarks("nonsense\nlines"), ([], []))

    def test_lists_are_capped(self):
        text = "[Recent]\n" + "\n".join("dir%d" % i for i in range(50))
        recent, _ = roots.parse_bookmarks(text, max_recent=3)
        self.assertEqual(len(recent), 3)


class RootDiscoveryCase(unittest.TestCase):

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="apex_roots_")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def mkdir(self, relative):
        path = os.path.join(self.base, relative.replace("/", os.sep))
        if not os.path.isdir(path):
            os.makedirs(path)
        return path

    def paths_of(self, discovered):
        return [os.path.normcase(r.path) for r in discovered]

    def assertFound(self, discovered, relative):
        wanted = os.path.normcase(os.path.normpath(
            os.path.join(self.base, relative.replace("/", os.sep))))
        self.assertIn(wanted, self.paths_of(discovered))


class ProbeTest(RootDiscoveryCase):
    """Known RSX / Legion layouts, found with isdir calls only."""

    def test_rsx_nested_layout(self):
        self.mkdir("mdl/wraith_v20_heist_w/wraith_v20_heist_w")
        found = roots.probe(os.path.join(self.base, "mdl"),
                            ["wraith_v20_heist_w"])
        self.assertEqual(len(found), 2)
        self.assertTrue(found[0].endswith(
            os.path.join("wraith_v20_heist_w", "wraith_v20_heist_w")))

    def test_export_root_layout(self):
        self.mkdir("wraith_v20_heist_w/wraith_v20_heist_w")
        found = roots.probe(self.base, ["wraith_v20_heist_w"])
        self.assertTrue(found)

    def test_legion_layouts(self):
        self.mkdir("legend_body/Materials")
        self.mkdir("legend_body/_images")
        found = roots.probe(self.base, ["legend_body"])
        self.assertEqual(len(found), 3)      # the folder plus both sub-folders

    def test_unknown_model_finds_nothing(self):
        self.mkdir("some_other_model")
        self.assertEqual(roots.probe(self.base, ["legend_body"]), [])

    def test_missing_base_is_safe(self):
        self.assertEqual(
            roots.probe(os.path.join(self.base, "nope"), ["x"]), [])


class LibraryRootTest(RootDiscoveryCase):
    """What a successful run should remember."""

    def test_remembers_the_export_and_the_library(self):
        textures = self.mkdir("mdl/wraith_v20_heist_w/wraith_v20_heist_w")
        learned = roots.library_roots(textures)
        self.assertTrue(learned)
        self.assertEqual(os.path.basename(learned[0]), "mdl")
        self.assertIn(
            os.path.normcase(os.path.join(self.base, "mdl",
                                          "wraith_v20_heist_w")),
            [os.path.normcase(p) for p in learned])

    def test_deduplicates_most_recent_first(self):
        result = roots.remember(["/a", "/b"], ["/b", "/c"])
        self.assertEqual([os.path.normpath(p) for p in result],
                         [os.path.normpath(p) for p in ("/b", "/c", "/a")])

    def test_memory_is_capped(self):
        result = roots.remember([], ["/p%d" % i for i in range(20)], limit=4)
        self.assertEqual(len(result), 4)


class DiscoverTest(RootDiscoveryCase):

    def test_material_image_directory_comes_first(self):
        textures = self.mkdir("mdl/model_w/model_w")
        found = roots.discover(material_dirs=[textures], names=["model_w"])
        self.assertEqual(os.path.normcase(found[0].path),
                         os.path.normcase(textures))
        self.assertEqual(found[0].rank, roots.RANK_MATERIAL_IMAGE)

    def test_cold_start_uses_the_browser_history(self):
        # No images, no manual folder, no memory: exactly the RSX "Real"
        # naming case that beta 3 could not resolve on its own.
        self.mkdir("mdl/wraith_v20_heist_w/wraith_v20_heist_w")
        found = roots.discover(
            names=["wraith_v20_heist_w_LOD0"],
            browsed=[os.path.join(self.base, "mdl")])
        self.assertFound(found, "mdl/wraith_v20_heist_w/wraith_v20_heist_w")

    def test_remembered_root_carries_a_later_model(self):
        self.mkdir("mdl/second_model_w/second_model_w")
        found = roots.discover(
            names=["second_model_w_LOD0"],
            remembered=[os.path.join(self.base, "mdl")])
        self.assertFound(found, "mdl/second_model_w/second_model_w")

    def test_manual_folder_outranks_memory(self):
        manual = self.mkdir("manual")
        self.mkdir("mdl/model_w")
        found = roots.discover(
            names=["model_w"], manual=manual,
            remembered=[os.path.join(self.base, "mdl")])
        ranks = dict((os.path.normcase(r.path), r.rank) for r in found)
        self.assertLess(ranks[os.path.normcase(manual)],
                        roots.RANK_REMEMBERED)

    def test_nothing_available_yields_nothing(self):
        self.assertEqual(roots.discover(names=["model_w"]), [])

    def test_missing_directories_are_skipped(self):
        found = roots.discover(
            material_dirs=[os.path.join(self.base, "gone")],
            manual=os.path.join(self.base, "also_gone"),
            names=["model_w"])
        self.assertEqual(found, [])

    def test_no_duplicate_roots(self):
        textures = self.mkdir("mdl/model_w/model_w")
        found = roots.discover(
            material_dirs=[textures, textures + os.sep],
            names=["model_w"],
            manual=textures,
            remembered=[textures],
            browsed=[textures],
            image_dirs=[textures])
        self.assertEqual(len(self.paths_of(found)),
                         len(set(self.paths_of(found))))

    def test_only_a_few_browsed_folders_become_plain_roots(self):
        browsed = [self.mkdir("b%d" % i) for i in range(10)]
        found = roots.discover(names=["model_w"], browsed=browsed)
        plain = [r for r in found if r.rank == roots.RANK_BROWSED]
        self.assertLessEqual(len(plain), 4)

    def test_recursive_only_where_asked(self):
        manual = self.mkdir("manual")
        found = roots.discover(names=["x"], manual=manual,
                               search_subfolders=False)
        self.assertFalse(any(r.recursive for r in found))
        found = roots.discover(names=["x"], manual=manual,
                               search_subfolders=True)
        self.assertTrue(any(r.recursive for r in found))

    def test_describe_is_readable(self):
        textures = self.mkdir("mdl/model_w/model_w")
        found = roots.discover(material_dirs=[textures], names=["model_w"])
        self.assertIn("material image", roots.describe(found))
        self.assertIn("no texture folder", roots.describe([]))


if __name__ == "__main__":
    unittest.main()
