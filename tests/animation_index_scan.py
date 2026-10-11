"""Animation index integration checks in a factory-startup Blender process.

Run with Blender --background --factory-startup --python-exit-code 1 --python
tests/animation_index_scan.py. Append -- --release to test the packaged add-on.
Synthetic CAST exports use the installed CAST writer; no game data is needed.
"""
from collections import Counter
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import addon_utils
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from workflow_integration import (addon, animations, cast_index, workflows,
                                  model_file, animation_file, make_rig)


class AnimationIndexScanTests(unittest.TestCase):
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
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.cache_root = self.folder / 'user-data' / 'animation-index'
        self.cache_patch = patch.object(animations, 'index_cache_root', return_value=self.cache_root)
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)
        self.rig_path = self.folder / 'pilot_medium.cast'
        model_file(self.cast, self.rig_path, mesh=False)
        self.sequences = self.folder / 'anims_pilot_medium'
        self.sequences.mkdir()
        self.idle = self.sequences / 'idle.cast'
        self.walk = self.sequences / 'walk.cast'
        animation_file(self.cast, self.idle)
        animation_file(self.cast, self.walk, names=('walk', 'run'))
        self.rig = make_rig()

    def scan(self, force=False):
        reads = []
        original = cast_index.iter_cast

        def counted(path):
            reads.append(Path(path).resolve())
            return original(path)

        started = time.perf_counter()
        scan = animations.LibraryScan(self.rig, str(self.rig_path), force=force)
        try:
            with patch.object(cast_index, 'iter_cast', side_effect=counted):
                while not scan.step():
                    pass
                scan.commit(self.rig)
        finally:
            scan.close()
        return scan, Counter(reads), time.perf_counter() - started

    def test_first_scan_parses_exports_and_cached_relink_only_parses_rig(self):
        first, reads, _ = self.scan()
        self.assertEqual(reads, Counter({self.rig_path: 1, self.idle: 1, self.walk: 1}))
        self.assertEqual(first.cache_hits, 0)
        expected = [(entry.name, entry.offset, entry.guid, entry.sequence_hash) for entry in first.entries]
        second, reads, _ = self.scan()
        self.assertEqual(reads, Counter({self.rig_path: 1}))
        self.assertEqual(second.cache_hits, 2)
        self.assertEqual([(entry.name, entry.offset, entry.guid, entry.sequence_hash)
                          for entry in second.entries], expected)
        self.assertIn('saved index for 2 unchanged', self.rig.apex_animation_library.summary)

    def test_only_changed_export_is_reparsed(self):
        self.scan()
        animation_file(self.cast, self.idle, names=('updated_idle', 'updated_emote'))
        scan, reads, _ = self.scan()
        self.assertEqual(reads, Counter({self.rig_path: 1, self.idle: 1}))
        self.assertEqual(scan.cache_hits, 1)
        self.assertEqual({entry.name for entry in scan.entries},
                         {'updated_idle', 'updated_emote', 'walk', 'run'})
        _, reads, _ = self.scan()
        self.assertEqual(reads, Counter({self.rig_path: 1}))

    def test_added_nested_exports_and_deleted_exports_update_library(self):
        self.scan()
        self.walk.unlink()
        nested = self.sequences / 'nested'
        nested.mkdir()
        crouch = nested / 'crouch.cast'
        animation_file(self.cast, crouch, names=('crouch',))
        scan, reads, _ = self.scan()
        self.assertEqual(reads, Counter({self.rig_path: 1, crouch: 1}))
        self.assertEqual(scan.cache_hits, 1)
        self.assertEqual({item.name for item in self.rig.apex_animation_library.clips}, {'idle', 'crouch'})
        # The persisted index also drops the deleted file.
        index = animations.animation_cache.Index(self.rig_path, self.cache_root)
        self.assertEqual(len(index._known), 2)

    def test_force_scan_and_refresh_operator_reparse_all_exports(self):
        self.scan()
        forced, reads, _ = self.scan(force=True)
        expected = Counter({self.rig_path: 1, self.idle: 1, self.walk: 1})
        self.assertEqual(reads, expected)
        self.assertEqual(forced.cache_hits, 0)
        original = cast_index.iter_cast
        reads = []

        def counted(path):
            reads.append(Path(path).resolve())
            return original(path)

        with patch.object(cast_index, 'iter_cast', side_effect=counted):
            self.assertEqual(bpy.ops.object.apex_refresh_animations(), {'FINISHED'})
        self.assertEqual(Counter(reads), expected)

    def test_warnings_for_bad_exports_survive_cached_scan(self):
        bad = self.sequences / 'broken.cast'
        bad.write_bytes(b'broken export')
        first, reads, _ = self.scan()
        self.assertIn(bad, reads)
        self.assertEqual(len(first.warnings), 1)
        second, reads, _ = self.scan()
        self.assertEqual(reads, Counter({self.rig_path: 1}))
        self.assertEqual(second.cache_hits, 3)
        self.assertEqual(second.warnings, first.warnings)
        self.assertIn('warning', self.rig.apex_animation_library.summary)

    def test_cancelled_scan_preserves_completed_index_and_library(self):
        self.scan()
        library = self.rig.apex_animation_library
        previous = [(clip.filepath, clip.offset, clip.name) for clip in library.clips]
        before = {path.name: path.read_bytes() for path in self.cache_root.glob('*.json')}
        animation_file(self.cast, self.idle, names=('new_idle',))
        scan = animations.LibraryScan(self.rig, str(self.rig_path), force=True)
        with patch.object(animations.animation_cache.Index, 'finish', autospec=True) as finish:
            for _ in range(10000):
                if scan.entries:
                    break
                self.assertFalse(scan.step(0))
            else:
                self.fail('Fixture never reached its first animation.')
            scan.close()
            finish.assert_not_called()
        self.assertTrue(scan.cancelled)
        with self.assertRaisesRegex(ValueError, 'Finish indexing'):
            scan.commit(self.rig)
        self.assertEqual([(clip.filepath, clip.offset, clip.name) for clip in library.clips], previous)
        self.assertEqual({path.name: path.read_bytes() for path in self.cache_root.glob('*.json')}, before)

    def test_saved_favourites_custom_names_recent_and_selection_survive_cached_relink(self):
        self.scan()
        library = self.rig.apex_animation_library
        target_index = next(index for index, item in enumerate(library.clips) if item.name == 'run')
        target = library.clips[target_index]
        target.favourite = True
        target.menu_name = 'My saved run'
        target.menu_role = 'Custom role'
        target.menu_source = 'CUSTOM'
        target.recent_order = 1
        library.index = target_index
        library.names_file = str(self.folder / 'custom.locl')
        rig_name = self.rig.name
        blend = self.folder / 'saved-library.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
        bpy.ops.wm.open_mainfile(filepath=str(blend))
        self.rig = bpy.data.objects[rig_name]
        scan, reads, _ = self.scan()
        self.assertEqual(reads, Counter({self.rig_path: 1}))
        self.assertEqual(scan.cache_hits, 2)
        library = self.rig.apex_animation_library
        target = next(item for item in library.clips if item.name == 'run')
        self.assertTrue(target.favourite)
        self.assertEqual((target.menu_name, target.menu_role, target.menu_source, target.recent_order),
                         ('My saved run', 'Custom role', 'CUSTOM', 1))
        self.assertEqual(library.clips[library.index].name, 'run')
        self.assertEqual(library.names_file, str(self.folder / 'custom.locl'))

    def test_cached_index_does_not_bypass_target_rig_validation(self):
        self.scan()
        for bone in self.rig.data.bones:
            bone.name = 'unrelated_' + bone.name
        scan = animations.LibraryScan(self.rig, str(self.rig_path))
        try:
            with patch.object(animations.animation_cache, 'Index') as cache_constructor:
                with self.assertRaisesRegex(ValueError, 'does not match'):
                    while not scan.step():
                        pass
                cache_constructor.assert_not_called()
        finally:
            scan.close()

    def test_rig_changed_after_scan_rejects_commit_and_preserves_library(self):
        self.scan()
        library = self.rig.apex_animation_library
        before = [(item.filepath, item.offset, item.name) for item in library.clips]
        summary = library.summary
        scan = animations.LibraryScan(self.rig, str(self.rig_path))
        try:
            while not scan.step():
                pass
            self.rig_path.write_bytes(self.rig_path.read_bytes() + b'changed')
            with self.assertRaisesRegex(ValueError, 'export changed during indexing'):
                scan.commit(self.rig)
            self.assertEqual([(item.filepath, item.offset, item.name) for item in library.clips], before)
            self.assertEqual(library.summary, summary)
        finally:
            scan.close()

    def test_sequence_changed_after_cached_or_parsed_scan_preserves_library(self):
        for force in (False, True):
            with self.subTest(force=force):
                self.scan(force=True)
                library = self.rig.apex_animation_library
                before = [(item.filepath, item.offset, item.name) for item in library.clips]
                summary = library.summary
                scan = animations.LibraryScan(self.rig, str(self.rig_path), force=force)
                try:
                    while not scan.step():
                        pass
                    self.assertEqual(scan.cache_hits, 0 if force else 2)
                    animation_file(self.cast, self.idle, names=('modified_idle_%s' % force,))
                    with self.assertRaisesRegex(ValueError, 'export changed during indexing'):
                        scan.commit(self.rig)
                    self.assertEqual([(item.filepath, item.offset, item.name) for item in library.clips], before)
                    self.assertEqual(library.summary, summary)
                finally:
                    scan.close()

    def test_same_offset_different_clip_rejects_load_without_scene_changes(self):
        self.scan()
        library = self.rig.apex_animation_library
        item = next(item for item in library.clips if item.name == 'idle')
        previous = bpy.data.actions.new('Previous action')
        self.rig.animation_data_create()
        self.rig.animation_data.action = previous
        self.rig.rotation_mode = 'XYZ'
        self.rig.rotation_euler = (0.2, 0.4, 0.6)
        self.rig.pose.bones['root'].rotation_mode = 'XYZ'
        self.rig.pose.bones['root'].rotation_euler = (0.3, 0.1, 0.2)
        self.rig.pose.bones['child'].location = (0.2, 0.3, 0.4)
        scene = bpy.context.scene
        scene.frame_start, scene.frame_end = 3, 91
        scene.render.fps, scene.render.fps_base = 24, 1.0
        scene.frame_set(7, subframe=0.5)
        bpy.context.view_layer.update()
        poses = {bone.name: (bone.rotation_mode, bone.matrix_basis.copy()) for bone in self.rig.pose.bones}
        transform = self.rig.matrix_world.copy()
        timing = (scene.frame_start, scene.frame_end, scene.frame_current, scene.frame_subframe,
                  scene.render.fps, scene.render.fps_base)
        actions = set(bpy.data.actions)
        original_offset = item.offset
        animation_file(self.cast, self.idle, names=('wave',))
        changed = cast_index.nodes_of(cast_index.read_cast(self.idle), b'anim')[0]
        self.assertEqual(changed.offset, original_offset)
        self.assertNotEqual(changed.properties['n'], item.name)
        with self.assertRaisesRegex(ValueError, 'export changed'):
            animations.load_clip(bpy.context, self.rig, item)
        self.assertEqual(self.rig.animation_data.action, previous)
        self.assertEqual(set(bpy.data.actions), actions)
        self.assertEqual(self.rig.matrix_world, transform)
        self.assertEqual({bone.name: (bone.rotation_mode, bone.matrix_basis.copy())
                          for bone in self.rig.pose.bones}, poses)
        self.assertEqual((scene.frame_start, scene.frame_end, scene.frame_current, scene.frame_subframe,
                          scene.render.fps, scene.render.fps_base), timing)
        self.assertEqual(bpy.context.active_object, self.rig)
        self.assertEqual(list(bpy.context.selected_objects), [self.rig])
        self.assertEqual(item.name, 'idle')
        self.assertEqual(item.recent_order, 0)

    def test_explicit_reimport_of_renamed_reidentified_clip_updates_existing_item(self):
        self.scan()
        library = self.rig.apex_animation_library
        original = next(item for item in library.clips if item.name == 'idle')
        original_offset, original_guid = original.offset, original.guid
        count = len(library.clips)
        animation_file(self.cast, self.idle, names=('wave',))
        node = cast_index.nodes_of(cast_index.read_cast(self.idle), b'anim')[0]
        expected = animations.clip_from_node(self.idle, node)
        self.assertEqual(node.offset, original_offset)
        self.assertNotEqual(expected.guid, original_guid)
        item, missing = animations.import_single_clip(bpy.context, self.rig, str(self.idle))
        self.assertEqual(item, original)
        self.assertEqual(len(library.clips), count)
        self.assertEqual((item.name, item.guid, item.sequence_hash),
                         (expected.name, expected.guid, expected.sequence_hash))
        self.assertEqual(missing, 0)
        self.assertEqual(self.rig.animation_data.action.name, 'wave')
        self.assertEqual(item.action, self.rig.animation_data.action)
        self.assertEqual(library.clips[library.index], item)

    def test_failed_explicit_reimport_keeps_existing_metadata_and_action(self):
        self.scan()
        item, _ = animations.import_single_clip(bpy.context, self.rig, str(self.idle))
        item.favourite = True
        item.menu_name, item.menu_role, item.menu_source = 'Custom idle', 'My role', 'CUSTOM'
        attributes = ('name', 'filepath', 'offset', 'fps', 'additive', 'guid', 'sequence_hash',
                      'external', 'action', 'stamp', 'favourite', 'menu_name', 'menu_role',
                      'menu_source', 'recent_order')
        before = tuple(getattr(item, name) for name in attributes)
        action = self.rig.animation_data.action
        actions = set(bpy.data.actions)
        animation_file(self.cast, self.idle, names=('wave',))
        importer, _, _ = workflows.cast_modules()
        with patch.object(importer, 'importAnimationNode', side_effect=RuntimeError('fixture import failed')):
            with self.assertRaisesRegex(RuntimeError, 'fixture import failed'):
                animations.import_single_clip(bpy.context, self.rig, str(self.idle))
        self.assertEqual(tuple(getattr(item, name) for name in attributes), before)
        self.assertEqual(self.rig.animation_data.action, action)
        self.assertEqual(set(bpy.data.actions), actions)
        self.assertEqual(len(self.rig.apex_animation_library.clips), 3)

    def test_same_size_and_mtime_atomic_replacement_invalidates_cached_action(self):
        self.scan()
        item = next(item for item in self.rig.apex_animation_library.clips if item.name == 'idle')
        animations.load_clip(bpy.context, self.rig, item)
        previous = self.rig.animation_data.action
        scene = bpy.context.scene
        scene.frame_set(10)
        self.assertAlmostEqual(self.rig.pose.bones['root'].location.x, 2.0, places=4)
        info = self.idle.stat()
        content = self.idle.read_bytes()
        original_values = struct.pack('<ff', 0.0, 2.0)
        self.assertEqual(content.count(original_values), 1)
        changed = content.replace(original_values, struct.pack('<ff', 0.0, 7.0))
        replacement = self.idle.with_suffix('.replacement')
        replacement.write_bytes(changed)
        os.utime(replacement, ns=(info.st_atime_ns, info.st_mtime_ns))
        os.replace(replacement, self.idle)
        self.assertEqual(self.idle.stat().st_size, info.st_size)
        self.assertEqual(self.idle.stat().st_mtime_ns, info.st_mtime_ns)
        # Name, identifiers and offset are unchanged; only source identity and
        # a curve value differ. Reusing the earlier Action would keep x == 2.
        animations.load_clip(bpy.context, self.rig, item)
        self.assertNotEqual(self.rig.animation_data.action, previous)
        self.assertTrue(previous.use_fake_user)
        scene.frame_set(10)
        self.assertAlmostEqual(self.rig.pose.bones['root'].location.x, 7.0, places=4)

    def test_many_files_relink_skips_cast_parsing(self):
        for index in range(500):
            animation_file(self.cast, self.sequences / ('clip_%04d.cast' % index),
                           names=('lobby_clip_%04d' % index,))
        first, first_reads, first_seconds = self.scan()
        second, second_reads, second_seconds = self.scan()
        self.assertEqual(sum(first_reads.values()), 503)
        self.assertEqual(second_reads, Counter({self.rig_path: 1}))
        self.assertEqual(second.cache_hits, 502)
        self.assertEqual(len(first.entries), 503)
        self.assertEqual(len(second.entries), 503)
        print('INDEX BENCHMARK: 502 sequence files; first %.4fs, repeat %.4fs; '
              'repeat skipped 502 CAST parses' % (first_seconds, second_seconds), flush=True)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(AnimationIndexScanTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
