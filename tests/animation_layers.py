"""Real CAST + Blender NLA layer tests, isolated from the user's files and scenes."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import addon_utils
import bpy
from mathutils import Quaternion, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from workflow_integration import addon, model_file, animation_file, make_rig, select
from Apex_toolbox.apex_tex import animation_layers as layers, animations, workflows


class AnimationLayers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        addon_utils.enable('io_scene_cast', default_set=False)
        _, cls.cast, _ = workflows.cast_modules()
        addon.register()

    @classmethod
    def tearDownClass(cls):
        addon.unregister()
        addon_utils.disable('io_scene_cast', default_set=False)

    def setUp(self):
        if bpy.context.object and bpy.context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for action in list(bpy.data.actions):
            bpy.data.actions.remove(action, do_unlink=True)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.path = self.folder / 'test_rig.cast'
        model_file(self.cast, self.path, mesh=False)
        anim_folder = self.folder / 'anims_test_rig'
        anim_folder.mkdir()
        animation_file(self.cast, anim_folder / 'base.cast', names=('base',))
        animation_file(self.cast, anim_folder / 'hands.cast', names=('hands',), additive=True)
        animation_file(self.cast, anim_folder / 'hands_two.cast', names=('hands_two',), additive=True)
        animation_file(self.cast, anim_folder / 'missing.cast', names=('missing',), additive=True, missing=True)
        self.rig = make_rig()
        select(self.rig)
        animations.link_library(self.rig, str(self.path))
        self.library = self.rig.apex_animation_library
        self.base = self.item('base')
        self.hands = self.item('hands')
        animations.load_clip(bpy.context, self.rig, self.base, allow_missing=True)
        self.base_action = self.rig.animation_data.action
        self.slot = layers._slot_handle(self.rig.animation_data)
        bpy.context.scene.frame_set(10)

    def item(self, name):
        return next(item for item in self.library.clips if item.name == name)

    def add(self, item=None, **kwargs):
        return layers.add(bpy.context, self.rig, item or self.item('hands'), **kwargs)

    def custom_clip(self, name, tracks, frames=(0, 10)):
        path = self.folder / (name + '.cast')
        doc = self.cast.Cast()
        anim = doc.CreateRoot().CreateAnimation()
        anim.SetName(name)
        anim.SetFramerate(30)
        for prop, mode, values in tracks:
            curve = anim.CreateCurve()
            curve.SetNodeName('root')
            curve.SetKeyPropertyName(prop)
            curve.SetKeyFrameBuffer(list(frames[prop] if isinstance(frames, dict) else frames))
            if prop == 'rq':
                curve.SetVec4KeyValueBuffer(values)
            else:
                curve.SetFloatKeyValueBuffer(values)
            curve.SetMode(mode)
        doc.save(str(path))
        node = animations.cast_index.nodes_of(animations.cast_index.read_cast(path), b'anim')[0]
        clip = animations.clip_from_node(path, node)
        item = self.library.clips.add()
        for prop in ('name', 'filepath', 'offset', 'guid', 'sequence_hash', 'fps', 'additive'):
            setattr(item, prop, getattr(clip, prop))
        return item

    def load_long_base(self):
        base = self.custom_clip('long_base', [
            ('rq', 'relative', [(0, 0, 0, 1), (0, 0, 0.38268343, 0.92387953)]),
            ('tx', 'relative', (0.0, 5.0)),
        ], frames=(0, 100))
        animations.load_clip(bpy.context, self.rig, base)
        self.base_action = self.rig.animation_data.action

    def static_pose(self, name='crouch_offset'):
        return self.custom_clip(name, [
            ('rq', 'additive', [(0, 0, 0.38268343, 0.92387953)]),
            # This animated, normal channel must be excluded from the layer
            # and from deciding whether its additive delta is a held pose.
            ('tx', 'relative', (100.0, 200.0)),
        ], frames={'rq': (0,), 'tx': (0, 100)})

    def rotation(self, name='root'):
        return self.rig.pose.bones[name].rotation_quaternion.copy()

    def assert_quaternion(self, actual, expected):
        self.assertAlmostEqual(actual.rotation_difference(expected).angle, 0.0, places=5)

    def state(self):
        scene = bpy.context.scene
        return (self.rig.animation_data.action, layers._slot_handle(self.rig.animation_data),
                self.rig.matrix_world.copy(), scene.frame_start, scene.frame_end,
                scene.frame_current, scene.frame_subframe, scene.render.fps, scene.render.fps_base,
                tuple(context_obj.name for context_obj in bpy.context.selected_objects),
                bpy.context.active_object.name if bpy.context.active_object else '', bpy.context.mode)

    def test_real_cast_additive_rotations_combine_and_normal_root_motion_is_not_doubled(self):
        before = self.rotation()
        root_location = self.rig.pose.bones['root'].location.copy()
        self.add()
        self.assertEqual(len(self.rig.animation_data.nla_tracks), 2)
        self.assertIsNone(self.rig.animation_data.action)
        self.assertEqual(layers.layers(self.rig)[0].blend_type, 'COMBINE')
        self.assert_quaternion(self.rotation(), before @ before)
        self.assertLess((self.rig.pose.bones['root'].location - root_location).length, 1e-5)
        self.assertEqual(self.base_action, layers._state(self.rig)['base']['action'])

    def test_zero_and_half_influence_evaluate_without_changing_source(self):
        base_rotation = self.rotation()
        self.add(influence=0.0)
        self.assert_quaternion(self.rotation(), base_rotation)
        strip = layers.layers(self.rig)[0]
        layers.set_influence(bpy.context, self.rig, 0, 0.5)
        self.assert_quaternion(self.rotation(), base_rotation @ Quaternion().slerp(base_rotation, 0.5))
        self.assertNotEqual(strip.action, self.hands.action)

    def test_two_different_layers_stack_and_remove_restores_base_slot(self):
        original = self.rotation()
        self.add()
        self.add(self.item('hands_two'))
        self.assertEqual(len(layers.layers(self.rig)), 2)
        self.assert_quaternion(self.rotation(), original @ original @ original)
        layers.remove(bpy.context, self.rig)
        self.assertFalse(layers.can_remove(self.rig))
        self.assertEqual(len(self.rig.animation_data.nla_tracks), 0)
        self.assertEqual(self.rig.animation_data.action, self.base_action)
        self.assertEqual(layers._slot_handle(self.rig.animation_data), self.slot)
        self.assert_quaternion(self.rotation(), original)

    def test_duplicate_clip_is_rejected_without_changing_existing_layer(self):
        self.add()
        strip = layers.layers(self.rig)[0]
        before_actions = set(bpy.data.actions)
        before_rotation = self.rotation()
        with self.assertRaisesRegex(ValueError, 'already has a layer'):
            self.add()
        self.assertEqual(layers.layers(self.rig), [strip])
        self.assertEqual(set(bpy.data.actions), before_actions)
        self.assert_quaternion(self.rotation(), before_rotation)

    def test_scene_selection_orientation_and_pose_mode_are_preserved(self):
        self.rig.rotation_euler = (0.2, -0.1, 0.4)
        self.rig.location = (2, 3, 4)
        scene = bpy.context.scene
        scene.frame_start, scene.frame_end = 4, 73
        scene.frame_set(6, subframe=0.25)
        bpy.ops.object.mode_set(mode='POSE')
        before = self.state()
        self.add()
        after = self.state()
        self.assertEqual(before[2:], after[2:])
        layers.remove(bpy.context, self.rig)
        self.assertEqual(self.state(), before)

    def test_influence_and_action_flags_restore(self):
        data = self.rig.animation_data
        data.use_nla = False
        data.action_extrapolation = 'HOLD_FORWARD'
        data.action_influence = 0.75
        bpy.context.scene.frame_set(10)
        original = self.rotation()
        self.add(influence=0)
        self.assert_quaternion(self.rotation(), original)
        self.assertTrue(data.use_nla)
        layers.remove(bpy.context, self.rig)
        self.assertFalse(data.use_nla)
        self.assertEqual(data.action_extrapolation, 'HOLD_FORWARD')
        self.assertAlmostEqual(data.action_influence, 0.75)

    def test_dormant_active_action_mix_flags_do_not_change_evaluated_base_motion(self):
        data, scene = self.rig.animation_data, bpy.context.scene
        data.use_nla = True
        data.action_blend_type = 'ADD'
        data.action_extrapolation = 'NOTHING'
        data.action_influence = 0.5
        expected = {}
        for frame in (-5, 5, 15):
            scene.frame_set(frame)
            expected[frame] = self.rotation(), self.rig.pose.bones['root'].location.copy()
        self.add(influence=0)
        for frame, (rotation, location) in expected.items():
            scene.frame_set(frame)
            self.assert_quaternion(self.rotation(), rotation)
            self.assertLess((self.rig.pose.bones['root'].location - location).length, 1e-5)
        layers.remove(bpy.context, self.rig)
        self.assertEqual(data.action_blend_type, 'ADD')
        self.assertEqual(data.action_extrapolation, 'NOTHING')
        self.assertAlmostEqual(data.action_influence, 0.5)

    def test_manual_base_action_range_does_not_crop_existing_motion(self):
        self.base_action.use_frame_range = True
        self.base_action.frame_start, self.base_action.frame_end = 2, 8
        expected = {}
        for frame in (1, 5, 9, 15):
            bpy.context.scene.frame_set(frame)
            expected[frame] = self.rotation(), self.rig.pose.bones['root'].location.copy()
        self.add(influence=0)
        for frame, (rotation, location) in expected.items():
            bpy.context.scene.frame_set(frame)
            self.assert_quaternion(self.rotation(), rotation)
            self.assertLess((self.rig.pose.bones['root'].location - location).length, 1e-5)
        layers.remove(bpy.context, self.rig)
        self.assertTrue(self.base_action.use_frame_range)
        self.assertEqual(tuple(self.base_action.frame_range), (2, 8))

    def test_custom_base_extrapolation_is_rejected_without_changing_motion(self):
        curve = next(curve for curves in layers._curve_collections(self.base_action)
                     for curve in curves if curve.data_path.endswith('location'))
        curve.extrapolation = 'LINEAR'
        bpy.context.scene.frame_set(15)
        location = self.rig.pose.bones['root'].location.copy()
        before = self.state()
        with self.assertRaisesRegex(ValueError, 'custom extrapolation'):
            self.add()
        self.assertEqual(self.state(), before)
        self.assertEqual(self.rig.pose.bones['root'].location, location)
        self.assertEqual(len(self.rig.animation_data.nla_tracks), 0)

    def test_layer_uses_clip_fps_and_offset_without_changing_scene_fps(self):
        scene = bpy.context.scene
        scene.render.fps, scene.render.fps_base = 60, 1.0
        self.add(frame_offset=8)
        strip = layers.layers(self.rig)[0]
        self.assertAlmostEqual(strip.frame_start, 8.0)
        self.assertAlmostEqual(strip.scale, 60 / self.hands.fps, places=5)
        self.assertEqual(strip.extrapolation, 'NOTHING')
        self.assertEqual(scene.render.fps, 60)

    def test_single_frame_pose_holds_through_a_long_base_and_preserves_root_motion(self):
        self.load_long_base()
        pose = self.static_pose()
        scene = bpy.context.scene
        expected = {}
        for frame in (0, 35, 68, 100, 150):
            scene.frame_set(frame)
            expected[frame] = self.rotation(), self.rig.pose.bones['root'].location.copy()
        self.add(pose)
        strip = layers.layers(self.rig)[0]
        self.assertEqual(strip.extrapolation, 'HOLD_FORWARD')
        self.assertEqual(tuple(strip.action.curve_frame_range), (0, 0))
        delta = Quaternion((0.92387953, 0, 0, 0.38268343))
        for frame, (rotation, location) in expected.items():
            scene.frame_set(frame)
            self.assert_quaternion(self.rotation(), rotation @ delta)
            self.assertLess((self.rig.pose.bones['root'].location - location).length, 1e-5)
        layers.remove(bpy.context, self.rig)
        self.assertEqual(self.rig.animation_data.action, self.base_action)
        self.assert_quaternion(self.rotation(), expected[150][0])

    def test_single_frame_pose_strength_evaluates_zero_half_and_full_at_a_late_frame(self):
        self.load_long_base()
        bpy.context.scene.frame_set(68)
        original = self.rotation()
        self.add(self.static_pose(), influence=0)
        self.assert_quaternion(self.rotation(), original)
        delta = Quaternion((0.92387953, 0, 0, 0.38268343))
        for strength in (0.5, 1.0, 0.0):
            layers.set_influence(bpy.context, self.rig, 0, strength)
            self.assert_quaternion(self.rotation(), original @ Quaternion().slerp(delta, strength))
        layers.remove(bpy.context, self.rig)
        self.assert_quaternion(self.rotation(), original)

    def test_single_frame_pose_does_not_affect_frames_before_its_positive_offset(self):
        self.load_long_base()
        pose = self.static_pose()
        scene = bpy.context.scene
        expected = {}
        for frame in (0, 19, 20, 68, 100):
            scene.frame_set(frame)
            expected[frame] = self.rotation()
        self.add(pose, frame_offset=20)
        delta = Quaternion((0.92387953, 0, 0, 0.38268343))
        for frame, rotation in expected.items():
            scene.frame_set(frame)
            self.assert_quaternion(self.rotation(), rotation if frame < 20 else rotation @ delta)

    def test_single_frame_pose_hold_strength_and_removal_survive_save_and_reload(self):
        self.load_long_base()
        bpy.context.scene.frame_set(68)
        base_rotation = self.rotation()
        self.add(self.static_pose(), influence=0.5, frame_offset=20)
        layered_rotation = self.rotation()
        name = self.rig.name
        path = self.folder / 'held-pose.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        bpy.ops.wm.open_mainfile(filepath=str(path))
        self.rig = bpy.data.objects[name]
        self.library = self.rig.apex_animation_library
        strip = layers.layers(self.rig)[0]
        self.assertEqual(strip.extrapolation, 'HOLD_FORWARD')
        self.assertAlmostEqual(strip.frame_start, 20)
        self.assertEqual(tuple(strip.action.curve_frame_range), (0, 0))
        self.assertAlmostEqual(layers.influence(strip), 0.5)
        self.assert_quaternion(self.rotation(), layered_rotation)
        layers.set_influence(bpy.context, self.rig, 0, 0)
        self.assert_quaternion(self.rotation(), base_rotation)
        layers.set_influence(bpy.context, self.rig, 0, 0.5)
        self.assert_quaternion(self.rotation(), layered_rotation)
        layers.remove(bpy.context, self.rig)
        self.assert_quaternion(self.rotation(), base_rotation)

    def test_animated_additive_clip_still_ends_at_its_original_duration(self):
        self.load_long_base()
        scene = bpy.context.scene
        expected = {}
        for frame in (5, 68):
            scene.frame_set(frame)
            expected[frame] = self.rotation()
        self.add()
        strip = layers.layers(self.rig)[0]
        self.assertEqual(strip.extrapolation, 'NOTHING')
        scene.frame_set(5)
        self.assertGreater(self.rotation().rotation_difference(expected[5]).angle, 0.1)
        scene.frame_set(68)
        self.assert_quaternion(self.rotation(), expected[68])

    def test_missing_bones_enabled_imports_only_matching_additive_tracks(self):
        self.library.allow_missing = True
        message = self.add(self.item('missing'))
        self.assertIn('Skipped 1 missing bone', message)
        self.assertEqual(len(layers.layers(self.rig)), 1)

    def test_missing_bones_disabled_leaves_state_unchanged(self):
        self.library.allow_missing = False
        before, actions = self.state(), set(bpy.data.actions)
        with self.assertRaisesRegex(ValueError, 'missing'):
            self.add(self.item('missing'))
        self.assertEqual(self.state(), before)
        self.assertEqual(set(bpy.data.actions), actions)
        self.assertEqual(len(self.rig.animation_data.nla_tracks), 0)

    def test_normal_clip_cannot_be_added_as_layer(self):
        self.assertFalse(layers.can_add(self.rig, self.base))
        with self.assertRaisesRegex(ValueError, 'additive animation'):
            self.add(self.base)

    def test_no_base_animation_requires_loading_one(self):
        self.rig.animation_data.action = None
        self.assertFalse(layers.can_add(self.rig, self.hands))
        with self.assertRaisesRegex(ValueError, 'base animation'):
            self.add()

    def test_unrelated_nla_is_never_overwritten(self):
        track = self.rig.animation_data.nla_tracks.new()
        track.name = 'My hand-authored track'
        strip = track.strips.new('custom', 0, self.base_action)
        with self.assertRaisesRegex(ValueError, 'already has NLA'):
            self.add()
        self.assertEqual(list(track.strips), [strip])
        self.assertEqual(self.rig.animation_data.action, self.base_action)

    def test_remove_preserves_later_user_tracks_and_strips(self):
        self.add()
        data = self.rig.animation_data
        track = data.nla_tracks.new()
        track.name = 'My later track'
        strip = track.strips.new('custom', 80, self.base_action)
        layers.remove(bpy.context, self.rig)
        self.assertEqual(list(data.nla_tracks), [track])
        self.assertEqual(list(track.strips), [strip])

    def test_remove_preserves_user_strip_added_to_managed_track(self):
        self.add()
        data = self.rig.animation_data
        track = data.nla_tracks[next(iter(layers._state(self.rig)['layers'].values()))['track']]
        strip = track.strips.new('user strip', 80, self.base_action)
        layers.remove(bpy.context, self.rig)
        self.assertEqual(list(data.nla_tracks), [track])
        self.assertEqual(list(track.strips), [strip])

    def test_modified_layer_identity_is_not_deleted(self):
        self.add()
        strip = layers.layers(self.rig)[0]
        strip.action = self.base_action
        with self.assertRaisesRegex(ValueError, 'renamed or replaced'):
            layers.remove(bpy.context, self.rig)
        self.assertEqual(strip.action, self.base_action)

    def test_failed_import_rolls_back_data_and_scene(self):
        before, actions = self.state(), set(bpy.data.actions)
        with patch.object(animations, 'load_clip', side_effect=RuntimeError('fixture failure')):
            with self.assertRaisesRegex(RuntimeError, 'fixture failure'):
                self.add()
        self.assertEqual(self.state(), before)
        self.assertEqual(set(bpy.data.actions), actions)
        self.assertNotIn(layers.STATE, self.rig)

    def test_failed_nla_commit_restores_base_and_removes_temporary_actions(self):
        before, actions = self.state(), set(bpy.data.actions)
        real = layers._strip
        def broken(*args, **kwargs):
            if args[5] == 'COMBINE':
                raise RuntimeError('fixture commit failure')
            return real(*args, **kwargs)
        with patch.object(layers, '_strip', side_effect=broken):
            with self.assertRaisesRegex(RuntimeError, 'fixture commit failure'):
                self.add()
        self.assertEqual(self.state(), before)
        self.assertEqual(set(bpy.data.actions), actions)
        self.assertEqual(len(self.rig.animation_data.nla_tracks), 0)

    def test_changed_export_is_rejected_before_nla(self):
        animation_file(self.cast, Path(self.hands.filepath), names=('changed',), additive=True)
        before = self.state()
        with self.assertRaisesRegex(ValueError, 'export changed'):
            self.add()
        self.assertEqual(self.state(), before)

    def test_layers_survive_save_and_reload(self):
        self.add()
        name = self.rig.name
        path = self.folder / 'layers.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        bpy.ops.wm.open_mainfile(filepath=str(path))
        self.rig = bpy.data.objects[name]
        self.library = self.rig.apex_animation_library
        self.base_action = layers._state(self.rig)['base']['action']
        self.assertEqual(len(layers.layers(self.rig)), 1)
        layers.remove(bpy.context, self.rig)
        self.assertEqual(self.rig.animation_data.action, self.base_action)

    def test_scale_layers_multiply_instead_of_adding_identity_scale(self):
        base = self.custom_clip('scale_base', [(prop, 'relative', (2.0, 2.0)) for prop in ('sx', 'sy', 'sz')])
        animations.load_clip(bpy.context, self.rig, base)
        additive = self.custom_clip('scale_delta', [(prop, 'additive', (1.5, 1.5)) for prop in ('sx', 'sy', 'sz')])
        self.add(additive)
        self.assertTrue(all(abs(value - 3.0) < 1e-5 for value in self.rig.pose.bones['root'].scale))

    def test_complete_additive_translation_adds_to_base(self):
        delta = self.custom_clip('translation_delta', [
            ('tx', 'additive', (1.0, 1.0)), ('ty', 'additive', (2.0, 2.0)), ('tz', 'additive', (3.0, 3.0))])
        bpy.context.scene.frame_set(5)
        before = self.rig.pose.bones['root'].location.copy()
        self.add(delta)
        result = self.rig.pose.bones['root'].location - before
        self.assertLess((result - self.rig.data.bones['root'].matrix.inverted() @ Vector((1, 2, 3))).length, 1e-5)

    def test_partial_additive_translation_is_rejected_before_import(self):
        delta = self.custom_clip('partial_delta', [('tx', 'additive', (1.0, 1.0))])
        before = self.state()
        with self.assertRaisesRegex(ValueError, 'all three XYZ'):
            self.add(delta)
        self.assertEqual(self.state(), before)

    def test_custom_influence_keys_are_not_overwritten(self):
        self.add()
        strip = layers.layers(self.rig)[0]
        strip.influence = 0.2
        strip.keyframe_insert(data_path='influence', frame=9)
        with self.assertRaisesRegex(ValueError, 'custom influence keys'):
            layers.set_influence(bpy.context, self.rig, 0, 0.5)
        self.assertEqual(len(strip.fcurves[0].keyframe_points), 2)

    def test_failed_second_layer_keeps_first_layer_and_cached_actions(self):
        self.add()
        before_actions = set(bpy.data.actions)
        before_layers = layers.layers(self.rig)
        before_rotation = self.rotation()
        with patch.object(layers, '_strip', side_effect=RuntimeError('fixture failed second layer')):
            with self.assertRaisesRegex(RuntimeError, 'failed second layer'):
                self.add(self.item('hands_two'))
        self.assertEqual(set(bpy.data.actions), before_actions)
        self.assertEqual(layers.layers(self.rig), before_layers)
        self.assert_quaternion(self.rotation(), before_rotation)

    def test_base_fake_user_flag_is_not_changed(self):
        self.base_action.use_fake_user = False
        self.add()
        self.assertFalse(self.base_action.use_fake_user)
        layers.remove(bpy.context, self.rig)
        self.assertFalse(self.base_action.use_fake_user)

    def test_base_action_nonfirst_slot_is_preserved(self):
        if not hasattr(self.base_action, 'slots'):
            self.skipTest('Legacy Blender action has no slots')
        original_slot = self.rig.animation_data.action_slot
        other_slot = self.base_action.slots.new(id_type='OBJECT', name='other_model')
        self.base_action.slots.active = other_slot
        self.assertNotEqual(original_slot, other_slot)
        self.add()
        base_strip = layers._record_strip(self.rig, layers._state(self.rig)['base'])
        self.assertEqual(base_strip.action_slot, original_slot)
        layers.remove(bpy.context, self.rig)
        self.assertEqual(self.rig.animation_data.action_slot, original_slot)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AnimationLayers))
    if not result.wasSuccessful():
        raise SystemExit(1)
