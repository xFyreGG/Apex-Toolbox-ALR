"""Add CAST additive channels above a base action without changing either clip.

NLA Combine multiplies quaternion rotations and scale while adding translations.
The source action remains a reusable cache. Only the private, channel-filtered
copy belongs to the layer and is removed with it.
"""
import math
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import bpy

from . import animation_cache, animations, cast_index, workflows


STATE = '_apex_animation_layers'


def _state(rig):
    value = rig.get(STATE)
    return value if value and hasattr(value, 'get') and value.get('version') == 1 else None


def _record_strip(rig, record):
    if not rig.animation_data or not record:
        return None
    track = rig.animation_data.nla_tracks.get(record.get('track', ''))
    strip = track.strips.get(record.get('strip', '')) if track else None
    return strip if strip and strip.action == record.get('action') else None


def layers(rig):
    """Managed layer strips, suitable for drawing native influence controls."""
    state = _state(rig)
    return [strip for record in state.get('layers', {}).values()
            if (strip := _record_strip(rig, record))] if state else []


def can_remove(rig):
    return bool(rig and _state(rig))


def _validate(rig, first=False):
    if not rig or rig.type != 'ARMATURE' or not rig.is_editable or not rig.data.is_editable:
        raise ValueError('Select a local imported armature first.')
    data = rig.animation_data
    if rig.constraints or any(b.constraints for b in rig.pose.bones) or (data and data.drivers):
        raise ValueError('Animation layers need an imported rig without constraints or drivers.')
    if data and data.use_tweak_mode:
        raise ValueError('Leave NLA Tweak Mode before changing animation layers.')
    state = _state(rig)
    if first and state is None:
        if data and data.nla_tracks:
            raise ValueError('This rig already has NLA tracks. Use the NLA editor to layer its animation.')
        if not data or not data.action:
            raise ValueError('Load a base animation before adding an additive layer.')
        if any(curve.extrapolation != 'CONSTANT' or curve.modifiers
               for curves in _curve_collections(data.action) for curve in curves):
            raise ValueError('The base animation has custom extrapolation or curve modifiers. '
                             'Use the NLA editor to preserve that motion.')
    if state:
        base = _record_strip(rig, state.get('base'))
        if base is None:
            raise ValueError('The Toolbox base track was changed. Restore it before changing layers.')
        if data.action:
            raise ValueError('This rig has a new active action. Clear it in the NLA editor before changing layers.')
        for record in state.get('layers', {}).values():
            if _record_strip(rig, record) is None:
                raise ValueError('A Toolbox layer was renamed or replaced. Restore it before changing layers.')
    return state


def can_add(rig, item):
    if not item or not item.additive:
        return False
    try:
        _validate(rig, first=True)
        return True
    except (ValueError, ReferenceError, RuntimeError):
        return False


def _slot_handle(owner):
    return getattr(owner, 'action_slot_handle', 0)


def _set_slot(owner, action, handle):
    if hasattr(owner, 'action_slot') and getattr(action, 'slots', None):
        slot = next((slot for slot in action.slots if slot.handle == handle), None)
        if slot is None:
            raise ValueError('The animation action slot changed. Load the base animation again.')
        owner.action_slot = slot


def _curve_collections(action):
    if getattr(action, 'is_action_layered', False) and action.layers:
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    yield bag.fcurves
    else:
        yield action.fcurves


