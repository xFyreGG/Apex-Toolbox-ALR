"""Foreground event-loop checks in a disposable --factory-startup Blender.

No UI input or user preferences are changed. The script quits its own process.
The launcher must check for ANIMATION SCAN CHECKS PASSED and a clean process exit.
"""
from pathlib import Path
import sys
import tempfile
import time
import traceback

import bpy
import addon_utils

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from workflow_integration import model_file, animation_file, make_rig
import Apex_toolbox as addon

addon_utils.enable('io_scene_cast', default_set=False)
addon.register()
_, cast, _ = addon.apex_workflows.cast_modules()
temporary = tempfile.TemporaryDirectory()
folder = Path(temporary.name)
rig_path = folder / 'legend.cast'
model_file(cast, rig_path, mesh=False)
sequences = folder / 'anims_legend'
sequences.mkdir()
animation_file(cast, sequences / 'idle.cast')
rig = make_rig()
rig_name = rig.name
addon.apex_animations.link_library(rig, str(rig_path))
blend_path = folder / 'scan.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
animation_file(cast, sequences / 'large.cast', names=tuple('lobby_clip_%d' % i for i in range(6000)))

phase, heartbeats = 0, 0
deadline = time.monotonic() + 60


def start_refresh():
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
        assert bpy.ops.object.apex_refresh_animations() == {'FINISHED'}
    assert addon._active_animation_scan is not None


def quit_fixture():
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
        bpy.ops.wm.quit_blender()


def tick():
    global phase, heartbeats, rig
    try:
        assert time.monotonic() < deadline, 'Scan did not finish in the fixture timeout'
        if phase == 0:
            with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
                bpy.ops.ed.undo_push(message='Animation scan baseline in event loop')
            start_refresh()
            assert not bpy.ops.object.apex_load_animation.poll()
            assert len(rig.apex_animation_library.clips) == 1
            assert bpy.ops.object.apex_cancel_animation_scan() == {'FINISHED'}
            assert addon._active_animation_scan is None
            assert len(rig.apex_animation_library.clips) == 1
            phase = 1
        elif phase == 1:
            start_refresh()
            phase = 2
        elif phase == 2:
            if addon._active_animation_scan is not None:
                heartbeats += 1
                assert len(rig.apex_animation_library.clips) == 1
            else:
                assert heartbeats > 1, 'The event loop must run during a large scan'
                assert len(rig.apex_animation_library.clips) == 6001
                assert not rig.apex_animation_library.summary.endswith('not indexed.')
                print('COMPLETE: 6001 clips; %d responsive timer ticks' % heartbeats, flush=True)
                phase = 30
        elif phase == 30:
            with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
                bpy.ops.ed.undo()
            rig = bpy.data.objects[rig_name]
            assert len(rig.apex_animation_library.clips) == 1
            phase = 31
        elif phase == 31:
            with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
                bpy.ops.ed.redo()
            rig = bpy.data.objects[rig_name]
            assert len(rig.apex_animation_library.clips) == 6001
            phase = 3
        elif phase == 3:
            start_refresh()
            addon.unregister()
            assert addon._active_animation_scan is None
            assert addon.cancel_animation_scan not in bpy.app.handlers.load_pre
            addon.register()
            assert bpy.app.handlers.load_pre.count(addon.cancel_animation_scan) == 1
            phase = 4
        elif phase == 4:
            start_refresh()
            bpy.ops.wm.open_mainfile(filepath=str(blend_path))
            assert addon._active_animation_scan is None
            phase = 5
        elif phase == 5:
            addon.unregister()
            temporary.cleanup()
            print('ANIMATION SCAN CHECKS PASSED: completion, responsive UI loop, Undo/Redo, cancellation, disable and file-load cleanup', flush=True)
            quit_fixture()
            return None
        return 0.01
    except Exception:
        traceback.print_exc()
        addon.cancel_animation_scan()
        print('ANIMATION SCAN CHECKS FAILED', flush=True)
        quit_fixture()
        return None


bpy.app.timers.register(tick, first_interval=0.5, persistent=True)
