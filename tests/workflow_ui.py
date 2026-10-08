"""Disposable UI fixture: blender --factory-startup --python tests/workflow_ui.py."""
from pathlib import Path
import sys
import struct

import addon_utils
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from workflow_integration import addon, model_file, animation_file

addon_utils.enable('io_scene_cast', default_set=False)
addon.register()
_, cast, _ = addon.apex_workflows.cast_modules()
folder = ROOT / 'artifacts' / ('workflow-fixture-' + addon.ver[1:])
folder.mkdir(parents=True, exist_ok=True)
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
model_file(cast, folder / 'legend.cast')
model_file(cast, folder / 'legend_rig.cast', mesh=False)
sequences = folder / 'anims_legend_rig'
sequences.mkdir(exist_ok=True)
animation_file(cast, sequences / 'idle.cast')
animation_file(cast, sequences / 'locomotion.cast', names=('walk_forward', 'run_forward', 'crouch_idle'))
animation_file(cast, sequences / 'categories.cast', names=('gladcard_intro', 'emote_wave', 'lobby_idle', 'execution_test'))
# Synthetic animation content carrying one known RSX sequence identifier verifies
# automatic labels from the packaged catalogue, without importing name metadata.
path = sequences / 'categories.cast'
data = bytearray(path.read_bytes())
guid = addon.apex_animations.animation_names.string_guid(
    'animseq/humans/class/light/pilot_light_wraith/wraith_gladcard_animated_bluesteel.rseq')
struct.pack_into('<Q', data, 48, guid)
path.write_bytes(data)
image = bpy.data.images.new('test_body_col', width=8, height=8)
image.generated_color = (0.1, 0.5, 0.8, 1)
image.filepath_raw = str(folder / 'test_body_col.png')
image.file_format = 'PNG'
image.save()
bpy.data.images.remove(image)
bpy.ops.object.apex_import_texture(filepath=str(folder / 'legend.cast'))
addon.apex_animations.link_library(bpy.context.active_object, str(folder / 'legend_rig.cast'))
library = bpy.context.active_object.apex_animation_library
assert library.clips[0].menu_name == 'Window to the Soul'
assert library.clips[0].menu_source == 'BUILTIN'
assert not library.names_file
library.show_name_options = '--options' in sys.argv
if '--before-animation' not in sys.argv:
    bpy.ops.object.apex_load_animation()
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.show_region_ui = True
            area.spaces.active.region_3d.view_distance = 0.2
            area.spaces.active.region_3d.view_location = (0, 0, 0)
bpy.ops.wm.save_as_mainfile(filepath=str(folder / ('Apex Toolbox %s UI Test.blend' % addon.ver[1:])))
# Startup scripts do not create the UI undo history that normal clicks do.
# Seed the fixture so the first manually tested operator has a valid baseline.
bpy.ops.ed.undo_push(message='Apex workflow test ready')
print('WORKFLOW UI FIXTURE READY', flush=True)