def _additive_mask(rig, item):
    path = Path(bpy.path.abspath(item.filepath)).resolve()
    stamp = animation_cache.file_fingerprint(path)
    nodes = cast_index.read_cast(path)
    node = next((n for n in cast_index.nodes_of(nodes, b'anim') if n.offset == item.offset), None)
    if node is None or node.byte_size > 64 * 1024 * 1024:
        raise ValueError('This export changed or is too large. Refresh the linked animation rig.')
    current = animations.clip_from_node(path, node)
    if (current.name != item.name or (item.guid and current.guid != item.guid)
            or (item.sequence_hash and current.sequence_hash != item.sequence_hash)):
        raise ValueError('This export changed. Refresh the linked animation rig.')
    importer, decoder, _ = workflows.cast_modules()
    with path.open('rb') as stream:
        stream.seek(node.offset)
        decoded = decoder.CastNode.load(stream)
    overrides = decoded.CurveModeOverrides()
    bones = {bone.name.casefold(): bone for bone in rig.pose.bones}
    groups = {}
    for curve in decoded.Curves():
        bone = bones.get((curve.NodeName() or '').casefold())
        if bone is None:
            continue
        prop = curve.KeyPropertyName()
        if prop not in {'rq', 'tx', 'ty', 'tz', 'sx', 'sy', 'sz'}:
            continue
        kind = 'rotation_quaternion' if prop == 'rq' else 'location' if prop[0] == 't' else 'scale'
        mode = importer.utilityResolveCurveModeOverride(
            bone, curve.Mode(), overrides, isTranslate=kind == 'location',
            isRotate=kind == 'rotation_quaternion', isScale=kind == 'scale')
        groups.setdefault((bone.name, kind), {})[prop] = mode
    allowed = set()
    for (name, kind), modes in groups.items():
        if not any(mode == 'additive' for mode in modes.values()):
            continue
        if any(mode != 'additive' for mode in modes.values()):
            raise ValueError('This clip mixes additive and normal components on one bone. Use the NLA editor.')
        bone = rig.pose.bones[name]
        if kind == 'rotation_quaternion' and bone.rotation_mode != 'QUATERNION':
            raise ValueError('Load a base animation with quaternion bone rotations before adding this layer.')
        if kind == 'location' and set(modes) != {'tx', 'ty', 'tz'}:
            raise ValueError('Additive position tracks need all three XYZ components. Use the NLA editor for this clip.')
        indices = range(4) if kind == 'rotation_quaternion' else range(3)
        if kind == 'scale':
            indices = ['xyz'.index(prop[1]) for prop in modes]
        for index in indices:
            allowed.add((bone.path_from_id(kind), index))
    if not allowed:
        raise ValueError('This clip has no additive tracks matching the selected rig.')
    if stamp is None or animation_cache.file_fingerprint(path) != stamp:
        raise ValueError('The animation export changed while reading it. Try again after RSX finishes exporting.')
    return allowed, stamp


def _cached_action(context, rig, item, operator):
    """Use the existing importer on an isolated rig, leaving the real rig intact."""
    selected, active, mode = list(context.selected_objects), context.active_object, context.mode
    scene = context.scene
    timing = (scene.frame_start, scene.frame_end, scene.frame_current, scene.frame_subframe,
              scene.render.fps, scene.render.fps_base)
    temp = temp_data = None
    proxy = SimpleNamespace(**{name: getattr(item, name) for name in
                              ('filepath', 'offset', 'name', 'guid', 'sequence_hash', 'action', 'stamp')})
    proxy.recent_order = 0
    try:
        temp = rig.copy()
        temp.data = rig.data.copy()
        temp_data = temp.data
        temp.animation_data_clear()
        if STATE in temp:
            del temp[STATE]
        temp.hide_viewport = temp.hide_select = False
        context.collection.objects.link(temp)
        temp.hide_set(False)
        workflows.select_objects(context, [temp], temp)
        missing = animations.load_clip(context, temp, proxy, fit_timeline=False,
                                       allow_missing=rig.apex_animation_library.allow_missing, operator=operator)
        return proxy.action, proxy.stamp, _slot_handle(temp.animation_data), missing
    finally:
        if temp:
            if temp.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.data.objects.remove(temp, do_unlink=True)
        if temp_data:
            bpy.data.armatures.remove(temp_data)
        scene.frame_start, scene.frame_end = timing[:2]
        scene.render.fps, scene.render.fps_base = timing[4:]
        scene.frame_set(timing[2], subframe=timing[3])
        workflows.select_objects(context, selected, active)
        if mode == 'POSE' and active:
            bpy.ops.object.mode_set(mode='POSE')


