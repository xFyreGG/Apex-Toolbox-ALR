"""Check legacy IK controls using a disposable real legend export.

Usage: blender --background --factory-startup --python tests/real_ik_check.py -- <model.cast>
Does not modify or copy the export. Use --save for a disposable visual check.
"""
from pathlib import Path
import ast
import sys
import tempfile
import zipfile

import addon_utils
import bpy

ROOT = Path(__file__).resolve().parents[1]
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
save_scene = '--save' in args
use_release = '--release' in args
args = [arg for arg in args if arg not in {'--save', '--release'}]
assert len(args) == 1, 'Pass one real legend CAST path after --'
path = Path(args[0])
assert path.is_file(), path

release = None
if use_release:
    tree = ast.parse((ROOT / 'Apex_toolbox' / '__init__.py').read_text(encoding='utf-8'))
    info = next(ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == 'bl_info'
                        for target in node.targets))
    sys.path.insert(0, str(ROOT / 'tools'))
    from build_release import release_label
    version = release_label()
    release = tempfile.TemporaryDirectory()
    with zipfile.ZipFile(ROOT / 'dist' / ('Apex-Toolbox-ALR-%s.zip' % version)) as archive:
        archive.extractall(release.name)
sys.path.insert(0, str(Path(release.name) if release else ROOT))
import Apex_toolbox as addon
addon_utils.enable('io_scene_cast', default_set=False)
addon.register()
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
assert bpy.ops.object.apex_import_texture(filepath=str(path)) == {'FINISHED'}
armature = bpy.context.active_object
assert armature.type == 'ARMATURE'
assert bpy.ops.object.button_ikbone() == {'FINISHED'}
assert bpy.ops.object.button_ikbone() == {'CANCELLED'}, 'Duplicate IK controls were allowed'

for bone_name in ('HandIK.L', 'HandIK.R', 'LegIK.L', 'LegIK.R',
                  'ElbowIK.L', 'ElbowIK.R', 'KneeIK.L', 'KneeIK.R'):
    assert bone_name in armature.pose.bones, bone_name
for bone_name in ('def_l_wrist', 'def_r_wrist', 'def_l_ankle', 'def_r_ankle'):
    constraints = [c for c in armature.pose.bones[bone_name].constraints
                   if c.type == 'IK']
    assert len(constraints) == 1, (bone_name, constraints)
    constraint = constraints[0]
    assert constraint.target == armature
    assert constraint.pole_target == armature
    assert constraint.subtarget in armature.pose.bones
    assert constraint.pole_subtarget in armature.pose.bones
for bone_name in ('ElbowIK.L', 'ElbowIK.R', 'KneeIK.L', 'KneeIK.R'):
    assert not any(c.type == 'LIMIT_DISTANCE'
                   for c in armature.pose.bones[bone_name].constraints), bone_name

try:
    bpy.ops.object.mode_set(mode='OBJECT')
except RuntimeError:
    pass
bpy.context.view_layer.update()
wrist = armature.pose.bones['def_l_wrist']
control = armature.pose.bones['HandIK.L']
before = (armature.matrix_world @ wrist.matrix).translation.copy()
control.location.x += 0.2
bpy.context.view_layer.update()
after = (armature.matrix_world @ wrist.matrix).translation.copy()
movement = (after - before).length
assert movement > 0.005, movement
ankle = armature.pose.bones['def_l_ankle']
leg_control = armature.pose.bones['LegIK.L']
before_ankle = (armature.matrix_world @ ankle.matrix).translation.copy()
leg_control.location.x += 0.2
bpy.context.view_layer.update()
ankle_movement = ((armature.matrix_world @ ankle.matrix).translation - before_ankle).length
assert ankle_movement > 0.005, ankle_movement
if save_scene:
    armature.show_in_front = True
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.show_region_ui = False
                area.spaces.active.region_3d.view_location = (0, 0, 0)
                area.spaces.active.region_3d.view_distance = 3
    destination = ROOT / 'artifacts' / 'real-ik-visual-clean.blend'
    destination.parent.mkdir(exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(destination))
print('REAL IK PASSED: %s, wrist %.4f, ankle %.4f' %
      (path.name, movement, ankle_movement), flush=True)
