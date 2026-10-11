"""Optional read-only preview/cache smoke test against a local RSX rig export.

Run in factory-startup Blender, passing -- --rig <rig.cast> --release.
All cache data and extracted package files are temporary. An optional --output
path receives test results only. User exports are never changed or packaged.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

import addon_utils
import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--rig', required=True)
parser.add_argument('--release', action='store_true')
parser.add_argument('--output')
args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
sys.path.insert(0, str(ROOT / 'tests'))
from workflow_integration import addon, animations, cast_index, workflows
from Apex_toolbox.apex_tex import animation_preview as preview


def matrix_close(actual, expected):
    difference = max(abs(actual[row][column] - expected[row][column])
                     for row in range(4) for column in range(4))
    assert difference < 1e-5, 'Matrix changed by %.8g' % difference


def timing(scene):
    return (scene.frame_start, scene.frame_end, scene.frame_current, scene.frame_subframe,
            scene.render.fps, scene.render.fps_base)


def scan_library(rig, rig_path):
    reads = []
    original = cast_index.iter_cast

    def counted(path):
        reads.append(Path(path).resolve())
        return original(path)

    started = time.perf_counter()
    scan = animations.LibraryScan(rig, str(rig_path))
    try:
        with patch.object(cast_index, 'iter_cast', side_effect=counted):
            while not scan.step():
                pass
            scan.commit(rig)
    finally:
        scan.close()
    return scan, reads, time.perf_counter() - started


addon_utils.enable('io_scene_cast', default_set=False)
addon.register()
temporary = tempfile.TemporaryDirectory()
cache_patch = patch.object(animations, 'index_cache_root', return_value=Path(temporary.name) / 'index')
cache_patch.start()
try:
    rig_path = Path(args.rig).resolve()
    importer, decoder, rna = workflows.cast_modules()
    document = decoder.Cast.load(str(rig_path))
    before = set(bpy.data.objects)
    for root in document.Roots():
        for model in root.ChildrenOfType(decoder.Model):
            importer.importModelNode(workflows.import_options(rna, import_merge=False),
                                     model, str(rig_path), None)
    rigs = [obj for obj in bpy.data.objects if obj not in before and obj.type == 'ARMATURE']
    assert len(rigs) == 1, 'Expected one imported animation rig.'
    rig = rigs[0]
    workflows.select_objects(bpy.context, [rig], rig)
    if rig.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    first, first_reads, first_seconds = scan_library(rig, rig_path)
    first_entries = [asdict(entry) for entry in first.entries]
    second, repeat_reads, repeat_seconds = scan_library(rig, rig_path)
    assert [asdict(entry) for entry in second.entries] == first_entries
    assert second.warnings == first.warnings
    assert repeat_reads == [rig_path], 'Repeat browsing must still validate the rig and skip sequence parsing.'
    sequence_reads = sum(path != rig_path for path in first_reads)
    assert second.cache_hits == sequence_reads

    library = rig.apex_animation_library
    samples = []
    for category in ('EMOTE', 'GLADCARD', 'FINISHER'):
        eligible = [item for item in library.clips if not item.additive and item.menu_name
                    and animations.clip_matches(item.name, category)]
        if eligible:
            samples.append((category, eligible[0]))
    assert len(samples) >= 2, 'Choose an export with at least two named animation categories.'

    # Give Revert an existing Action and a nontrivial manual pose to recover.
    baseline_action = bpy.data.actions.new('Real preview smoke baseline')
    rig.animation_data_create().action = baseline_action
    rig.rotation_mode = 'XYZ'
    rig.rotation_euler = (0.1, 0.2, 0.3)
    rig.location = (1.0, 2.0, 3.0)
    first_bone = next(iter(rig.pose.bones))
    first_bone.rotation_mode = 'XYZ'
    first_bone.rotation_euler = (0.05, 0.1, 0.15)
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 3, 123
    scene.render.fps, scene.render.fps_base = 24, 1.0
    scene.frame_set(17, subframe=0.25)
    bpy.context.view_layer.update()
    baseline_timing = timing(scene)
    baseline_object = rig.matrix_world.copy()
    baseline_bones = {bone.name: (bone.rotation_mode, bone.matrix_basis.copy(), bone.matrix.copy())
                      for bone in rig.pose.bones}
    results = []
    for category, item in samples:
        missing = preview.start(bpy.context, rig, item)
        assert preview.active(rig) is not None
        assert rig.animation_data.action == item.action
        assert item.recent_order == 0, 'Temporary previews must not enter recent history.'
        frame = int(sum(item.action.frame_range) / 2)
        scene.frame_set(frame, subframe=0.25)
        results.append({'category': category, 'clip': item.name, 'menu_name': item.menu_name,
                        'scrub_frame': frame, 'missing_bones': missing})
    assert preview.revert(bpy.context)
    assert preview.active() is None
    assert rig.animation_data.action == baseline_action
    assert timing(scene) == baseline_timing
    matrix_close(rig.matrix_world, baseline_object)
    for bone in rig.pose.bones:
        mode, basis, matrix = baseline_bones[bone.name]
        assert bone.rotation_mode == mode
        matrix_close(bone.matrix_basis, basis)
        matrix_close(bone.matrix, matrix)
    assert bpy.context.active_object == rig
    assert list(bpy.context.selected_objects) == [rig]

    _, accepted = samples[0]
    preview.start(bpy.context, rig, accepted)
    accepted_action = rig.animation_data.action
    preview.apply(bpy.context)
    assert preview.active() is None
    assert rig.animation_data.action == accepted_action
    assert accepted.recent_order == 1
    applied_timing = timing(scene)
    animations.remove_animation(bpy.context, rig)
    assert rig.animation_data.action is None
    assert timing(scene) == applied_timing
    matrix_close(rig.matrix_world, baseline_object)
    for bone in rig.pose.bones:
        matrix_close(bone.matrix_basis, Matrix.Identity(4))

    output = {'status': 'passed', 'blender': bpy.app.version_string,
              'toolbox': '.'.join(map(str, addon.bl_info['version'])),
              'packaged': args.release, 'rig': rig_path.name,
              'clips': len(first.entries), 'sequence_files': sequence_reads,
              'first_scan_seconds': round(first_seconds, 6),
              'repeat_scan_seconds': round(repeat_seconds, 6),
              'repeat_cache_hits': second.cache_hits,
              'repeat_sequence_parses': sum(path != rig_path for path in repeat_reads),
              'warnings': len(first.warnings), 'samples': results,
              'checks': ['preview', 'scrub', 'switch', 'revert original action and all bone matrices',
                         'revert timeline and object matrix', 'apply', 'recent history', 'remove to rest']}
    if args.output:
        destination = Path(args.output).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    print('REAL ANIMATION PREVIEW PASSED:', json.dumps(output), flush=True)
finally:
    preview.cancel_preview()
    cache_patch.stop()
    temporary.cleanup()
    addon.unregister()
    addon_utils.disable('io_scene_cast', default_set=False)
