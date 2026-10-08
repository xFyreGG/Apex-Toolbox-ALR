"""Scene inspection and exact-name image repair without rebuilding shaders."""

import os
import math
from dataclasses import dataclass

import bpy
from mathutils import Matrix

from . import graph, paths


@dataclass
class Issue:
    code: str
    severity: str
    object: object
    title: str
    detail: str


def prepare_armatures(objects):
    """Convert imported inches/Z-up once, preserving selection and rig data.

    The marker is stored on the object and participates in Blender Undo. An
    already scaled rig is also left alone to cover scenes prepared in 3.8.
    """
    converted = skipped = 0
    for obj in objects:
        if obj.type != 'ARMATURE' or not obj.is_editable:
            continue
        if (obj.get('apex_model_prepared', False)
                or all(abs(abs(value) - 0.0254) < 1e-6 for value in obj.scale)):
            skipped += 1
            continue
        correction = Matrix.Rotation(math.pi / 2, 4, 'X') @ Matrix.Scale(0.0254, 4)
        # Keep the model where the user placed it. Transform the orientation
        # and scale, never the translation or any mesh/bone data.
        location = obj.matrix_world.translation.copy()
        obj.matrix_world = correction @ obj.matrix_world
        obj.matrix_world.translation = location
        obj['apex_model_prepared'] = True
        converted += 1
    return converted, skipped


def model_meshes(objects, view_layer, include_model=True):
    """Meshes selected directly, below a selected root, or bound to its rig.

    Never leave the current view layer. Collection membership alone is not
    evidence that an unselected mesh belongs to the chosen model.
    """
    selected = set(objects)
    roots = {obj for obj in selected if obj.type in {'ARMATURE', 'EMPTY'}}
    result = []
    for obj in view_layer.objects:
        if obj.type != 'MESH':
            continue
        belongs = obj in selected
        if include_model and not belongs:
            parent = obj.parent
            while parent is not None:
                if parent in roots:
                    belongs = True
                    break
                parent = parent.parent
            if not belongs:
                belongs = any(mod.type == 'ARMATURE' and mod.object in roots
                              for mod in obj.modifiers)
        if belongs:
            result.append(obj)
    return sorted(result, key=lambda obj: obj.name.casefold())


def model_rotation_targets(objects, view_layer):
    """Selected model objects, their rigs and descendants in this view layer."""
    available = set(view_layer.objects)
    targets = {obj for obj in objects if obj in available
               and obj.type in {'MESH', 'ARMATURE', 'EMPTY'}}
    for obj in list(targets):
        if obj.type == 'MESH':
            rig = obj.find_armature()
            if rig in available:
                targets.add(rig)
            parent = obj.parent
            while parent is not None:
                if parent.type == 'ARMATURE':
                    if parent in available:
                        targets.add(parent)
                    break
                parent = parent.parent
    roots = {obj for obj in targets if obj.type in {'ARMATURE', 'EMPTY'}}
    targets.update(model_meshes(roots, view_layer))
    for obj in available:
        if obj.type not in {'MESH', 'ARMATURE', 'EMPTY'}:
            continue
        parent = obj.parent
        while parent is not None:
            if parent in roots:
                targets.add(obj)
                break
            parent = parent.parent
    return sorted(targets, key=lambda obj: obj.name.casefold())


def use_xyz_euler(objects, pose_bones=()):
    """Change unanimated quaternion rotations to XYZ without changing the pose.

    Existing Actions (including NLA), drivers and constraints need deliberate
    animation conversion, not a mode switch. Leave their owners/targets alone.
    This also handles object delta rotations, which Blender's rotation-mode
    setter does not convert along with the main rotation.
    """
    converted_objects = converted_bones = skipped = 0
    for is_bone, targets in ((False, objects), (True, pose_bones)):
        for target in set(targets):
            if target.rotation_mode != 'QUATERNION':
                continue
            owner = target.id_data if is_bone else target
            animation = owner.animation_data
            if (not owner.is_editable
                    or (animation and (animation.action or animation.nla_tracks
                                       or animation.drivers))
                    or target.constraints):
                skipped += 1
                continue
            delta = None
            if not is_bone:
                delta = target.delta_rotation_quaternion.copy()
            # Blender converts the main rotation when its mode changes.
            target.rotation_mode = 'XYZ'
            if delta is not None:
                target.delta_rotation_euler = delta.to_euler('XYZ')
            if is_bone:
                converted_bones += 1
            else:
                converted_objects += 1
    return converted_objects, converted_bones, skipped


