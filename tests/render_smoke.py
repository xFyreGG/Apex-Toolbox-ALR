"""Render the three supported shaders and prepare an optional UI test scene.

blender -b --factory-startup --python-exit-code 1 --python tests/render_smoke.py
blender --factory-startup --python tests/render_smoke.py -- --ui
"""
from pathlib import Path
import math
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import Apex_toolbox as addon
from Apex_toolbox.apex_tex import roles as R, shaders, autotex

addon.register()
autotex.browsed_directories = lambda: []
output = ROOT / 'artifacts'
output.mkdir(exist_ok=True)

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

targets = []
colors = [(0.34, 0.018, 0.026, 1), (0.014, 0.20, 0.23, 1), (0.4, 0.20, 0.025, 1)]
for i, definition in enumerate(shaders.SHADER_DEFS.values()):
    addon.append_apex_node_group(definition.group_name)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=((i - 1) * 2.5, 0, 1.05))
    obj = bpy.context.object
    obj.name = definition.group_name + ' sample'
    targets.append(obj)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    mat = bpy.data.materials.new(definition.group_name + ' sample')
    mat.use_nodes = True
    obj.data.materials.append(mat)
    images = {}
    for role, color in [(R.ALBEDO, colors[i]), (R.SPECULAR, (0.15, 0.15, 0.15, 1)),
                        (R.ROUGHNESS, (0.35, 0.35, 0.35, 1)), (R.NORMAL, (0.5, 0.5, 1, 1))]:
        image = bpy.data.images.new('%s_%s' % (obj.name, role), width=32, height=32)
        image.generated_color = color
        images[role] = image
    shaders.build_material(mat, definition, images)

bpy.ops.mesh.primitive_plane_add(size=200)
floor = bpy.context.object
floor.name = 'Test floor'
mat = bpy.data.materials.new('Test floor')
mat.use_nodes = True
mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.018, 0.022, 0.03, 1)
mat.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.42
floor.data.materials.append(mat)

for location, energy, size in [((0, -4, 7), 1300, 6), ((3, 2, 6), 1700, 5)]:
    light = bpy.data.lights.new('Test area', 'AREA')
    light.energy = energy
    light.shape = 'DISK'
    light.size = size
    obj = bpy.data.objects.new('Test area', light)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector((0, 0, 0.8)) - obj.location).to_track_quat('-Z', 'Y').to_euler()

camera = bpy.data.objects.new('Test camera', bpy.data.cameras.new('Test camera'))
bpy.context.collection.objects.link(camera)
camera.location = (0, -13, 5.4)
camera.rotation_euler = (Vector((0, 0, 1)) - camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 9.3
scene = bpy.context.scene
scene.camera = camera
scene.world = bpy.data.worlds.new('Test world')
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.15, 0.18, 0.23, 1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.25
scene.render.engine = 'CYCLES'
scene.cycles.samples = 16
scene.cycles.use_denoising = True
scene.render.resolution_x = 900
scene.render.resolution_y = 400
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(output / 'shader-preview.png')
for obj in bpy.context.selected_objects:
    obj.select_set(False)
for obj in targets:
    obj.select_set(True)
bpy.context.view_layer.objects.active = targets[0]
scene.my_prefs.autotex_folder = ''
if '--ui' in sys.argv:
    # A controlled issue makes the health list and selection controls visible.
    targets[2].data.uv_layers.remove(targets[2].data.uv_layers[0])
bpy.ops.object.apex_check_scene()
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.show_region_ui = True
            area.spaces.active.region_3d.view_perspective = 'CAMERA'

if '--ui' not in sys.argv:
    bpy.ops.render.render(write_still=True)
    result = bpy.data.images.load(scene.render.filepath, check_existing=False)
    assert tuple(result.size) == (900, 400)
    pixels = list(result.pixels)
    assert max(pixels[0::4]) - min(pixels[0::4]) > 0.1, 'Render is blank'
    assert sum(1 for r, g, b in zip(pixels[0::4], pixels[1::4], pixels[2::4])
               if r > 0.9 and b > 0.9 and g < 0.1) < 100, 'Render contains missing-texture magenta'
    bpy.data.images.remove(result)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / 'shader-preview.blend'))
    print('THREE-SHADER RENDER PASSED')
