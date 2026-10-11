"""Real event-loop preview Apply/Undo/Redo in disposable foreground Blender.

Run with --factory-startup, without --background. The script quits its own
process; require PREVIEW EVENT LOOP CHECKS PASSED and a clean exit. ``--release``
loads the packaged ZIP through the existing workflow fixture bootstrap.
"""
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
from Apex_toolbox.apex_tex import animation_preview as preview

addon = fixtures.addon
addon_utils.enable('io_scene_cast', default_set=False)
addon.register()
_, cast, _ = addon.apex_workflows.cast_modules()
temporary = tempfile.TemporaryDirectory()
folder = Path(temporary.name)
cache_root = patch.object(addon.apex_animations, 'index_cache_root', return_value=folder / 'cache')
cache_root.start()
rig_path = folder / 'legend.cast'
fixtures.model_file(cast, rig_path, mesh=False)
sequences = folder / 'anims_legend'
sequences.mkdir()
fixtures.animation_file(cast, sequences / 'idle.cast')
fixtures.animation_file(cast, sequences / 'walk.cast', names=('walk',))
rig = fixtures.make_rig()
rig_name = rig.name
addon.apex_animations.link_library(rig, str(rig_path))
action = bpy.data.actions.new('Original foreground action')
rig.animation_data_create()
rig.animation_data.action = action
if hasattr(action, 'slots'):
    rig.animation_data.action_slot = action.slots.new(id_type='OBJECT', name='Original foreground slot')
rig['preview_fixture_value'] = 0.1
rig.keyframe_insert(data_path='["preview_fixture_value"]', frame=0)
rig['preview_fixture_value'] = 0.2
rig.keyframe_insert(data_path='["preview_fixture_value"]', frame=10)
original_action_name = action.name
rig.location = (2, 3, -4)
rig.rotation_mode = 'ZYX'
rig.rotation_euler = (0.3, -0.4, 0.6)
rig.scale = (0.25, 0.25, 0.25)
for bone in rig.pose.bones:
    bone.rotation_mode = 'XYZ'
    bone.location = (0.2, -0.4, 0.7)
    bone.rotation_euler = (0.3, -0.2, 0.4)
scene = bpy.context.scene
scene.frame_start, scene.frame_end = 3, 103
scene.render.fps, scene.render.fps_base = 24, 1.001
scene.frame_set(7, subframe=0.375)
bpy.context.view_layer.update()


def transform(owner):
    return (owner.rotation_mode, tuple(owner.location), tuple(owner.scale),
            tuple(owner.rotation_euler), tuple(owner.rotation_quaternion),
            tuple(owner.rotation_axis_angle))


def state():
    target = bpy.data.objects[rig_name]
    animation = target.animation_data
    library = target.apex_animation_library
    slot = getattr(animation, 'action_slot', None)
    return (animation.action.name if animation and animation.action else None,
            slot.identifier if slot else None,
            transform(target), tuple((bone.name, transform(bone)) for bone in target.pose.bones),
            (scene.frame_start, scene.frame_end, scene.frame_current, scene.frame_subframe,
             scene.render.fps, scene.render.fps_base),
            (library.has_rest_rotation, library.rest_rotation_mode, tuple(library.rest_rotation)))


baseline = state()
bpy.ops.wm.save_as_mainfile(filepath=str(folder / 'preview.blend'))
phase = 0
deadline = time.monotonic() + 60
accepted = None


def quit_fixture():
    with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
        bpy.ops.wm.quit_blender()


