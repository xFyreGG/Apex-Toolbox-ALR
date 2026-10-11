"""Relink, animation layers and model review in disposable foreground Blender.

Run without --background. The fixture uses real event-loop ticks and Undo/Redo,
writes an explicit JSON result, then closes only its own Blender process.
Append -- --release to exercise the built ZIP.
"""
import json
from pathlib import Path
import sys
import time
import traceback
from unittest.mock import patch

import addon_utils
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
import workflow_integration as fixtures
from relink import RelinkTests

addon = fixtures.addon
addon_utils.enable('io_scene_cast', default_set=False)
addon.register()
_, cast, _ = addon.apex_workflows.cast_modules()
case = RelinkTests()
case.cast = cast
case.setUp()
for setting in (patch.object(addon.apex_autotex, 'browsed_directories', return_value=[]),
                patch.object(addon, 'remembered_texture_roots', return_value=[])):
    setting.start()
    case.addCleanup(setting.stop)
folder = Path(case.temp.name)
hands_path = case.sequence.parent / 'hands.cast'
fixtures.animation_file(cast, hands_path, names=('hands',), additive=True)
addon.apex_animations.link_library(case.rig, str(case.export))
library = case.rig.apex_animation_library
base_index = next(i for i, clip in enumerate(library.clips) if clip.name == 'idle')
hands_index = next(i for i, clip in enumerate(library.clips) if clip.name == 'hands')
library.index = base_index
addon.apex_animations.load_clip(bpy.context, case.rig, library.clips[base_index], allow_missing=True)
base_name = case.rig.animation_data.action.name
library.index = hands_index
case.rig.location = (4, 5, 6)
fixtures.select(case.rig)
bpy.context.view_layer.update()
rig_name, mesh_name = case.rig.name, case.mesh.name
initial_objects = {obj.name for obj in bpy.data.objects}
initial_matrix = tuple(tuple(row) for row in case.rig.matrix_world)
# The copied library was made before the additive fixture was added.
target_hands = case.moved(hands_path)
target_hands.write_bytes(hands_path.read_bytes())
second_model = case.new / 'mdl' / 'ash_base' / 'ash_base_LOD0.cast'
second_model.parent.mkdir()
fixtures.model_file(cast, second_model)
review_files = [str(case.moved(case.model)), str(second_model)]
texture_folder = case.moved(case.model.parent)
(texture_folder / 'test_body_col.png').write_bytes((texture_folder / 'body_col.png').read_bytes())
bpy.context.preferences.edit.use_global_undo = True
result_path = ROOT / 'artifacts' / ('release-tools-foreground-%s.json' %
                                  '.'.join(map(str, bpy.app.version[:2])))
result_path.parent.mkdir(exist_ok=True)
phase, popup_ticks = 0, 0
checks = []
started = time.monotonic()
deadline = started + 90


def rig():
    return bpy.data.objects[rig_name]


def library_state():
    return rig().apex_animation_library


def assert_base():
    current = rig()
    assert current.animation_data.action is not None
    assert current.animation_data.action.name == base_name
    assert not current.animation_data.nla_tracks
    assert tuple(tuple(row) for row in current.matrix_world) == initial_matrix


def assert_layers(strength):
    current = rig()
    strips = addon.apex_layers.layers(current)
    assert len(strips) == 1, 'Expected one additive layer'
    assert len(current.animation_data.nla_tracks) == 2
    assert current.animation_data.action is None
    assert abs(addon.apex_layers.influence(strips[0]) - strength) < 1e-5
    assert tuple(tuple(row) for row in current.matrix_world) == initial_matrix


def push(message):
    # Python timer calls do not pass through the native button Undo dispatch.
    # Explicit snapshots model the same before/after state native clicks create.
    assert bpy.ops.ed.undo_push(message=message) == {'FINISHED'}


def quit_fixture(passed, error=None):
    result_path.write_text(json.dumps({
        'passed': passed, 'error': error, 'blender': bpy.app.version_string,
        'background': bpy.app.background,
        'elapsed_seconds': round(time.monotonic() - started, 3), 'checks': checks,
    }, indent=2), encoding='utf-8')
    print('RELEASE TOOLS EVENT LOOP CHECKS %s' % ('PASSED' if passed else 'FAILED'), flush=True)
    case.doCleanups()
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
        bpy.ops.wm.quit_blender()


