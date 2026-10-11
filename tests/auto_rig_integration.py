"""Automatic animation rig linking with real Blender and synthetic CAST exports.

Run in a factory-startup background Blender process. Append -- --release to
exercise the packaged add-on. Only temporary exports and scenes are created.
"""
from collections import Counter
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import addon_utils
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from workflow_integration import (addon, animations, cast_index, workflows,
                                  model_file, animation_file, make_rig, select)
from Apex_toolbox.apex_tex import auto_rigs, autotex, model_files


class AutoRigIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        addon_utils.enable('io_scene_cast', default_set=False)
        _, cls.cast, _ = workflows.cast_modules()
        addon.register()

    @classmethod
    def tearDownClass(cls):
        addon.cancel_animation_scan(None)
        addon.unregister()
        addon_utils.disable('io_scene_cast', default_set=False)

    def setUp(self):
        addon.cancel_animation_scan(None)
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for action in list(bpy.data.actions):
            bpy.data.actions.remove(action, do_unlink=True)
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.exports = self.folder / 'user-chosen-exports'
        self.prefs = bpy.context.scene.my_prefs
        self.prefs.animation_parent_folder = ''
        self.prefs.model_parent_folder = ''
        self.prefs.auto_link_rigs = True
        for target, attribute, value in (
                (animations, 'index_cache_root', self.folder / 'user-data' / 'animation-index'),
                (autotex, 'browsed_directories', []),
                (model_files, 'bookmarked_animrig', None)):
            mocked = patch.object(target, attribute, return_value=value)
            mocked.start()
            self.addCleanup(mocked.stop)
        self.wraith = self.model('wraith_base')
        self.wraith_export = self.rig_export('pilot_medium_wraith')

    def model(self, name, exports=None):
        path = (exports or self.exports) / 'mdl' / name / (name + '_LOD0.cast')
        path.parent.mkdir(parents=True, exist_ok=True)
        model_file(self.cast, path)
        return path

    def rig_export(self, name, exports=None, bones=('root', 'child')):
        path = (exports or self.exports) / 'animrig' / name / (name + '.cast')
        path.parent.mkdir(parents=True, exist_ok=True)
        doc = self.cast.Cast()
        model = doc.CreateRoot().CreateModel()
        model.SetName(name)
        skeleton = model.CreateSkeleton()
        for index, name in enumerate(bones):
            bone = skeleton.CreateBone()
            bone.SetName(name)
            bone.SetParentIndex(index - 1)
            bone.SetLocalPosition((0, 0, index))
            bone.SetLocalRotation((0, 0, 0, 1))
            bone.SetScale((1, 1, 1))
        doc.save(str(path))
        sequences = path.parent / ('anims_' + path.stem)
        sequences.mkdir(exist_ok=True)
        animation_file(self.cast, sequences / 'idle.cast')
        animation_file(self.cast, sequences / 'walk.cast', names=('walk', 'run'))
        return path

    def model_rig(self, source=None, name='rig'):
        rig = make_rig()
        rig.name = name
        if source:
            rig['apex_source_model'] = str(source)
        return rig

    def planned(self, *rigs):
        return auto_rigs.plan(bpy.context, rigs)

    def batch(self, targets):
        return auto_rigs.BatchScan(*targets[0], targets=targets)

    def finish(self, scan, commit=True):
        for _ in range(10000):
            if scan.step(0):
                break
        else:
            self.fail('Automatic animation linking did not finish.')
        return scan.commit(None) if commit else None

    def assert_linked(self, rig, path):
        library = rig.apex_animation_library
        self.assertEqual(Path(library.rig_file), path, library.summary)
        self.assertEqual({clip.name for clip in library.clips}, {'idle', 'walk', 'run'})

    def test_source_export_precedes_saved_animation_folder(self):
        other = self.rig_export('pilot_medium_wraith', self.folder / 'another-export')
        self.prefs.animation_parent_folder = str(other.parent.parent)
        rig = self.model_rig(self.wraith)
        targets, notices = self.planned(rig, rig)
        self.assertEqual(targets, [(rig, str(self.wraith_export))])
        self.assertEqual(len(notices), 1)
        self.assertFalse(rig.apex_animation_library.rig_file)
        self.assertEqual(len(rig.apex_animation_library.clips), 0)

    def test_saved_animation_folder_fallback_uses_custom_user_path(self):
        source = self.model('mirage_base', self.folder / 'models-only')
        exported = self.rig_export('pilot_medium_holo', self.folder / 'separate-animation-exports')
        self.prefs.animation_parent_folder = str(exported.parent.parent)
        rig = self.model_rig(source)
        targets, _ = self.planned(rig)
        self.assertEqual(targets, [(rig, str(exported))])
        scan = self.batch(targets)
        try:
            self.finish(scan)
            self.assert_linked(rig, exported)
        finally:
            scan.close()

    def test_recent_rsx_folder_is_used_when_model_export_has_no_rig(self):
        source = self.model('mirage_base', self.folder / 'models-only')
        exported = self.rig_export('pilot_medium_holo', self.folder / 'exported_files')
        rig = self.model_rig(source)
        with patch.object(autotex, 'browsed_directories', return_value=[str(exported.parent)]):
            targets, _ = self.planned(rig)
        self.assertEqual(targets, [(rig, str(exported))])

    def test_unreadable_model_animation_folder_can_use_saved_folder(self):
        exported = self.rig_export('pilot_medium_wraith', self.folder / 'accessible')
        self.prefs.animation_parent_folder = str(exported.parent.parent)
        rig = self.model_rig(self.wraith)
        original = model_files.legend_animation_rigs

        def guarded(path):
            if Path(path) == self.exports / 'animrig':
                raise PermissionError('Fixture unavailable export')
            return original(path)

        with patch.object(model_files, 'legend_animation_rigs', side_effect=guarded):
            targets, _ = self.planned(rig)
        self.assertEqual(targets, [(rig, str(exported))])

    def test_ambiguous_source_does_not_fall_through_to_another_export(self):
        self.rig_export('pilot_light_wraith')
        other = self.rig_export('pilot_medium_wraith', self.folder / 'other')
        self.prefs.animation_parent_folder = str(other.parent.parent)
        rig = self.model_rig(self.wraith)
        targets, notices = self.planned(rig)
        self.assertFalse(targets)
        self.assertEqual(len(notices), 1)
        self.assertIn('Several animation rigs', rig.apex_animation_library.summary)
        self.assertFalse(rig.apex_animation_library.rig_file)

    def test_missing_export_and_nonlegend_have_distinct_outcomes(self):
        legend = self.model_rig(self.model('pathfinder_base'))
        weapon = self.model_rig(self.model('wpn_wraith_heirloom'))
        targets, notices = self.planned(legend, weapon)
        self.assertFalse(targets)
        self.assertEqual(len(notices), 1)
        self.assertIn('Pathfinder', legend.apex_animation_library.summary)
        self.assertFalse(weapon.apex_animation_library.summary)

    def test_manual_link_is_kept(self):
        rig = self.model_rig(self.wraith)
        animations.link_library(rig, str(self.wraith_export))
        item = rig.apex_animation_library.clips[0]
        item.favourite = True
        item.menu_name = 'Saved custom name'
        item.menu_source = 'CUSTOM'
        identity = animations.library_identity(rig.apex_animation_library)
        targets, notices = self.planned(rig)
        self.assertFalse(targets)
        self.assertFalse(notices)
        self.assertEqual(animations.library_identity(rig.apex_animation_library), identity)
        self.assertTrue(item.favourite)
        self.assertEqual(item.menu_name, 'Saved custom name')

    def test_default_import_links_matching_rig_without_loading_animation(self):
        self.assertEqual(bpy.ops.object.apex_import_texture(filepath=str(self.wraith)), {'FINISHED'})
        rig = bpy.context.active_object
        self.assert_linked(rig, self.wraith_export)
        self.assertIsNone(rig.animation_data.action if rig.animation_data else None)
        self.assertEqual(len(bpy.data.actions), 0)
        self.assertAlmostEqual(rig.scale.x, 0.0254)

    def test_import_option_can_disable_auto_linking(self):
        self.assertEqual(bpy.ops.object.apex_import_texture(
            filepath=str(self.wraith), auto_link=False), {'FINISHED'})
        rig = bpy.context.active_object
        self.assertFalse(rig.apex_animation_library.rig_file)
        self.assertEqual(len(rig.apex_animation_library.clips), 0)
        self.assertFalse(self.prefs.auto_link_rigs)

    def test_one_click_links_existing_model_and_preserves_scene_state(self):
        rig = self.model_rig(self.wraith)
        rig.location = (7, 8, 9)
        rig.rotation_euler = (0.2, -0.1, 0.3)
        rig.pose.bones['child'].location = (0.1, 0.2, 0.3)
        action = bpy.data.actions.new('Existing action')
        rig.animation_data_create().action = action
        scene = bpy.context.scene
        scene.frame_set(23, subframe=0.5)
        scene.frame_start, scene.frame_end = 5, 86
        scene.render.fps, scene.render.fps_base = 60, 1.001
        before = (rig.matrix_world.copy(), rig.pose.bones['child'].matrix_basis.copy(),
                  scene.frame_current, scene.frame_subframe, scene.frame_start, scene.frame_end,
                  scene.render.fps, scene.render.fps_base, list(bpy.context.selected_objects))
        self.assertEqual(bpy.ops.object.apex_auto_link_animation_rig(), {'FINISHED'})
        self.assert_linked(rig, self.wraith_export)
        after = (rig.matrix_world.copy(), rig.pose.bones['child'].matrix_basis.copy(),
                 scene.frame_current, scene.frame_subframe, scene.frame_start, scene.frame_end,
                 scene.render.fps, scene.render.fps_base, list(bpy.context.selected_objects))
        self.assertEqual(after, before)
        self.assertEqual(rig.animation_data.action, action)
        self.assertEqual(list(bpy.data.actions), [action])
        self.assertFalse(bpy.ops.object.apex_auto_link_animation_rig.poll())

    def test_batch_import_links_each_legend_and_keeps_side_by_side_placement(self):
        mirage = self.model('mirage_base')
        mirage_export = self.rig_export('pilot_medium_holo')
        misc = self.model('crate')
        files = [{'name': str(path.relative_to(self.exports / 'mdl'))}
                 for path in (self.wraith, mirage, misc)]
        self.assertEqual(bpy.ops.object.apex_import_texture(
            directory=str(self.exports / 'mdl'), files=files), {'FINISHED'})
        rigs = {Path(obj['apex_source_model']).parent.name: obj
                for obj in bpy.context.selected_objects if obj.type == 'ARMATURE'}
        self.assertEqual(set(rigs), {'wraith_base', 'mirage_base', 'crate'})
        self.assert_linked(rigs['wraith_base'], self.wraith_export)
        self.assert_linked(rigs['mirage_base'], mirage_export)
        self.assertFalse(rigs['crate'].apex_animation_library.rig_file)
        groups = [[obj for obj in bpy.context.selected_objects if obj.get('apex_source_model') == rig.get('apex_source_model')]
                  for rig in rigs.values()]
        bounds = sorted((workflows.model_bounds(group) for group in groups), key=lambda item: item[0].x)
        for (_, right), (left, _) in zip(bounds, bounds[1:]):
            self.assertGreater(left.x, right.x)
        self.assertEqual(len(bpy.data.actions), 0)

    def test_alias_model_links_overdrive_export(self):
        source = self.model('axle_base')
        exported = self.rig_export('pilot_medium_overdrive')
        rig = self.model_rig(source)
        targets, _ = self.planned(rig)
        self.assertEqual(targets, [(rig, str(exported))])
        scan = self.batch(targets)
        try:
            self.finish(scan)
            self.assert_linked(rig, exported)
        finally:
            scan.close()

    def test_identical_model_skins_share_one_export_scan(self):
        first = self.model_rig(self.wraith)
        second = self.model_rig(self.model('wraith_lgnd_v01'))
        targets, _ = self.planned(first, second)
        scan = self.batch(targets)
        reads = []
        original = cast_index.iter_cast

        def counted(path):
            reads.append(Path(path))
            return original(path)

        try:
            with patch.object(cast_index, 'iter_cast', side_effect=counted):
                self.finish(scan, commit=False)
            self.assertFalse(first.apex_animation_library.rig_file)
            self.assertFalse(second.apex_animation_library.rig_file)
            self.assertEqual(Counter(reads)[self.wraith_export], 1)
            self.assertEqual(len(scan.scans), 1)
            message, warning = scan.commit(None)
            self.assertFalse(warning, message)
            self.assert_linked(first, self.wraith_export)
            self.assert_linked(second, self.wraith_export)
        finally:
            scan.close()

    def test_incompatible_bones_skip_that_model_without_failing_other_models(self):
        good = self.model_rig(self.wraith)
        source = self.model('mirage_base')
        self.rig_export('pilot_medium_holo', bones=('foreign_root', 'foreign_child'))
        bad = self.model_rig(source)
        targets, _ = self.planned(bad, good)
        scan = self.batch(targets)
        try:
            message, warning = self.finish(scan)
            self.assertTrue(warning, message)
            self.assertIn('1 model skipped', message)
            self.assert_linked(good, self.wraith_export)
            self.assertFalse(bad.apex_animation_library.rig_file)
            self.assertIn('not linked', bad.apex_animation_library.summary)
        finally:
            scan.close()

    def test_cancel_does_not_replace_existing_clips_or_remove_models(self):
        rig = self.model_rig(self.wraith)
        library = rig.apex_animation_library
        item = library.clips.add()
        item.name, item.filepath, item.external = 'Imported single clip', 'custom.cast', True
        before = animations.library_identity(library)
        targets, _ = self.planned(rig)
        scan = self.batch(targets)
        scan.step(0)
        scan.close()
        self.assertTrue(scan.cancelled)
        with self.assertRaisesRegex(ValueError, 'Finish indexing'):
            scan.commit(None)
        self.assertEqual(animations.library_identity(library), before)
        self.assertIn(rig.name, bpy.data.objects)
        self.assertIn('cancelled', library.summary)

    def test_deleted_first_target_does_not_prevent_other_model_linking(self):
        first = self.model_rig(self.wraith)
        second = self.model_rig(self.model('wraith_lgnd_v01'))
        targets, _ = self.planned(first, second)
        scan = self.batch(targets)
        bpy.data.objects.remove(first, do_unlink=True)
        try:
            message, warning = self.finish(scan)
            self.assertTrue(warning, message)
            self.assert_linked(second, self.wraith_export)
        finally:
            scan.close()

    def test_changed_bones_after_scan_skip_only_changed_target(self):
        first = self.model_rig(self.wraith)
        second = self.model_rig(self.model('wraith_lgnd_v01'))
        targets, _ = self.planned(first, second)
        scan = self.batch(targets)
        try:
            self.finish(scan, commit=False)
            first.data.bones['child'].name = 'changed'
            message, warning = scan.commit(None)
            self.assertTrue(warning, message)
            self.assertFalse(first.apex_animation_library.rig_file)
            self.assert_linked(second, self.wraith_export)
        finally:
            scan.close()

    def test_manual_link_added_during_scan_is_not_overwritten(self):
        rig = self.model_rig(self.wraith)
        targets, _ = self.planned(rig)
        scan = self.batch(targets)
        try:
            self.finish(scan, commit=False)
            library = rig.apex_animation_library
            library.rig_file = 'manually-chosen.cast'
            library.summary = 'Manual selection kept'
            item = library.clips.add()
            item.name = 'Manual animation'
            identity = animations.library_identity(library)
            message, warning = scan.commit(None)
            self.assertTrue(warning, message)
            self.assertEqual(animations.library_identity(library), identity)
            self.assertEqual(library.summary, 'Manual selection kept')
        finally:
            scan.close()

    def test_changed_export_after_scan_is_rejected_before_commit(self):
        rig = self.model_rig(self.wraith)
        targets, _ = self.planned(rig)
        scan = self.batch(targets)
        try:
            self.finish(scan, commit=False)
            path = self.wraith_export.parent / ('anims_' + self.wraith_export.stem) / 'idle.cast'
            animation_file(self.cast, path, names=('reexported_idle',))
            message, warning = scan.commit(None)
            self.assertTrue(warning, message)
            self.assertFalse(rig.apex_animation_library.rig_file)
        finally:
            scan.close()


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(AutoRigIntegration))
    if not result.wasSuccessful():
        raise SystemExit(1)
