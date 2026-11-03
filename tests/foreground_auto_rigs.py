"""Automatic import linking, Undo and cancellation in disposable UI Blender.

Run without --background. --release uses the packaged ZIP. This fixture closes
only its own Blender process and writes an explicit pass/fail result.
"""
import json
from pathlib import Path
import sys
import tempfile
import time
import traceback
from unittest.mock import patch

import addon_utils
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import workflow_integration as fixtures

addon = fixtures.addon
addon_utils.enable('io_scene_cast', default_set=False)
addon.register()
_, cast, _ = addon.apex_workflows.cast_modules()
temporary = tempfile.TemporaryDirectory()
folder = Path(temporary.name)
cache_patch = patch.object(addon.apex_animations, 'index_cache_root', return_value=folder / 'cache')
fallback_patch = patch.object(addon.apex_auto_rigs, '_fallback_roots', return_value=[])
cache_patch.start()
fallback_patch.start()
mdl = folder / 'mdl'
skins = ('wraith_base', 'wraith_lgnd_v01_test_w', 'ash_base')
for skin in skins:
    path = mdl / skin / (skin + '_LOD0.cast')
    path.parent.mkdir(parents=True)
    fixtures.model_file(cast, path)
for legend in ('wraith', 'ash'):
    name = 'pilot_medium_' + legend
    path = folder / 'animrig' / name / (name + '.cast')
    path.parent.mkdir(parents=True)
    fixtures.model_file(cast, path, mesh=False)
    sequences = path.parent / ('anims_' + name)
    sequences.mkdir()
    for index in range(30):
        fixtures.animation_file(cast, sequences / ('clip_%02d.cast' % index), names=('idle_%02d' % index,))

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
bpy.context.preferences.edit.use_global_undo = True
result_path = ROOT / 'artifacts' / ('auto-rigs-foreground-%s.json' % '.'.join(map(str, bpy.app.version[:2])))
result_path.parent.mkdir(exist_ok=True)
phase = 0
names = []
scan_count = 0
deadline = time.monotonic() + 90
started = time.monotonic()
transforms = None


class Reporter:
    def report(self, level, message):
        print('AUTO RIG FIXTURE:', message, flush=True)


def rigs():
    return [bpy.data.objects[name] for name in names if name in bpy.data.objects]


def transform_state():
    return {rig.name: tuple(tuple(row) for row in rig.matrix_world) for rig in rigs()}


def quit_fixture(passed, error=None):
    addon.cancel_animation_scan()
    result_path.write_text(json.dumps({'passed': passed, 'error': error,
        'blender': bpy.app.version_string, 'elapsed_seconds': round(time.monotonic() - started, 3),
        'checks': 'batch default, index reuse, row placement, Undo/Redo, cancel, save, deleted anchor, selection change'}, indent=2), encoding='utf-8')
    print('AUTO RIG EVENT LOOP CHECKS %s' % ('PASSED' if passed else 'FAILED'), flush=True)
    addon.unregister()
    cache_patch.stop()
    fallback_patch.stop()
    temporary.cleanup()
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
        bpy.ops.wm.quit_blender()


def tick():
    global phase, names, transforms, scan_count
    try:
        assert time.monotonic() < deadline, 'Auto-link fixture timed out'
        with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
            if phase == 0:
                bpy.ops.ed.undo_push(message='Before batch model import')
                assert bpy.ops.object.apex_import_texture(
                    ui_stage='CHOOSE', parent_folder=str(mdl),
                    folder_items=[{'name': skin, 'selected': True} for skin in skins]) == {'FINISHED'}
                names = [obj.name for obj in bpy.context.selected_objects if obj.type == 'ARMATURE']
                assert len(names) == 3
                assert addon._active_animation_scan is not None
                assert not bpy.ops.object.apex_import_texture.poll()
                assert not any(rig.apex_animation_library.rig_file for rig in rigs())
                transforms = transform_state()
                bpy.ops.ed.undo_push(message='Imported models before automatic linking')
                phase = 1
            elif phase == 1:
                if addon._active_animation_scan is not None:
                    scan_count = len(addon._active_animation_scan.job.scans)
                    return 0.01
                assert all(len(rig.apex_animation_library.clips) == 30 for rig in rigs()), [
                    rig.apex_animation_library.summary for rig in rigs()]
                assert all(not rig.animation_data or not rig.animation_data.action for rig in rigs())
                assert transform_state() == transforms
                assert bpy.ops.object.apex_import_texture.poll()
                phase = 2
            elif phase == 2:
                assert bpy.ops.ed.undo() == {'FINISHED'}
                assert len(rigs()) == 3, 'Undo of linking removed imported models'
                assert not any(rig.apex_animation_library.rig_file for rig in rigs())
                assert transform_state() == transforms
                phase = 3
            elif phase == 3:
                assert bpy.ops.ed.redo() == {'FINISHED'}
                assert all(len(rig.apex_animation_library.clips) == 30 for rig in rigs())
                assert transform_state() == transforms
                phase = 4
            elif phase == 4:
                assert bpy.ops.ed.undo() == {'FINISHED'}
                fixtures.select(rigs()[0])
                assert bpy.ops.object.apex_auto_link_animation_rig() == {'FINISHED'}
                assert addon._active_animation_scan is not None
                assert bpy.ops.object.apex_cancel_animation_scan() == {'FINISHED'}
                assert addon._active_animation_scan is None
                assert not any(rig.apex_animation_library.rig_file for rig in rigs())
                assert transform_state() == transforms
                phase = 5
            elif phase == 5:
                assert bpy.ops.object.apex_auto_link_animation_rig() == {'FINISHED'}
                bpy.ops.wm.save_as_mainfile(filepath=str(folder / 'cancel-on-save.blend'))
                assert addon._active_animation_scan is None
                assert not any(rig.apex_animation_library.rig_file for rig in rigs())
                assert 'cancelled' in rigs()[0].apex_animation_library.summary.lower()
                phase = 6
            elif phase == 6:
                assert addon.start_auto_rig_links(bpy.context, rigs(), Reporter()) == {'FINISHED'}
                removed = rigs()[0]
                bpy.data.objects.remove(removed, do_unlink=True)
                bpy.ops.mesh.primitive_cube_add()
                phase = 7
            elif phase == 7:
                if addon._active_animation_scan is not None:
                    return 0.01
                assert len(rigs()) == 2
                assert all(len(rig.apex_animation_library.clips) == 30 for rig in rigs())
                assert bpy.context.active_object.type == 'MESH', 'Auto-link stole the new selection'
                assert all(transform_state()[rig.name] == transforms[rig.name] for rig in rigs())
                quit_fixture(True)
                return None
        return 0.03
    except Exception:
        error = traceback.format_exc()
        print(error, flush=True)
        quit_fixture(False, error)
        return None


bpy.app.timers.register(tick, first_interval=0.5, persistent=True)
