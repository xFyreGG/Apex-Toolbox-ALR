"""Validate an extracted release in a fresh Blender process, without installing it."""
from pathlib import Path
import sys
import tempfile
import zipfile

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_release import release_version

expected_version = release_version()
version_label = '.'.join(map(str, expected_version))
archive_path = ROOT / 'dist' / ('Apex-Toolbox-ALR-%s.zip' % version_label)

with tempfile.TemporaryDirectory() as directory:
    extracted = Path(directory)
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        archive.extractall(extracted)
    sys.path.insert(0, directory)
    import Apex_toolbox as addon
    assert Path(addon.__file__).resolve().is_relative_to(extracted)
    assert tuple(addon.bl_info['version']) == expected_version
    assert addon.ver == 'v' + version_label
    assert 'Experimental' in addon.bl_info['warning']
    addon.register()
    assert not hasattr(addon, 'BUTTON_TOON')
    assert addon.APEX_PT_shadow.bl_parent_id == 'APEX_PT_apex_effects'
    assert hasattr(bpy.types.Object, 'apex_animation_library')
    assert bpy.ops.object.apex_import_texture.get_rna_type()
    assert bpy.ops.object.apex_load_animation.get_rna_type()
    assert bpy.ops.object.apex_remove_animation.get_rna_type()
    assert bpy.ops.object.apex_cancel_animation_scan.get_rna_type()
    assert bpy.ops.object.apex_builtin_animation_names.get_rna_type()
    catalog = addon.apex_animations.animation_names.bundled_catalog()
    assert catalog.match(0, addon.apex_animations.animation_names.string_guid('wraith_ground_emote_energy'))[0] == 'Acrobat'
    addon.apex_autotex.browsed_directories = lambda: []
    obj = bpy.context.active_object
    material = bpy.data.materials.new('package_body')
    material.use_nodes = True
    obj.data.materials.clear()
    obj.data.materials.append(material)
    image = bpy.data.images.new('package_body_col', width=8, height=8)
    image.filepath_raw = str(extracted / 'package_body_col.png')
    image.file_format = 'PNG'
    image.save()
    bpy.data.images.remove(image)
    prefs = bpy.context.scene.my_prefs
    prefs.autotex_folder = directory
    obj.rotation_mode = 'QUATERNION'
    assert bpy.ops.object.apex_xyz_euler() == {'FINISHED'}
    assert obj.rotation_mode == 'XYZ'
    for key in ('OP1', 'OP2', 'OP3'):
        prefs.cust_enum2 = key
        assert bpy.ops.object.button_custom() == {'FINISHED'}
        assert '1 textured' in prefs.texture_summary
        assert prefs.texture_report is not None
    assert bpy.ops.object.apex_check_scene() == {'FINISHED'}
    assert not prefs.health_issues
    assert (extracted / 'Apex_toolbox' / 'WORKFLOW_GUIDE.md').is_file()
    addon.unregister()
    assert addon.cancel_animation_scan not in bpy.app.handlers.load_pre
    assert not hasattr(bpy.types.Object, 'apex_animation_library')
print('PACKAGED RELEASE PASSED: XYZ Euler, all three shaders, reports, scene health and unregister')
