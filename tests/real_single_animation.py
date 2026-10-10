"""Optional read-only check of direct import from an RSX animrig sequence folder.

blender --background --factory-startup --python-exit-code 1 --python this.py --
  --rig <pilot_medium_*.cast> --clip <anims_pilot_medium_*/sequence.cast>
"""
import argparse
from pathlib import Path
import sys
import tempfile
import zipfile

import addon_utils
import bpy

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--rig', required=True)
parser.add_argument('--clip', required=True)
parser.add_argument('--release', action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
if args.release:
    import ast
    tree = ast.parse((ROOT / 'Apex_toolbox' / '__init__.py').read_text(encoding='utf-8'))
    info = next(ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == 'bl_info'
                        for target in node.targets))
    version = '.'.join(map(str, info['version']))
    release = tempfile.TemporaryDirectory()
    with zipfile.ZipFile(ROOT / 'dist' / ('Apex-Toolbox-ALR-%s.zip' % version)) as archive:
        archive.extractall(release.name)
    sys.path.insert(0, release.name)
else:
    sys.path.insert(0, str(ROOT))
import Apex_toolbox as addon
from Apex_toolbox.apex_tex import workflows

addon_utils.enable('io_scene_cast', default_set=False)
addon.register()
importer, decoder, rna = workflows.cast_modules()
document = decoder.Cast.load(args.rig)
for root in document.Roots():
    for model in root.ChildrenOfType(decoder.Model):
        importer.importModelNode(workflows.import_options(rna, import_merge=False),
                                 model, args.rig, None)
rig = next(obj for obj in bpy.data.objects if obj.type == 'ARMATURE')
workflows.select_objects(bpy.context, [rig], rig)
if rig.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

library = rig.apex_animation_library
assert not library.rig_file and not library.clips
assert bpy.ops.object.apex_import_animation_cast(filepath=args.clip) == {'FINISHED'}
assert rig.animation_data and rig.animation_data.action
assert len(library.clips) == 1 and library.clips[0].external
assert Path(library.clips[0].filepath).resolve() == Path(args.clip).resolve()
action = rig.animation_data.action
assert bpy.ops.object.apex_remove_animation() == {'FINISHED'}
assert bpy.ops.object.apex_load_animation() == {'FINISHED'}
assert rig.animation_data.action == action
print('REAL ANIMRIG SINGLE-CLIP IMPORT PASSED:', Path(args.clip).name,
      'as', action.name, flush=True)
addon.unregister()
