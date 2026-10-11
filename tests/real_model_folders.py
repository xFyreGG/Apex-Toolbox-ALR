"""Read-only smoke check for batch import from real RSX model folders.

blender --background --factory-startup --python-exit-code 1 --python this.py --
  --mdl <exported_files/mdl> --models <folder> <folder> [<folder> ...] [--release]

The scene is disposable. No game assets are copied into the repository.
"""
import argparse
import ast
from pathlib import Path
import sys
import tempfile
import time
import zipfile

import addon_utils
import bpy


ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--mdl', type=Path, required=True)
parser.add_argument('--models', nargs='+', required=True)
parser.add_argument('--release', action='store_true')
parser.add_argument('--require-auto-links', action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])

release = None
if args.release:
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
from Apex_toolbox.apex_tex import model_files, workflows


mdl = args.mdl.resolve()
assert mdl.is_dir() and mdl.name.casefold() == 'mdl', 'Choose the RSX mdl directory'
names = list(dict.fromkeys(args.models))
assert len(names) >= 2, 'Choose at least two different model folders'
assert len(names) <= model_files.MAX_BATCH_MODELS
for name in names:
    assert name == Path(name).name and (mdl / name).is_dir(), 'Invalid model folder: %s' % name
    assert model_files.model_cast(mdl / name), 'No model CAST in %s' % name

addon_utils.enable('io_scene_cast', default_set=False)
addon.register()
started = time.perf_counter()
result = bpy.ops.object.apex_import_texture(
    ui_stage='CHOOSE', source_mode='FOLDERS', parent_folder=str(mdl),
    folder_items=[{'name': name, 'selected': True} for name in names])
elapsed = time.perf_counter() - started
assert result == {'FINISHED'}, 'Import & Texture did not finish'

groups = {}
for obj in bpy.context.selected_objects:
    source = obj.get('apex_source_model')
    if source:
        groups.setdefault(source, []).append(obj)
expected = {str(model_files.model_cast(mdl / name)) for name in names}
assert set(groups) == expected, 'Imported sources do not match selected folders'

bounds = [workflows.model_bounds(groups[path]) for path in sorted(groups)]
for (_, right), (left, _) in zip(bounds, bounds[1:]):
    assert left.x > right.x, 'Imported models overlap'
centers = [(low.y + high.y) / 2 for low, high in bounds]
bottoms = [low.z for low, _ in bounds]
assert max(centers) - min(centers) < 1e-4, 'Model centres are not aligned'
assert max(bottoms) - min(bottoms) < 1e-4, 'Model bottoms are not aligned'

if args.require_auto_links:
    linked = 0
    for source, objects in groups.items():
        for rig in (obj for obj in objects if obj.type == 'ARMATURE'):
            legend = model_files.model_legend(source, (rig.name, rig.data.name))
            if not legend:
                continue
            library = rig.apex_animation_library
            assert library.rig_file and library.clips, library.summary
            assert not rig.animation_data or not rig.animation_data.action, 'Auto-link applied an animation'
            linked += 1
            print('REAL AUTO-LINK PASSED:', legend, len(library.clips), 'clips,', library.rig_file, flush=True)
    assert linked, 'No legend models were selected for the automatic link check'

print('REAL MODEL BATCH PASSED:', len(groups), 'models,',
      sum(obj.type == 'MESH' for items in groups.values() for obj in items),
      'meshes, %.2fs' % elapsed, flush=True)
addon.unregister()
if release:
    release.cleanup()
