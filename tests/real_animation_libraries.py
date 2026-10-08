"""Validate every available legend rig and sample real playback in a fresh Blender.

-- --audit <tools/audit_animation_libraries.py report> --output <local report>
   [--release]
Missing rigs/empty exports are recorded as unavailable, never reported as passed.
"""
import argparse
import json
from pathlib import Path
import sys
import time
import traceback

import addon_utils
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from workflow_integration import addon
from Apex_toolbox.apex_tex import animations, workflows


def category(item):
    name = item.name.lower()
    if 'freefall_emote' in name:
        return 'SKYDIVE'
    return next((key for key in ('EMOTE', 'GLADCARD', 'FINISHER')
                 if animations.clip_matches(name, key)), None)


def clear_scene():
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for kind in ('actions', 'armatures', 'meshes', 'collections'):
        for item in list(getattr(bpy.data, kind)):
            getattr(bpy.data, kind).remove(item, do_unlink=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--release', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    audit = json.loads(args.audit.read_text(encoding='utf-8'))
    addon_utils.enable('io_scene_cast', default_set=False)
    addon.register()
    importer, decoder, rna = workflows.cast_modules()
    report = {'version': addon.ver, 'libraries': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for source in audit['libraries']:
        name = Path(source['folder']).name
        result = dict(export=name, status='unavailable', samples=[], clips=0, named=0, notes=[])
        report['libraries'].append(result)
        started = time.monotonic()
        try:
            if not source['rig_files']:
                result['notes'].append('Standalone rig CAST is missing; names were audited but rig loading was not tested.')
                continue
            if not source['clips']:
                result['notes'].append('No exported animation clips; rig playback was not tested.')
                continue
            if len(source['rig_files']) != 1:
                result['notes'].append('More than one rig CAST; select a specific rig before testing.')
                continue
            clear_scene()
            rig_path = source['rig_files'][0]
            document = decoder.Cast.load(rig_path)
            for root in document.Roots():
                for model in root.ChildrenOfType(decoder.Model):
                    importer.importModelNode(workflows.import_options(rna, import_merge=False), model, rig_path, None)
            rig = next(obj for obj in bpy.data.objects if obj.type == 'ARMATURE')
            workflows.select_objects(bpy.context, [rig], rig)
            if rig.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            assert bpy.ops.object.apex_link_animation_rig(filepath=rig_path) == {'FINISHED'}
            library = rig.apex_animation_library
            result['clips'] = len(library.clips)
            result['named'] = sum(bool(item.menu_name) for item in library.clips)
            assert result['clips'] == len(source['clips'])
            assert result['named'] == source['named']
            assert not library.names_file, 'Names must work without metadata imports'
            expected = {(clip['file'], clip['offset']): (clip['menu_name'], clip['menu_role'])
                        for clip in source['clips']}
            for item in library.clips:
                assert (item.menu_name, item.menu_role) == expected[(item.filepath, item.offset)]
            tested = set()
            for index, item in enumerate(library.clips):
                group = category(item)
                if not item.menu_name or not group or group in tested or item.additive or item.menu_role in {'Still', 'Preview', 'Loop'}:
                    continue
                library.filter_text = item.menu_name
                library.index = index
                assert index in animations.visible_clip_indices(library)
                assert bpy.ops.object.apex_load_animation() == {'FINISHED'}
                action = rig.animation_data.action
                assert action and action.fcurves
                assert bpy.ops.object.apex_remove_animation() == {'FINISHED'}
                assert rig.animation_data.action is None
                assert bpy.ops.object.apex_load_animation() == {'FINISHED'}
                assert rig.animation_data.action == action
                result['samples'].append(dict(category=group, clip=item.name, menu_name=item.menu_name,
                                              curves=len(action.fcurves)))
                tested.add(group)
            result['status'] = 'passed' if tested else 'index_only'
            if not tested:
                result['notes'].append('Index verified; no named cosmetic clips to sample in this variant.')
        except Exception as error:
            result['status'] = 'failed'
            result['notes'].append(str(error))
            traceback.print_exc()
        finally:
            result['seconds'] = round(time.monotonic() - started, 2)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print('LIBRARY RESULT: %s | %s | %d clips | %d named | %d playback samples | %.1fs | %s' % (
                name, result['status'], result['clips'], result['named'], len(result['samples']),
                result['seconds'], '; '.join(result['notes'])), flush=True)
    clear_scene()
    addon.unregister()
    print('REAL LIBRARIES CHECKS COMPLETE', flush=True)
    if any(item['status'] == 'failed' for item in report['libraries']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
