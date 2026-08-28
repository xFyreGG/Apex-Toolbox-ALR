# -*- coding: utf-8 -*-
"""End to end resolution against real directories of (empty) texture files."""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from apex_tex import paths            # noqa: E402
from apex_tex import resolver         # noqa: E402
from apex_tex import roles as R       # noqa: E402

#: Roles the Apex Shader+ adapter asks for; used by most of the tests.
WANTED = [R.ALBEDO, R.SPECULAR, R.EMISSIVE, R.SCATTER, R.OPACITY, R.NORMAL,
          R.GLOSS, R.AO, R.CAVITY, R.ANISO_SPEC_DIR, R.IRIDESCENCE_RAMP,
          R.ROUGHNESS]


class ResolverCase(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="apex_tex_test_")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    # -- helpers ----------------------------------------------------------

    def write(self, relative, size=4096):
        path = os.path.join(self.root, relative.replace("/", os.sep))
        directory = os.path.dirname(path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory)
        with open(path, "wb") as handle:
            handle.write(b"\0" * size)
        return path

    def index_of(self, *relative_dirs, **kwargs):
        recursive = kwargs.pop("recursive", False)
        index = paths.TextureIndex()
        for relative in (relative_dirs or ("",)):
            index.add_root(os.path.join(self.root, relative.replace("/", os.sep)),
                           recursive=recursive)
        return index

    def resolve(self, material, index, graph_hits=(), wanted=None):
        return resolver.resolve_roles(
            material, wanted or WANTED, index, graph_hits=graph_hits)

    def assertResolved(self, results, role, filename, source=None):
        result = results[role]
        self.assertEqual(result.status, resolver.STATUS_RESOLVED,
                         "%s: %s (%s)" % (role, result.status, result.note))
        self.assertEqual(os.path.basename(result.display), filename)
        if source is not None:
            self.assertEqual(result.source, source)

    def assertUnresolved(self, results, role):
        self.assertEqual(results[role].status, resolver.STATUS_UNRESOLVED,
                         "%s unexpectedly %s -> %s" % (
                             role, results[role].status, results[role].display))


class LegacyTest(ResolverCase):
    """(1) A Legion+ export must resolve exactly as it always did."""

    MATERIAL = "wraith_lgnd_v19_liberator_body"

    def setUp(self):
        ResolverCase.setUp(self)
        for token in R.LEGACY_TOKENS.values():
            self.write("%s_%s.png" % (self.MATERIAL, token))

    def test_every_legacy_role_resolves_by_exact_name(self):
        results = self.resolve(self.MATERIAL, self.index_of())
        for role, token in R.LEGACY_TOKENS.items():
            self.assertResolved(results, role,
                                "%s_%s.png" % (self.MATERIAL, token),
                                source=resolver.SOURCE_LEGACY)

    def test_blender_duplicate_material_name_still_matches(self):
        # Blender renames a second copy of the material to "...body.001".
        results = self.resolve(self.MATERIAL + ".001", self.index_of())
        self.assertResolved(results, R.ALBEDO,
                            self.MATERIAL + "_albedoTexture.png",
                            source=resolver.SOURCE_LEGACY)


class RsxRealNamingTest(ResolverCase):
    """(2) "Real" naming: the file basename is the Apex asset name."""

    MATERIAL = "wraith_lgnd_v20_boosted_body"

    def setUp(self):
        ResolverCase.setUp(self)
        for suffix in ("col", "nml", "spc", "gls", "ao", "cav", "ilm"):
            self.write("wraith_v20_heist_w/%s_%s.png" % (self.MATERIAL, suffix))
        # A second material lives in the same folder. (23)
        for suffix in ("col", "nml", "spc", "gls", "ao", "cav", "ilm"):
            self.write("wraith_v20_heist_w/wraith_lgnd_v20_boosted_head_%s.png"
                       % suffix)

    def test_roles_resolve_by_family(self):
        index = self.index_of("wraith_v20_heist_w")
        results = self.resolve(self.MATERIAL, index)
        self.assertResolved(results, R.ALBEDO, self.MATERIAL + "_col.png",
                            source=resolver.SOURCE_FAMILY)
        self.assertResolved(results, R.NORMAL, self.MATERIAL + "_nml.png")
        self.assertResolved(results, R.SPECULAR, self.MATERIAL + "_spc.png")
        self.assertResolved(results, R.GLOSS, self.MATERIAL + "_gls.png")
        self.assertResolved(results, R.AO, self.MATERIAL + "_ao.png")
        self.assertResolved(results, R.CAVITY, self.MATERIAL + "_cav.png")
        self.assertResolved(results, R.EMISSIVE, self.MATERIAL + "_ilm.png")

    def test_head_material_never_gets_the_body_textures(self):
        # (23) multiple materials sharing one directory
        index = self.index_of("wraith_v20_heist_w")
        results = self.resolve("wraith_lgnd_v20_boosted_head", index)
        for role in (R.ALBEDO, R.NORMAL, R.SPECULAR, R.GLOSS, R.AO, R.CAVITY):
            self.assertIn("head", results[role].display, role)

    def test_missing_role_stays_unresolved(self):
        # (15) missing texture -- never invented, never guessed
        index = self.index_of("wraith_v20_heist_w")
        results = self.resolve(self.MATERIAL, index)
        self.assertUnresolved(results, R.OPACITY)
        self.assertUnresolved(results, R.SCATTER)
        self.assertUnresolved(results, R.IRIDESCENCE_RAMP)


