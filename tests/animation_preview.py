"""Temporary animation previews against Blender and the real CAST importer.

Run in a factory-startup Blender process. Fixtures are synthetic; no game
assets or user scene files are read. ``--release`` tests the packaged ZIP.
"""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import addon_utils
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import workflow_integration as fixtures
from Apex_toolbox.apex_tex import animation_preview as preview

addon = fixtures.addon
animations = fixtures.animations
workflows = fixtures.workflows
make_rig = fixtures.make_rig
make_mesh = fixtures.make_mesh
select = fixtures.select


def transforms(owner):
    return (owner.rotation_mode, tuple(owner.location), tuple(owner.scale),
            tuple(owner.rotation_euler), tuple(owner.rotation_quaternion),
            tuple(owner.rotation_axis_angle))


def timing(scene):
    return (scene.frame_start, scene.frame_end, scene.render.fps,
            scene.render.fps_base, scene.frame_current, scene.frame_subframe)


class AnimationPreview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        addon_utils.enable('io_scene_cast', default_set=False)
        cls.importer, cls.cast, _ = workflows.cast_modules()
        addon.register()

    @classmethod
    def tearDownClass(cls):
        preview.revert(bpy.context)
        addon.unregister()
        addon_utils.disable('io_scene_cast', default_set=False)

    def setUp(self):
        preview.revert(bpy.context)
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for action in list(bpy.data.actions):
            bpy.data.actions.remove(action, do_unlink=True)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        cache_root = patch.object(animations, 'index_cache_root', return_value=self.folder / 'cache')
        cache_root.start()
        self.addCleanup(cache_root.stop)
        self.rig_path = self.folder / 'legend_rig.cast'
        fixtures.model_file(self.cast, self.rig_path, mesh=False)
        self.anim_folder = self.folder / 'anims_legend_rig'
        self.anim_folder.mkdir()
        fixtures.animation_file(self.cast, self.anim_folder / 'idle.cast')
        fixtures.animation_file(self.cast, self.anim_folder / 'walk.cast', names=('walk', 'run'))
        self.rig = make_rig()
        animations.link_library(self.rig, str(self.rig_path))
        self.library = self.rig.apex_animation_library
        self.scene = bpy.context.scene
        self.scene.frame_start, self.scene.frame_end = 3, 137
        self.scene.render.fps, self.scene.render.fps_base = 24, 1.001
        self.scene.frame_set(7, subframe=0.375)
        self.previous = bpy.data.actions.new('Original action')
        self.rig.animation_data_create()
        self.rig.animation_data.action = self.previous
        if hasattr(self.previous, 'slots'):
            slot = self.previous.slots.new(id_type='OBJECT', name='Original slot')
            self.rig.animation_data.action_slot = slot
        self.configure_transforms()
        bpy.context.view_layer.update()
        self.baseline = self.state()

    def tearDown(self):
        preview.revert(bpy.context)

    def configure_transforms(self):
        for index, owner in enumerate([self.rig, *self.rig.pose.bones]):
            owner.location = (index + 0.2, index - 0.4, -index - 0.1)
            owner.scale = (0.8 + index * 0.1, 1.2, 0.9)
            owner.rotation_euler = (0.3, -0.5, 0.7)
            owner.rotation_quaternion = (0.8, 0.2, -0.3, 0.4)
            owner.rotation_axis_angle = (0.6, 0.0, 1.0, 0.0)
            owner.rotation_mode = ('ZYX', 'AXIS_ANGLE', 'QUATERNION')[index]

    def state(self):
        animation = self.rig.animation_data
        return {
            'action': animation.action if animation else None,
            'slot': getattr(animation, 'action_slot', None) if animation else None,
            'object': transforms(self.rig),
            'bones': {bone.name: transforms(bone) for bone in self.rig.pose.bones},
            'timing': timing(self.scene),
            'rest': (self.library.has_rest_rotation, self.library.rest_rotation_mode,
                     tuple(self.library.rest_rotation)),
        }

    def assertStateEqual(self, actual, expected):
        self.assertEqual(actual['action'], expected['action'])
        self.assertEqual(actual['slot'], expected['slot'])
        self.assertEqual(actual['timing'], expected['timing'])
        self.assertEqual(actual['rest'], expected['rest'])
        self.assertEqual(actual['bones'].keys(), expected['bones'].keys())
        for name, actual_value, expected_value in [
                ('object', actual['object'], expected['object']),
                *((name, value, expected['bones'][name]) for name, value in actual['bones'].items())]:
            self.assertEqual(actual_value[0], expected_value[0], name)
            for actual_channel, expected_channel in zip(actual_value[1:], expected_value[1:]):
                for a, b in zip(actual_channel, expected_channel):
                    self.assertAlmostEqual(a, b, places=6, msg=name)

    def start(self, index=0):
        self.library.index = index
        return preview.start(bpy.context, self.rig, self.library.clips[index])

    def test_revert_restores_action_slot_all_transform_channels_and_timeline(self):
        self.assertEqual(self.start(), 0)
        self.assertIsNotNone(preview.active(self.rig))
        self.assertNotEqual(self.rig.animation_data.action, self.previous)
        self.scene.frame_set(8, subframe=0.5)
        self.assertTrue(preview.revert(bpy.context))
        self.assertIsNone(preview.active())
        self.assertStateEqual(self.state(), self.baseline)
        self.assertFalse(preview.revert(bpy.context))

    def test_switching_previews_keeps_first_baseline(self):
        self.start(0)
        first_action = self.rig.animation_data.action
        self.scene.frame_set(9, subframe=0.25)
        self.start(2)
        self.assertNotEqual(self.rig.animation_data.action, first_action)
        self.assertEqual(self.rig.animation_data.action.name, 'run')
        self.start(0)
        self.assertEqual(self.rig.animation_data.action, first_action)
        self.assertTrue(preview.revert(bpy.context))
        self.assertStateEqual(self.state(), self.baseline)

    def test_apply_records_only_the_committed_clip(self):
        self.start(0)
        self.start(2)
        self.assertTrue(all(item.recent_order == 0 for item in self.library.clips))
        action = self.rig.animation_data.action
        self.scene.frame_set(6, subframe=0.125)
        committed_timing = timing(self.scene)
        preview.apply(bpy.context)
        self.assertIsNone(preview.active())
        self.assertEqual(self.rig.animation_data.action, action)
        self.assertEqual(timing(self.scene), committed_timing)
        self.assertGreater(self.library.clips[2].recent_order, 0)
        self.assertEqual(self.library.clips[0].recent_order, 0)
        self.assertTrue(self.library.has_rest_rotation)
        self.assertFalse(preview.revert(bpy.context))
        animations.remove_animation(bpy.context, self.rig)
        self.assertEqual(self.rig.rotation_mode, self.baseline['object'][0])
        for a, b in zip(self.rig.rotation_euler, self.baseline['object'][3]):
            self.assertAlmostEqual(a, b, places=6)

    def test_apply_uses_previewed_clip_when_browser_selection_has_changed(self):
        self.start(0)
        action = self.rig.animation_data.action
        self.library.index = 2
        preview.apply(bpy.context)
        self.assertEqual(self.rig.animation_data.action, action)
        self.assertGreater(self.library.clips[0].recent_order, 0)
        self.assertEqual(self.library.clips[2].recent_order, 0)

    def test_changed_action_cannot_be_applied_as_the_preview(self):
        self.start()
        self.rig.animation_data.action = bpy.data.actions.new('External change')
        with self.assertRaisesRegex(ValueError, 'preview action changed'):
            preview.apply(bpy.context)
        self.assertIsNotNone(preview.active())
        preview.revert(bpy.context)
        self.assertStateEqual(self.state(), self.baseline)

    def test_changed_action_slot_cannot_be_applied_as_the_preview(self):
        self.start()
        action = self.rig.animation_data.action
        if not hasattr(action, 'slots'):
            self.skipTest('Action slots are available in Blender 4.4 and newer')
        other_slot = action.slots.new(id_type='OBJECT', name='External slot change')
        self.rig.animation_data.action_slot = other_slot
        with self.assertRaises(ValueError):
            preview.apply(bpy.context)
        self.assertIsNotNone(preview.active())
        preview.revert(bpy.context)
        self.assertStateEqual(self.state(), self.baseline)

    def test_failed_first_preview_leaves_no_session_or_scene_changes(self):
        real = self.importer.importAnimationNode
        def broken(*args):
            real(*args)
            raise RuntimeError('interrupted preview fixture')
        actions = set(bpy.data.actions)
        with patch.object(self.importer, 'importAnimationNode', broken):
            with self.assertRaisesRegex(RuntimeError, 'interrupted preview'):
                self.start(0)
        self.assertIsNone(preview.active())
        self.assertEqual(set(bpy.data.actions), actions)
        self.assertStateEqual(self.state(), self.baseline)

    def test_failed_switch_keeps_current_preview_and_original_baseline(self):
        self.start(0)
        self.scene.frame_set(4, subframe=0.625)
        current = self.state()
        session = preview.active()
        real = self.importer.importAnimationNode
        def broken(*args):
            real(*args)
            raise RuntimeError('interrupted switch fixture')
        with patch.object(self.importer, 'importAnimationNode', broken):
            with self.assertRaisesRegex(RuntimeError, 'interrupted switch'):
                self.start(2)
        self.assertIs(preview.active(), session)
        self.assertStateEqual(self.state(), current)
        preview.revert(bpy.context)
        self.assertStateEqual(self.state(), self.baseline)

    def test_no_action_baseline_restores_pose_and_detaches_preview(self):
        self.rig.animation_data_clear()
        self.baseline = self.state()
        self.start()
        preview.revert(bpy.context)
        self.assertStateEqual(self.state(), self.baseline)

    def test_timeline_option_and_pose_mode_selection_are_preserved(self):
        mesh = make_mesh('another selected object')
        select(self.rig, mesh)
        bpy.ops.object.mode_set(mode='POSE')
        self.library.fit_timeline = False
        before_timing = timing(self.scene)
        self.start()
        self.assertEqual(timing(self.scene), before_timing)
        self.assertEqual(bpy.context.mode, 'POSE')
        self.assertEqual(set(bpy.context.selected_objects), {self.rig, mesh})
        self.assertEqual(bpy.context.active_object, self.rig)
        preview.revert(bpy.context)
        self.assertEqual(bpy.context.mode, 'POSE')
        self.assertEqual(set(bpy.context.selected_objects), {self.rig, mesh})
        self.assertStateEqual(self.state(), self.baseline)

    def test_other_rig_is_rejected_without_losing_active_preview(self):
        self.start()
        session = preview.active()
        other = make_rig()
        animations.link_library(other, str(self.rig_path))
        with self.assertRaises(ValueError):
            preview.start(bpy.context, other, other.apex_animation_library.clips[0])
        self.assertIs(preview.active(), session)
        self.assertIsNone(preview.active(other))
        self.assertIsNone(other.animation_data)
        preview.revert(bpy.context)
        self.assertStateEqual(self.state(), self.baseline)

    def test_revert_after_target_deletion_still_restores_timing(self):
        self.start()
        bpy.data.objects.remove(self.rig, do_unlink=True)
        preview.revert(bpy.context)
        self.assertIsNone(preview.active())
        self.assertEqual(timing(self.scene), self.baseline['timing'])

    def test_preview_uses_allow_missing_bones_setting(self):
        path = self.anim_folder / 'idle.cast'
        fixtures.animation_file(self.cast, path, missing=True)
        animations.link_library(self.rig, str(self.rig_path))
        self.library.allow_missing = False
        with self.assertRaisesRegex(ValueError, 'animated bones are missing'):
            self.start()
        self.assertIsNone(preview.active())
        self.library.allow_missing = True
        self.assertEqual(self.start(), 1)
        preview.revert(bpy.context)
        self.assertStateEqual(self.state(), self.baseline)

    def test_existing_rest_orientation_bookkeeping_survives_revert(self):
        self.library.has_rest_rotation = True
        self.library.rest_rotation_mode = 'AXIS_ANGLE'
        self.library.rest_rotation = (0.45, 1, 0, 0)
        self.baseline = self.state()
        self.start()
        preview.revert(bpy.context)
        self.assertStateEqual(self.state(), self.baseline)

    def test_preview_apply_and_revert_operators(self):
        self.assertEqual(bpy.ops.object.apex_preview_animation(), {'FINISHED'})
        self.assertIsNotNone(preview.active())
        self.assertEqual(bpy.ops.object.apex_revert_animation_preview(), {'FINISHED'})
        self.assertStateEqual(self.state(), self.baseline)
        self.assertEqual(bpy.ops.object.apex_preview_animation(), {'FINISHED'})
        action = self.rig.animation_data.action
        self.assertEqual(bpy.ops.object.apex_apply_animation_preview(), {'FINISHED'})
        self.assertEqual(self.rig.animation_data.action, action)
        self.assertIsNone(preview.active())

    def test_saving_reverts_preview_before_serializing_scene(self):
        self.start()
        path = self.folder / 'preview_save.blend'
        rig_name, action_name = self.rig.name, self.previous.name
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        self.assertIsNone(preview.active())
        self.assertStateEqual(self.state(), self.baseline)
        bpy.ops.wm.open_mainfile(filepath=str(path))
        self.rig = bpy.data.objects[rig_name]
        self.library = self.rig.apex_animation_library
        self.scene = bpy.context.scene
        self.assertEqual(self.rig.animation_data.action.name, action_name)
        self.assertEqual(timing(self.scene), self.baseline['timing'])
        self.assertIsNone(preview.active())

    def test_save_cleanup_recovers_preview_marker_copied_by_rig_duplication(self):
        self.start()
        duplicate = self.rig.copy()
        duplicate.data = self.rig.data.copy()
        bpy.context.collection.objects.link(duplicate)
        duplicate.location = (9, 8, 7)
        duplicate_transform = transforms(duplicate)
        self.assertIn('_apex_animation_preview', duplicate)
        preview.cancel_preview(None)
        self.assertNotIn('_apex_animation_preview', duplicate)
        self.assertNotIn('_apex_animation_preview', self.rig)
        self.assertEqual(duplicate.animation_data.action, self.previous)
        self.assertEqual(transforms(duplicate), duplicate_transform)
        self.assertEqual({bone.name: transforms(bone) for bone in duplicate.pose.bones}, self.baseline['bones'])
        self.assertStateEqual(self.state(), self.baseline)

    def test_lifecycle_handlers_clear_preview_and_do_not_duplicate(self):
        for handlers in (bpy.app.handlers.load_pre, bpy.app.handlers.undo_pre,
                         bpy.app.handlers.redo_pre, bpy.app.handlers.save_pre):
            matching = [fn for fn in handlers if 'preview' in fn.__name__]
            self.assertEqual(len(matching), 1, [fn.__name__ for fn in handlers])
            self.start()
            matching[0](None)
            self.assertIsNone(preview.active())
            self.assertStateEqual(self.state(), self.baseline)
        addon.unregister()
        addon.register()
        for handlers in (bpy.app.handlers.load_pre, bpy.app.handlers.undo_pre,
                         bpy.app.handlers.redo_pre, bpy.app.handlers.save_pre):
            self.assertEqual(len([fn for fn in handlers if 'preview' in fn.__name__]), 1)

    def test_unregister_reverts_active_preview(self):
        self.start()
        action, object_transform = self.previous, transforms(self.rig)
        addon.unregister()
        try:
            self.assertIsNone(preview.active())
            self.assertEqual(self.rig.animation_data.action, action)
            self.assertEqual(transforms(self.rig), self.baseline['object'])
            self.assertEqual(timing(self.scene), self.baseline['timing'])
            self.assertNotEqual(transforms(self.rig), object_transform)
        finally:
            addon.register()


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(AnimationPreview))
    if not result.wasSuccessful():
        raise SystemExit(1)