def _strip(track, name, action, slot, start, blend, influence, extrapolation, scale=1.0):
    strip = track.strips.new(name, int(start), action)
    _set_slot(strip, action, slot)
    # A manual Action playback range does not crop an active action. Use its
    # actual key range when moving it to NLA, so existing motion stays intact.
    frame_start, frame_end = getattr(action, 'curve_frame_range', action.frame_range)
    strip.action_frame_start = frame_start
    strip.action_frame_end = max(frame_start + 1.0, frame_end)
    strip.frame_start = start
    strip.frame_end = start + max(1.0, frame_end - frame_start)
    strip.blend_type = blend
    # Without this Blender evaluates the full strip regardless of the stored
    # influence value. It also lets the native slider be keyframed later.
    strip.use_animated_influence = True
    strip.influence = influence
    strip.extrapolation = extrapolation
    strip.scale = scale
    strip.use_auto_blend = False
    strip.blend_in = strip.blend_out = 0.0
    # Enabling animated influence creates a zero-valued control curve. Replace
    # its key explicitly; assigning strip.influence alone is only transient.
    strip.influence = influence
    strip.keyframe_insert(data_path='influence', frame=start)
    for curve in strip.fcurves:
        if curve.data_path == 'influence':
            for point in curve.keyframe_points:
                point.interpolation = 'CONSTANT'
    return strip


def _record(track, strip, action, source=''):
    return {'track': track.name, 'strip': strip.name, 'action': action, 'source': source}


def _source(item):
    return '%s:%s:%s' % (animations.export_path_key(item.filepath), item.offset, item.guid)


def influence(strip):
    curve = next((curve for curve in strip.fcurves if curve.data_path == 'influence'), None)
    return curve.evaluate(strip.frame_start) if curve else strip.influence


def set_influence(context, rig, index, value):
    """Update a constant Toolbox layer weight without overwriting custom keys."""
    _validate(rig)
    strips = layers(rig)
    if not 0 <= index < len(strips):
        raise ValueError('That animation layer is no longer available.')
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Layer influence must be between 0 and 1.')
    strip = strips[index]
    curve = next((curve for curve in strip.fcurves if curve.data_path == 'influence'), None)
    if curve is None or len(curve.keyframe_points) != 1 or curve.modifiers:
        raise ValueError('This layer has custom influence keys. Adjust them in the NLA editor.')
    curve.keyframe_points[0].co[1] = value
    curve.update()
    context.scene.frame_set(context.scene.frame_current, subframe=context.scene.frame_subframe)
    context.view_layer.update()
    return 'Updated layer influence to %d%%.' % round(value * 100)


