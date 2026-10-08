"""Run with Blender 4.2+: blender -b --factory-startup --python-exit-code 1 --python tests/blender_integration.py.

Uses real image files, Blender datablocks, operators and the bundled shader
library. All writes are in a temporary directory, never the user's scene.
"""
import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import bpy
from mathutils import Euler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import Apex_toolbox as addon
from Apex_toolbox.apex_tex import autotex, graph, health, roles as R, shaders


def make_mesh(name='hero_body', material=True, uv=True):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    if uv:
        mesh.uv_layers.new()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    if material:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        mesh.materials.append(mat)
    return obj


def select(*objects):
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0] if objects else None


def snapshot(material):
    tree = material.node_tree
    return (material.use_nodes,
            [(n.as_pointer(), n.name, n.bl_idname) for n in tree.nodes],
            [(l.from_socket.as_pointer(), l.to_socket.as_pointer()) for l in tree.links],
            tree.nodes.active.as_pointer() if tree.nodes.active else None,
            [(n.name, n.is_active_output) for n in tree.nodes if n.type == 'OUTPUT_MATERIAL'])


def make_rig():
    rig = bpy.data.objects.new('rig', bpy.data.armatures.new('rig'))
    bpy.context.collection.objects.link(rig)
    select(rig)
    bpy.ops.object.mode_set(mode='EDIT')
    root = rig.data.edit_bones.new('root')
    root.head, root.tail = (0, 0, 0), (0, 0, 1)
    child = rig.data.edit_bones.new('child')
    child.head, child.tail = (0, 0, 1), (0.25, 0.1, 2)
    child.parent = root
    bpy.ops.object.mode_set(mode='OBJECT')
    return rig


def assert_matrix_close(test, actual, expected):
    for row in range(4):
        for column in range(4):
            test.assertAlmostEqual(actual[row][column], expected[row][column], places=5)


class BlenderIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        addon.register()
        for definition in shaders.SHADER_DEFS.values():
            addon.append_apex_node_group(definition.group_name)

    @classmethod
    def tearDownClass(cls):
        addon.unregister()
        importlib.reload(addon)
        addon.register()
        addon.unregister()
        print('REGISTER / UNREGISTER / HOT RELOAD PASSED')

    def setUp(self):
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        for mat in list(bpy.data.materials):
            bpy.data.materials.remove(mat)
        for image in list(bpy.data.images):
            bpy.data.images.remove(image)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.prefs = bpy.context.scene.my_prefs
        self.prefs.autotex_folder = str(self.folder)
        self.prefs.aut_subf = True
        self.prefs.cust_enum2 = 'OP1'
        self.prefs.cust_enum = 'OP1'
        self.prefs.include_model_meshes = True
        self.prefs.health_scope = 'SELECTION'
        self.prefs.health_issues.clear()
        self.prefs.repair_folder = str(self.folder)
        # Isolate automatic discovery from this machine's personal bookmarks.
        self.bookmarks = patch.object(autotex, 'browsed_directories', return_value=[])
        self.bookmarks.start()
        self.addCleanup(self.bookmarks.stop)

    def image_file(self, name='hero_body_col.png', color=(0.4, 0.2, 0.1, 1)):
        path = self.folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        image = bpy.data.images.new(path.stem, width=8, height=8)
        image.generated_color = color
        image.filepath_raw = str(path)
        image.file_format = 'TIFF' if path.suffix == '.tif' else 'PNG'
        image.save()
        bpy.data.images.remove(image)
        return path

    def bind_image(self, obj, image, socket='Base Color'):
        mat = obj.active_material
        tree = mat.node_tree
        node = tree.nodes.new('ShaderNodeTexImage')
        node.image = image
        tree.links.new(node.outputs['Color'], tree.nodes.get('Principled BSDF').inputs[socket])
        return node

    def missing_image(self, name='hero_body_col.png'):
        path = self.image_file('old/' + name)
        image = bpy.data.images.load(str(path))
        path.unlink()
        image.reload()
        return image

    def test_conversion_reports_are_reused_and_selection_is_preserved(self):
        self.image_file()
        self.image_file('hero_body_nml.png')
        obj = make_mesh()
        select(obj)
        relative = bpy.context.preferences.filepaths.use_relative_paths
        self.assertEqual(bpy.ops.object.button_custom(), {'FINISHED'})
        report = self.prefs.texture_report
        self.assertIn('1 textured; 0 left untouched', report.as_string())
        self.assertIn('hero_body_col.png', report.as_string())
        self.assertIn('hero_body_nml.png', report.as_string())
        self.assertIn(str(self.folder), report.as_string())
        self.assertEqual(bpy.context.preferences.filepaths.use_relative_paths, relative)
        counts = (len(bpy.data.images), len(bpy.data.node_groups))
        bpy.ops.object.button_custom()
        self.assertEqual((len(bpy.data.images), len(bpy.data.node_groups)), counts)
        self.assertEqual(self.prefs.texture_report, report)
        self.assertEqual(list(bpy.context.selected_objects), [obj])

    def test_each_shader_converts_and_repeated_runs_preserve_roles(self):
        for key, definition in shaders.SHADER_DEFS.items():
            with self.subTest(shader=key):
                obj = make_mesh('model_' + key + '_body')
                self.image_file(obj.name + '_col.png')
                self.image_file(obj.name + '_roughness.png')
                self.image_file(obj.name + '_nml.png', (0.5, 0.5, 1, 1))
                select(obj)
                self.prefs.cust_enum2 = key
                for _ in range(2):
                    self.assertEqual(bpy.ops.object.button_custom(), {'FINISHED'})
                    tree = obj.active_material.node_tree
                    self.assertEqual(sum(n.type == 'INVERT' for n in tree.nodes), 1)
                    self.assertEqual(graph.inspect_material(obj.active_material).roles,
                                     {R.ALBEDO, R.NORMAL, R.ROUGHNESS})
                    self.assertIn('0', tree.nodes)
                    self.assertIn('6', tree.nodes)
                    self.assertEqual(tree.nodes['5'].image.colorspace_settings.name, 'Non-Color')
                self.assertEqual(bpy.context.view_layer.objects.active, obj)

    def test_shader_failure_rolls_back_graph_active_output_and_image_settings(self):
        obj = make_mesh()
        image = bpy.data.images.load(str(self.image_file()))
        self.bind_image(obj, image)
        before = snapshot(obj.active_material)
        settings = (image.colorspace_settings.name, image.alpha_mode)
        invalid = shaders.ShaderDef('bad', 'Apex Shader', {R.ALBEDO: 'Does not exist'}, {})
        with self.assertRaises(RuntimeError):
            shaders.build_material(obj.active_material, invalid, {R.ALBEDO: image})
        self.assertEqual(snapshot(obj.active_material), before)
        self.assertEqual((image.colorspace_settings.name, image.alpha_mode), settings)
        with patch.object(shaders, 'apply_colorspace', side_effect=RuntimeError('forced failure')):
            with self.assertRaises(RuntimeError):
                shaders.build_material(obj.active_material, shaders.SHADER_DEFS['OP1'], {R.ALBEDO: image})
        self.assertEqual(snapshot(obj.active_material), before)

    def test_material_without_nodes_can_be_textured(self):
        obj = make_mesh()
        obj.active_material.use_nodes = False
        self.image_file()
        select(obj)
        self.assertEqual(bpy.ops.object.button_custom(), {'FINISHED'})
        self.assertTrue(obj.active_material.use_nodes)
        self.assertIn(R.ALBEDO, graph.inspect_material(obj.active_material).roles)

    def test_missing_reference_does_not_blank_or_partially_replace_material(self):
        obj = make_mesh()
        image = self.missing_image('anonymous.png')
        self.bind_image(obj, image)
        self.image_file('hero_body_nml.png')
        before = snapshot(obj.active_material)
        select(obj)
        bpy.ops.object.button_custom()
        self.assertEqual(snapshot(obj.active_material), before)
        self.assertIn('Left untouched', self.prefs.texture_report.as_string())

    def test_corrupt_candidate_does_not_destroy_original_shader(self):
        obj = make_mesh()
        (self.folder / 'hero_body_col.png').write_text('not an image')
        self.image_file('hero_body_nml.png')
        before = snapshot(obj.active_material)
        select(obj)
        bpy.ops.object.button_custom()
        self.assertEqual(snapshot(obj.active_material), before)
        self.assertIn('Left untouched', self.prefs.texture_report.as_string())

    def test_stale_loaded_image_does_not_win_over_valid_disk_file(self):
        self.missing_image()
        good = self.image_file()
        obj = make_mesh()
        select(obj)
        bpy.ops.object.button_custom()
        result = graph.inspect_material(obj.active_material)
        self.assertEqual(Path(result.hits[0].path), good)

    def test_current_folder_beats_unrelated_loaded_old_export(self):
        old = self.image_file('old/hero_body_col.png')
        bpy.data.images.load(str(old))
        current = self.image_file('current/hero_body_col.png')
        self.prefs.autotex_folder = str(current.parent)
        obj = make_mesh()
        select(obj)
        bpy.ops.object.button_custom()
        self.assertEqual(Path(graph.inspect_material(obj.active_material).hits[0].path), current)

    def test_armature_scope_includes_bound_and_parented_meshes(self):
        rig = bpy.data.objects.new('rig', bpy.data.armatures.new('rig'))
        bpy.context.collection.objects.link(rig)
        parented = make_mesh('parented')
        parented.parent = rig
        bound = make_mesh('bound')
        bound.modifiers.new('Rig', 'ARMATURE').object = rig
        unrelated = make_mesh('unrelated')
        select(rig)
        self.assertEqual(set(addon.texture_targets(bpy.context)), {parented, bound})
        self.prefs.include_model_meshes = False
        self.assertEqual(addon.texture_targets(bpy.context), [])
        select(unrelated)
        self.assertEqual(addon.texture_targets(bpy.context), [unrelated])

    def test_health_check_and_issue_selection(self):
        good = make_mesh('good')
        bad = make_mesh('bad', material=False, uv=False)
        bad.modifiers.new('Missing Rig', 'ARMATURE')
        select(bad, good)
        before = list(bpy.context.selected_objects)
        bpy.ops.object.apex_check_scene()
        self.assertEqual(list(bpy.context.selected_objects), before)
        self.assertEqual({item.code for item in self.prefs.health_issues},
                         {'NO_UV', 'NO_MATERIAL', 'NO_RIG'})
        bpy.ops.object.apex_select_issues(code='NO_UV')
        self.assertEqual(list(bpy.context.selected_objects), [bad])
        self.assertIn('Missing Rig', self.prefs.health_report.as_string())

    def test_health_packed_images_are_valid_but_missing_files_are_flagged(self):
        obj = make_mesh()
        image = bpy.data.images.load(str(self.image_file()))
        self.bind_image(obj, image)
        image.pack()
        Path(image.filepath).unlink()
        self.assertFalse(health.is_missing_file(image))
        select(obj)
        bpy.ops.object.apex_check_scene()
        self.assertFalse(self.prefs.health_issues)

    def test_missing_image_inside_nested_group_is_checked_and_repaired(self):
        obj = make_mesh()
        image = self.missing_image()
        group = bpy.data.node_groups.new('Test nested', 'ShaderNodeTree')
        group.nodes.new('ShaderNodeTexImage').image = image
        obj.active_material.node_tree.nodes.new('ShaderNodeGroup').node_tree = group
        replacement = self.image_file()
        select(obj)
        bpy.ops.object.apex_check_scene()
        self.assertIn('MISSING_IMAGE', {entry.code for entry in self.prefs.health_issues})
        before = snapshot(obj.active_material)
        bpy.ops.object.apex_repair_textures()
        self.assertEqual(Path(image.filepath), replacement)
        self.assertEqual(snapshot(obj.active_material), before)
        self.assertFalse(health.is_missing_file(image))
        self.assertFalse(self.prefs.health_issues)

    def test_ambiguous_repair_does_not_guess(self):
        image = self.missing_image()
        self.image_file('a/hero_body_col.png')
        self.image_file('b/hero_body_col.png')
        before = image.filepath
        summary, body = health.repair_images([image], str(self.folder))
        self.assertIn('ambiguous', body)
        self.assertIn('0 repaired', summary)
        self.assertEqual(image.filepath, before)

    def test_corrupt_repair_file_leaves_original_reference(self):
        image = self.missing_image()
        (self.folder / 'hero_body_col.png').write_text('not a PNG')
        before = image.filepath
        count = len(bpy.data.images)
        summary, body = health.repair_images([image], str(self.folder))
        self.assertIn('0 repaired', summary)
        self.assertEqual(image.filepath, before)
        self.assertEqual(len(bpy.data.images), count)

    def test_incomplete_search_never_claims_a_repair_match_is_unique(self):
        image = self.missing_image()
        self.image_file('a/hero_body_col.png')
        self.image_file('b/hero_body_col.png')
        before = image.filepath
        with patch.object(health.paths.TextureIndex, 'MAX_FILES', 1):
            summary, body = health.repair_images([image], str(self.folder))
        self.assertIn('incomplete', summary)
        self.assertEqual(image.filepath, before)

    def test_repair_preserves_relative_paths(self):
        # Set the blend filename without touching the user's files.
        blend_path = self.folder / 'relative.blend'
        obj = make_mesh()
        image = self.missing_image()
        self.bind_image(obj, image)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
        image.filepath = '//old/hero_body_col.png'
        self.image_file()
        self.assertTrue((self.folder / 'hero_body_col.png').is_file(),
                        str(list(self.folder.rglob('*'))))
        summary, body = health.repair_images([image], str(self.folder))
        self.assertIn('1 repaired', summary, body)
        self.assertTrue(image.filepath.startswith('//'))
        self.assertFalse(health.is_missing_file(image))

    def test_health_reports_zero_scale_and_empty_binding(self):
        obj = make_mesh()
        obj.scale.z = 0
        self.bind_image(obj, None)
        select(obj)
        bpy.ops.object.apex_check_scene()
        self.assertEqual({item.code for item in self.prefs.health_issues},
                         {'ZERO_SCALE', 'EMPTY_IMAGE'})

    def test_material_report_roundtrips_in_saved_blend(self):
        obj = make_mesh()
        select(obj)
        self.image_file()
        bpy.ops.object.button_custom()
        report_name = self.prefs.texture_report.name
        body = self.prefs.texture_report.as_string()
        path = self.folder / 'report-roundtrip.blend'
        bpy.ops.wm.save_as_mainfile(filepath=str(path))
        bpy.ops.wm.open_mainfile(filepath=str(path))
        self.prefs = bpy.context.scene.my_prefs
        self.assertEqual(self.prefs.texture_report.name, report_name)
        self.assertEqual(self.prefs.texture_report.as_string(), body)

    def test_recolour_supports_rsx_tiff_without_trailing_separator_and_shared_material(self):
        obj = make_mesh('hero_original_body')
        other = make_mesh('shared', material=False)
        other.data.materials.append(obj.active_material)
        path = self.image_file('hero_new/hero_new_body/hero_new_body_col.tif')
        self.image_file('hero_new/hero_new_body/hero_new_body_nml.png')
        select(obj, other)
        self.prefs.recolor_folder = str(self.folder / 'hero_new')
        self.assertEqual(bpy.ops.object.button_custom2(), {'FINISHED'})
        self.assertIn('1 updated', self.prefs.texture_summary)
        self.assertIn(R.ALBEDO, graph.inspect_material(obj.active_material).roles)
        self.assertEqual(Path(graph.inspect_material(obj.active_material).hits[0].path), path)

    def test_recolour_invalid_folder_is_graceful(self):
        obj = make_mesh()
        select(obj)
        self.prefs.recolor_folder = str(self.folder / 'not-here')
        before = snapshot(obj.active_material)
        self.assertEqual(bpy.ops.object.button_custom2(), {'CANCELLED'})
        self.assertEqual(snapshot(obj.active_material), before)

    def test_recolour_never_reuses_an_image_outside_the_chosen_folder(self):
        obj = make_mesh()
        old = self.image_file('old/hero_body_albedoTexture.png')
        bpy.data.images.load(str(old))
        empty = self.folder / 'new-skin'
        empty.mkdir()
        results, images = autotex.resolve_from_folder(obj.active_material, [R.ALBEDO], str(empty))
        self.assertFalse(images)
        self.assertFalse(results[R.ALBEDO].resolved)

    def test_preparation_is_idempotent_and_preserves_position_selection(self):
        rig = make_rig()
        rig.rotation_mode = 'QUATERNION'
        rig.location = (2, 3, 4)
        obj = make_mesh()
        obj.parent = rig
        select(rig, obj)
        bpy.context.view_layer.update()
        position = rig.matrix_world.translation.copy()
        bpy.ops.object.ef_button_spawn(cool_effect='adjust_model')
        self.assertEqual(rig.rotation_mode, 'XYZ')
        self.assertTrue(all(bone.rotation_mode == 'XYZ' for bone in rig.pose.bones))
        matrix = rig.matrix_world.copy()
        bpy.ops.object.ef_button_spawn(cool_effect='adjust_model')
        self.assertEqual(rig.matrix_world, matrix)
        self.assertEqual(rig.matrix_world.translation, position)
        self.assertAlmostEqual(rig.scale.x, 0.0254)
        self.assertEqual(set(bpy.context.selected_objects), {rig, obj})
        self.assertEqual(bpy.context.view_layer.objects.active, rig)

    def test_item_rig_snaps_to_hand_and_follows_pose(self):
        legend = make_rig()
        legend.name = 'legend'
        legend.data.bones['child'].name = 'ja_l_propHand'
        legend.location = (2, 3, 4)
        legend.pose.bones['ja_l_propHand'].rotation_euler = (0.2, 0.1, -0.3)
        item = make_rig()
        item.name = 'item'
        mesh = make_mesh('item_mesh')
        mesh.parent = item
        scene = bpy.context.scene
        scene.apex_attachment_legend = legend
        scene.apex_attachment_item = item
        select(legend, item)
        bpy.context.view_layer.update()
        expected = legend.matrix_world @ legend.pose.bones['ja_l_propHand'].matrix
        self.assertEqual(bpy.ops.object.apex_pair_item(socket='LEFT_HAND'), {'FINISHED'})
        self.assertEqual(item.parent, legend)
        self.assertEqual(item.parent_type, 'BONE')
        self.assertEqual(item.parent_bone, 'ja_l_propHand')
        self.assertEqual(mesh.parent, item)
        assert_matrix_close(self, item.matrix_world, expected)

        legend.pose.bones['ja_l_propHand'].rotation_euler = (0.4, -0.2, 0.5)
        bpy.context.view_layer.update()
        expected = legend.matrix_world @ legend.pose.bones['ja_l_propHand'].matrix
        assert_matrix_close(self, item.matrix_world, expected)

    def test_missing_attachment_bone_preserves_item(self):
        legend = make_rig()
        item = make_rig()
        scene = bpy.context.scene
        scene.apex_attachment_legend = legend
        scene.apex_attachment_item = item
        select(legend, item)
        bpy.context.view_layer.update()
        before = item.matrix_world.copy()
        with self.assertRaisesRegex(RuntimeError, 'no weapon attachment bone'):
            bpy.ops.object.apex_pair_item(socket='WEAPON')
        self.assertIsNone(item.parent)
        assert_matrix_close(self, item.matrix_world, before)

    def test_selected_rigs_can_pair_weapon_and_other_bone(self):
        legend = make_rig()
        legend.data.bones['child'].name = 'ja_c_propGun'
        item = make_rig()
        select(item, legend)
        self.assertEqual(bpy.ops.object.apex_use_selected_attachment_rigs(), {'FINISHED'})
        scene = bpy.context.scene
        self.assertEqual(scene.apex_attachment_legend, legend)
        self.assertEqual(scene.apex_attachment_item, item)
        self.assertEqual(bpy.ops.object.apex_pair_item(socket='WEAPON'), {'FINISHED'})
        self.assertEqual(item.parent_bone, 'ja_c_propGun')
        scene.apex_attachment_bone = 'root'
        self.assertEqual(bpy.ops.object.apex_pair_item(socket='CUSTOM'), {'FINISHED'})
        self.assertEqual(item.parent_bone, 'root')

    def test_existing_prepared_scale_is_not_converted_again(self):
        rig = bpy.data.objects.new('rig', bpy.data.armatures.new('rig'))
        bpy.context.collection.objects.link(rig)
        rig.scale = (0.0254,) * 3
        bpy.context.view_layer.update()
        matrix = rig.matrix_world.copy()
        self.assertEqual(health.prepare_armatures([rig]), (0, 1))
        self.assertEqual(rig.matrix_world, matrix)

    def test_xyz_preserves_model_world_transforms_pose_and_selection(self):
        rig = make_rig()
        parent = bpy.data.objects.new('model_root', None)
        bpy.context.collection.objects.link(parent)
        parent.rotation_euler = (0.2, -0.3, 0.4)
        parent.scale = (1.5, 0.8, 1.2)
        rig.parent = parent
        rig.rotation_mode = 'QUATERNION'
        rig.rotation_quaternion = Euler((0.35, 0.2, -0.8)).to_quaternion()
        rig.delta_rotation_quaternion = Euler((0.2, -0.1, 0.05)).to_quaternion()
        rig.location, rig.scale = (2, 3, 4), (-1.2, 0.9, 1.1)
        for bone in rig.pose.bones:
            bone.rotation_quaternion = Euler((0.3, -0.2, 0.5)).to_quaternion()
        mesh = make_mesh()
        mesh.parent = rig
        mesh.rotation_mode = 'QUATERNION'
        mesh.rotation_quaternion = Euler((0.15, 0.25, -0.35)).to_quaternion()
        untouched = make_mesh('other_model')
        untouched.rotation_mode = 'QUATERNION'
        select(mesh)  # Choosing the model's mesh also finds its rig.
        bpy.context.view_layer.update()
        before = {obj: obj.matrix_world.copy() for obj in (parent, rig, mesh, untouched)}
        pose = {bone.name: bone.matrix.copy() for bone in rig.pose.bones}
        self.assertEqual(bpy.ops.object.apex_xyz_euler(), {'FINISHED'})
        bpy.context.view_layer.update()
        self.assertEqual((rig.rotation_mode, mesh.rotation_mode), ('XYZ', 'XYZ'))
        self.assertEqual(untouched.rotation_mode, 'QUATERNION')
        for obj, matrix in before.items():
            assert_matrix_close(self, obj.matrix_world, matrix)
        for bone in rig.pose.bones:
            self.assertEqual(bone.rotation_mode, 'XYZ')
            assert_matrix_close(self, bone.matrix, pose[bone.name])
        self.assertEqual(list(bpy.context.selected_objects), [mesh])
        self.assertEqual(bpy.context.view_layer.objects.active, mesh)
        self.assertEqual(health.use_xyz_euler([rig, mesh], rig.pose.bones), (0, 0, 0))

    def test_xyz_in_pose_mode_only_changes_selected_bones(self):
        rig = make_rig()
        root, child = rig.pose.bones['root'], rig.pose.bones['child']
        root.rotation_quaternion = Euler((0.3, 0.4, -0.5)).to_quaternion()
        bpy.context.view_layer.update()
        before = root.matrix.copy()
        bpy.ops.object.mode_set(mode='POSE')
        try:
            for bone in rig.data.bones:
                bone.select = bone.name == 'root'
            rig.data.bones.active = rig.data.bones['root']
            self.assertEqual(bpy.ops.object.apex_xyz_euler(), {'FINISHED'})
            bpy.context.view_layer.update()
            self.assertEqual(root.rotation_mode, 'XYZ')
            self.assertEqual(child.rotation_mode, 'QUATERNION')
            assert_matrix_close(self, root.matrix, before)
            self.assertEqual(bpy.context.mode, 'POSE')
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')

    def test_xyz_does_not_disable_existing_animation_nla_drivers_or_constraints(self):
        rig = make_rig()
        rig.rotation_mode = 'QUATERNION'
        rig.pose.bones['root'].keyframe_insert('rotation_quaternion', frame=1)
        action = rig.animation_data.action
        self.assertEqual(health.use_xyz_euler([rig], rig.pose.bones), (0, 0, 3))
        self.assertIs(rig.animation_data.action, action)
        track = rig.animation_data.nla_tracks.new()
        track.strips.new('animation', 1, action)
        rig.animation_data.action = None
        self.assertEqual(health.use_xyz_euler([rig], rig.pose.bones), (0, 0, 3))
        obj = make_mesh()
        obj.rotation_mode = 'QUATERNION'
        obj.driver_add('rotation_quaternion', 0).driver.expression = '1.0'
        self.assertEqual(health.use_xyz_euler([obj]), (0, 0, 1))
        obj.animation_data_clear()
        obj.constraints.new('COPY_ROTATION')
        self.assertEqual(health.use_xyz_euler([obj]), (0, 0, 1))
        self.assertEqual(obj.rotation_mode, 'QUATERNION')

    def test_xyz_is_applied_to_already_prepared_models_without_resizing(self):
        rig = make_rig()
        rig.scale = (0.0254,) * 3
        rig.rotation_mode = 'QUATERNION'
        rig.rotation_quaternion = Euler((0.3, 0.4, 0.5)).to_quaternion()
        bpy.context.view_layer.update()
        before = rig.matrix_world.copy()
        self.assertEqual(bpy.ops.object.ef_button_spawn(cool_effect='adjust_model'), {'FINISHED'})
        bpy.context.view_layer.update()
        self.assertEqual(rig.rotation_mode, 'XYZ')
        assert_matrix_close(self, rig.matrix_world, before)

    def test_scene_scope_checks_camera_and_selection_scope_does_not(self):
        select(make_mesh())
        bpy.context.scene.camera = None
        bpy.ops.object.apex_check_scene()
        self.assertNotIn('NO_CAMERA', {item.code for item in self.prefs.health_issues})
        self.prefs.health_scope = 'VIEW_LAYER'
        bpy.ops.object.apex_check_scene()
        self.assertIn('NO_CAMERA', {item.code for item in self.prefs.health_issues})

    def test_deleted_issue_object_can_be_selected_safely(self):
        obj = make_mesh(uv=False)
        select(obj)
        bpy.ops.object.apex_check_scene()
        bpy.data.objects.remove(obj, do_unlink=True)
        self.assertEqual(bpy.ops.object.apex_select_issues(), {'CANCELLED'})

    def test_lite_staging_assets_can_be_appended(self):
        self.assertEqual(bpy.ops.object.lb_button_spawn(lobby_other='Animated Staging'), {'FINISHED'})
        self.assertIn('Staging Camera', bpy.data.objects)
        bpy.ops.object.ef_button_spawn(cool_effect='Staging Camera')
        self.assertEqual(bpy.context.scene.camera.name, 'Staging Camera')

    def test_existing_lite_effects_still_append(self):
        calls = [
            (bpy.ops.object.wr_button_portal, {}),
            (bpy.ops.object.gb_button_items, {'gibby': 'Gibby bubble friendly'}),
            (bpy.ops.object.vk_button_items, {'valk': 'Flames'}),
            (bpy.ops.object.seer_button_spawn, {'lgnd_effect': 'Seer Ultimate'}),
            (bpy.ops.object.wpn_button_spawn, {'weapon': 'Laser'}),
            (bpy.ops.object.ef_button_spawn, {'cool_effect': 'basic lights'}),
        ]
        for operator, kwargs in calls:
            with self.subTest(operator=str(operator)):
                self.assertEqual(operator(**kwargs), {'FINISHED'})
        for name in ['wraith_portal', 'Gibby bubble friendly', 'Flames left', 'Laser']:
            self.assertIn(name, bpy.data.objects)


    def test_wireframe_repeat_and_removal(self):
        obj = make_mesh()
        select(obj)
        for _ in range(2):
            bpy.ops.object.ef_button_spawn(cool_effect='wireframe')
        self.assertEqual(len(obj.modifiers), 1)
        bpy.ops.object.ef_button_spawn(cool_effect='wireframe_clear')
        self.assertEqual(len(obj.modifiers), 0)

    def test_report_open_starts_at_first_line(self):
        select(make_mesh())
        self.image_file()
        bpy.ops.object.button_custom()
        report = self.prefs.texture_report
        self.assertEqual(report.current_line_index, 0)
        self.assertEqual(report.select_end_line_index, 0)
        self.assertEqual(bpy.ops.object.apex_report(kind='texture'), {'FINISHED'})

    def test_search_without_materials_and_empty_selection_are_graceful(self):
        select()
        self.assertFalse(bpy.ops.object.button_custom.poll())
        select(make_mesh(material=False))
        self.assertEqual(bpy.ops.object.button_custom(), {'CANCELLED'})


if __name__ == '__main__':
    selected_tests = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    suite = (unittest.defaultTestLoader.loadTestsFromNames(
        ['BlenderIntegration.' + name for name in selected_tests], module=sys.modules[__name__])
        if selected_tests else unittest.defaultTestLoader.loadTestsFromTestCase(BlenderIntegration))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise RuntimeError('Blender integration tests failed')
