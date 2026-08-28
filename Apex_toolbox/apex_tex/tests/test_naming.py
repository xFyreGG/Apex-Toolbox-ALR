# -*- coding: utf-8 -*-
"""File name normalisation, role detection and family matching."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from apex_tex import naming            # noqa: E402
from apex_tex import roles as R        # noqa: E402


class SplitNameTest(unittest.TestCase):
    """Extensions must never come from ``name.split('.')[1]``."""

    def test_plain(self):
        self.assertEqual(naming.split_name("body_col.png"),
                         ("body_col", ".png"))

    def test_multiple_periods(self):
        # (9) multiple periods in filename
        self.assertEqual(
            naming.split_name("wraith.v20.heist_body_albedoTexture.png"),
            ("wraith.v20.heist_body_albedoTexture", ".png"))

    def test_blender_datablock_suffix(self):
        # (10) Blender's ".001" uniquifying suffix
        self.assertEqual(naming.split_name("body_col.png.001"),
                         ("body_col", ".png"))
        self.assertEqual(naming.split_name("Image Texture.001"),
                         ("Image Texture", ""))

    def test_unknown_extension_is_part_of_the_name(self):
        self.assertEqual(naming.split_name("wraith_v20.5_body"),
                         ("wraith_v20.5_body", ""))

    def test_mixed_extensions(self):
        # (22) mixed extensions
        for extension in (".png", ".dds", ".tga", ".tif", ".tiff", ".jpg"):
            self.assertTrue(naming.is_image_file("body_col" + extension),
                            extension)
        self.assertFalse(naming.is_image_file("body_col.txt"))
        self.assertFalse(naming.is_image_file("model.cast"))

    def test_directory_is_ignored(self):
        self.assertEqual(
            naming.split_name("D:/rsx/mdl/model/body_col.png"),
            ("body_col", ".png"))
        self.assertEqual(
            naming.split_name("D:\\rsx\\mdl\\model\\body_col.png"),
            ("body_col", ".png"))


class TokenizeTest(unittest.TestCase):

    def test_camel_case(self):
        self.assertEqual(naming.tokenize("body_albedoTexture"),
                         ["body", "albedo", "texture"])

    def test_separator_differences(self):
        # (11) separator differences
        expected = ["wraith", "body", "col"]
        for stem in ("wraith_body_col", "wraith-body-col", "wraith body col",
                     "wraith__body--col", "wraith.body.col"):
            self.assertEqual(naming.tokenize(stem), expected, stem)

    def test_case_folding(self):
        # (8) uppercase / lowercase
        self.assertEqual(naming.tokenize("WRAITH_Body_COL"),
                         ["wraith", "body", "col"])

    def test_version_tokens_are_not_split(self):
        self.assertIn("v20", naming.tokenize("wraith_lgnd_v20_boosted_body"))


class RoleDetectionTest(unittest.TestCase):

    def check(self, stem, role, family=None):
        analysis = naming.analyze(stem)
        self.assertEqual(analysis.role, role, stem)
        if family is not None:
            self.assertEqual(analysis.family, family, stem)

    def test_legacy_legion_names(self):
        # (1) old Legion exact filenames
        material = "wraith_lgnd_v19_liberator_body"
        family = ["wraith", "lgnd", "v19", "liberator", "body"]
        for token, role in R.LEGACY_TOKENS.items():
            self.check(material + "_" + role + ".png", token, family)

    def test_rsx_semantic_names(self):
        # (4) RSX "Semantic" naming
        self.check("alter_v24_body_albedoTexture.png", R.ALBEDO)
        self.check("alter_v24_body_normalTexture.png", R.NORMAL)
        self.check("alter_v24_body_glossTexture.png", R.GLOSS)
        self.check("alter_v24_body_specTexture.png", R.SPECULAR)
        self.check("alter_v24_body_aoTexture.png", R.AO)
        self.check("alter_v24_body_cavityTexture.png", R.CAVITY)
        self.check("alter_v24_body_emissiveTexture.png", R.EMISSIVE)

    def test_rsx_real_names(self):
        # (2) RSX "Real" naming: the short Respawn asset codes
        family = ["wraith", "lgnd", "v20", "boosted", "body"]
        self.check("wraith_lgnd_v20_boosted_body_col.png", R.ALBEDO, family)
        self.check("wraith_lgnd_v20_boosted_body_nml.png", R.NORMAL, family)
        self.check("wraith_lgnd_v20_boosted_body_spc.png", R.SPECULAR, family)
        self.check("wraith_lgnd_v20_boosted_body_gls.png", R.GLOSS, family)
        self.check("wraith_lgnd_v20_boosted_body_ao.png", R.AO, family)
        self.check("wraith_lgnd_v20_boosted_body_cav.png", R.CAVITY, family)
        self.check("wraith_lgnd_v20_boosted_body_ilm.png", R.EMISSIVE, family)

    def test_rsx_text_names(self):
        # (3) RSX "Text" naming: meaningful, un-suffixed words
        self.check("legend_body_albedo.png", R.ALBEDO, ["legend", "body"])
        self.check("legend_body_normal.png", R.NORMAL, ["legend", "body"])
        self.check("legend_body_base_color.png", R.ALBEDO, ["legend", "body"])
        self.check("legend_body_ambient_occlusion.png", R.AO,
                   ["legend", "body"])

    def test_guid_names_carry_no_role(self):
        # (5)(7) GUID naming is intentionally opaque -- never guess from it
        for stem in ("0x123456789ABCDEF.png", "0xE5E0D66DD62EE.png",
                     "0x47BCE128CF.png"):
            self.assertIsNone(naming.analyze(stem).role, stem)

    def test_unrelated_n_token_is_not_a_normal_map(self):
        # (18) "_n" must not be read as a normal map
        self.assertIsNone(naming.analyze("character_body_n.png").role)
        self.assertEqual(
            naming.analyze("character_n_body_col.png").family,
            ["character", "n", "body"])

    def test_detail_maps_are_not_the_main_maps(self):
        self.assertIsNone(naming.analyze("body_detailNormalTexture.png").role)
        self.assertIsNone(naming.analyze("body_detailTexture.png").role)
        self.assertIsNone(naming.analyze("body_uvDistortionTexture.png").role)
        self.assertIsNone(naming.analyze("body_emissiveMultiplyTexture.png").role)

    def test_opacity_and_scatter_survive(self):
        self.assertEqual(
            naming.analyze("body_opacityMultiplyTexture.png").role, R.OPACITY)
        self.assertEqual(
            naming.analyze("body_scatterThicknessTexture.png").role, R.SCATTER)
        self.assertEqual(naming.analyze("body_thk.png").role, R.SCATTER)

    def test_apex_specific_maps_survive(self):
        self.assertEqual(
            naming.analyze("body_anisoSpecDirTexture.png").role,
            R.ANISO_SPEC_DIR)
        self.assertEqual(
            naming.analyze("body_iridescenceRampTexture.png").role,
            R.IRIDESCENCE_RAMP)

    def test_roughness_and_gloss_are_distinct(self):
        # (19) roughness vs gloss
        self.assertEqual(naming.analyze("body_roughness.png").role,
                         R.ROUGHNESS)
        self.assertEqual(naming.analyze("body_gloss.png").role, R.GLOSS)
        self.assertNotEqual(R.GLOSS, R.ROUGHNESS)

    def test_mip_suffixes(self):
        # (20) mip suffixes are variants, never roles
        for stem in ("body_col_001.png", "body_col_level1.png",
                     "body_col_001_level1.png", "body_col_mip2.png"):
            analysis = naming.analyze(stem)
            self.assertEqual(analysis.role, R.ALBEDO, stem)
            self.assertEqual(analysis.family, ["body"], stem)
            self.assertTrue(analysis.is_variant, stem)
        primary = naming.analyze("body_col.png")
        self.assertFalse(primary.is_variant)

    def test_array_suffixes(self):
        # (21) array / repeated-binding suffixes
        analysis = naming.analyze("base_smear_1_col.png")
        self.assertEqual(analysis.role, R.ALBEDO)
        self.assertEqual(analysis.family, ["base", "smear", "1"])

        analysis = naming.analyze("body_albedoTexture1.png")
        self.assertEqual(analysis.role, R.ALBEDO)
        self.assertEqual(analysis.family, ["body"])
        self.assertEqual(analysis.binding_index, 1)

        analysis = naming.analyze("body_normal2Texture.png")
        self.assertEqual(analysis.role, R.NORMAL)
        self.assertEqual(analysis.binding_index, 2)


class FamilyMatchTest(unittest.TestCase):

    def test_exact(self):
        self.assertEqual(
            naming.family_score(["a", "b", "body"], ["a", "b", "body"]),
            naming.FAMILY_EXACT)

    def test_indexed_sibling(self):
        self.assertEqual(
            naming.family_score(["a", "b", "gear"], ["a", "b", "gear", "1"]),
            naming.FAMILY_INDEXED)

    def test_different_body_part_is_rejected(self):
        # (23) several materials share one folder
        score = naming.family_score(
            ["wraith", "lgnd", "v20", "boosted", "body"],
            ["wraith", "lgnd", "v20", "boosted", "head"])
        self.assertLess(score, naming.FAMILY_MIN_ACCEPT)

    def test_unrelated_prefix_is_rejected(self):
        score = naming.family_score(["madmaggie", "base"],
                                    ["madmaggie", "base", "eyecornea"])
        self.assertEqual(score, naming.FAMILY_NONE)

    def test_unrelated_material_is_rejected(self):
        # (24) material name absent from every texture filename
        score = naming.family_score(["legend", "skin", "body"],
                                    ["tex", "184726"])
        self.assertEqual(score, naming.FAMILY_NONE)


if __name__ == "__main__":
    unittest.main()
