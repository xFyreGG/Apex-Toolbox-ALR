"""Optional read-only validation with user-supplied RSX exports, never bundled.

blender --background --factory-startup --python-exit-code 1 --python this.py --
  --rig <legend.cast> --names <localization.locl> [--release]
"""
import argparse
from pathlib import Path
import sys

import bpy
import addon_utils

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from workflow_integration import addon
from Apex_toolbox.apex_tex import animations, workflows

parser = argparse.ArgumentParser()
parser.add_argument('--rig', required=True)
parser.add_argument('--names', required=True)
parser.add_argument('--release', action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
addon_utils.enable('io_scene_cast', default_set=False)
addon.register()
importer, decoder, rna = workflows.cast_modules()
document = decoder.Cast.load(args.rig)
for root in document.Roots():
    for model in root.ChildrenOfType(decoder.Model):
        importer.importModelNode(workflows.import_options(rna, import_merge=False), model, args.rig, None)
rig = next(obj for obj in bpy.data.objects if obj.type == 'ARMATURE')
workflows.select_objects(bpy.context, [rig], rig)
if rig.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')
assert bpy.ops.object.apex_link_animation_rig(filepath=args.rig) == {'FINISHED'}
assert bpy.ops.object.apex_import_animation_names(filepath=args.names) == {'FINISHED'}
library = rig.apex_animation_library
assert any(item.menu_name for item in library.clips)
print('REAL EXPORT INDEX:', len(library.clips), 'clips,', sum(bool(item.menu_name) for item in library.clips), 'named', flush=True)
tested = set()
for i, item in enumerate(library.clips):
    category = next((category for category in ('EMOTE', 'GLADCARD', 'FINISHER')
                     if animations.clip_matches(item.name, category)), None)
    if not item.menu_name or not category or category in tested or item.menu_role in {'Still', 'Preview'}:
        continue
    library.filter_text = item.menu_name
    library.index = i
    assert i in animations.visible_clip_indices(library)
    assert bpy.ops.object.apex_load_animation() == {'FINISHED'}
    action = rig.animation_data.action
    assert action and action.fcurves
    assert bpy.ops.object.apex_remove_animation() == {'FINISHED'}
    assert rig.animation_data.action is None
    assert bpy.ops.object.apex_load_animation() == {'FINISHED'}
    assert rig.animation_data.action == action
    print('REAL EXPORT PLAYBACK:', item.name, '=>', item.menu_name, len(action.fcurves), 'curves', flush=True)
    tested.add(category)
assert tested == {'EMOTE', 'GLADCARD', 'FINISHER'}
addon.unregister()
print('REAL EXPORT CHECKS PASSED', flush=True)
