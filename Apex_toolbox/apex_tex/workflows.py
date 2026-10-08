"""CAST import adapter and selection-safe model import."""
import importlib
from pathlib import Path
from types import SimpleNamespace

import bpy
from mathutils import Matrix, Vector

from . import cast_index, health


def cast_modules():
    try:
        rna = bpy.ops.import_scene.cast.get_rna_type()
        cls = bpy.types.Operator.bl_rna_get_subclass_py(rna.identifier)
        package = cls.__module__
        importer = importlib.import_module(package + '.import_cast')
        decoder = importlib.import_module(package + '.cast')
        if not callable(getattr(importer, 'load', None)) or not hasattr(decoder, 'CastNode'):
            raise AttributeError('Unsupported CAST importer')
        return importer, decoder, rna
    except (AttributeError, ImportError, RuntimeError, KeyError) as error:
        raise ValueError('Install and enable the CAST Blender add-on first (File > Import > Cast).') from error


def import_options(rna, operator=None, **overrides):
    def report(level, message):
        if 'ERROR' in level:
            raise RuntimeError(message)
        if operator is not None:
            operator.report(level, message)
    options = {prop.identifier: prop.default for prop in rna.properties
               if prop.type in {'BOOLEAN', 'STRING', 'INT', 'FLOAT', 'ENUM'}
               and not getattr(prop, 'is_array', False) and hasattr(prop, 'default')}
    options.update(overrides)
    options['report'] = report
    return SimpleNamespace(**options)


def select_objects(context, objects, active=None):
    # CAST can leave an unselected active armature in Pose Mode. Blender's
    # context.object can still refer to the invoking selection at that point.
    current = context.view_layer.objects.active
    if current and current.mode != 'OBJECT':
        with context.temp_override(object=current, active_object=current):
            bpy.ops.object.mode_set(mode='OBJECT')
    for obj in context.selected_objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    context.view_layer.objects.active = active


def selected_rig(context):
    obj = context.active_object
    if obj is None or not obj.select_get():
        return None
    if obj.type == 'ARMATURE':
        return obj
    if obj.type == 'MESH':
        rig = obj.find_armature()
        if rig and rig.name in context.view_layer.objects:
            return rig
    return None


def model_bounds(objects):
    """World-space mesh bounds for one imported model."""
    points = [obj.matrix_world @ Vector(corner)
              for obj in objects if obj.type == 'MESH'
              for corner in obj.bound_box]
    if not points:
        raise ValueError('The imported model has no mesh bounds for placement.')
    return (Vector(tuple(min(point[axis] for point in points) for axis in range(3))),
            Vector(tuple(max(point[axis] for point in points) for axis in range(3))))


def arrange_models_in_row(context, groups):
    """Keep the first import in place; put later models beside it along X."""
    if len(groups) < 2:
        return
    context.view_layer.update()
    first_min, first_max = model_bounds(groups[0])
    row_y = (first_min.y + first_max.y) / 2
    row_floor = first_min.z
    previous_right = first_max.x
    previous_width = first_max.x - first_min.x
    for objects in groups[1:]:
        minimum, maximum = model_bounds(objects)
        width = maximum.x - minimum.x
        depth = maximum.y - minimum.y
        gap = max(0.2 * max(previous_width, width), 0.1 * depth, 0.01)
        shift = Vector((previous_right + gap - minimum.x,
                        row_y - (minimum.y + maximum.y) / 2,
                        row_floor - minimum.z))
        members = set(objects)
        for obj in objects:
            if obj.parent not in members:
                obj.matrix_world = Matrix.Translation(shift) @ obj.matrix_world
        context.view_layer.update()
        previous_right = maximum.x + shift.x
        previous_width = width


def import_model(context, filepath, prepare=True, operator=None):
    """Import a single model, never merge with or texture an existing model.

    On import failure remove only datablocks created by this call. Texturing
    happens afterwards so a missing texture never discards a usable model.
    """
    importer, decoder, rna = cast_modules()
    path = Path(bpy.path.abspath(filepath)).resolve()
    roots = cast_index.read_cast(path)
    if not cast_index.nodes_of(roots, b'mesh'):
        raise ValueError('This CAST has no meshes. Use Link Animation Rig for a rig export.')
    if cast_index.nodes_of(roots, b'anim') or cast_index.nodes_of(roots, b'inst'):
        raise ValueError('Choose a model-only CAST export for Import & Texture.')
    selected, active = list(context.selected_objects), context.active_object
    collections = ('objects', 'collections', 'meshes', 'armatures', 'materials',
                   'images', 'actions', 'node_groups', 'curves')
    before = {name: set(getattr(bpy.data, name)) for name in collections}
    select_objects(context, [])
    try:
        options = import_options(rna, operator, import_merge=False)
        document = decoder.Cast.load(str(path))
        used_names = {mat.name for mat in bpy.data.materials}
        for root in document.Roots():
            for model in root.ChildrenOfType(decoder.Model):
                # CAST otherwise reuses existing materials by name, including
                # their old image paths. Give incoming materials unique names.
                for material in model.Materials():
                    base = material.Name() or 'Material'
                    name, suffix = base, 1
                    while name in used_names:
                        name = '%s.%03d' % (base, suffix)
                        suffix += 1
                    material.SetName(name)
                    used_names.add(name)
                importer.importModelNode(options, model, str(path), None)
        context.view_layer.update()
        created = [obj for obj in bpy.data.objects if obj not in before['objects']]
        if not any(obj.type == 'MESH' for obj in created):
            raise ValueError('CAST did not import a model mesh.')
        # Exit Pose Mode before preparation and texture operators run.
        for obj in created:
            if obj.mode != 'OBJECT':
                context.view_layer.objects.active = obj
                with context.temp_override(object=obj, active_object=obj):
                    bpy.ops.object.mode_set(mode='OBJECT')
        # CAST may reuse a named material from a different model. Copy it before
        # Auto Texture so the existing model's graph cannot be changed.
        copies = {}
        for obj in created:
            if obj.type != 'MESH':
                continue
            for slot in obj.material_slots:
                if slot.material in before['materials']:
                    original = slot.material
                    if original not in copies:
                        copies[original] = original.copy()
                    slot.material = copies[original]
        if prepare:
            health.prepare_armatures(created)
            health.use_xyz_euler(created, [bone for obj in created if obj.type == 'ARMATURE'
                                          for bone in obj.pose.bones])
        rig = next((obj for obj in created if obj.type == 'ARMATURE'), None)
        select_objects(context, created, rig or created[0])
        for obj in created:
            obj['apex_source_model'] = str(path)
        return created
    except Exception:
        if context.object and context.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for name in collections:
            data = getattr(bpy.data, name)
            for item in list(data):
                if item not in before[name]:
                    data.remove(item, do_unlink=True)
        select_objects(context, selected, active)
        raise
