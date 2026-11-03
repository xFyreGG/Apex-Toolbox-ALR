"""Name matching for automatic legend animation library linking, without bpy."""

import importlib.util
from pathlib import Path
import unittest


MODULE_PATH = Path(__file__).resolve().parents[1] / 'Apex_toolbox/apex_tex/model_files.py'
SPEC = importlib.util.spec_from_file_location('auto_rig_model_files', MODULE_PATH)
model_files = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(model_files)


class AutoRigMatchingTests(unittest.TestCase):
    def test_all_supported_legends_match_skin_and_pilot_exports(self):
        self.assertEqual(len(model_files.LEGEND_NAMES), 28)
        for legend in model_files.LEGEND_NAMES:
            with self.subTest(legend=legend):
                self.assertEqual(model_files.model_legend(
                    f'exports/mdl/{legend}_lgnd_v99_test_w/{legend}_lgnd_v99_test_w_LOD0.cast'),
                    legend)
                self.assertEqual(model_files.model_legend(
                    f'exports/mdl/pilot_medium_{legend}/pilot_medium_{legend}.cast'), legend)
                candidates = [(f'pilot_medium_{legend}', f'rigs/{legend}.cast')]
                self.assertEqual(model_files.choose_animation_rig(legend, candidates),
                                 (f'rigs/{legend}.cast', 'matched'))

    def test_aliases_match_their_legends(self):
        for alias, legend in {'holo': 'mirage', 'nova': 'horizon',
                              'overdrive': 'axle', 'stim': 'octane'}.items():
            with self.subTest(alias=alias):
                self.assertEqual(model_files.model_legend(
                    f'mdl/{alias}_base/{alias}_base_LOD0.cast'), legend)
                self.assertEqual(model_files.model_legend(
                    f'mdl/pilot_medium_{alias}/pilot_medium_{alias}.cast'), legend)
                self.assertEqual(model_files.choose_animation_rig(legend,
                    [(f'pilot_medium_{alias}', f'{alias}.cast')]), (f'{alias}.cast', 'matched'))

    def test_windows_paths_lod_duplicate_suffix_and_case(self):
        self.assertEqual(model_files.model_legend(
            r'G:\Exports\mdl\WRAITH_lgnd_v19_test_w\Wraith_lgnd_v19_test_w_LOD0.cast',
            ['Wraith_lgnd_v19_test_w_LOD0.001', 'Armature']), 'wraith')
        self.assertEqual(model_files.model_legend(
            'mdl/model.cast', ['Mad Maggie.001']), 'madmaggie')
        self.assertEqual(model_files.model_legend(
            'mdl/model.cast', ['Mad_Maggie_armature.001']), 'madmaggie')

    def test_generic_file_can_use_known_folder_or_armature(self):
        self.assertEqual(model_files.model_legend('mdl/wraith_base/model.cast'), 'wraith')
        self.assertEqual(model_files.model_legend('mdl/model.cast', ['nova_rig']), 'horizon')
        self.assertEqual(model_files.model_legend('mdl/model.cast', ['wraith_skeleton']), 'wraith')

    def test_conflicting_sources_do_not_guess(self):
        self.assertIsNone(model_files.model_legend('mdl/wraith_base/ash_base.cast'))
        self.assertIsNone(model_files.model_legend('mdl/wraith_base/wraith_base.cast', ['ash']))
        self.assertIsNone(model_files.model_legend('mdl/model.cast', ['wraith', 'ash_rig']))
        self.assertEqual(model_files.model_legend('mdl/holo_base/mirage_base.cast'), 'mirage')

    def test_weapons_heirlooms_and_legend_props_do_not_match(self):
        for name in ('wraith_kunai_rt01_w', 'valkyrie_heirloom_v22_base_w',
                     'lifeline_drone', 'horizon_cluttered_desk_base_w',
                     'nova_trophy_system', 'holo_drone', 'r301_base_w',
                     'w_r99_s07_reactive', 'district_wall_01', 'pilot_medium_dummie'):
            with self.subTest(name=name):
                self.assertIsNone(model_files.model_legend(f'mdl/{name}/{name}.cast'))
        self.assertIsNone(model_files.model_legend('mdl/lifeline_drone/model.cast', ['lifeline']))
        self.assertIsNone(model_files.model_legend('mdl/wraith_kunai_rt01_w/model.cast', ['wraith']))
        self.assertIsNone(model_files.model_legend('mdl/model.cast', ['lifeline_drone']))

    def test_unknown_models_are_left_for_manual_linking(self):
        for filepath in ('', None, 'mdl/model.cast', 'mdl/unknown_skin/model.cast'):
            with self.subTest(filepath=filepath):
                self.assertIsNone(model_files.model_legend(filepath, ['Armature', 'mesh_0']))
        self.assertEqual(model_files.choose_animation_rig('dummy', []),
                         (None, 'unknown_legend'))

    def test_base_pilot_rig_wins_over_named_variants(self):
        candidates = [('pilot_medium_wraith_alt', 'alt.cast'),
                      ('pilot_light_wraith', 'base.cast'),
                      ('pilot_medium_bangalore', 'other.cast')]
        self.assertEqual(model_files.choose_animation_rig('wraith', candidates),
                         ('base.cast', 'matched'))
        self.assertEqual(model_files.choose_animation_rig('wraith', reversed(candidates)),
                         ('base.cast', 'matched'))

    def test_multiple_base_rigs_or_multiple_variants_are_ambiguous(self):
        for candidates in ([('pilot_light_wraith', 'one.cast'),
                            ('pilot_medium_wraith', 'two.cast')],
                           [('pilot_medium_holo', 'one.cast'),
                            ('pilot_medium_mirage', 'two.cast')],
                           [('pilot_medium_wraith_alt', 'one.cast'),
                            ('pilot_medium_wraith_other', 'two.cast')]):
            legend = 'mirage' if 'holo' in candidates[0][0] else 'wraith'
            with self.subTest(candidates=candidates):
                self.assertEqual(model_files.choose_animation_rig(legend, candidates),
                                 (None, 'ambiguous'))

    def test_one_named_pilot_variant_can_match(self):
        self.assertEqual(model_files.choose_animation_rig('wraith',
            [('pilot_medium_wraith_alt', 'alt.cast')]), ('alt.cast', 'matched'))

    def test_companion_prop_rigs_never_link_to_character(self):
        for legend, candidates in (
                ('mirage', [('holo_drone', 'drone.cast')]),
                ('horizon', [('nova_trophy_system', 'trophy.cast')])):
            with self.subTest(legend=legend):
                self.assertEqual(model_files.choose_animation_rig(legend, candidates),
                                 (None, 'no_match'))
                candidates.append((f'pilot_medium_{legend}', 'base.cast'))
                self.assertEqual(model_files.choose_animation_rig(legend, candidates),
                                 ('base.cast', 'matched'))

    def test_duplicate_candidate_paths_do_not_create_ambiguity(self):
        self.assertEqual(model_files.choose_animation_rig('wraith',
            [('pilot_light_wraith', r'C:\Rigs\base.cast'),
             ('pilot_light_wraith', 'c:/rigs/base.cast')]), ('c:/rigs/base.cast', 'matched'))

    def test_similar_names_do_not_match(self):
        self.assertEqual(model_files.choose_animation_rig('ash',
            [('pilot_medium_ashley', 'ashley.cast'),
             ('pilot_medium_bangalore', 'bangalore.cast')]), (None, 'no_match'))
        self.assertIsNone(model_files.model_legend('mdl/ashley_base/ashley_base.cast'))


if __name__ == '__main__':
    unittest.main()
