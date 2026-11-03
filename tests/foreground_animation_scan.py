"""Exercise the UI timer path for linking an animation rig in disposable Blender.

Run without --background. Writes a JSON result to artifacts and closes Blender.
"""
import json
import ast
from pathlib import Path
import sys
import tempfile
import time
import zipfile

import addon_utils
import bpy

ROOT = Path(__file__).resolve().parents[1]
release = None
if '--release' in sys.argv:
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
sys.path[:0] = [str(Path(release.name) if release else ROOT), str(ROOT / 'tests')]
from workflow_integration import addon, animation_file, model_file

addon_utils.enable('io_scene_cast', default_set=False)
addon.register()
_, cast, _ = addon.apex_workflows.cast_modules()
folder = ROOT / 'artifacts' / 'foreground-animation-scan'
folder.mkdir(parents=True, exist_ok=True)
result_file = folder / ('result-' + addon.ver[1:] + '-blender-'
                        + '.'.join(map(str, bpy.app.version[:2])) + '.json')
if result_file.exists():
    result_file.unlink()

model_file(cast, folder / 'model.cast')
library = folder / 'animrig'
rig_folder = library / 'pilot_light_wraith'
rig_folder.mkdir(parents=True, exist_ok=True)
rig_path = rig_folder / 'pilot_light_wraith.cast'
model_file(cast, rig_path, mesh=False)
sequences = rig_folder / 'anims_pilot_light_wraith'
sequences.mkdir(exist_ok=True)
animation_file(cast, sequences / 'idle.cast')
animation_file(cast, sequences / 'walk.cast', names=('walk_forward',))
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
assert bpy.ops.object.apex_import_texture(filepath=str(folder / 'model.cast')) == {'FINISHED'}
armature = bpy.context.active_object
assert armature.type == 'ARMATURE'
started = time.monotonic()
launch_result = None
error = None


def start_link():
    global launch_result, error
    try:
        assert bpy.context.window is not None
        launch_result = sorted(bpy.ops.object.apex_link_animation_rig(
            'EXEC_DEFAULT', ui_stage='CHOOSE', source_mode='LEGENDS',
            parent_folder=str(library), rig_legend='wraith', rig_index=0,
            rig_items=[{'name': rig_folder.name, 'selected': False}]))
    except Exception as exc:
        error = repr(exc)
    return None


def check_link():
    elapsed = time.monotonic() - started
    linked = armature.apex_animation_library
    if not error and linked.rig_file != str(rig_path) and elapsed < 20:
        return 0.1
    result = {
        'background': bpy.app.background,
        'window_present': bpy.context.window is not None,
        'launch_result': launch_result,
        'rig_file': linked.rig_file,
        'clip_count': len(linked.clips),
        'elapsed_seconds': round(elapsed, 3),
        'error': error,
        'scan_active': addon._active_animation_scan is not None,
    }
    result['passed'] = (not result['background'] and result['window_present']
                        and result['launch_result'] == ['FINISHED']
                        and result['rig_file'] == str(rig_path)
                        and result['clip_count'] == 2
                        and result['error'] is None
                        and not result['scan_active'])
    result_file.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('FOREGROUND ANIMATION SCAN %s:' %
          ('PASSED' if result['passed'] else 'FAILED'), result, flush=True)
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(start_link, first_interval=0.5)
bpy.app.timers.register(check_link, first_interval=0.6)