def image_nodes(tree):
    """Visit nested node groups once, including muted and unconnected nodes."""
    pending = [tree] if tree else []
    seen = set()
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        for node in current.nodes:
            if node.bl_idname in {'ShaderNodeTexImage', 'ShaderNodeTexEnvironment'}:
                yield node
            elif node.type == 'GROUP' and node.node_tree:
                pending.append(node.node_tree)


def is_missing_file(image):
    if image is None or image.packed_file or image.source not in {'FILE', 'TILED', 'SEQUENCE'}:
        return False
    path = graph.image_filepath(image)
    if image.source == 'TILED' and '<UDIM>' in path:
        return any(not os.path.isfile(path.replace('<UDIM>', str(tile.number)))
                   for tile in image.tiles)
    return not path or not os.path.isfile(path)


def inspect_scene(objects, scene, include_scene=False):
    """Return actionable issues; never modify scene data or selection."""
    issues = []
    material_cache = {}
    for obj in objects:
        def add(code, severity, title, detail):
            issues.append(Issue(code, severity, obj, title, detail))

        if not obj.data.polygons:
            add('EMPTY_MESH', 'WARNING', 'No faces', 'This mesh has no faces to render.')
        if not obj.data.uv_layers:
            add('NO_UV', 'WARNING', 'No UV map', 'Import or unwrap UVs before applying model textures.')
        if not obj.material_slots or any(slot.material is None for slot in obj.material_slots):
            add('NO_MATERIAL', 'WARNING', 'Missing material slots',
                'Assign materials to empty slots before using Auto Texture.')
        if any(abs(value) < 1e-8 for value in obj.scale):
            add('ZERO_SCALE', 'ERROR', 'Zero scale', 'One scale axis is zero; the mesh may not render.')
        for modifier in obj.modifiers:
            if modifier.type == 'ARMATURE' and modifier.object is None:
                add('NO_RIG', 'WARNING', 'Armature target missing',
                    "Choose the rig in modifier '%s'." % modifier.name)
        seen_materials = set()
        for slot in obj.material_slots:
            material = slot.material
            if material is None or material in seen_materials:
                continue
            seen_materials.add(material)
            if material not in material_cache:
                findings = []
                if not material.is_editable:
                    findings.append(('LINKED', 'INFO', 'Linked material',
                                     'Make the material local before changing its shader.'))
                if material.use_nodes:
                    surface = graph._output_shader(material.node_tree)
                    if surface is None:
                        findings.append(('NO_SURFACE', 'ERROR', 'No surface shader',
                                         'Connect a shader to the active Material Output.'))
                    for node in image_nodes(material.node_tree):
                        if node.image is None:
                            if any(output.is_linked for output in node.outputs):
                                findings.append(('EMPTY_IMAGE', 'WARNING', 'Empty image binding',
                                                 "Node '%s' needs an image. Try Auto Texture." % node.name))
                        elif is_missing_file(node.image):
                            findings.append(('MISSING_IMAGE', 'ERROR', 'Missing texture file',
                                             "%s: %s. Choose its new folder and repair missing textures."
                                             % (node.image.name, graph.image_filepath(node.image))))
                material_cache[material] = list(dict.fromkeys(findings))
            for code, severity, title, detail in material_cache[material]:
                add(code, severity, title, material.name + ' — ' + detail)
    if include_scene:
        if scene.camera is None:
            issues.append(Issue('NO_CAMERA', 'WARNING', None, 'No render camera',
                                'Add a camera and set it as the active scene camera.'))
        if scene.world and scene.world.use_nodes:
            for node in image_nodes(scene.world.node_tree):
                if node.image and is_missing_file(node.image):
                    issues.append(Issue('MISSING_WORLD', 'ERROR', None, 'Missing environment image',
                                        node.image.name + ': ' + graph.image_filepath(node.image)))
    return issues


