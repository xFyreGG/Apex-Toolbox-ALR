"""Moved RSX library checks using real CAST exports and Blender datablocks.

Run in a factory-startup background Blender process. Append -- --release to
test the packaged add-on. All files are temporary; no user exports are changed.
"""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

import addon_utils
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from workflow_integration import (addon, animations, cast_index, workflows,
                                  model_file, animation_file, make_rig, make_mesh, select)
from Apex_toolbox.apex_tex import relink


class RelinkTests(unittest.TestCase):
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
        for name in ('actions', 'images'):
            for item in list(getattr(bpy.data, name)):
                getattr(bpy.data, name).remove(item, do_unlink=True)
        for scene in bpy.data.scenes:
            scene.my_prefs.model_parent_folder = ''
            scene.my_prefs.animation_parent_folder = ''
            scene.my_prefs.autotex_folder = ''
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.old, self.new = base / 'original' / 'exported_files', base / 'moved' / 'exported_files'
        self.model = self.old / 'mdl' / 'wraith_base' / 'wraith_base_LOD0.cast'
        self.model.parent.mkdir(parents=True)
        model_file(self.cast, self.model)
        self.export = self.old / 'animrig' / 'pilot_medium_wraith' / 'pilot_medium_wraith.cast'
        self.export.parent.mkdir(parents=True)
        model_file(self.cast, self.export, mesh=False)
        self.sequence = self.export.parent / 'anims_pilot_medium_wraith' / 'clips.cast'
        self.sequence.parent.mkdir()
        animation_file(self.cast, self.sequence, names=('idle', 'lobby_walk'))
        texture = self.model.parent / 'body_col.png'
        generated = bpy.data.images.new('fixture', width=2, height=2)
        generated.filepath_raw, generated.file_format = str(texture), 'PNG'
        generated.save()
        bpy.data.images.remove(generated)
        self.image = bpy.data.images.load(str(texture))
        self.rig = make_rig()
        self.mesh = make_mesh()
        self.rig['apex_source_model'] = str(self.model)
        self.mesh['apex_source_model'] = str(self.model)
        self.cache_patch = patch.object(animations, 'index_cache_root', return_value=None)
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)
        animations.link_library(self.rig, str(self.export))
        self.library = self.rig.apex_animation_library
        self.library.index = 1
        item = self.library.clips[1]
        item.favourite, item.recent_order = True, 1
        item.menu_name, item.menu_role, item.menu_source = 'Custom Walk', 'Loop', 'CUSTOM'
        self.library.names_summary = '1 custom name.'
        self.library.names_file = '/catalog/english.locl'
        bpy.context.scene.my_prefs.model_parent_folder = str(self.old / 'mdl')
        bpy.context.scene.my_prefs.animation_parent_folder = str(self.old / 'animrig')
        bpy.context.scene.my_prefs.autotex_folder = str(self.model.parent)
        shutil.copytree(self.old, self.new)
        select(self.rig, self.mesh)

    def moved(self, path):
        return self.new / path.relative_to(self.old)

    def state(self):
        return (self.rig['apex_source_model'], self.mesh['apex_source_model'],
                self.library.rig_file,
                tuple(relink._clip_state(item) for item in self.library.clips),
                self.image.filepath_raw,
                tuple(getattr(bpy.context.scene.my_prefs, key) for key in
                      ('model_parent_folder', 'animation_parent_folder', 'autotex_folder')))

    def plan(self):
        return relink.build(bpy.context, str(self.old), str(self.new))

    def test_preview_changes_nothing_and_cancel_leaves_all_paths(self):
        before = self.state()
        plan = self.plan()
        self.assertEqual(self.state(), before)
        self.assertEqual(len(plan.changes), 9)
        self.assertEqual(plan.missing, [])
        self.assertEqual(plan.warnings, [])
        self.assertIn('2 animation(s)', plan.summary)
        del plan
        self.assertEqual(self.state(), before)

    def test_moved_library_preserves_action_pose_timeline_selection_and_browser_state(self):
        item = self.library.clips[1]
        animations.load_clip(bpy.context, self.rig, item, fit_timeline=False, allow_missing=True)
        action = item.action
        self.assertTrue(action.use_fake_user)
        item.stamp = 'old cached source identity'
        matrix = self.rig.matrix_world.copy()
        pose = [bone.matrix_basis.copy() for bone in self.rig.pose.bones]
        selected, active = list(bpy.context.selected_objects), bpy.context.active_object
        scene = bpy.context.scene
        timeline = (scene.frame_start, scene.frame_end, scene.frame_current,
                    scene.render.fps, scene.render.fps_base)
        shutil.rmtree(self.old)
        plan = self.plan()
        message, warning = relink.apply(plan)
        self.assertFalse(warning, message)
        self.assertEqual(self.rig['apex_source_model'], str(self.moved(self.model)))
        self.assertEqual(self.mesh['apex_source_model'], str(self.moved(self.model)))
        self.assertEqual(self.library.rig_file, str(self.moved(self.export)))
        self.assertEqual(self.image.filepath_raw, str(self.moved(self.model.parent / 'body_col.png')))
        self.assertTrue(all(c.filepath == str(self.moved(self.sequence)) for c in self.library.clips))
        self.assertEqual(item.stamp, '')
        self.assertEqual(item.action, action)
        self.assertEqual(self.rig.animation_data.action, action)
        self.assertTrue(action.use_fake_user)
        self.assertEqual(self.library.index, 1)
        self.assertEqual((item.favourite, item.recent_order, item.menu_name,
                          item.menu_role, item.menu_source), (True, 1, 'Custom Walk', 'Loop', 'CUSTOM'))
        self.assertEqual(self.library.names_file, '/catalog/english.locl')
        self.assertEqual(self.library.names_summary, '1 custom name.')
        self.assertEqual(self.rig.matrix_world, matrix)
        self.assertEqual([bone.matrix_basis for bone in self.rig.pose.bones], pose)
        self.assertEqual(list(bpy.context.selected_objects), selected)
        self.assertEqual(bpy.context.active_object, active)
        self.assertEqual((scene.frame_start, scene.frame_end, scene.frame_current,
                          scene.render.fps, scene.render.fps_base), timeline)
        self.assertEqual(scene.my_prefs.model_parent_folder, str(self.new / 'mdl'))
        self.assertEqual(scene.my_prefs.animation_parent_folder, str(self.new / 'animrig'))
        self.assertEqual(scene.my_prefs.autotex_folder, str(self.moved(self.model.parent)))
        animations.load_clip(bpy.context, self.rig, item, fit_timeline=False, allow_missing=True)
        self.assertNotEqual(item.action, action)
        self.assertIn(action, bpy.data.actions[:])

    def test_missing_targets_keep_their_working_paths_and_other_changes_apply(self):
        self.moved(self.sequence).unlink()
        self.moved(self.model.parent / 'body_col.png').unlink()
        plan = self.plan()
        self.assertEqual(len(plan.missing), 3)
        self.assertEqual(plan.warnings, [])
        _, warning = relink.apply(plan)
        self.assertTrue(warning)
        self.assertEqual(self.library.rig_file, str(self.moved(self.export)))
        self.assertTrue(all(item.filepath == str(self.sequence) for item in self.library.clips))
        self.assertEqual(self.image.filepath_raw, str(self.model.parent / 'body_col.png'))

    def test_corrupt_cast_is_skipped_without_repointing_model_paths(self):
        self.moved(self.model).write_bytes(b'cast broken')
        plan = self.plan()
        self.assertEqual(len(plan.warnings), 2)
        self.assertEqual(plan.missing, [])
        relink.apply(plan)
        self.assertEqual(self.rig['apex_source_model'], str(self.model))
        self.assertEqual(self.mesh['apex_source_model'], str(self.model))

    def test_animation_cast_cannot_replace_model_or_rig_cast(self):
        shutil.copyfile(self.sequence, self.moved(self.model))
        shutil.copyfile(self.sequence, self.moved(self.export))
        plan = self.plan()
        self.assertEqual(len(plan.warnings), 3)
        self.assertTrue(all(change.kind not in {'model', 'rig'} for change in plan.changes))

    def test_reordered_animation_nodes_update_offsets_by_exact_identity(self):
        before = {item.name: (item.offset, item.guid) for item in self.library.clips}
        doc = self.cast.Cast.load(str(self.moved(self.sequence)))
        doc.Roots()[0].childNodes.reverse()
        doc.save(str(self.moved(self.sequence)))
        plan = self.plan()
        self.assertEqual(plan.warnings, [])
        relink.apply(plan)
        after = {item.name: (item.offset, item.guid) for item in self.library.clips}
        self.assertNotEqual(before['idle'][0], after['idle'][0])
        self.assertNotEqual(before['lobby_walk'][0], after['lobby_walk'][0])
        self.assertEqual({name: value[1] for name, value in before.items()},
                         {name: value[1] for name, value in after.items()})
        animations.load_clip(bpy.context, self.rig, self.library.clips[1], allow_missing=True)

    def test_changed_animation_identity_is_not_guessed_from_its_name(self):
        doc = self.cast.Cast.load(str(self.moved(self.sequence)))
        doc.Roots()[0].childNodes[0].hash += 100
        doc.save(str(self.moved(self.sequence)))
        plan = self.plan()
        self.assertEqual(len(plan.warnings), 1)
        relink.apply(plan)
        self.assertEqual(self.library.clips[0].filepath, str(self.sequence))
        self.assertEqual(self.library.clips[1].filepath, str(self.moved(self.sequence)))

    def test_ambiguous_legacy_clip_is_not_assigned_by_offset(self):
        self.library.clips[0].guid = ''
        doc = self.cast.Cast.load(str(self.moved(self.sequence)))
        doc.Roots()[0].childNodes[1].SetName('idle')
        doc.save(str(self.moved(self.sequence)))
        plan = self.plan()
        self.assertEqual(len(plan.warnings), 2)
        self.assertTrue(any('multiple matching clips' in warning for warning in plan.warnings))

    def test_file_race_aborts_before_any_path_changes(self):
        plan, before = self.plan(), self.state()
        self.moved(self.sequence).write_bytes(b'replaced after preview')
        with self.assertRaisesRegex(ValueError, 'changed or disappeared'):
            relink.apply(plan)
        self.assertEqual(self.state(), before)

    def test_path_changed_after_preview_aborts_without_overwriting_it(self):
        plan = self.plan()
        self.library.rig_file = 'user-changed.cast'
        before = self.state()
        with self.assertRaisesRegex(ValueError, 'path changed'):
            relink.apply(plan)
        self.assertEqual(self.state(), before)

    def test_clip_removed_after_preview_aborts_all_changes(self):
        plan = self.plan()
        self.library.clips.remove(0)
        before = self.state()
        with self.assertRaisesRegex(ValueError, 'library changed'):
            relink.apply(plan)
        self.assertEqual(self.state(), before)

    def test_deleted_owner_after_preview_aborts_all_changes(self):
        plan = self.plan()
        bpy.data.objects.remove(self.mesh, do_unlink=True)
        with self.assertRaisesRegex(ValueError, 'removed'):
            relink.apply(plan)
        self.assertEqual(self.rig['apex_source_model'], str(self.model))
        self.assertEqual(self.library.rig_file, str(self.export))

    def test_bone_edit_after_preview_aborts_all_changes(self):
        plan, before = self.plan(), self.state()
        self.rig.data.bones['child'].name = 'user_changed_bone'
        with self.assertRaisesRegex(ValueError, 'skeleton changed'):
            relink.apply(plan)
        self.assertEqual(self.state(), before)

    def test_packing_a_texture_after_preview_aborts_all_changes(self):
        plan, before = self.plan(), self.state()
        self.image.pack()
        with self.assertRaisesRegex(ValueError, 'texture changed'):
            relink.apply(plan)
        self.assertEqual(self.state(), before)

    def test_target_race_after_first_assignment_rolls_back_every_change(self):
        plan, before = self.plan(), self.state()
        stamp, calls = relink._stamp, []
        def racing(change):
            calls.append(change)
            # All preflight checks and one assignment have already succeeded.
            if len(calls) == len(plan.changes) + 2:
                self.assertNotEqual(self.state(), before)
                return None
            return stamp(change)
        with patch.object(relink, '_stamp', side_effect=racing):
            with self.assertRaisesRegex(ValueError, 'changed or disappeared'):
                relink.apply(plan)
        self.assertEqual(self.state(), before)
        self.assertFalse(plan.applied)

    def test_other_scene_references_are_relinked_without_switching_scenes(self):
        scene = bpy.data.scenes.new('other_scene')
        self.addCleanup(lambda: bpy.data.scenes.remove(scene))
        scene.my_prefs.model_parent_folder = str(self.old / 'mdl')
        other = make_mesh('other_scene_model')
        other['apex_source_model'] = str(self.model)
        bpy.context.collection.objects.unlink(other)
        scene.collection.objects.link(other)
        active_scene = bpy.context.scene
        relink.apply(self.plan())
        self.assertEqual(other['apex_source_model'], str(self.moved(self.model)))
        self.assertEqual(scene.my_prefs.model_parent_folder, str(self.new / 'mdl'))
        self.assertEqual(bpy.context.scene, active_scene)

    def test_packed_images_and_prefix_overlap_paths_are_untouched(self):
        self.image.pack()
        other = make_mesh('other_library')
        other['apex_source_model'] = str(self.old.parent / 'exported_files_extra' / 'x.cast')
        plan = self.plan()
        self.assertFalse(any(change.kind == 'image' for change in plan.changes))
        self.assertFalse(any(change.owner == other for change in plan.changes))
        self.assertEqual(plan.missing, [])
        relink.apply(plan)
        self.assertEqual(self.image.filepath_raw, str(self.model.parent / 'body_col.png'))
        self.assertTrue(self.image.packed_file)
        self.assertIn('exported_files_extra', other['apex_source_model'])

    def udim_image(self):
        source = self.model.parent / 'body_col.png'
        for number in (1001, 1002):
            old = self.model.parent / ('body.%d.png' % number)
            shutil.copyfile(source, old)
            shutil.copyfile(source, self.moved(old))
        self.image.source = 'TILED'
        self.image.filepath_raw = str(self.model.parent / 'body.<UDIM>.png')
        self.image.tiles.new(1002)

    def test_unpacked_udim_images_check_referenced_tiles_and_relink_pattern(self):
        self.udim_image()
        plan = self.plan()
        self.assertEqual(plan.missing, [])
        self.assertEqual(plan.warnings, [])
        relink.apply(plan)
        self.assertEqual(self.image.filepath_raw, str(self.moved(self.model.parent / 'body.<UDIM>.png')))
        self.assertEqual([tile.number for tile in self.image.tiles], [1001, 1002])

    def test_missing_udim_tile_keeps_existing_image_pattern(self):
        self.udim_image()
        self.moved(self.model.parent / 'body.1002.png').unlink()
        plan = self.plan()
        self.assertEqual(len(plan.missing), 1)
        relink.apply(plan)
        self.assertEqual(self.image.filepath_raw, str(self.model.parent / 'body.<UDIM>.png'))

    def test_image_sequence_relinks_existing_start_file_without_scanning(self):
        self.image.source = 'SEQUENCE'
        plan = self.plan()
        self.assertEqual(plan.missing, [])
        relink.apply(plan)
        self.assertEqual(self.image.filepath_raw, str(self.moved(self.model.parent / 'body_col.png')))

    def test_blend_location_change_requires_a_new_preview(self):
        plan, before = self.plan(), self.state()
        plan.blend_file = 'a previous blend location.blend'
        with self.assertRaisesRegex(ValueError, 'blend file changed'):
            relink.apply(plan)
        self.assertEqual(self.state(), before)

    def test_duplicate_models_keep_separate_animation_state(self):
        second = self.rig.copy()
        second.data = self.rig.data.copy()
        bpy.context.collection.objects.link(second)
        second.apex_animation_library.clips[0].favourite = True
        second.apex_animation_library.index = 0
        relink.apply(self.plan())
        self.assertEqual(second.apex_animation_library.index, 0)
        self.assertTrue(second.apex_animation_library.clips[0].favourite)
        self.assertFalse(self.library.clips[0].favourite)
        self.assertEqual(self.library.index, 1)
        self.assertTrue(all(item.filepath == str(self.moved(self.sequence))
                            for item in second.apex_animation_library.clips))

    def test_apply_cannot_run_twice_and_unchosen_invalid_roots_are_rejected(self):
        plan = self.plan()
        relink.apply(plan)
        with self.assertRaisesRegex(ValueError, 'already applied'):
            relink.apply(plan)
        with self.assertRaisesRegex(ValueError, 'different folder'):
            relink.build(bpy.context, str(self.old), str(self.old))
        with self.assertRaisesRegex(ValueError, 'does not exist'):
            relink.build(bpy.context, str(self.old), str(self.new / 'missing'))

    def test_suggest_uses_saved_paths_when_old_drive_is_missing(self):
        shutil.rmtree(self.old)
        self.assertEqual(relink.suggest_old_root(bpy.context), str(self.old))
        self.rig['apex_source_model'] = 'G:/RSX/exported_files/mdl/wraith_base/wraith.cast'
        self.assertEqual(Path(relink.suggest_old_root(bpy.context)), Path('G:/RSX/exported_files'))

    @unittest.skipUnless(sys.platform == 'win32', 'Windows path semantics')
    def test_windows_drive_case_and_component_containment(self):
        old, new = Path('g:/rsx/exported_files'), Path('H:/Moved Library')
        mapped = relink._mapped('G:/RSX/EXPORTED_FILES/mdl/wraith/x.cast', old, new)
        self.assertEqual(mapped, new / 'mdl/wraith/x.cast')
        self.assertIsNone(relink._mapped('G:/RSX/exported_files_extra/x.cast', old, new))
        self.assertIsNone(relink._mapped('I:/RSX/exported_files/x.cast', old, new))


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(RelinkTests))
    if not result.wasSuccessful():
        raise SystemExit(1)