class RsxTextAndSemanticTest(ResolverCase):
    """(3)(4) "Text" and "Semantic" naming."""

    def test_text_naming(self):
        material = "legend_v25_body"
        self.write(material + "_albedo.png")
        self.write(material + "_normal.png")
        self.write(material + "_gloss.png")
        results = self.resolve(material, self.index_of())
        self.assertResolved(results, R.ALBEDO, material + "_albedo.png")
        self.assertResolved(results, R.NORMAL, material + "_normal.png")
        self.assertResolved(results, R.GLOSS, material + "_gloss.png")

    def test_semantic_naming_with_a_different_material_name(self):
        # (24) The Blender material name appears nowhere in the file names;
        # the family seed comes from an image the CAST importer attached.
        self.write("alter_lgnd_v24_body_albedoTexture.png")
        self.write("alter_lgnd_v24_body_aoTexture.png")
        self.write("alter_lgnd_v24_body_cavityTexture.png")
        hit = resolver.GraphHit(
            R.ALBEDO, image_key="img",
            display="alter_lgnd_v24_body_albedoTexture.png",
            path=os.path.join(self.root, "alter_lgnd_v24_body_albedoTexture.png"))
        results = self.resolve("Material.003", self.index_of(),
                               graph_hits=[hit])
        self.assertResolved(results, R.ALBEDO,
                            "alter_lgnd_v24_body_albedoTexture.png",
                            source=resolver.SOURCE_GRAPH)
        self.assertResolved(results, R.AO,
                            "alter_lgnd_v24_body_aoTexture.png",
                            source=resolver.SOURCE_FAMILY)
        self.assertResolved(results, R.CAVITY,
                            "alter_lgnd_v24_body_cavityTexture.png")


class GuidTest(ResolverCase):
    """(5)(6)(7) GUID naming."""

    def setUp(self):
        ResolverCase.setUp(self)
        self.albedo = self.write("0x47BCE128CF.png")
        self.normal = self.write("0x123456789ABCDEF.png")
        self.write("0xE5E0D66DD62EE.png")

    def test_without_semantics_nothing_is_guessed(self):
        # (7) opaque names and no graph information -> unresolved, not a guess
        results = self.resolve("legend_body", self.index_of())
        for role in WANTED:
            self.assertUnresolved(results, role)

    def test_with_graph_semantics_the_guid_files_are_used(self):
        # (6) the CAST importer already knows which GUID is which
        hits = [
            resolver.GraphHit(R.ALBEDO, image_key="a",
                              display="0x47BCE128CF.png", path=self.albedo),
            resolver.GraphHit(R.NORMAL, image_key="n",
                              display="0x123456789ABCDEF.png",
                              path=self.normal),
        ]
        results = self.resolve("legend_body", self.index_of(), graph_hits=hits)
        self.assertResolved(results, R.ALBEDO, "0x47BCE128CF.png",
                            source=resolver.SOURCE_GRAPH)
        self.assertResolved(results, R.NORMAL, "0x123456789ABCDEF.png",
                            source=resolver.SOURCE_GRAPH)
        self.assertUnresolved(results, R.SPECULAR)


