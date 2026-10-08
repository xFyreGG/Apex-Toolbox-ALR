"""Disposable foreground test for cancellable names, Undo/Redo and cleanup."""
from pathlib import Path
import json
import struct
import sys
import tempfile
import time
import traceback

import bpy
import addon_utils

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from workflow_integration import addon, model_file, animation_file, make_rig
from Apex_toolbox.apex_tex import animation_names

addon_utils.enable('io_scene_cast', default_set=False)
addon.register()
_, cast, _ = addon.apex_workflows.cast_modules()
temporary = tempfile.TemporaryDirectory()
folder = Path(temporary.name)
rig_path = folder / 'legend.cast'
model_file(cast, rig_path, mesh=False)
sequences = folder / 'anims_legend'
sequences.mkdir()
clip_path = sequences / 'emote.cast'
animation_file(cast, clip_path)
reference = 'animseq/humans/test/fixture.rseq'
data = bytearray(clip_path.read_bytes())
struct.pack_into('<Q', data, 48, animation_names.string_guid(reference))
clip_path.write_bytes(data)
rig = make_rig()
rig_name = rig.name
addon.apex_animations.link_library(rig, str(rig_path))
rig.apex_animation_library.clips[0].menu_name = 'Before Import'
localization = folder / 'localization'
localization.mkdir()
locl = localization / 'test.locl'
locl.write_text('"test"\n{\n"%x" "Fixture Name"\n}\n' % animation_names.string_guid('TEST_NAME'))
settings = folder / 'settings' / 'itemflav' / 'skydive_emote' / 'test'
settings.mkdir(parents=True)
body = json.dumps({'settings': {'itemType': 'skydive_emote', 'localizationKey_NAME': '#TEST_NAME',
                               'animSequence': reference}})
for i in range(1000):
    (settings / ('%04d.json' % i)).write_text(body)
blend_path = folder / 'names.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
bpy.ops.ed.undo_push(message='Name import baseline')
phase, heartbeats = 0, 0
deadline = time.monotonic() + 60


def start():
    assert bpy.ops.object.apex_import_animation_names(filepath=str(locl)) == {'FINISHED'}
    assert addon._active_animation_scan is not None


def tick():
    global phase, heartbeats
    window = bpy.context.window_manager.windows[0]
    with bpy.context.temp_override(window=window):
        try:
            assert time.monotonic() < deadline
            library = bpy.data.objects[rig_name].apex_animation_library
            if phase == 0:
                # Establish history after Blender has initialized its event loop.
                bpy.ops.ed.undo_push(message='Name import baseline in event loop')
                start()
                bpy.ops.object.apex_cancel_animation_scan()
                assert library.clips[0].menu_name == 'Before Import'
                phase = 1
            elif phase == 1:
                start()
                phase = 2
            elif phase == 2:
                if addon._active_animation_scan:
                    heartbeats += 1
                    assert library.clips[0].menu_name == 'Before Import'
                else:
                    assert heartbeats > 0
                    assert library.clips[0].menu_name == 'Fixture Name'
                    assert library.clips[0].menu_source == 'CUSTOM'
                    phase = 3
            elif phase == 3:
                bpy.ops.ed.undo()
                assert bpy.data.objects[rig_name].apex_animation_library.clips[0].menu_name == 'Before Import'
                assert bpy.data.objects[rig_name].apex_animation_library.clips[0].menu_source == ''
                phase = 4
            elif phase == 4:
                bpy.ops.ed.redo()
                assert bpy.data.objects[rig_name].apex_animation_library.clips[0].menu_name == 'Fixture Name'
                assert bpy.data.objects[rig_name].apex_animation_library.clips[0].menu_source == 'CUSTOM'
                phase = 5
            elif phase == 5:
                start()
                bpy.ops.wm.open_mainfile(filepath=str(blend_path))
                assert addon._active_animation_scan is None
                phase = 6
            elif phase == 6:
                start()
                addon.unregister()
                assert addon._active_animation_scan is None
                temporary.cleanup()
                print('ANIMATION NAMES CHECKS PASSED: atomic completion, responsive ticks %d, cancel, Undo/Redo, load/disable cleanup' % heartbeats, flush=True)
                bpy.ops.wm.quit_blender()
                return None
            return 0.02
        except Exception:
            traceback.print_exc()
            addon.cancel_animation_scan()
            print('ANIMATION NAMES CHECKS FAILED', flush=True)
            bpy.ops.wm.quit_blender()
            return None


bpy.app.timers.register(tick, first_interval=0.5, persistent=True)