def tick():
    global phase, popup_ticks
    try:
        assert not bpy.app.background, 'Run this fixture without --background'
        assert time.monotonic() < deadline, 'Release tools fixture timed out'
        window = bpy.context.window_manager.windows[0]
        area = next((area for area in window.screen.areas if area.type == 'VIEW_3D'), window.screen.areas[0])
        region = next(region for region in area.regions if region.type == 'WINDOW')
        with bpy.context.temp_override(window=window, area=area, region=region):
            if phase == 0:
                push('Before RSX library relink')
                assert bpy.ops.object.apex_apply_rsx_relink(
                    old_root=str(case.old), new_root=str(case.new)) == {'FINISHED'}
                push('Relinked RSX library')
            elif phase == 1:
                assert library_state().rig_file == str(case.moved(case.export))
                assert rig()['apex_source_model'] == str(case.moved(case.model))
                assert bpy.ops.ed.undo() == {'FINISHED'}
            elif phase == 2:
                assert library_state().rig_file == str(case.export)
                assert rig()['apex_source_model'] == str(case.model)
                assert bpy.ops.ed.redo() == {'FINISHED'}
            elif phase == 3:
                assert library_state().rig_file == str(case.moved(case.export))
                assert rig()['apex_source_model'] == str(case.moved(case.model))
                checks.append('Relink Apply / Undo / Redo')
                fixtures.select(rig())
                library_state().index = hands_index
                push('Before additive animation layer')
                assert bpy.ops.object.apex_add_animation_layer.poll()
                assert bpy.ops.object.apex_add_animation_layer() == {'FINISHED'}
                push('Added additive animation layer')
            elif phase == 4:
                assert_layers(1.0)
                assert bpy.ops.ed.undo() == {'FINISHED'}
            elif phase == 5:
                assert_base()
                assert bpy.ops.ed.redo() == {'FINISHED'}
            elif phase == 6:
                assert_layers(1.0)
                checks.append('Add layer / Undo / Redo')
                assert bpy.ops.object.apex_adjust_animation_layer(index=0, strength=0.4) == {'FINISHED'}
                push('Changed animation layer strength')
            elif phase == 7:
                assert_layers(0.4)
                assert bpy.ops.ed.undo() == {'FINISHED'}
            elif phase == 8:
                assert_layers(1.0)
                assert bpy.ops.ed.redo() == {'FINISHED'}
            elif phase == 9:
                assert_layers(0.4)
                checks.append('Adjust strength / Undo / Redo')
                assert bpy.ops.object.apex_remove_animation_layers() == {'FINISHED'}
                push('Removed additive animation layers')
            elif phase == 10:
                assert_base()
                assert bpy.ops.ed.undo() == {'FINISHED'}
            elif phase == 11:
                assert_layers(0.4)
                assert bpy.ops.ed.redo() == {'FINISHED'}
            elif phase == 12:
                assert_base()
                checks.append('Remove layers / Undo / Redo')
                assert bpy.ops.object.apex_review_model_import(
                    files=[{'name': path} for path in review_files], auto_link=False,
                    placement='GRID', columns=2, gap=0.5, separate_collections=True,
                    texture_folder=str(texture_folder),
                    summary='Two model exports checked.') == {'FINISHED'}
                push('Imported reviewed model batch')
            elif phase == 13:
                assert len(bpy.data.objects) == len(initial_objects) + 4
                assert 'Imported 2 models in a grid' in bpy.context.scene.my_prefs.import_summary
                assert bpy.ops.ed.undo() == {'FINISHED'}
            elif phase == 14:
                assert {obj.name for obj in bpy.data.objects} == initial_objects
                assert bpy.ops.ed.redo() == {'FINISHED'}
            elif phase == 15:
                assert len(bpy.data.objects) == len(initial_objects) + 4
                checks.append('Reviewed batch import / Undo / Redo')
                result = bpy.ops.object.apex_review_model_import('INVOKE_DEFAULT',
                    files=[{'name': path} for path in review_files], auto_link=False,
                    summary='Two model exports checked. Nothing imports until confirmation.')
                assert result == {'RUNNING_MODAL'}, result
            elif phase == 16:
                assert len(bpy.data.objects) == len(initial_objects) + 4, 'The review popup imported before confirmation'
                popup_ticks += 1
                if popup_ticks < 5:
                    return 0.1
                checks.append('Native model review popup invoked and drawn without importing')
                quit_fixture(True)
                return None
        phase += 1
        return 0.08
    except Exception:
        error = traceback.format_exc()
        print(error, flush=True)
        quit_fixture(False, error)
        return None


bpy.app.timers.register(tick, first_interval=0.5, persistent=True)