class PathTest(ResolverCase):
    """(12)(13)(14) nested folders, full asset paths, relative paths."""

    def test_nested_directories(self):
        material = "env_moon_foundry_wall"
        self.write("export/model/textures/%s_col.png" % material)
        self.write("export/model/textures/%s_nml.png" % material)
        index = self.index_of("export", recursive=True)
        results = self.resolve(material, index)
        self.assertResolved(results, R.ALBEDO, material + "_col.png")
        self.assertResolved(results, R.NORMAL, material + "_nml.png")

    def test_full_asset_paths(self):
        # RSX "Export full asset paths" recreates the game's own tree.
        material = "wraith_lgnd_v20_boosted_body"
        self.write("texture/models/humans/wraith/%s_col.png" % material)
        index = self.index_of("texture", recursive=True)
        results = self.resolve(material, index)
        self.assertResolved(results, R.ALBEDO, material + "_col.png")

    def test_relative_cast_path_resolution(self):
        model = os.path.join(self.root, "model", "wraith_LOD0.cast")
        resolved = paths.resolve_relative(model, "wraith_w/body_col.png")
        self.assertEqual(
            os.path.normcase(resolved),
            os.path.normcase(os.path.join(self.root, "model", "wraith_w",
                                          "body_col.png")))

    def test_absolute_cast_path_is_kept(self):
        absolute = os.path.join(self.root, "elsewhere", "body_col.png")
        self.assertEqual(
            os.path.normcase(paths.resolve_relative("ignored.cast", absolute)),
            os.path.normcase(os.path.normpath(absolute)))


class DeduplicationTest(ResolverCase):
    """(16) The same file discovered through two roots is one candidate."""

    def test_duplicate_roots_do_not_create_duplicates(self):
        material = "legend_body"
        self.write("tex/%s_col.png" % material)
        index = paths.TextureIndex()
        index.add_root(os.path.join(self.root, "tex"))
        index.add_root(os.path.join(self.root, "tex"))
        index.add_root(os.path.join(self.root, "tex") + os.sep)
        self.assertEqual(len(index), 1)
        results = self.resolve(material, index)
        self.assertResolved(results, R.ALBEDO, material + "_col.png")


class AmbiguityTest(ResolverCase):
    """(17) Equally strong candidates from different families are reported."""

    def test_two_families_tie(self):
        self.write("cavity_a_cavityTexture.png")
        self.write("cavity_b_cavityTexture.png")
        hit = resolver.GraphHit(
            R.ALBEDO, image_key="a", display="cavity_albedoTexture.png")
        seeds = [resolver.Seed(["cavity", "a"], resolver.SEED_GRAPH, 0),
                 resolver.Seed(["cavity", "b"], resolver.SEED_GRAPH, 0)]
        results = resolver.resolve_roles(
            "cavity", [R.CAVITY], self.index_of(), graph_hits=[hit],
            seeds=seeds)
        result = results[R.CAVITY]
        self.assertEqual(result.status, resolver.STATUS_AMBIGUOUS)
        self.assertEqual(sorted(result.alternatives),
                         ["cavity_a_cavityTexture.png",
                          "cavity_b_cavityTexture.png"])

    def test_naming_modes_in_one_folder_are_not_ambiguous(self):
        # Real and Semantic exports side by side: same family, same role.
        # The canonical spelling wins deterministically.
        material = "overdrive_base_body"
        self.write(material + "_albedoTexture.png")
        self.write(material + "_col.png")
        results = self.resolve(material, self.index_of())
        self.assertResolved(results, R.ALBEDO, material + "_albedoTexture.png")


class MipAndArrayTest(ResolverCase):
    """(20)(21) Variants must never beat the primary image."""

    def test_primary_beats_mip(self):
        material = "legend_body"
        self.write(material + "_col.png", size=8192)
        self.write(material + "_col_level1.png", size=64)
        self.write(material + "_col_001.png", size=32)
        results = self.resolve(material, self.index_of())
        self.assertResolved(results, R.ALBEDO, material + "_col.png")

    def test_a_mip_alone_is_still_usable(self):
        material = "legend_body"
        self.write(material + "_col_level1.png", size=64)
        results = self.resolve(material, self.index_of())
        self.assertResolved(results, R.ALBEDO, material + "_col_level1.png")

    def test_larger_mip_wins_when_only_mips_exist(self):
        material = "legend_body"
        self.write(material + "_col_level1.png", size=4096)
        self.write(material + "_col_level2.png", size=64)
        results = self.resolve(material, self.index_of())
        self.assertResolved(results, R.ALBEDO, material + "_col_level1.png")

    def test_primary_binding_beats_indexed_binding(self):
        material = "overdrive_base_gear"
        self.write(material + "_col.png")
        self.write(material + "_1_col.png")
        results = self.resolve(material, self.index_of())
        self.assertResolved(results, R.ALBEDO, material + "_col.png")


