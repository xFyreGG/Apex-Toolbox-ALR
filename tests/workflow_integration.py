"""Real CAST importer tests. Run in a separate factory-startup Blender process.

Requires the user's installed io_scene_cast add-on. No game assets are needed;
fixtures are generated with CAST's own writer in a temporary directory.
"""
import importlib
from pathlib import Path
import sys
import tempfile
import atexit
import zipfile
import unittest
import itertools
import json
from unittest.mock import patch

import addon_utils
import bpy
from mathutils import Euler, Matrix

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
if '--release' in sys.argv:
    sys.path.insert(0, str(ROOT / 'tools'))
    from build_release import release_version
    release_directory = tempfile.TemporaryDirectory()
    atexit.register(release_directory.cleanup)
    version = '.'.join(map(str, release_version()))
    with zipfile.ZipFile(ROOT / 'dist' / ('Apex-Toolbox-ALR-%s.zip' % version)) as archive:
        archive.extractall(release_directory.name)
    sys.path.insert(0, release_directory.name)
import Apex_toolbox as addon
if '--release' in sys.argv:
    assert Path(addon.__file__).is_relative_to(release_directory.name)
from Apex_toolbox.apex_tex import animations, animation_names, cast_index, workflows
from blender_integration import make_rig, make_mesh, select, snapshot, assert_matrix_close


def skeleton(model):
    skel = model.CreateSkeleton()
    for index, name in enumerate(('root', 'child')):
        bone = skel.CreateBone()
        bone.SetName(name)
        bone.SetParentIndex(index - 1)
        bone.SetLocalPosition((0, 0, index))
        bone.SetLocalRotation((0, 0, 0, 1))
        bone.SetScale((1, 1, 1))
    return skel


def model_file(cast, path, mesh=True, width=1.0):
    doc = cast.Cast()
    model = doc.CreateRoot().CreateModel()
    model.SetName('test_legend')
    skeleton(model)
    if mesh:
        material = model.CreateMaterial()
        material.SetName('test_body')
        material.SetType('pbr')
        texture = material.CreateFile()
        texture.SetPath('test_body_col.png')
        material.SetSlot('albedo', texture.Hash())
        part = model.CreateMesh()
        part.SetName('test_body')
        part.SetVertexPositionBuffer([(0, 0, 0), (width, 0, 0), (0, 0, 1)])
        part.SetFaceBuffer([0, 1, 2])
        part.SetUVLayerCount(1)
        part.SetVertexUVLayerBuffer(0, [(0, 0), (1, 0), (0, 1)])
        part.SetMaterial(material.Hash())
        part.SetMaximumWeightInfluence(1)
        part.SetVertexWeightBoneBuffer([0, 0, 1])
        part.SetVertexWeightValueBuffer([1, 1, 1])
    doc.save(str(path))


def animation_file(cast, path, names=('idle',), missing=False, additive=False):
    doc = cast.Cast()
    root = doc.CreateRoot()
    for name in names:
        anim = root.CreateAnimation()
        anim.SetName(name)
        anim.SetFramerate(29.97)
        anim.SetLooping(True)
        for bone_name in (('root', 'absent') if missing else ('root', 'child')):
            curve = anim.CreateCurve()
            curve.SetNodeName(bone_name)
            curve.SetKeyPropertyName('rq')
            curve.SetKeyFrameBuffer([0, 10])
            curve.SetVec4KeyValueBuffer([(0, 0, 0, 1), (0, 0, 0.38268343, 0.92387953)])
            curve.SetMode('additive' if additive else 'relative')
        curve = anim.CreateCurve()
        curve.SetNodeName('root')
        curve.SetKeyPropertyName('tx')
        curve.SetKeyFrameBuffer([0, 10])
        curve.SetFloatKeyValueBuffer([0, 2])
        curve.SetMode('relative')
    doc.save(str(path))


class WorkflowIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        addon_utils.enable('io_scene_cast', default_set=False)
        cls.importer, cls.cast, _ = workflows.cast_modules()
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
        self.model_path = self.folder / 'legend.cast'
        model_file(self.cast, self.model_path)
        self.rig_path = self.folder / 'legend_rig.cast'
        model_file(self.cast, self.rig_path, mesh=False)
        self.anim_folder = self.folder / 'anims_legend_rig'
        self.anim_folder.mkdir()
        animation_file(self.cast, self.anim_folder / 'idle.cast')
        animation_file(self.cast, self.anim_folder / 'walk.cast', names=('walk', 'run'))
        self.rig = make_rig()
        self.bookmarks = patch.object(addon.apex_autotex, 'browsed_directories', return_value=[])
        self.bookmarks.start()
        self.addCleanup(self.bookmarks.stop)

    def image(self):
        image = bpy.data.images.new('test_body_col', width=8, height=8)
        image.filepath_raw = str(self.folder / 'test_body_col.png')
        image.file_format = 'PNG'
        image.save()
        bpy.data.images.remove(image)

    def link(self):
        result = bpy.ops.object.apex_link_animation_rig(filepath=str(self.rig_path))
        self.assertEqual(result, {'FINISHED'})
        return self.rig.apex_animation_library

    def test_import_and_texture_isolates_existing_model_and_material(self):
        self.image()
        existing = make_mesh('existing')
        existing.active_material.name = 'test_body'
        before = snapshot(existing.active_material)
        select(self.rig, existing)
        self.assertEqual(bpy.ops.object.apex_import_texture(filepath=str(self.model_path)), {'FINISHED'})
        self.assertEqual(bpy.context.mode, 'OBJECT')
        self.assertEqual(snapshot(existing.active_material), before)
        self.assertNotIn(existing, bpy.context.selected_objects)
        imported = bpy.context.active_object
        self.assertEqual(imported.type, 'ARMATURE')
        self.assertNotEqual(imported, self.rig)
        self.assertAlmostEqual(imported.scale[0], 0.0254)
        self.assertEqual(imported.rotation_mode, 'XYZ')
        self.assertTrue(all(b.rotation_mode == 'XYZ' for b in imported.pose.bones))
        self.assertIn('1 textured', bpy.context.scene.my_prefs.texture_summary)
        meshes = [o for o in bpy.context.selected_objects if o.type == 'MESH']
        self.assertEqual(len(meshes), 1)
        self.assertIsNot(meshes[0].active_material, existing.active_material)

    def test_failed_import_rolls_back_new_data_and_selection(self):
        before = {name: set(getattr(bpy.data, name)) for name in
                  ('objects', 'meshes', 'armatures', 'materials', 'collections')}
        real = self.importer.importModelNode
        def broken(*args):
            real(*args)
            raise RuntimeError('test interrupted import')
        with patch.object(self.importer, 'importModelNode', broken):
            with self.assertRaisesRegex(RuntimeError, 'interrupted import'):
                workflows.import_model(bpy.context, str(self.model_path))
        for name, data in before.items():
            self.assertEqual(set(getattr(bpy.data, name)), data, name)
        self.assertEqual(bpy.context.active_object, self.rig)
        self.assertEqual(list(bpy.context.selected_objects), [self.rig])

    def test_missing_textures_keep_imported_model(self):
        self.assertEqual(bpy.ops.object.apex_import_texture(filepath=str(self.model_path), prepare=False), {'FINISHED'})
        self.assertEqual(bpy.context.active_object.scale[:], (1, 1, 1))
        self.assertIn('0 textured', bpy.context.scene.my_prefs.texture_summary)
        self.assertTrue(any(o.type == 'MESH' for o in bpy.context.selected_objects))

    def test_batch_import_places_models_side_by_side_without_moving_existing_objects(self):
        self.image()
        existing = make_mesh('existing')
        original_matrix = existing.matrix_world.copy()
        second = self.folder / 'second.cast'
        third = self.folder / 'third.cast'
        model_file(self.cast, second, width=3.0)
        model_file(self.cast, third, width=0.5)
        files = [{'name': name} for name in ('third.cast', 'legend.cast', 'second.cast')]
        self.assertEqual(bpy.ops.object.apex_import_texture(
            directory=str(self.folder), files=files), {'FINISHED'})
        self.assertEqual(existing.matrix_world, original_matrix)
        groups = {}
        for obj in bpy.context.selected_objects:
            groups.setdefault(Path(obj['apex_source_model']).name, []).append(obj)
        self.assertEqual(set(groups), {'legend.cast', 'second.cast', 'third.cast'})
        bounds = [workflows.model_bounds(groups[name]) for name in
                  ('legend.cast', 'second.cast', 'third.cast')]
        for (_, right), (left, _) in zip(bounds, bounds[1:]):
            self.assertGreater(left.x, right.x)
        centers = [(low.y + high.y) / 2 for low, high in bounds]
        for center in centers[1:]:
            self.assertAlmostEqual(center, centers[0], places=5)
        for low, _ in bounds[1:]:
            self.assertAlmostEqual(low.z, bounds[0][0].z, places=5)
        self.assertIn('Imported 3 models', bpy.context.scene.my_prefs.import_summary)
        report = bpy.context.scene.my_prefs.texture_report.as_string()
        for name in groups:
            self.assertIn(name, report)

    def test_batch_import_keeps_successful_models_when_one_file_fails(self):
        second = self.folder / 'second.cast'
        model_file(self.cast, second)
        self.assertEqual(bpy.ops.object.apex_import_texture(
            directory=str(self.folder), files=[{'name': 'legend_rig.cast'},
                                               {'name': 'legend.cast'},
                                               {'name': 'second.cast'}]), {'FINISHED'})
        self.assertIn('1 file skipped', bpy.context.scene.my_prefs.import_summary)
        self.assertIn('legend_rig.cast', bpy.context.scene.my_prefs.texture_report.as_string())
        self.assertEqual(len([obj for obj in bpy.context.selected_objects
                              if obj.type == 'ARMATURE']), 2)

    def test_batch_import_with_no_models_keeps_existing_selection(self):
        select(self.rig)
        before = set(bpy.data.objects)
        with self.assertRaisesRegex(RuntimeError, 'No models imported'):
            bpy.ops.object.apex_import_texture(
                directory=str(self.folder), files=[{'name': 'legend_rig.cast'},
                                                   {'name': 'missing.cast'}])
        self.assertEqual(set(bpy.data.objects), before)
        self.assertEqual(bpy.context.active_object, self.rig)
        self.assertEqual(list(bpy.context.selected_objects), [self.rig])
        self.assertIn('No models imported', bpy.context.scene.my_prefs.import_summary)

    def test_link_indexes_all_clips_and_ignores_model_files(self):
        model_file(self.cast, self.anim_folder / 'rig_only.cast', mesh=False)
        (self.anim_folder / 'bad.cast').write_bytes(b'cast')
        library = self.link()
        self.assertEqual([c.name for c in library.clips], ['idle', 'walk', 'run'])
        self.assertIn('warning', library.summary)
        other = make_rig()
        self.assertFalse(other.apex_animation_library.clips)

    def test_missing_sequences_does_not_replace_link(self):
        library = self.link()
        path = self.folder / 'another.cast'
        model_file(self.cast, path, mesh=False)
        with self.assertRaisesRegex(ValueError, 'Export Rig Sequences'):
            animations.link_library(self.rig, str(path))
        self.assertEqual(len(library.clips), 3)
        self.assertEqual(library.rig_file, str(self.rig_path))

    def test_animation_switch_and_cache_preserve_actions(self):
        library = self.link()
        previous = bpy.data.actions.new('My existing pose')
        self.rig.animation_data_create()
        self.rig.animation_data.action = previous
        before_objects = set(bpy.data.objects)
        before_armatures = set(bpy.data.armatures)
        self.assertEqual(bpy.ops.object.apex_load_animation(), {'FINISHED'})
        idle = self.rig.animation_data.action
        self.assertEqual(bpy.context.mode, 'OBJECT')
        self.assertTrue(previous.use_fake_user)
        self.assertEqual(set(bpy.data.objects), before_objects)
        self.assertEqual(set(bpy.data.armatures), before_armatures)
        scene = bpy.context.scene
        self.assertEqual((scene.frame_start, scene.frame_end), (0, 10))
        self.assertAlmostEqual(scene.render.fps / scene.render.fps_base, 29.97, places=3)
        scene.frame_set(10)
        self.assertAlmostEqual(self.rig.pose.bones['root'].location.x, 2, places=4)
        self.assertAlmostEqual(self.rig.pose.bones['root'].rotation_quaternion.z, 0.38268343, places=4)
        library.index = 2
        self.assertEqual(bpy.ops.object.apex_load_animation(), {'FINISHED'})
        self.assertEqual(self.rig.animation_data.action.name, 'run')
        library.index = 0
        count = len(bpy.data.actions)
        self.assertEqual(bpy.ops.object.apex_load_animation(), {'FINISHED'})
        self.assertEqual(self.rig.animation_data.action, idle)
        self.assertEqual(len(bpy.data.actions), count)
        self.assertEqual(bpy.ops.object.apex_refresh_animations(), {'FINISHED'})
        self.assertEqual(library.clips[0].action, idle)

    def test_failed_animation_keeps_pose_action_timing_selection(self):
        library = self.link()
        previous = bpy.data.actions.new('Previous')
        self.rig.animation_data_create()
        self.rig.animation_data.action = previous
        self.rig.pose.bones['root'].rotation_mode = 'XYZ'
        self.rig.pose.bones['root'].rotation_euler.x = 0.7
        self.rig.rotation_mode = 'XYZ'
        self.rig.rotation_euler = (1.5707963, 0.2, -0.4)
        self.rig.location = (2, -3, 4)
        self.rig.scale = (0.0254, 0.0254, 0.0254)
        bpy.context.view_layer.update()
        object_transform = self.rig.matrix_world.copy()
        scene = bpy.context.scene
        scene.frame_set(7, subframe=0.5)
        timing = (scene.frame_start, scene.frame_end, scene.render.fps, scene.render.fps_base)
        bones = self.rig.pose.bones['root'].matrix_basis.copy()
        real = self.importer.importAnimationNode
        def broken(*args):
            real(*args)
            raise RuntimeError('test interrupted animation')
        before = set(bpy.data.actions)
        with patch.object(self.importer, 'importAnimationNode', broken):
            with self.assertRaisesRegex(RuntimeError, 'interrupted animation'):
                animations.load_clip(bpy.context, self.rig, library.clips[0])
        self.assertEqual(set(bpy.data.actions), before)
        self.assertEqual(self.rig.animation_data.action, previous)
        self.assertEqual(self.rig.pose.bones['root'].rotation_mode, 'XYZ')
        self.assertEqual(self.rig.pose.bones['root'].matrix_basis, bones)
        self.assertEqual(self.rig.rotation_mode, 'XYZ')
        assert_matrix_close(self, self.rig.matrix_world, object_transform)
        self.assertEqual(bpy.context.active_object, self.rig)
        self.assertEqual((scene.frame_current, scene.frame_subframe), (7, 0.5))
        self.assertEqual((scene.frame_start, scene.frame_end, scene.render.fps, scene.render.fps_base), timing)

    def test_missing_bones_require_explicit_opt_in(self):
        animation_file(self.cast, self.anim_folder / 'idle.cast', missing=True)
        library = self.link()
        with self.assertRaisesRegex(ValueError, 'animated bones are missing'):
            animations.load_clip(bpy.context, self.rig, library.clips[0])
        missing = animations.load_clip(bpy.context, self.rig, library.clips[0], allow_missing=True)
        self.assertEqual(missing, 1)

    def test_pose_mode_and_timeline_can_be_preserved(self):
        library = self.link()
        library.fit_timeline = False
        scene = bpy.context.scene
        scene.frame_start, scene.frame_end = 1, 100
        scene.render.fps, scene.render.fps_base = 24, 1
        scene.frame_set(5)
        bpy.ops.object.mode_set(mode='POSE')
        self.assertEqual(bpy.ops.object.apex_load_animation(), {'FINISHED'})
        self.assertEqual(bpy.context.mode, 'POSE')
        self.assertEqual((scene.frame_start, scene.frame_end, scene.frame_current, scene.render.fps), (1, 100, 5, 24))

    def test_constraints_and_nla_are_not_overwritten(self):
        library = self.link()
        constraint = self.rig.pose.bones['root'].constraints.new('LIMIT_ROTATION')
        with self.assertRaisesRegex(ValueError, 'constraints'):
            animations.load_clip(bpy.context, self.rig, library.clips[0])
        self.assertIn(constraint, list(self.rig.pose.bones['root'].constraints))

    def test_missing_importer_has_actionable_message(self):
        addon_utils.disable('io_scene_cast', default_set=False)
        try:
            with self.assertRaisesRegex(ValueError, 'Install and enable the CAST'):
                workflows.import_model(bpy.context, str(self.model_path))
        finally:
            addon_utils.enable('io_scene_cast', default_set=False)

    def test_mesh_selection_targets_its_own_rig(self):
        library = self.link()
        mesh = make_mesh('linked_mesh')
        modifier = mesh.modifiers.new('Rig', 'ARMATURE')
        modifier.object = self.rig
        other = make_rig()
        other.rotation_mode = self.rig.rotation_mode = 'XYZ'
        other.rotation_euler.x = self.rig.rotation_euler.x = 1.5707963
        other_rotation = other.rotation_euler.copy()
        select(mesh)
        self.assertEqual(bpy.ops.object.apex_load_animation(), {'FINISHED'})
        self.assertEqual(self.rig.animation_data.action, library.clips[0].action)
        self.assertIsNone(other.animation_data)
        self.assertEqual(self.rig.rotation_euler[:], (0, 0, 0))
        self.assertEqual(other.rotation_euler, other_rotation)
        self.assertEqual(bpy.context.active_object, mesh)
        self.assertEqual(list(bpy.context.selected_objects), [mesh])

    def test_animation_resets_rotation_for_new_and_cached_actions(self):
        library = self.link()
        parent = bpy.data.objects.new('Placement', None)
        bpy.context.collection.objects.link(parent)
        parent.location = (5, -2, 3)
        parent.rotation_euler = (0.2, 0.4, -0.3)
        self.rig.parent = parent
        self.rig.location = (2, -3, 4)
        self.rig.scale = (0.0254, 0.05, -0.0254)
        placement = self.rig.location.copy()
        scale = self.rig.scale.copy()
        rotation = Euler((1.5707963, 0.2, -0.4)).to_quaternion()
        for mode in ('XYZ', 'ZYX', 'QUATERNION', 'AXIS_ANGLE'):
            library.clips[0].action = None
            first_action = None
            for cached in (False, True):
                with self.subTest(mode=mode, cached=cached):
                    self.rig.rotation_mode = mode
                    if mode == 'QUATERNION':
                        self.rig.rotation_quaternion = rotation
                    elif mode == 'AXIS_ANGLE':
                        axis, angle = rotation.to_axis_angle()
                        self.rig.rotation_axis_angle = (angle, *axis)
                    else:
                        self.rig.rotation_euler = rotation.to_euler(mode)
                    bpy.context.view_layer.update()
                    world_position = self.rig.matrix_world.translation.copy()
                    count = len(bpy.data.actions)
                    self.assertEqual(bpy.ops.object.apex_load_animation(), {'FINISHED'})
                    self.assertEqual(self.rig.rotation_mode, mode)
                    expected_basis = Matrix.Translation(placement) @ Matrix.Diagonal((*scale, 1.0))
                    assert_matrix_close(self, self.rig.matrix_basis, expected_basis)
                    self.assertEqual(self.rig.location, placement)
                    self.assertEqual(self.rig.scale, scale)
                    self.assertLess((self.rig.matrix_world.translation - world_position).length, 1e-5)
                    self.assertEqual(bpy.context.active_object, self.rig)
                    if cached:
                        self.assertEqual(self.rig.animation_data.action, first_action)
                        self.assertEqual(len(bpy.data.actions), count)
                    else:
                        first_action = self.rig.animation_data.action
                    # Resetting the object must not flatten the imported bone motion.
                    bpy.context.scene.frame_set(10)
                    self.assertAlmostEqual(self.rig.pose.bones['root'].location.x, 2, places=4)
                    self.assertAlmostEqual(self.rig.pose.bones['root'].rotation_quaternion.z, 0.38268343, places=4)

    def test_changed_export_invalidates_cached_action(self):
        library = self.link()
        bpy.ops.object.apex_load_animation()
        old = self.rig.animation_data.action
        animation_file(self.cast, self.anim_folder / 'idle.cast', names=('updated_idle',))
        bpy.ops.object.apex_refresh_animations()
        bpy.ops.object.apex_load_animation()
        self.assertNotEqual(self.rig.animation_data.action, old)
        self.assertTrue(old.use_fake_user)
        self.assertEqual(self.rig.animation_data.action.name, 'updated_idle')

    def test_large_scan_finishes_after_old_timeout_and_keeps_only_clip_metadata(self):
        library = self.link()
        animation_file(self.cast, self.anim_folder / 'many.cast', names=tuple('clip_%d' % i for i in range(600)))
        scan = animations.LibraryScan(self.rig, str(self.rig_path))
        self.addCleanup(scan.close)
        ticks = itertools.count(0, 20)  # Every chunk crosses the old ten-second cutoff.
        chunks = 0
        with patch.object(animations.time, 'monotonic', side_effect=lambda: next(ticks)):
            while not scan.step():
                chunks += 1
                self.assertEqual(len(library.clips), 3)
        self.assertGreater(chunks, 600)
        self.assertEqual(len(scan.entries), 603)
        self.assertTrue(all(isinstance(item, animations.Clip) for item in scan.entries))
        self.assertFalse(scan.warnings)
        scan.commit(self.rig)
        self.assertEqual(len(library.clips), 603)

    def test_cancelled_scan_preserves_list_action_and_releases_files(self):
        library = self.link()
        bpy.ops.object.apex_load_animation()
        action = self.rig.animation_data.action
        previous = [(c.name, c.filepath, c.offset, c.action) for c in library.clips]
        scan = animations.LibraryScan(self.rig, str(self.rig_path))
        for _ in range(5):
            self.assertFalse(scan.step(0))
        scan.close()
        with self.assertRaisesRegex(ValueError, 'Finish indexing'):
            scan.commit(self.rig)
        self.assertEqual([(c.name, c.filepath, c.offset, c.action) for c in library.clips], previous)
        self.assertEqual(self.rig.animation_data.action, action)
        self.rig_path.unlink()

    def test_category_and_text_filters_combine_and_refresh_keeps_selection(self):
        animation_file(self.cast, self.anim_folder / 'categories.cast', names=(
            'WRAITH_GLADCARD_intro', 'wraith_emote_lobby', 'mirage_lobby_idle',
            'wraith_execution', 'wraith_sprint_forward'))
        library = self.link()
        library.category = 'LOBBY'
        self.assertEqual(library.clips[library.index].name, 'wraith_emote_lobby')
        library.filter_text = 'MIRAGE'
        self.assertEqual(library.clips[library.index].name, 'mirage_lobby_idle')
        animations.link_library(self.rig, str(self.rig_path))
        self.assertEqual((library.category, library.filter_text), ('LOBBY', 'MIRAGE'))
        self.assertEqual(library.clips[library.index].name, 'mirage_lobby_idle')
        library.filter_text = 'missing'
        with patch.object(animations, 'load_clip') as loader:
            self.assertEqual(bpy.ops.object.apex_load_animation(), {'CANCELLED'})
            loader.assert_not_called()
        for name, category in [('WRAITH_GLADCARD_intro', 'GLADCARD'), ('banner_pose', 'GLADCARD'),
                               ('wraith_emote_lobby', 'EMOTE'), ('wraith_execution', 'FINISHER'),
                               ('wraith_sprint_forward', 'MOVEMENT')]:
            self.assertTrue(animations.clip_matches(name, category))
        self.assertFalse(animations.clip_matches('lobby_idle', 'GLADCARD'))
        self.assertFalse(animations.clip_matches('wraith_emote_lobby', 'LOBBY', 'mirage'))

    def test_remove_animation_restores_every_bone_and_reuses_cached_action(self):
        library = self.link()
        self.rig.rotation_mode = 'XYZ'
        self.rig.rotation_euler = (1.5707963, 0.1, 0.3)
        self.rig.location = (2, 3, 4)
        self.rig.scale = (0.0254, 0.0254, 0.0254)
        bpy.context.view_layer.update()
        transform = self.rig.matrix_world.copy()
        bpy.ops.object.apex_load_animation()
        first = self.rig.animation_data.action
        library.index = 2
        bpy.ops.object.apex_load_animation()  # Switching clips must keep the original rotation.
        bpy.context.scene.frame_set(10)
        bpy.ops.object.mode_set(mode='POSE')
        self.assertEqual(bpy.ops.object.apex_remove_animation(), {'FINISHED'})
        self.assertEqual(bpy.context.mode, 'POSE')
        self.assertIsNone(self.rig.animation_data.action)
        self.assertEqual(len(library.clips), 3)
        assert_matrix_close(self, self.rig.matrix_world, transform)
        self.assertFalse(library.has_rest_rotation)
        for frame in (10, 2, 20):
            bpy.context.scene.frame_set(frame)
            for bone in self.rig.pose.bones:
                assert_matrix_close(self, bone.matrix_basis, Matrix.Identity(4))
                assert_matrix_close(self, bone.matrix, bone.bone.matrix_local)
        library.index = 0
        bpy.ops.object.apex_load_animation()
        self.assertEqual(self.rig.animation_data.action, first)
        self.assertEqual(bpy.context.active_object, self.rig)
        self.assertEqual(bpy.context.mode, 'POSE')

    def test_remove_animation_from_mesh_preserves_other_rig_and_timing(self):
        library = self.link()
        bpy.ops.object.apex_load_animation()
        mesh = make_mesh('linked_mesh')
        mesh.modifiers.new('Rig', 'ARMATURE').object = self.rig
        other = make_rig()
        other.pose.bones['root'].location.x = 7
        select(mesh)
        bpy.context.scene.frame_set(7, subframe=0.5)
        scene = bpy.context.scene
        timing = (scene.frame_start, scene.frame_end, scene.frame_current, scene.frame_subframe, scene.render.fps)
        bpy.ops.object.apex_remove_animation()
        self.assertEqual(bpy.context.active_object, mesh)
        self.assertEqual(list(bpy.context.selected_objects), [mesh])
        self.assertEqual(other.pose.bones['root'].location.x, 7)
        self.assertEqual((scene.frame_start, scene.frame_end, scene.frame_current, scene.frame_subframe, scene.render.fps), timing)
        self.assertTrue(library.clips[0].action.use_fake_user)

    def test_remove_animation_guards_constraints_nla_and_drivers(self):
        self.link()
        bpy.ops.object.apex_load_animation()
        action = self.rig.animation_data.action
        constraint = self.rig.constraints.new('LIMIT_ROTATION')
        with self.assertRaisesRegex(ValueError, 'constraints'):
            animations.remove_animation(bpy.context, self.rig)
        self.rig.constraints.remove(constraint)
        track = self.rig.animation_data.nla_tracks.new()
        with self.assertRaisesRegex(ValueError, 'NLA'):
            animations.remove_animation(bpy.context, self.rig)
        self.rig.animation_data.nla_tracks.remove(track)
        driver = self.rig.driver_add('location', 0)
        with self.assertRaisesRegex(ValueError, 'drivers'):
            animations.remove_animation(bpy.context, self.rig)
        self.assertEqual(self.rig.animation_data.action, action)

    def test_remove_animation_restores_all_object_rotation_modes(self):
        library = self.link()
        for mode in ('XYZ', 'ZYX', 'QUATERNION', 'AXIS_ANGLE'):
            with self.subTest(mode=mode):
                self.rig.rotation_mode = mode
                self.rig.matrix_basis = Euler((0.3, 0.7, -0.4)).to_matrix().to_4x4()
                bpy.context.view_layer.update()
                before = self.rig.matrix_basis.copy()
                bpy.ops.object.apex_load_animation()
                bpy.ops.object.apex_remove_animation()
                self.assertEqual(self.rig.rotation_mode, mode)
                assert_matrix_close(self, self.rig.matrix_basis, before)

    def test_link_and_cached_action_survive_save_reopen(self):
        library = self.link()
        self.rig.rotation_mode = 'XYZ'
        self.rig.rotation_euler = (1.5707963, 0, 0)
        bpy.ops.object.apex_load_animation()
        rig_name, action_name = self.rig.name, self.rig.animation_data.action.name
        path = self.folder / 'animation_test.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        bpy.ops.wm.open_mainfile(filepath=str(path))
        self.rig = bpy.data.objects[rig_name]
        library = self.rig.apex_animation_library
        self.assertEqual(library.rig_file, str(self.rig_path))
        self.assertEqual(len(library.clips), 3)
        self.assertEqual(library.clips[0].action.name, action_name)
        count = len(bpy.data.actions)
        select(self.rig)
        bpy.ops.object.apex_load_animation()
        self.assertEqual(len(bpy.data.actions), count)
        bpy.ops.object.apex_remove_animation()
        self.assertAlmostEqual(self.rig.rotation_euler.x, 1.5707963, places=5)
        self.assertIsNone(self.rig.animation_data.action)

    def test_favourites_filter_scope_and_unstar_selection(self):
        library = self.link()
        self.assertEqual(bpy.ops.object.apex_favourite_animation(index=0), {'FINISHED'})
        self.assertEqual(bpy.ops.object.apex_favourite_animation(index=2), {'FINISHED'})
        library.browse_mode = 'FAVOURITES'
        self.assertEqual(animations.visible_clip_indices(library), [0, 2])
        library.index = 0
        bpy.ops.object.apex_favourite_animation(index=0)
        self.assertEqual(library.index, 2)
        library.filter_text = 'idle'
        self.assertFalse(animations.visible_clip_indices(library))
        with patch.object(animations, 'load_clip') as loader:
            self.assertEqual(bpy.ops.object.apex_load_animation(), {'CANCELLED'})
            loader.assert_not_called()
        library.filter_text = ''
        library.category = 'MOVEMENT'
        self.assertEqual(animations.visible_clip_indices(library), [2])
        other = make_rig()
        self.assertFalse(other.apex_animation_library.clips)
        self.assertTrue(library.clips[2].favourite)

    def test_recents_track_only_successful_loads_and_cache_reuse(self):
        library = self.link()
        for index in (0, 1, 2, 0):
            library.index = index
            self.assertEqual(bpy.ops.object.apex_load_animation(), {'FINISHED'})
        self.assertEqual([c.recent_order for c in library.clips], [1, 3, 2])
        library.browse_mode = 'RECENT'
        self.assertEqual(animations.visible_clip_indices(library), [0, 2, 1])
        library.filter_text = 'r'
        self.assertEqual(animations.visible_clip_indices(library), [2])
        before = [c.recent_order for c in library.clips]
        with patch.object(animations, 'validate_target', side_effect=ValueError('fixture failure')):
            with self.assertRaisesRegex(ValueError, 'fixture failure'):
                animations.load_clip(bpy.context, self.rig, library.clips[1])
        self.assertEqual([c.recent_order for c in library.clips], before)
        action = self.rig.animation_data.action
        library.clips[0].favourite = True
        self.assertEqual(bpy.ops.object.apex_clear_recent_animations(), {'FINISHED'})
        self.assertFalse(animations.visible_clip_indices(library))
        self.assertEqual(self.rig.animation_data.action, action)
        self.assertTrue(library.clips[0].favourite)

    def test_recents_limit_and_display_order(self):
        animation_file(self.cast, self.anim_folder / 'recent.cast', names=tuple('recent_%02d' % i for i in range(23)))
        library = self.link()
        for item in library.clips:
            animations.record_recent(library, item)
        library.browse_mode = 'RECENT'
        visible = animations.visible_clip_indices(library)
        self.assertEqual(len(visible), 20)
        self.assertEqual(visible, list(range(len(library.clips) - 1, len(library.clips) - 21, -1)))
        self.assertEqual(library.index, visible[0])
        # Blender expects old-index -> new-position, including hidden rows.
        ui = type('ListStub', (), {'bitflag_filter_item': 1})()
        flags, order = addon.APEX_UL_animations.filter_items(ui, bpy.context, library, 'clips')
        self.assertEqual([i for i in sorted(range(len(order)), key=lambda i: order[i]) if flags[i]], visible)

    def test_refresh_preserves_bookmarks_when_clip_offsets_change(self):
        library = self.link()
        library.clips[2].favourite = True
        library.index = 2
        bpy.ops.object.apex_load_animation()
        old_offset = library.clips[2].offset
        animation_file(self.cast, self.anim_folder / 'walk.cast', names=('new_clip_with_long_name', 'run', 'walk'))
        animations.link_library(self.rig, str(self.rig_path))
        run = next(item for item in library.clips if item.name == 'run')
        self.assertNotEqual(run.offset, old_offset)
        self.assertTrue(run.favourite)
        self.assertEqual(run.recent_order, 1)
        self.assertEqual(library.clips[library.index].name, 'run')
        self.assertFalse(next(item for item in library.clips if item.name == 'walk').favourite)

    def test_refresh_does_not_guess_favourites_for_duplicate_names_or_new_rig(self):
        library = self.link()
        library.clips[2].favourite = True
        animation_file(self.cast, self.anim_folder / 'walk.cast', names=('run', 'run'))
        animations.link_library(self.rig, str(self.rig_path))
        self.assertFalse(any(item.favourite for item in library.clips))
        library.clips[0].favourite = True
        animations.record_recent(library, library.clips[0])
        alternate_rig = self.folder / 'another_legend.cast'
        model_file(self.cast, alternate_rig, mesh=False)
        alternate_sequences = self.folder / 'anims_another_legend'
        alternate_sequences.mkdir()
        animation_file(self.cast, alternate_sequences / 'idle.cast')
        animations.link_library(self.rig, str(alternate_rig))
        self.assertFalse(library.clips[0].favourite)
        self.assertEqual(library.clips[0].recent_order, 0)

    def test_favourites_and_recents_survive_save_reopen(self):
        library = self.link()
        bpy.ops.object.apex_favourite_animation(index=2)
        library.index = 2
        bpy.ops.object.apex_load_animation()
        library.browse_mode = 'FAVOURITES'
        rig_name = self.rig.name
        path = self.folder / 'bookmarked.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        bpy.ops.wm.open_mainfile(filepath=str(path))
        self.rig = bpy.data.objects[rig_name]
        library = self.rig.apex_animation_library
        self.assertEqual(library.browse_mode, 'FAVOURITES')
        self.assertEqual(animations.visible_clip_indices(library), [2])
        self.assertEqual(library.clips[2].recent_order, 1)

    def names_fixture(self, library):
        """A real CAST animation GUID referenced by synthetic RSX metadata."""
        item = library.clips[0]
        reference = 'animseq/humans/test/test_emote.rseq'
        import struct
        path = Path(item.filepath)
        data = bytearray(path.read_bytes())
        guid = animation_names.string_guid(reference)
        struct.pack_into('<Q', data, item.offset + 8, guid)
        path.write_bytes(data)
        animations.link_library(self.rig, str(self.rig_path))
        item = library.clips[0]
        self.assertEqual(item.guid, format(guid, 'x'))
        self.locl = self.folder / 'localization' / 'test.locl'
        self.locl.parent.mkdir()
        token = animation_names.string_guid('TEST_NAME')
        self.locl.write_text('"test"\n{\n"%x" "Star Dance"\n}\n' % token, encoding='utf-8')
        settings = self.folder / 'settings' / 'itemflav' / 'skydive_emote' / 'test_legend'
        settings.mkdir(parents=True)
        (settings / 'test.json').write_text(json.dumps({'settings': {
            'itemType': 'skydive_emote', 'localizationKey_NAME': '#TEST_NAME', 'animSequence': reference,
        }}), encoding='utf-8')
        return item

    def test_import_names_search_load_refresh_and_save_reopen(self):
        library = self.link()
        item = self.names_fixture(library)
        item.favourite = True
        self.assertEqual(bpy.ops.object.apex_import_animation_names(filepath=str(self.locl)), {'FINISHED'})
        self.assertEqual(item.menu_name, 'Star Dance')
        self.assertEqual(animations.clip_label(item, library), 'Star Dance')
        library.filter_text = 'star dance'
        self.assertEqual(animations.visible_clip_indices(library), [0])
        library.show_menu_names = False
        self.assertEqual(animations.clip_label(item, library), item.name)
        self.assertEqual(bpy.ops.object.apex_load_animation(), {'FINISHED'})
        self.assertEqual(item.recent_order, 1)
        animations.link_library(self.rig, str(self.rig_path))
        item = library.clips[0]
        self.assertEqual(item.menu_name, 'Star Dance')
        self.assertTrue(item.favourite)
        self.assertEqual(item.recent_order, 1)
        rig_name = self.rig.name
        path = self.folder / 'named.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        bpy.ops.wm.open_mainfile(filepath=str(path))
        self.rig = bpy.data.objects[rig_name]
        library = self.rig.apex_animation_library
        self.assertEqual(library.clips[0].menu_name, 'Star Dance')
        self.assertTrue(library.clips[0].favourite)
        self.assertEqual(animations.visible_clip_indices(library), [0])

    def test_cancelled_failed_and_stale_name_scans_keep_previous_names(self):
        library = self.link()
        item = self.names_fixture(library)
        item.menu_name = 'Kept Name'
        scan = animations.AnimationNamesScan(self.rig, str(self.locl))
        scan.step(0)
        self.assertFalse(scan.done)
        scan.close()
        self.assertEqual(item.menu_name, 'Kept Name')
        with self.assertRaises(ValueError):
            scan.commit(self.rig)
        scan = animations.AnimationNamesScan(self.rig, str(self.locl))
        while not scan.step():
            pass
        item.guid = '123'
        with self.assertRaisesRegex(ValueError, 'changed'):
            scan.commit(self.rig)
        scan.close()
        self.assertEqual(item.menu_name, 'Kept Name')
        scan = animations.AnimationNamesScan(self.rig, str(self.locl))
        with self.assertRaisesRegex(ValueError, 'No exact names'):
            while not scan.step():
                pass
        scan.close()
        self.assertEqual(item.menu_name, 'Kept Name')

    def test_refresh_clears_names_if_sequence_identity_changes(self):
        library = self.link()
        item = self.names_fixture(library)
        bpy.ops.object.apex_import_animation_names(filepath=str(self.locl))
        old_name, path = item.name, Path(item.filepath)
        item.favourite = True
        animation_file(self.cast, path, names=(old_name,))
        animations.link_library(self.rig, str(self.rig_path))
        self.assertTrue(library.clips[0].favourite)
        self.assertEqual(library.clips[0].menu_name, '')

    def test_refresh_selection_prefers_unique_name_over_reused_byte_offset(self):
        library = self.link()
        library.index = 2
        animation_file(self.cast, self.anim_folder / 'walk.cast', names=('run', 'walk'))
        animations.link_library(self.rig, str(self.rig_path))
        self.assertEqual(library.clips[library.index].name, 'run')

    def builtin_fixture(self):
        import struct
        library = self.link()
        item = library.clips[0]
        path = Path(item.filepath)
        data = bytearray(path.read_bytes())
        guid = animation_names.string_guid('animseq/humans/class/light/pilot_light_wraith/wraith_execution_blink.rseq')
        struct.pack_into('<Q', data, item.offset + 8, guid)
        path.write_bytes(data)
        self.assertEqual(bpy.ops.object.apex_refresh_animations(), {'FINISHED'})
        return library

    def test_included_names_on_link_and_refresh_without_metadata(self):
        library = self.builtin_fixture()
        item = library.clips[0]
        self.assertEqual(item.menu_name, 'Existential Crisis')
        self.assertEqual(item.menu_source, 'BUILTIN')
        self.assertEqual(library.names_file, '')
        library.filter_text = 'existential'
        self.assertEqual(animations.visible_clip_indices(library), [0])
        item.favourite = True
        bpy.ops.object.apex_load_animation()
        self.assertEqual(item.recent_order, 1)
        animations.link_library(self.rig, str(self.rig_path))
        item = library.clips[0]
        self.assertEqual(item.menu_name, 'Existential Crisis')
        self.assertEqual(item.menu_source, 'BUILTIN')
        self.assertTrue(item.favourite)
        self.assertEqual(item.recent_order, 1)

    def test_custom_names_survive_refresh_until_reset_to_included_names(self):
        library = self.builtin_fixture()
        item = library.clips[0]
        item.menu_name = 'Translated Name'
        item.menu_source = 'CUSTOM'
        library.names_file = str(self.folder / 'custom.locl')
        item.favourite = True
        animations.link_library(self.rig, str(self.rig_path))
        self.assertEqual(library.clips[0].menu_name, 'Translated Name')
        self.assertEqual(library.clips[0].menu_source, 'CUSTOM')
        self.assertEqual(bpy.ops.object.apex_builtin_animation_names(), {'FINISHED'})
        self.assertEqual(library.clips[0].menu_name, 'Existential Crisis')
        self.assertEqual(library.clips[0].menu_source, 'BUILTIN')
        self.assertTrue(library.clips[0].favourite)
        self.assertEqual(library.names_file, '')

    def test_legacy_imported_names_migrate_on_refresh(self):
        library = self.builtin_fixture()
        item = library.clips[0]
        item.menu_name = 'Legacy Name'
        item.menu_source = ''
        library.names_file = 'previously_imported.locl'
        animations.link_library(self.rig, str(self.rig_path))
        self.assertEqual(library.clips[0].menu_name, 'Legacy Name')
        self.assertEqual(library.clips[0].menu_source, 'CUSTOM')

    def test_missing_catalogue_does_not_prevent_linking_or_erase_existing_names(self):
        library = self.builtin_fixture()
        with patch.object(animation_names, 'bundled_catalog', side_effect=OSError('fixture missing file')):
            summary, warning = animations.link_library(self.rig, str(self.rig_path))
        self.assertTrue(warning)
        self.assertIn('reinstall Apex Toolbox', summary)
        self.assertEqual(library.clips[0].menu_name, 'Existential Crisis')
        self.assertEqual(len(library.clips), 3)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WorkflowIntegration)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