def tick():
    global phase, accepted, rig, scene
    try:
        assert time.monotonic() < deadline, 'Preview event-loop fixture timed out'
        with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
            rig = bpy.data.objects[rig_name]
            scene = bpy.context.scene
            if phase == 0:
                bpy.ops.ed.undo_push(message='Foreground preview baseline')
                assert bpy.ops.object.apex_preview_animation() == {'FINISHED'}
                assert not bpy.ops.object.apex_load_animation.poll()
                assert not bpy.ops.object.apex_remove_animation.poll()
                rig.apex_animation_library.index = 1
                assert bpy.ops.object.apex_preview_animation() == {'FINISHED'}
                assert rig.animation_data.action.name == 'walk'
                scene.frame_set(8, subframe=0.5)
                assert bpy.ops.object.apex_revert_animation_preview() == {'FINISHED'}
                assert state() == baseline, 'Switching and reverting did not restore the exact baseline'
                assert not bpy.ops.object.apex_apply_animation_preview.poll()
                assert not bpy.ops.object.apex_revert_animation_preview.poll()
                phase = 1
            elif phase == 1:
                rig.apex_animation_library.index = 0
                assert bpy.ops.object.apex_preview_animation() == {'FINISHED'}
                scene.frame_set(6, subframe=0.125)
                rig.apex_animation_library.index = 1
                assert bpy.ops.object.apex_apply_animation_preview() == {'FINISHED'}
                assert preview.active() is None
                assert rig.apex_animation_library.clips[0].recent_order > 0
                assert rig.apex_animation_library.clips[1].recent_order == 0
                assert bpy.data.actions[original_action_name].use_fake_user, 'Apply must keep the original action saved'
                accepted = state()
                assert accepted != baseline
                # Timer-driven bpy.ops calls do not get the window manager's
                # automatic post-operator Undo step from a real UI button.
                # Model that dispatch snapshot explicitly after Apply.
                bpy.ops.ed.undo_push(message='Applied preview from fixture')
                phase = 2
            elif phase == 2:
                assert bpy.ops.ed.undo() == {'FINISHED'}
                scene = bpy.context.scene
                assert preview.active() is None
                assert state() == baseline, 'Apply -> Undo did not restore the exact original scene'
                phase = 3
            elif phase == 3:
                assert bpy.ops.ed.redo() == {'FINISHED'}
                scene = bpy.context.scene
                assert preview.active() is None
                assert state() == accepted, 'Apply -> Undo -> Redo did not restore the accepted clip'
                assert bpy.ops.object.apex_load_animation.poll()
                phase = 4
            elif phase == 4:
                assert bpy.ops.object.apex_preview_animation() == {'FINISHED'}
                assert preview.active() is not None
                assert bpy.ops.ed.undo() == {'FINISHED'}
                scene = bpy.context.scene
                assert preview.active() is None, 'Undo did not clear an in-progress preview'
                assert state() == baseline
                phase = 5
            elif phase == 5:
                fixtures.select(rig)
                assert bpy.ops.object.apex_preview_animation() == {'FINISHED'}
                assert '_apex_animation_preview' in rig
                assert bpy.ops.mesh.primitive_cube_add() == {'FINISHED'}
                cube_name = bpy.context.active_object.name
                rig['preview_fixture_cube'] = cube_name
                # As for Apply above, explicitly model the Undo snapshot
                # produced by interactive dispatch of this unrelated edit.
                bpy.ops.ed.undo_push(message='Unrelated Blender edit during preview')
                assert bpy.ops.object.apex_revert_animation_preview() == {'FINISHED'}
                assert state() == baseline
                assert bpy.ops.ed.undo() == {'FINISHED'}
                scene = bpy.context.scene
                assert state() == baseline
                assert preview.active() is None
                assert '_apex_animation_preview' not in bpy.data.objects[rig_name]
                phase = 6
            elif phase == 6:
                assert bpy.ops.ed.redo() == {'FINISHED'}
                scene = bpy.context.scene
                rig = bpy.data.objects[rig_name]
                assert rig['preview_fixture_cube'] in bpy.data.objects, 'Redo must preserve the unrelated edit'
                assert state() == baseline, 'Redo resurrected an orphan temporary preview'
                assert preview.active() is None
                assert '_apex_animation_preview' not in rig
                phase = 7
            elif phase == 7:
                addon.unregister()
                cache_root.stop()
                temporary.cleanup()
                print('PREVIEW EVENT LOOP CHECKS PASSED: switching, Revert, Apply, Undo/Redo, unrelated edits and control polls', flush=True)
                quit_fixture()
                return None
        return 0.05
    except Exception:
        traceback.print_exc()
        preview.revert(bpy.context)
        print('PREVIEW EVENT LOOP CHECKS FAILED', flush=True)
        quit_fixture()
        return None


bpy.app.timers.register(tick, first_interval=0.5, persistent=True)