class RoughnessGlossTest(ResolverCase):
    """(19) Gloss and roughness are different textures."""

    def test_gloss_preferred_and_roughness_reported_separately(self):
        material = "legend_body"
        self.write(material + "_glossTexture.png")
        self.write(material + "_roughness.png")
        results = self.resolve(material, self.index_of())
        self.assertResolved(results, R.GLOSS, material + "_glossTexture.png")
        self.assertResolved(results, R.ROUGHNESS, material + "_roughness.png")

    def test_roughness_only(self):
        material = "legend_body"
        self.write(material + "_roughness.png")
        results = self.resolve(material, self.index_of())
        self.assertUnresolved(results, R.GLOSS)
        self.assertResolved(results, R.ROUGHNESS, material + "_roughness.png")

    def test_graph_gloss_through_invert_is_reported_as_gloss(self):
        hit = resolver.GraphHit(R.GLOSS, image_key="g",
                                display="0xABCDEF.png", path="0xABCDEF.png")
        results = self.resolve("legend_body", self.index_of(),
                               graph_hits=[hit])
        self.assertResolved(results, R.GLOSS, "0xABCDEF.png",
                            source=resolver.SOURCE_GRAPH)
        self.assertUnresolved(results, R.ROUGHNESS)


class CaseAndExtensionTest(ResolverCase):
    """(8)(9)(22) Case, periods and formats other than PNG."""

    def test_uppercase_files(self):
        material = "Legend_Body"
        self.write("LEGEND_BODY_COL.PNG")
        self.write("LEGEND_BODY_NML.TGA")
        results = self.resolve(material, self.index_of())
        self.assertResolved(results, R.ALBEDO, "LEGEND_BODY_COL.PNG")
        self.assertResolved(results, R.NORMAL, "LEGEND_BODY_NML.TGA")

    def test_mixed_extensions(self):
        material = "legend_body"
        self.write(material + "_col.dds")
        self.write(material + "_nml.tif")
        self.write(material + "_spc.tga")
        results = self.resolve(material, self.index_of())
        self.assertResolved(results, R.ALBEDO, material + "_col.dds")
        self.assertResolved(results, R.NORMAL, material + "_nml.tif")
        self.assertResolved(results, R.SPECULAR, material + "_spc.tga")

    def test_multiple_periods_in_filename(self):
        material = "legend.v2.body"
        self.write("legend.v2.body_col.png")
        results = self.resolve(material, self.index_of())
        self.assertResolved(results, R.ALBEDO, "legend.v2.body_col.png")

    def test_non_image_files_are_ignored(self):
        self.write("legend_body_col.cast")
        self.write("legend_body_col.txt")
        results = self.resolve("legend_body", self.index_of())
        self.assertUnresolved(results, R.ALBEDO)


class MissingSourceTest(ResolverCase):
    """RSX "Export Material Textures = OFF"."""

    def test_graph_hit_without_a_file_is_reported_not_dropped(self):
        hit = resolver.GraphHit(R.ALBEDO, image_key=None,
                                display="body_albedoTexture.png",
                                path="/gone/body_albedoTexture.png",
                                missing=True)
        results = self.resolve("body", self.index_of(), graph_hits=[hit])
        self.assertEqual(results[R.ALBEDO].status, resolver.STATUS_MISSING)


class ReportTest(ResolverCase):

    def test_report_lines(self):
        material = "body_skin_01"
        self.write(material + "_col.png")
        self.write(material + "_nml.png")
        results = self.resolve(material, self.index_of(),
                               wanted=[R.ALBEDO, R.NORMAL, R.GLOSS])
        lines = resolver.format_report(material, "RSX/CAST specular material",
                                       results,
                                       order=[R.ALBEDO, R.NORMAL, R.GLOSS])
        self.assertEqual(lines[0], "[Auto_tex] Material: body_skin_01")
        self.assertEqual(lines[1],
                         "[Auto_tex] Source: RSX/CAST specular material")
        self.assertIn("albedo -> body_skin_01_col.png [family match]", lines[2])
        self.assertTrue(lines[4].startswith("[Auto_tex] gloss -> unresolved"))


if __name__ == "__main__":
    unittest.main()