def format_health(issues, mesh_count, scope):
    errors = sum(issue.severity == 'ERROR' for issue in issues)
    warnings = sum(issue.severity == 'WARNING' for issue in issues)
    notes = sum(issue.severity == 'INFO' for issue in issues)
    summary = "%d errors; %d warnings; %d notes" % (errors, warnings, notes)
    lines = ['APEX TOOLBOX | Scene Health', '', summary,
             '%d meshes checked (%s).' % (mesh_count, scope),
             'Snapshot only. Run Check again after editing the scene.', '']
    for issue in issues:
        owner = issue.object.name if issue.object else 'Scene'
        lines.extend(['[%s] %s — %s' % (issue.severity, owner, issue.title),
                      '  ' + issue.detail])
    if not issues:
        lines.append('No issues found by these checks.')
    return summary, '\n'.join(lines) + '\n'


def referenced_images(objects, world=None):
    images = set()
    trees = set()
    for obj in objects:
        for slot in obj.material_slots:
            if slot.material and slot.material.node_tree:
                trees.add(slot.material.node_tree)
    if world and world.node_tree:
        trees.add(world.node_tree)
    for tree in trees:
        for node in image_nodes(tree):
            if node.image is not None:
                images.add(node.image)
    return sorted(images, key=lambda image: image.name.casefold())


def repair_images(images, directory, recursive=True):
    """Relink unique exact filenames, leaving ambiguous or broken files alone.

    Changes only an image's file reference and reloads it. Every user of that
    datablock benefits, including shaders with custom wiring. A temporary
    image validates the candidate before any existing image is touched.
    """
    if not os.path.isdir(directory):
        raise ValueError('Choose an existing texture folder first.')
    index = paths.TextureIndex()
    index.add_root(directory, recursive=recursive)
    by_name = {}
    for entry in index.files:
        by_name.setdefault(entry.name.casefold(), []).append(entry.path)
    repaired = 0
    lines = ['APEX TOOLBOX | Texture Repair', '', 'Search folder: ' + directory,
             'Exact filenames only. Shared image datablocks update for all their users.', '']
    if index.warnings:
        # A partial scan cannot prove a filename is unique: another matching
        # file may live in an unreadable folder or beyond a search limit.
        lines.extend('Search warning: ' + warning for warning in index.warnings)
        lines.append('No paths changed. Choose a smaller, readable folder and try again.')
        return 'Search incomplete; no paths changed', '\n'.join(lines) + '\n'
    for image in images:
        if not is_missing_file(image):
            continue
        if not image.is_editable or image.source != 'FILE':
            lines.append('%s: skipped (linked image, image sequence or tiled texture).' % image.name)
            continue
        raw = image.filepath
        # Use the original reference, not Blender's possibly renamed datablock.
        # Blender's // prefix means blend-relative, not a Windows UNC share.
        # ntpath.basename('//old/file.png') returns an empty string.
        filename = raw.replace('\\', '/').rsplit('/', 1)[-1]
        matches = by_name.get(filename.casefold(), []) if filename else []
        if len(matches) != 1:
            lines.append('%s: %s' % (image.name, 'ambiguous; choose a narrower folder.'
                                     if matches else 'no exact filename match.'))
            lines.extend('  ' + match for match in matches)
            continue
        candidate = matches[0]
        probe = None
        try:
            probe = bpy.data.images.load(candidate, check_existing=False)
            if not all(probe.size):
                raise RuntimeError('file contains no readable pixels')
            image.filepath = (bpy.path.relpath(candidate)
                              if raw.startswith('//') and bpy.data.filepath else candidate)
            image.reload()
            if not all(image.size):
                raise RuntimeError('image could not be reloaded')
        except (RuntimeError, OSError, ValueError) as error:
            image.filepath = raw
            lines.append('%s: left unchanged (%s).' % (image.name, error))
        else:
            repaired += 1
            lines.append('%s -> %s' % (image.name, candidate))
        finally:
            if probe is not None:
                bpy.data.images.remove(probe)
    lines.extend('Search warning: ' + warning for warning in index.warnings)
    remaining = sum(is_missing_file(image) for image in images)
    summary = '%d repaired; %d still missing' % (repaired, remaining)
    lines.insert(2, summary)
    return summary, '\n'.join(lines) + '\n'
