"""Read-only CAST preflight and batch placement with real Blender datablocks.

Run in factory-startup Blender; append -- --release for the packaged add-on.
All export fixtures and scene objects are disposable.
"""
from pathlib import Path
import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import addon_utils
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from workflow_integration import (addon, workflows, model_file, animation_file,
                                  make_rig, select, assert_matrix_close)
from Apex_toolbox.apex_tex import import_plan


class ImportPlanTests(unittest.TestCase):
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
        for name in ('materials', 'actions', 'images'):
            for item in list(getattr(bpy.data, name)):
                getattr(bpy.data, name).remove(item, do_unlink=True)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        # Operator checks must not search the host's remembered export roots.
        for owner, name, value in ((addon.apex_autotex, 'browsed_directories', []),
                                   (addon, 'remembered_texture_roots', []),
                                   (addon, 'store_texture_roots', None)):
            replacement = patch.object(owner, name, return_value=value)
            replacement.start()
            self.addCleanup(replacement.stop)
        bpy.context.scene.my_prefs.autotex_folder = ''

    def model(self, folder='model', name='model_LOD0.cast', mesh=True):
        directory = self.folder / folder
        directory.mkdir(exist_ok=True, parents=True)
        path = directory / name
        model_file(self.cast, path, mesh=mesh)
        return path

    def edit(self, path, edit):
        doc = self.cast.Cast.load(str(path))
        edit(doc.Roots()[0].ChildrenOfType(self.cast.Model)[0])
        doc.save(str(path))

    def group(self, name, size=(1, 1, 2), location=(0, 0, 0), scale=(1, 1, 1)):
        rig = make_rig()
        rig.name = name + '_rig'
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata([(x, y, z) for x in (0, size[0])
                          for y in (0, size[1]) for z in (0, size[2])], [], [])
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.parent = rig
        rig.location = location
        rig.scale = scale
        for item in (rig, obj):
            item['apex_source_model'] = str(self.folder / name / (name + '_LOD0.cast'))
        bpy.context.view_layer.update()
        return [rig, obj]

    def test_folder_picks_one_lod0_and_deduplicates_files(self):
        first = self.model('alpha', 'alpha_LOD0.cast')
        self.model('alpha', 'alpha_LOD1.cast')
        second = self.model('beta', 'beta.cast')
        result = import_plan.inspect(folders=[first.parent, second.parent], files=[first])
        self.assertEqual(result.paths, [str(first.resolve()), str(second.resolve())])
        self.assertEqual(result.model_count, 2)
        self.assertFalse(result.issues)
        self.assertIn('2 models ready', result.summary)

    def test_parent_is_one_level_and_skips_animation_subfolders(self):
        model = self.model('mdl/alpha', 'alpha.cast')
        self.model('mdl/anims_alpha', 'idle.cast', mesh=False)
        result = import_plan.inspect(folders=[self.folder / 'mdl'])
        self.assertEqual(result.paths, [str(model.resolve())])
        self.assertFalse(result.issues)

    def test_ambiguous_folder_does_not_discard_valid_sibling(self):
        valid = self.model('mdl/valid', 'valid.cast')
        self.model('mdl/ambiguous', 'a.cast')
        self.model('mdl/ambiguous', 'b.cast')
        result = import_plan.inspect(folders=[self.folder / 'mdl'])
        self.assertEqual(result.paths, [str(valid.resolve())])
        self.assertEqual(len(result.issues), 1)
        self.assertIn('ambiguous', result.issues[0])
        self.assertIn('unique LOD0', result.issues[0])

    def test_missing_empty_and_animation_only_sources_are_reported(self):
        empty = self.folder / 'empty'
        empty.mkdir()
        sequence = self.folder / 'anims_pilot'
        sequence.mkdir()
        rig = self.model('rig', 'pilot.cast', mesh=False)
        animation = self.folder / 'idle.cast'
        animation_file(self.cast, animation)
        result = import_plan.inspect(folders=[empty, sequence, self.folder / 'absent'],
                                     files=[rig, animation])
        self.assertEqual(result.paths, [])
        self.assertEqual(len(result.issues), 5)
        for name in ('empty', 'anims_pilot', 'absent', 'pilot.cast', 'idle.cast'):
            self.assertTrue(any(name in issue for issue in result.issues), name)

    def test_invalid_and_wrong_file_types_keep_valid_files(self):
        valid = self.model()
        corrupt = self.folder / 'bad.cast'
        corrupt.write_bytes(b'cast')
        wrong = self.folder / 'picture.png'
        wrong.touch()
        result = import_plan.inspect(files=[corrupt, valid, wrong, self.folder / 'missing.cast'])
        self.assertEqual(result.paths, [str(valid.resolve())])
        self.assertEqual(len(result.issues), 3)
        self.assertTrue(any('bad.cast' in item and 'Truncated' in item for item in result.issues))

    def test_model_with_animation_is_rejected_before_import(self):
        path = self.model()
        document = self.cast.Cast.load(str(path))
        document.Roots()[0].CreateAnimation().SetName('embedded')
        document.save(str(path))
        result = import_plan.inspect(files=[path])
        self.assertEqual(result.paths, [])
        self.assertIn('model-only', result.issues[0])

    def test_static_mesh_without_skeleton_remains_valid(self):
        path = self.model()
        self.edit(path, lambda model: setattr(model, 'childNodes', [node for node in model.childNodes
                                                                  if not isinstance(node, self.cast.Skeleton)]))
        result = import_plan.inspect(files=[path])
        self.assertEqual(result.paths, [str(path.resolve())])
        self.assertFalse(result.issues)

    def test_empty_skeleton_does_not_reject_static_props(self):
        path = self.model()
        self.edit(path, lambda model: setattr(model.ChildrenOfType(self.cast.Skeleton)[0],
                                              'childNodes', []))
        result = import_plan.inspect(files=[path])
        self.assertEqual(result.paths, [str(path.resolve())])
        self.assertFalse(result.issues)

    def test_over_fifty_models_blocks_the_whole_batch(self):
        paths = [self.model('many', '%02d.cast' % index) for index in range(51)]
        result = import_plan.inspect(files=paths)
        self.assertTrue(result.too_many)
        self.assertEqual(result.paths, [])
        self.assertIn('More than 50', result.issues[-1])

    def test_exactly_fifty_models_is_valid(self):
        paths = [self.model('many', '%02d.cast' % index) for index in range(50)]
        result = import_plan.inspect(files=paths)
        self.assertFalse(result.too_many)
        self.assertEqual(result.model_count, 50)

    def test_empty_selection_has_clear_issue(self):
        result = import_plan.inspect()
        self.assertEqual(result.model_count, 0)
        self.assertIn('Choose at least one', result.issues[0])

    def test_missing_texture_is_warning_and_preserves_model(self):
        path = self.model()
        result = import_plan.inspect(files=[path])
        self.assertEqual(result.paths, [str(path.resolve())])
        self.assertFalse(result.issues)
        self.assertEqual(len(result.texture_warnings), 1)
        self.assertIn('1 referenced texture', result.texture_warnings[0])

    def test_texture_hint_accepts_other_format_and_nested_relative_path(self):
        path = self.model()
        (path.parent / 'test_body_col.dds').touch()
        self.assertFalse(import_plan.inspect(files=[path]).texture_warnings)
        (path.parent / 'test_body_col.dds').unlink()
        texture = path.parent / 'nested/deeper/test_body_col.png'
        texture.parent.mkdir(parents=True)
        texture.touch()
        self.edit(path, lambda model: model.Materials()[0].ChildrenOfType(self.cast.File)[0].SetPath(
            'nested\\deeper\\test_body_col.png'))
        self.assertFalse(import_plan.inspect(files=[path]).texture_warnings)

    def test_manual_texture_folder_is_a_quick_hint(self):
        path = self.model()
        manual = self.folder / 'textures'
        manual.mkdir()
        (manual / 'test_body_col.tga').touch()
        result = import_plan.inspect(files=[path], texture_folder=str(manual))
        self.assertFalse(result.texture_warnings)

    def test_texture_check_failure_is_only_a_warning(self):
        path = self.model()
        with patch.object(import_plan, '_texture_hints', side_effect=OSError('unavailable texture folder')):
            result = import_plan.inspect(files=[path])
        self.assertEqual(result.paths, [str(path.resolve())])
        self.assertFalse(result.issues)
        self.assertEqual(len(result.texture_warnings), 1)
        self.assertIn('model can still be imported', result.texture_warnings[0])

    def test_checked_models_have_json_safe_content_fingerprints(self):
        path = self.model()
        result = import_plan.inspect(files=[path])
        fingerprint = result.fingerprints[str(path.resolve())]
        self.assertEqual(fingerprint[-1], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(fingerprint[0], path.stat().st_size)
        self.assertEqual(json.loads(json.dumps(result.fingerprints)), result.fingerprints)
        self.assertEqual(import_plan.source_fingerprint(path), fingerprint)

    def test_valid_same_path_replacement_changes_content_fingerprint(self):
        path = self.model()
        before = path.stat()
        first = import_plan.inspect(files=[path])
        replacement = path.read_bytes().replace(b'test_legend', b'other_model')
        self.assertNotEqual(replacement, path.read_bytes())
        path.write_bytes(replacement)
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        second = import_plan.inspect(files=[path])
        self.assertEqual(first.paths, second.paths)
        self.assertFalse(second.issues)
        self.assertEqual(first.fingerprints[str(path.resolve())][:2],
                         second.fingerprints[str(path.resolve())][:2])
        self.assertNotEqual(first.fingerprints[str(path.resolve())][-1],
                            second.fingerprints[str(path.resolve())][-1])

    def test_model_buffer_change_is_detected_with_unchanged_stat_metadata(self):
        path = self.model()
        original_stamp = import_plan._stat_stamp(path)
        with patch.object(import_plan, '_stat_stamp', return_value=original_stamp):
            first = import_plan.inspect(files=[path])
            self.edit(path, lambda model: model.Meshes()[0].SetVertexPositionBuffer(
                [(0, 0, 0), (2, 0, 0), (0, 0, 1)]))
            second = import_plan.inspect(files=[path])
        self.assertEqual(first.paths, second.paths)
        self.assertFalse(second.issues)
        self.assertNotEqual(first.fingerprints, second.fingerprints)

    def test_source_changed_during_metadata_check_is_not_accepted(self):
        path = self.model()
        read_cast = import_plan.cast_index.read_cast
        def changing(source):
            document = read_cast(source)
            replacement = path.read_bytes().replace(b'test_legend', b'other_model')
            path.write_bytes(replacement)
            return document
        with patch.object(import_plan.cast_index, 'read_cast', changing):
            result = import_plan.inspect(files=[path])
        self.assertEqual(result.paths, [])
        self.assertEqual(result.fingerprints, {})
        self.assertIn('changed while checking', result.issues[0])

    def test_source_changed_during_sample_is_not_accepted(self):
        path = self.model()
        sample_digest = import_plan._sample_digest
        def changing(source, size):
            digest = sample_digest(source, size)
            replacement = path.read_bytes().replace(b'test_legend', b'other_model')
            path.write_bytes(replacement)
            return digest
        with patch.object(import_plan, '_sample_digest', changing):
            result = import_plan.inspect(files=[path])
        self.assertEqual(result.paths, [])
        self.assertEqual(result.fingerprints, {})
        self.assertIn('changed while checking', result.issues[0])

    def test_content_sample_has_a_fixed_read_budget(self):
        class Source:
            def __init__(self):
                self.read_sizes = []
                self.seeks = []
            def read(self, size):
                self.read_sizes.append(size)
                return b'a' * size
            def seek(self, offset):
                self.seeks.append(offset)
        source = Source()
        large_size = 4 * 1024 ** 3
        import_plan._sample_digest(source, large_size)
        self.assertEqual(sum(source.read_sizes), 128 * 1024)
        self.assertEqual(source.seeks, [large_size - 64 * 1024])

    def test_review_operator_rejects_valid_replacement_without_scene_changes(self):
        path = self.model()
        plan = import_plan.inspect(files=[path])
        existing = self.group('existing', location=(10, 3, 4))
        select(existing[0])
        before = {name: set(getattr(bpy.data, name)) for name in
                  ('objects', 'meshes', 'armatures', 'materials', 'actions', 'collections')}
        matrices = [obj.matrix_world.copy() for obj in existing]
        self.edit(path, lambda model: model.Meshes()[0].SetVertexPositionBuffer(
            [(0, 0, 0), (2, 0, 0), (0, 0, 1)]))
        self.assertEqual(import_plan.inspect(files=[path]).paths, plan.paths)
        result = bpy.ops.object.apex_review_model_import(
            'EXEC_DEFAULT', files=[{'name': source} for source in plan.paths],
            fingerprints_json=json.dumps(plan.fingerprints), summary=plan.summary,
            auto_link=False, placement='GRID', separate_collections=True)
        self.assertEqual(result, {'CANCELLED'})
        for name, values in before.items():
            self.assertEqual(set(getattr(bpy.data, name)), values, name)
        self.assertEqual(bpy.context.active_object, existing[0])
        self.assertEqual(list(bpy.context.selected_objects), [existing[0]])
        for obj, matrix in zip(existing, matrices):
            assert_matrix_close(self, obj.matrix_world, matrix)

    def test_review_operator_imports_grid_collections_and_records_skipped_sources(self):
        paths = [self.model('model%d' % index, 'model%d.cast' % index) for index in range(5)]
        for index, path in enumerate(paths):
            self.edit(path, lambda model, width=index + 1: model.Meshes()[0].SetVertexPositionBuffer(
                [(0, 0, 0), (width, 0, 0), (0, 0, 1)]))
        invalid = self.folder / 'broken.cast'
        invalid.write_bytes(b'cast')
        image = bpy.data.images.new('test_body_col', width=8, height=8)
        image.filepath_raw = str(self.folder / 'test_body_col.png')
        image.file_format = 'PNG'
        image.save()
        bpy.data.images.remove(image)
        texture_bytes = (self.folder / 'test_body_col.png').read_bytes()
        for path in paths:
            (path.parent / 'test_body_col.png').write_bytes(texture_bytes)
        plan = import_plan.inspect(files=paths + [invalid], texture_folder=str(self.folder))
        self.assertEqual(plan.model_count, 5)
        self.assertEqual(len(plan.issues), 1)
        existing = self.group('existing', location=(100, 30, 40))
        existing_empty = bpy.data.collections.new('test_legend')
        bpy.context.scene.collection.children.link(existing_empty)
        before_collections = set(bpy.data.collections)
        matrices = [obj.matrix_world.copy() for obj in existing]
        result = bpy.ops.object.apex_review_model_import(
            'EXEC_DEFAULT', files=[{'name': source} for source in plan.paths],
            issues=[{'name': issue} for issue in plan.issues],
            fingerprints_json=json.dumps(plan.fingerprints), summary=plan.summary,
            auto_link=False, prepare=False, placement='GRID', columns=2, gap=0.75,
            separate_collections=True, texture_folder=str(self.folder))
        self.assertEqual(result, {'FINISHED'})
        groups = {}
        for obj in bpy.context.selected_objects:
            groups.setdefault(obj['apex_source_model'], []).append(obj)
        self.assertEqual(set(groups), set(plan.paths))
        ordered = [groups[str(path.resolve())] for path in paths]
        bounds = [workflows.model_bounds(group) for group in ordered]
        for index, (low, high) in enumerate(bounds):
            for other_low, other_high in bounds[index + 1:]:
                apart_x = (other_low.x - high.x >= 0.75 - 1e-5
                           or low.x - other_high.x >= 0.75 - 1e-5)
                apart_y = (other_low.y - high.y >= 0.75 - 1e-5
                           or low.y - other_high.y >= 0.75 - 1e-5)
                self.assertTrue(apart_x or apart_y)
        collections = set()
        for group in ordered:
            self.assertEqual(len(group[0].users_collection), 1)
            collection = group[0].users_collection[0]
            self.assertEqual(set(collection.objects), set(group))
            self.assertTrue(all(list(obj.users_collection) == [collection] for obj in group))
            collections.add(collection)
        self.assertEqual(len(collections), 5)
        self.assertEqual(set(bpy.data.collections) - before_collections, collections)
        self.assertEqual(bpy.data.collections.get(existing_empty.name), existing_empty)
        for obj, matrix in zip(existing, matrices):
            assert_matrix_close(self, obj.matrix_world, matrix)
        prefs = bpy.context.scene.my_prefs
        self.assertEqual(prefs.import_placement, 'GRID')
        self.assertEqual(prefs.import_columns, 2)
        self.assertAlmostEqual(prefs.import_gap, 0.75)
        self.assertTrue(prefs.import_collections)
        self.assertIn('Imported 5 models in a grid', prefs.import_summary)
        self.assertIn('1 issue skipped before import', prefs.import_summary)
        self.assertIn('broken.cast', prefs.texture_report.as_string())

    def test_preflight_never_creates_or_changes_blender_data(self):
        path = self.model()
        group = self.group('existing')
        select(group[0])
        before = {name: set(getattr(bpy.data, name)) for name in
                  ('objects', 'meshes', 'armatures', 'materials', 'collections')}
        active = bpy.context.active_object
        matrices = [obj.matrix_world.copy() for obj in group]
        import_plan.inspect(files=[path])
        for name, values in before.items():
            self.assertEqual(set(getattr(bpy.data, name)), values)
        self.assertEqual(bpy.context.active_object, active)
        self.assertEqual(list(bpy.context.selected_objects), [group[0]])
        for obj, matrix in zip(group, matrices):
            assert_matrix_close(self, obj.matrix_world, matrix)

    def test_row_preserves_first_model_and_existing_objects_with_minimum_gap(self):
        existing = self.group('existing', location=(40, 20, 10))
        groups = [self.group('a', location=(10, 4, 3)),
                  self.group('b', size=(3, 4, 2), scale=(2, 0.5, 3)),
                  self.group('c', size=(0.25, 0.5, 1), location=(-10, 12, -2))]
        originals = [obj.matrix_world.copy() for obj in existing + groups[0]]
        select(existing[0])
        self.assertEqual(import_plan.arrange(bpy.context, groups, gap=2.0), [])
        bounds = [workflows.model_bounds(group) for group in groups]
        for (_, high), (low, _) in zip(bounds, bounds[1:]):
            self.assertGreaterEqual(low.x - high.x, 2.0 - 1e-5)
        for low, high in bounds[1:]:
            self.assertAlmostEqual((low.y + high.y) / 2, (bounds[0][0].y + bounds[0][1].y) / 2)
            self.assertAlmostEqual(low.z, bounds[0][0].z)
        for obj, matrix in zip(existing + groups[0], originals):
            assert_matrix_close(self, obj.matrix_world, matrix)
        self.assertEqual(bpy.context.active_object, existing[0])
        self.assertEqual(list(bpy.context.selected_objects), [existing[0]])

    def test_grid_uses_largest_cell_sizes_with_no_overlaps(self):
        groups = [self.group('model%d' % index, size=size, location=(index, -index, index),
                             scale=scale) for index, (size, scale) in enumerate([
                                 ((1, 1, 2), (1, 1, 1)),
                                 ((5, 2, 3), (1, 2, 0.5)),
                                 ((0.5, 8, 1), (2, 1, 1)),
                                 ((4, 3, 4), (2, 1, 2)),
                                 ((1, 1, 1), (1, 1, 1))])]
        first = [obj.matrix_world.copy() for obj in groups[0]]
        local = [group[1].matrix_local.copy() for group in groups]
        import_plan.arrange(bpy.context, groups, layout='GRID', columns=2, gap=1.5)
        bounds = [workflows.model_bounds(group) for group in groups]
        for index, (low, high) in enumerate(bounds):
            for other_low, other_high in bounds[index + 1:]:
                apart_x = (other_low.x - high.x >= 1.5 - 1e-5
                           or low.x - other_high.x >= 1.5 - 1e-5)
                apart_y = (other_low.y - high.y >= 1.5 - 1e-5
                           or low.y - other_high.y >= 1.5 - 1e-5)
                self.assertTrue(apart_x or apart_y, (index, low, high, other_low, other_high))
            self.assertAlmostEqual(low.z, bounds[0][0].z)
        for obj, matrix in zip(groups[0], first):
            assert_matrix_close(self, obj.matrix_world, matrix)
        for group, matrix in zip(groups, local):
            self.assertEqual(group[1].parent, group[0])
            assert_matrix_close(self, group[1].matrix_local, matrix)
        self.assertAlmostEqual(bounds[0][0].x, bounds[2][0].x)
        self.assertAlmostEqual(bounds[0][0].x, bounds[4][0].x)

    def test_original_positions_can_still_create_separate_collections(self):
        groups = [self.group('same', location=(index * 5, 3, 2)) for index in range(2)]
        originals = [obj.matrix_world.copy() for group in groups for obj in group]
        collections = import_plan.arrange(bpy.context, groups, layout='NONE', separate_collections=True)
        self.assertEqual(len(collections), 2)
        self.assertNotEqual(collections[0].name, collections[1].name)
        self.assertTrue(collections[0].name.startswith('same'))
        for group, collection in zip(groups, collections):
            self.assertEqual(set(collection.objects), set(group))
            self.assertIn(collection.name, bpy.context.scene.collection.children)
            for obj in group:
                self.assertEqual(list(obj.users_collection), [collection])
        for obj, matrix in zip([obj for group in groups for obj in group], originals):
            assert_matrix_close(self, obj.matrix_world, matrix)

    def test_collection_creation_does_not_relink_existing_objects(self):
        existing = self.group('old')
        before = [list(obj.users_collection) for obj in existing]
        new = self.group('new')
        import_plan.arrange(bpy.context, [new], separate_collections=True)
        for obj, collections in zip(existing, before):
            self.assertEqual(list(obj.users_collection), collections)

    def test_grouping_removes_only_empty_import_collections(self):
        existing_empty = bpy.data.collections.new('existing_empty')
        bpy.context.scene.collection.children.link(existing_empty)
        groups = [self.group('first'), self.group('second')]
        importer_collections = []
        importer_names = []
        for group in groups:
            collection = bpy.data.collections.new('Cast Model')
            bpy.context.scene.collection.children.link(collection)
            for obj in group:
                collection.objects.link(obj)
            importer_collections.append(collection)
            importer_names.append(collection.name)
        created = import_plan.arrange(bpy.context, groups, separate_collections=True,
                                     import_collections=importer_collections)
        self.assertEqual(len(created), 2)
        self.assertTrue(all(name not in bpy.data.collections for name in importer_names))
        self.assertEqual(bpy.data.collections.get(existing_empty.name), existing_empty)
        self.assertTrue(all(set(collection.objects) == set(group)
                            for collection, group in zip(created, groups)))

    def test_import_collection_cleanup_keeps_objects_and_unlisted_children(self):
        parent = bpy.data.collections.new('imported_parent')
        child = bpy.data.collections.new('existing_child')
        parent.children.link(child)
        bpy.context.scene.collection.children.link(parent)
        populated = bpy.data.collections.new('imported_populated')
        bpy.context.scene.collection.children.link(populated)
        old = self.group('old')
        populated.objects.link(old[0])
        new = self.group('new')
        import_plan.arrange(bpy.context, [new], separate_collections=True,
                            import_collections=[parent, populated])
        self.assertEqual(bpy.data.collections.get(parent.name), parent)
        self.assertEqual(bpy.data.collections.get(child.name), child)
        self.assertEqual(bpy.data.collections.get(populated.name), populated)
        self.assertIn(old[0].name, populated.objects)

    def test_import_collection_cleanup_handles_nested_containers(self):
        parent = bpy.data.collections.new('imported_parent')
        child = bpy.data.collections.new('imported_child')
        parent.children.link(child)
        bpy.context.scene.collection.children.link(parent)
        names = (parent.name, child.name)
        group = self.group('new')
        child.objects.link(group[0])
        import_plan.arrange(bpy.context, [group], separate_collections=True,
                            import_collections=[parent, child])
        self.assertTrue(all(name not in bpy.data.collections for name in names))

    def test_import_collection_cleanup_is_opt_in_with_grouping(self):
        empty = bpy.data.collections.new('imported_empty')
        bpy.context.scene.collection.children.link(empty)
        group = self.group('new')
        import_plan.arrange(bpy.context, [group], separate_collections=False,
                            import_collections=[empty])
        self.assertEqual(bpy.data.collections.get(empty.name), empty)

    def test_invalid_layout_options_fail_before_moving_models(self):
        groups = [self.group('first'), self.group('second')]
        matrices = [obj.matrix_world.copy() for group in groups for obj in group]
        for arguments in ({'layout': 'UNKNOWN'}, {'gap': -1}, {'gap': float('nan')}, {'columns': 0}):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                import_plan.arrange(bpy.context, groups, **arguments)
        for obj, matrix in zip([obj for group in groups for obj in group], matrices):
            assert_matrix_close(self, obj.matrix_world, matrix)

    def test_directory_check_is_bounded(self):
        self.model('many', 'a.cast')
        self.model('many', 'b.cast')
        with patch.object(import_plan, 'MAX_FOLDER_ENTRIES', 1):
            result = import_plan.inspect(folders=[self.folder / 'many'])
        self.assertEqual(result.paths, [])
        self.assertIn('too many entries', result.issues[0])


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ImportPlanTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