def add(context, rig, item, influence=1.0, frame_offset=0, operator=None):
    """Put matching additive channels over the loaded base, as a removable NLA layer."""
    state = _validate(rig, first=True)
    previous_state = state.to_dict() if state else None
    if not item or not item.additive:
        raise ValueError('Choose an additive animation for the layer.')
    if (not math.isfinite(influence) or not 0 <= influence <= 1
            or not math.isfinite(frame_offset) or abs(frame_offset) > 100000):
        raise ValueError('Layer influence must be between 0 and 1, and the offset within 100,000 frames.')
    source = _source(item)
    if state and any(record.get('source') == source for record in state.get('layers', {}).values()):
        raise ValueError('This clip already has a layer. Adjust its influence instead of adding it twice.')
    allowed, source_stamp = _additive_mask(rig, item)
    old_actions, created_tracks = set(bpy.data.actions), []
    old_item = item.action, item.stamp
    old_recents = [(clip, clip.recent_order) for clip in rig.apex_animation_library.clips]
    data = rig.animation_data
    original = {'action': data.action, 'slot': _slot_handle(data), 'use_nla': data.use_nla,
                'blend': data.action_blend_type, 'extrapolation': data.action_extrapolation,
                'influence': data.action_influence}
    try:
        cached, stamp, slot, missing = _cached_action(context, rig, item, operator)
        if animation_cache.file_fingerprint(Path(bpy.path.abspath(item.filepath)).resolve()) != source_stamp:
            raise ValueError('The animation export changed during import. Try again after RSX finishes exporting.')
        action = cached.copy()
        action.name = 'ALR Layer - ' + item.name
        action.use_fake_user = False
        for curves in _curve_collections(action):
            for curve in list(curves):
                if (curve.data_path, curve.array_index) not in allowed:
                    curves.remove(curve)
        if not any(len(curves) for curves in _curve_collections(action)):
            raise ValueError('CAST did not produce any supported additive channels.')
        token = uuid4().hex[:12]
        if state is None:
            base_action = data.action
            base_track = data.nla_tracks.new()
            created_tracks.append(base_track)
            base_track.name = 'ALR Base ' + token
            # With no prior NLA tracks, Blender evaluates the active action at
            # full weight and holds its endpoint values, ignoring its NLA mix
            # settings. Copying those dormant settings to a strip changes the
            # motion. Preserve that evaluated result; restore the saved mix
            # settings when the base becomes the active action again.
            base_strip = _strip(base_track, 'Base ' + token, base_action, original['slot'],
                                float(getattr(base_action, 'curve_frame_range', base_action.frame_range)[0]),
                                'REPLACE', 1.0, 'HOLD')
            state = {'version': 1, 'original': original, 'base': _record(base_track, base_strip, base_action),
                     'layers': {}}
        else:
            base_strip = _record_strip(rig, state['base'])
            # Copy to a plain dictionary so nothing persistent changes until commit.
            state = state.to_dict()
        track = data.nla_tracks.new(prev=data.nla_tracks[-1])
        created_tracks.append(track)
        track.name = 'ALR Additive ' + token
        fps = context.scene.render.fps / context.scene.render.fps_base
        # Aim and crouch offsets are often single-frame poses. Keep their
        # additive delta active after the offset instead of dropping it after
        # one frame. Inspect the filtered action: normal root-motion tracks in
        # the source clip must not make an otherwise static pose look animated.
        first_frame, last_frame = getattr(action, 'curve_frame_range', action.frame_range)
        extrapolation = 'HOLD_FORWARD' if first_frame == last_frame else 'NOTHING'
        layer_strip = _strip(track, item.name + ' ' + token, action, slot,
                             base_strip.frame_start + frame_offset, 'COMBINE', influence,
                             extrapolation, fps / float(cached.get('apex_clip_fps', item.fps)))
        state['layers'][token] = _record(track, layer_strip, action, source)
        data.action = None
        data.use_nla = True
        rig[STATE] = state
        item.action, item.stamp = cached, stamp
        animations.record_recent(rig.apex_animation_library, item)
        context.scene.frame_set(context.scene.frame_current, subframe=context.scene.frame_subframe)
        context.view_layer.update()
    except Exception:
        if previous_state is not None:
            rig[STATE] = previous_state
        elif STATE in rig:
            del rig[STATE]
        for track in reversed(created_tracks):
            data.nla_tracks.remove(track)
        data.action = original['action']
        if original['action']:
            _set_slot(data, original['action'], original['slot'])
        data.use_nla = original['use_nla']
        item.action, item.stamp = old_item
        for clip, order in old_recents:
            clip.recent_order = order
        for created in list(bpy.data.actions):
            if created not in old_actions:
                bpy.data.actions.remove(created, do_unlink=True)
        context.scene.frame_set(context.scene.frame_current, subframe=context.scene.frame_subframe)
        context.view_layer.update()
        raise
    message = 'Added an additive layer: %s.' % item.name
    if missing:
        message += ' Skipped %d missing bone(s).' % missing
    rig.apex_animation_library.summary = message
    return message


def remove(context, rig):
    """Remove exact Toolbox strips and restore the original base action and slot."""
    state = _validate(rig)
    if state is None:
        raise ValueError('This rig has no Toolbox animation layers.')
    data = rig.animation_data
    records = list(state['layers'].values()) + [state['base']]
    original = state['original'].to_dict()
    action = original.get('action')
    if action and hasattr(action, 'slots') and action.slots:
        if not any(slot.handle == original['slot'] for slot in action.slots):
            raise ValueError('The base action slot was deleted. Restore it before removing layers.')
    layer_actions = [record['action'] for record in state['layers'].values()]
    count = len(layer_actions)
    for record in records:
        track = data.nla_tracks[record['track']]
        strip = _record_strip(rig, record)
        track.strips.remove(strip)
        if not track.strips:
            data.nla_tracks.remove(track)
    del rig[STATE]
    data.action = action
    if action:
        _set_slot(data, action, original['slot'])
    data.action_blend_type = original['blend']
    data.action_extrapolation = original['extrapolation']
    data.action_influence = original['influence']
    data.use_nla = original['use_nla'] if not data.nla_tracks else data.use_nla
    for layer_action in layer_actions:
        if layer_action and not layer_action.users:
            bpy.data.actions.remove(layer_action)
    context.scene.frame_set(context.scene.frame_current, subframe=context.scene.frame_subframe)
    context.view_layer.update()
    message = 'Removed %d additive layer(s). Restored the base animation.' % count
    rig.apex_animation_library.summary = message
    return message
