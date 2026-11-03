"""Install the release ZIP into isolated Blender user scripts and enable it."""
import os
from pathlib import Path
import sys

import addon_utils
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_release import release_version, release_label

assert os.environ.get('BLENDER_USER_SCRIPTS'), 'Use an isolated user scripts folder'
version = release_label()
archive = ROOT / 'dist' / ('Apex-Toolbox-ALR-%s.zip' % version)
assert archive.is_file(), archive
assert bpy.ops.preferences.addon_install(filepath=str(archive), overwrite=True) == {'FINISHED'}
addon_utils.modules_refresh()
module = addon_utils.enable('Apex_toolbox', default_set=False)
assert module and Path(module.__file__).resolve().is_relative_to(
    Path(os.environ['BLENDER_USER_SCRIPTS']).resolve())
assert tuple(module.bl_info['version']) == release_version()
assert bpy.ops.object.apex_import_texture.get_rna_type()
addon_utils.disable('Apex_toolbox', default_set=False)
print('ZIP INSTALL AND ENABLE PASSED:', version, bpy.app.version_string, flush=True)
