"""Per-model RSX animation libraries, loaded through the installed CAST importer."""
import math
import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import time

import bpy

from . import animation_cache, animation_names, cast_index, workflows


def bone_names(rig):
    return {bone.name.casefold() for bone in rig.data.bones}


CATEGORY_KEYWORDS = {
    'GLADCARD': ('gladcard', 'glad_card', 'banner'),
    'EMOTE': ('emote',),
    'LOBBY': ('lobby',),
    'FINISHER': ('finisher', 'execution', 'execute'),
    'MOVEMENT': ('walk', 'run', 'sprint', 'jump', 'slide', 'crouch', 'mantle', 'climb', 'swim'),
}


def clip_matches(name, category='ALL', search='', menu_name=''):
    name = name.casefold()
    return ((search.casefold() in name or search.casefold() in menu_name.casefold()) and
            (category == 'ALL' or any(word in name for word in CATEGORY_KEYWORDS.get(category, ()))))


def clip_label(item, library):
    if library.show_menu_names and item.menu_name:
        return item.menu_name + (' · ' + item.menu_role if item.menu_role else '')
    return item.name


RECENT_LIMIT = 20


def visible_clip_indices(library):
    """Underlying collection indices, in the order displayed by the browser."""
    indices = [i for i, item in enumerate(library.clips)
               if clip_matches(item.name, library.category, library.filter_text, item.menu_name)
               and (library.browse_mode != 'FAVOURITES' or item.favourite)
               and (library.browse_mode != 'RECENT' or item.recent_order > 0)]
    if library.browse_mode == 'RECENT':
        indices.sort(key=lambda i: library.clips[i].recent_order)
    return indices


def ensure_visible_selection(library):
    visible = visible_clip_indices(library)
    if library.index not in visible:
        library.index = visible[0] if visible else 0


def record_recent(library, item):
    """Successful loads only; reuse moves a clip to the front without duplicates."""
    older = sorted((clip for clip in library.clips if clip != item and clip.recent_order),
                   key=lambda clip: clip.recent_order)
    for rank, clip in enumerate(older, start=2):
        clip.recent_order = rank if rank <= RECENT_LIMIT else 0
    item.recent_order = 1


def clear_recent(library):
    for item in library.clips:
        item.recent_order = 0
    ensure_visible_selection(library)


def export_path_key(filepath):
    return os.path.normcase(os.path.abspath(bpy.path.abspath(str(filepath))))


@dataclass
class Clip:
    filepath: str
    offset: int
    name: str
    fps: float
    additive: bool
    guid: str = ''
    sequence_hash: str = ''
    external: bool = False


def clip_from_node(path, node, external=False):
    return Clip(str(path), node.offset, node.properties.get('n') or path.stem,
                node.properties.get('fr') or 30.0,
                any(child.properties.get('m') == 'additive'
                    for child in node.children if child.kind == b'curv'),
                format(node.guid, 'x'),
                next((format(child.guid, 'x') for child in node.children
                      if child.kind == b'skel'), ''), external)


class IncrementalScan:
    def step(self, seconds=0.04):
        if self.cancelled:
            raise ValueError('This animation scan was cancelled.')
        deadline = time.monotonic() + seconds
        while not self.done:
            try:
                next(self._steps)
            except StopIteration:
                self.done = True
                break
            if time.monotonic() >= deadline:
                break
        return self.done

    def close(self):
        self._steps.close()
        if not self.done:
            self.cancelled = True


def index_cache_root():
    """User data survives add-on reinstalls; an unavailable cache is optional."""
    try:
        return bpy.utils.user_resource('DATAFILES', path='Apex Toolbox/animation-index', create=True) or None
    except (OSError, RuntimeError):
        return None


class LibraryScan(IncrementalScan):
    """Cooperative scan: no total deadline and no Blender changes until commit.

    Only lightweight clip metadata survives each file. Closing the generator
    releases open directory/file handles, including a partially parsed CAST.
    """
    def __init__(self, rig, filepath, force=False):
        self.path = Path(bpy.path.abspath(filepath)).resolve()
        self.bones = bone_names(rig)
        self.entries, self.warnings = [], []
        self.status = 'Checking the exported rig…'
        self.done = False
        self.cancelled = False
        self.force = force
        self.cache_hits = 0
        self.source_stamps = {}
        self._steps = self._scan()

    def _scan(self):
        self.source_stamps[self.path] = animation_cache.file_fingerprint(self.path)
        for roots in cast_index.iter_cast(self.path):
            yield
        bones = {node.properties.get('n', '').casefold()
                 for node in cast_index.nodes_of(roots, b'bone')}
        if not bones:
            raise ValueError('Choose the exported rig CAST, not an individual animation.')
        matching = bones & self.bones
        if not matching or len(matching) < min(len(bones), len(self.bones)) / 2:
            raise ValueError('The exported rig does not match the selected model\'s bone names.')
        del roots
        folder = self.path.parent / ('anims_' + self.path.stem)
        if not folder.is_dir():
            raise ValueError('No anims_%s folder beside the rig. In RSX enable Export Rig Sequences, '
                             'choose CAST for animations, and export the rig again.' % self.path.stem)
        index_cache = animation_cache.Index(self.path, index_cache_root(), force=self.force)
        files = []
        for entry in cast_index.iter_animation_files(folder):
            if isinstance(entry, Path):
                files.append(entry)
            elif isinstance(entry, str):
                self.warnings.append(entry)
            self.status = 'Finding animation files: %d found…' % len(files)
            yield
        for index, path in enumerate(sorted(files)):
            self.source_stamps[path] = animation_cache.file_fingerprint(path)
            self.status = 'Reading file %d of %d · %d animations found' % (index + 1, len(files), len(self.entries))
            cached = index_cache.lookup(path)
            if cached is not None:
                values, warnings = cached
                # A single CAST can contain thousands of clips. Keep cached
                # rebuilds cooperative too, rather than freezing the sidebar.
                for value in values:
                    self.entries.append(Clip(**value))
                    yield
                self.warnings.extend(warnings)
                self.cache_hits += 1
                yield
                continue
            entries, warnings = [], []
            try:
                for roots in cast_index.iter_cast(path):
                    yield
                for node in cast_index.nodes_of(roots, b'anim'):
                    entries.append(clip_from_node(path, node))
                    yield
                del roots
            except (OSError, ValueError, UnicodeError) as error:
                warnings.append('%s: %s' % (path, error))
            self.entries.extend(entries)
            self.warnings.extend(warnings)
            index_cache.record(path, entries, warnings)
            yield
        if not self.entries:
            detail = self.warnings[0] if self.warnings else 'Choose CAST as the animation sequence export format in RSX.'
            raise ValueError('No CAST animations found. ' + detail)
        index_cache.finish()

    def commit(self, rig):
        if not self.done or self.cancelled:
            raise ValueError('Finish indexing before replacing the animation library.')
        if not rig.is_editable or bone_names(rig) != self.bones:
            raise ValueError('The selected rig changed during indexing. Link it again.')
        if any(animation_cache.file_fingerprint(path) != stamp
               for path, stamp in self.source_stamps.items()):
            raise ValueError('An export changed during indexing. Link the rig again after RSX finishes exporting.')
        message, warning = replace_library(rig, self.path, self.entries, self.warnings)
        if self.cache_hits:
            message += ' Reused the saved index for %d unchanged file(s).' % self.cache_hits
            rig.apex_animation_library.summary = message
        return message, warning


def library_identity(library):
    return (library.rig_file, tuple((clip.filepath, clip.offset, clip.guid, clip.sequence_hash)
                                   for clip in library.clips))


def set_catalog_name(item, catalog):
    item.menu_name, item.menu_role, ambiguous = catalog.match(
        int(item.guid or '0', 16), int(item.sequence_hash or '0', 16))
    item.menu_source = 'BUILTIN' if item.menu_name else ''
    return ambiguous


def names_summary(library):
    named = sum(bool(item.menu_name) for item in library.clips)
    return '%d of %d clips have in-game names.' % (named, len(library.clips))


def use_bundled_names(library):
    if not any(item.guid for item in library.clips):
        raise ValueError('Refresh the linked animation rig first to read its sequence identifiers.')
    catalog = animation_names.bundled_catalog()
    for item in library.clips:
        set_catalog_name(item, catalog)
    library.names_file = ''
    library.names_summary = names_summary(library)
    ensure_visible_selection(library)
    return library.names_summary


class AnimationNamesScan(IncrementalScan):
    def __init__(self, rig, filepath, settings_folder=''):
        self.path = Path(bpy.path.abspath(filepath)).resolve()
        self.settings_folder = bpy.path.abspath(settings_folder) if settings_folder else ''
        self.identity = library_identity(rig.apex_animation_library)
        self.matches = []
        self.status = 'Reading exported in-game names…'
        self.done = self.cancelled = False
        self.ambiguous = 0
        self._steps = self._scan()

    def _scan(self):
        if not self.identity[1] or not any(item[2] for item in self.identity[1]):
            raise ValueError('Refresh the linked animation rig first, then import in-game names.')
        catalog = animation_names.NameCatalog()
        for _ in catalog.read(self.path, self.settings_folder):
            self.status = catalog.status
            yield
        for _, _, guid, sequence_hash in self.identity[1]:
            name, role, ambiguous = catalog.match(int(guid or '0', 16), int(sequence_hash or '0', 16))
            self.matches.append((name, role))
            self.ambiguous += ambiguous
            self.status = 'Matching in-game names: %d of %d…' % (len(self.matches), len(self.identity[1]))
            yield
        if not any(name for name, _ in self.matches):
            raise ValueError('No exact names matched this rig. Export its animation item settings and '
                             'the matching language file. Existing names were kept.')

    def commit(self, rig):
        if not self.done or self.cancelled:
            raise ValueError('Finish importing names before applying them.')
        library = rig.apex_animation_library
        if not rig.is_editable or library_identity(library) != self.identity:
            raise ValueError('The animation library changed. Import the names again.')
        for item, (name, role) in zip(library.clips, self.matches):
            item.menu_name, item.menu_role = name, role
            item.menu_source = 'CUSTOM' if name else ''
        library.names_file = str(self.path)
        library.names_summary = names_summary(library)
        if self.ambiguous:
            library.names_summary += ' %d conflicting matches kept their export names.' % self.ambiguous
        ensure_visible_selection(library)
        return library.names_summary, bool(self.ambiguous)


def link_library(rig, filepath):
    """Synchronous entry point for background Blender and automation scripts."""
    scan = LibraryScan(rig, filepath)
    try:
        while not scan.step():
            pass
        return scan.commit(rig)
    finally:
        scan.close()


def import_single_clip(context, rig, filepath, operator=None):
    """Apply one CAST animseq without linking a full RSX rig export."""
    path = Path(bpy.path.abspath(filepath)).resolve()
    nodes = cast_index.nodes_of(cast_index.read_cast(path), b'anim')
    if len(nodes) != 1:
        raise ValueError('Choose a CAST file with one animation sequence; found %d.' % len(nodes))
    clip = clip_from_node(path, nodes[0], external=True)
    library = rig.apex_animation_library
    existing = next((item for item in library.clips
                     if export_path_key(item.filepath) == export_path_key(path)
                     and item.offset == clip.offset), None)
    added = existing is None
    item = library.clips.add() if added else existing
    previous_index = library.index
    if added:
        item.name, item.filepath, item.offset = clip.name, clip.filepath, clip.offset
        item.fps, item.additive = clip.fps, clip.additive
        item.guid, item.sequence_hash, item.external = clip.guid, clip.sequence_hash, True
        try:
            set_catalog_name(item, animation_names.bundled_catalog())
        except (OSError, ValueError, TypeError):
            pass
    try:
        missing = load_clip(context, rig, item, library.fit_timeline,
                            library.allow_missing, operator, expected_clip=clip)
    except Exception:
        if added:
            library.clips.remove(len(library.clips) - 1)
            library.index = previous_index
        raise
    if not added:
        item.name, item.fps, item.additive = clip.name, clip.fps, clip.additive
        item.guid, item.sequence_hash = clip.guid, clip.sequence_hash
        if item.menu_source != 'CUSTOM':
            try:
                set_catalog_name(item, animation_names.bundled_catalog())
            except (OSError, ValueError, TypeError):
                pass
    library.browse_mode = 'ALL'
    library.category = 'ALL'
    library.filter_text = ''
    library.index = next(index for index, current in enumerate(library.clips) if current == item)
    library.summary = '%d animations available.' % len(library.clips)
    return item, missing


def replace_library(rig, path, entries, warnings):
    library = rig.apex_animation_library
    warnings = list(warnings)
    try:
        catalog = animation_names.bundled_catalog()
    except (OSError, ValueError, TypeError) as error:
        catalog = None
        warnings.append('Included names could not be read; reinstall Apex Toolbox. %s' % error)
    entries = list(entries)
    incoming = {(export_path_key(clip.filepath), clip.offset) for clip in entries}
    for item in library.clips:
        if item.external and (export_path_key(item.filepath), item.offset) not in incoming:
            entries.append(Clip(item.filepath, item.offset, item.name, item.fps,
                                item.additive, item.guid, item.sequence_hash, True))
    old = {(item.filepath, item.offset): (item.action, item.stamp) for item in library.clips}
    # Names survive changed buffer sizes and offsets when a CAST file is
    # re-exported. Never transfer a favourite to a different named clip that
    # happens to occupy the old byte offset, or to another linked rig export.
    clip_key = lambda item: (export_path_key(item.filepath), item.name)
    same_rig = bool(library.rig_file and export_path_key(library.rig_file) == export_path_key(path))
    old_counts = Counter(clip_key(item) for item in library.clips)
    new_counts = Counter(clip_key(item) for item in entries)
    saved = {clip_key(item): (item.favourite, item.recent_order, item.guid, item.sequence_hash,
                             item.menu_name, item.menu_role, item.menu_source)
             for item in library.clips if (same_rig or item.external) and old_counts[clip_key(item)] == 1}
    selected_name = (clip_key(library.clips[library.index])
                     if library.index < len(library.clips) else None)
    selected = ((library.clips[library.index].filepath, library.clips[library.index].offset)
                if library.index < len(library.clips) else None)
    library.clips.clear()
    library.rig_file = str(path)
    library.index = 0
    selected_by_name = (same_rig and old_counts[selected_name] == new_counts[selected_name] == 1)
    for clip in entries:
        item = library.clips.add()
        item.name, item.filepath, item.offset = clip.name, clip.filepath, clip.offset
        item.fps, item.additive = clip.fps, clip.additive
        item.guid, item.sequence_hash = clip.guid, clip.sequence_hash
        item.external = clip.external
        if catalog is not None:
            set_catalog_name(item, catalog)
        item.action, item.stamp = old.get((clip.filepath, clip.offset), (None, ''))
        key = clip_key(item)
        if new_counts[key] == 1 and key in saved:
            item.favourite, item.recent_order = saved[key][:2]
            saved_source = saved[key][6]
            custom = saved_source == 'CUSTOM' or (not saved_source and bool(library.names_file))
            if (item.guid, item.sequence_hash) == saved[key][2:4] and (custom or catalog is None):
                item.menu_name, item.menu_role = saved[key][4:6]
                item.menu_source = 'CUSTOM' if custom and item.menu_name else saved_source
        if (key == selected_name if selected_by_name else (clip.filepath, clip.offset) == selected):
            library.index = len(library.clips) - 1
    if not same_rig:
        library.names_file = ''
    library.names_summary = names_summary(library)
    ensure_visible_selection(library)
    library.summary = '%d animations linked.' % len(entries)
    if warnings:
        library.summary += ' %d file/search warning(s): %s' % (len(warnings), warnings[0])
    return library.summary, bool(warnings)


def validate_clip(node, rig, allow_missing=False):
    curves = [n for n in node.children if n.kind == b'curv']
    if any(n.properties.get('kp') == 'bs' for n in curves):
        raise ValueError('This clip animates blend shapes. Import it with the CAST importer instead.')
    if any(n.properties.get('kp') not in {'rq', 'tx', 'ty', 'tz', 'sx', 'sy', 'sz'} for n in curves):
        raise ValueError('This clip contains unsupported animation tracks. Use the CAST importer instead.')
    names = {n.properties.get('nn', '').casefold() for n in curves}
    missing = names - bone_names(rig)
    if not names or names == missing:
        raise ValueError('This animation has no tracks matching the selected model.')
    if missing and not allow_missing:
        examples = ', '.join(sorted(missing)[:3])
        raise ValueError('%d animated bones are missing (%s). Choose a matching rig, or enable '
                         'Allow Missing Bones to load only matching tracks.' % (len(missing), examples))
    fps = node.properties.get('fr')
    if not isinstance(fps, (float, int)) or not math.isfinite(fps) or not 1 <= fps <= 240:
        raise ValueError('The animation has an unsupported frame rate (expected 1–240 fps).')
    return missing


def rig_signature(rig):
    # A cached action is reusable only for the same rest skeleton.
    import hashlib
    values = [(b.name, b.parent.name if b.parent else '', tuple(v for row in b.matrix_local for v in row))
              for b in rig.data.bones]
    return hashlib.sha256(repr(values).encode()).hexdigest()


def validate_target(rig):
    if not rig.is_editable or not rig.data.is_editable:
        raise ValueError('Make the selected rig local before changing its animation.')
    animation = rig.animation_data
    if (rig.constraints or any(b.constraints for b in rig.pose.bones)
            or (animation and (animation.drivers or animation.nla_tracks or animation.use_tweak_mode))):
        raise ValueError('Use an imported rig without constraints, drivers or NLA tracks for this selector.')


def remove_animation(context, rig):
    """Detach the action, restore all rest transforms and the pre-load orientation."""
    validate_target(rig)
    if rig.animation_data and rig.animation_data.action:
        rig.animation_data.action.use_fake_user = True
        rig.animation_data.action = None
    for bone in rig.pose.bones:
        bone.matrix_basis.identity()
    library = rig.apex_animation_library
    if library.has_rest_rotation:
        rig.rotation_mode = library.rest_rotation_mode
        if rig.rotation_mode == 'QUATERNION':
            rig.rotation_quaternion = library.rest_rotation
        elif rig.rotation_mode == 'AXIS_ANGLE':
            rig.rotation_axis_angle = library.rest_rotation
        else:
            rig.rotation_euler = library.rest_rotation[:3]
        library.has_rest_rotation = False
    context.view_layer.update()


def load_clip(context, rig, item, fit_timeline=True, allow_missing=False, operator=None,
              record_history=True, expected_clip=None):
    validate_target(rig)
    importer, decoder, rna = workflows.cast_modules()
    path = Path(bpy.path.abspath(item.filepath)).resolve()
    source_stamp = animation_cache.file_fingerprint(path)
    roots = cast_index.read_cast(path)
    node = next((n for n in cast_index.nodes_of(roots, b'anim') if n.offset == item.offset), None)
    if node is None:
        raise ValueError('This export changed. Refresh the linked rig before loading.')
    current = clip_from_node(path, node)
    expected = expected_clip or item
    if (current.name != expected.name or (expected.guid and current.guid != expected.guid)
            or (expected.sequence_hash and current.sequence_hash != expected.sequence_hash)):
        raise ValueError('This export changed. Refresh the linked rig before loading.')
    if node.byte_size > 64 * 1024 * 1024:
        raise ValueError('This animation exceeds the 64 MB clip limit. Use the CAST importer directly.')
    missing = validate_clip(node, rig, allow_missing)
    if source_stamp is None or animation_cache.file_fingerprint(path) != source_stamp:
        raise ValueError('This export changed while reading it. Try again after RSX finishes exporting.')
    stamp = '%s:%s' % (source_stamp, rig_signature(rig))
    action = item.action if item.stamp == stamp else None
    selected, active = list(context.selected_objects), context.active_object
    original_mode = context.mode
    scene = context.scene
    timing = (scene.frame_start, scene.frame_end, scene.frame_current, scene.frame_subframe,
              scene.render.fps, scene.render.fps_base)
    temp = temp_data = None
    old_actions = set(bpy.data.actions)
    try:
        if action is None:
            # Import against a disposable copy. The real rig and its action are
            # untouched until CAST has successfully produced a complete action.
            temp = rig.copy()
            temp.data = rig.data.copy()
            temp_data = temp.data
            temp.animation_data_clear()
            temp.hide_viewport = False
            temp.hide_select = False
            context.collection.objects.link(temp)
            temp.hide_set(False)
            workflows.select_objects(context, [temp], temp)
            with open(path, 'rb') as stream:
                stream.seek(node.offset)
                cast_node = decoder.CastNode.load(stream)
            # CAST interpolates quaternion tracks frame by frame. Reject broken
            # exports with huge frame numbers before entering that loop.
            for curve in cast_node.Curves():
                frames, values = curve.KeyFrameBuffer(), curve.KeyValueBuffer()
                width = 4 if curve.KeyPropertyName() == 'rq' else 1
                if (not frames or not values or len(values) != len(frames) * width
                        or max(frames) > 100000 or any(not math.isfinite(v) for v in values)):
                    raise ValueError('Invalid or oversized animation keyframes. Re-export this clip.')
            if missing:
                # The CAST importer reports every unmatched rotation, position
                # and scale track separately. Allow Missing Bones already
                # validated this partial import; skip those curves in this
                # disposable decoded node and keep the single operator summary.
                cast_node.childNodes = [child for child in cast_node.childNodes
                                        if not isinstance(child, decoder.Curve)
                                        or child.NodeName().casefold() not in missing]
            options = workflows.import_options(rna, operator, import_reset=True, import_time=False)
            importer.importAnimationNode(options, cast_node, str(path), temp)
            action = temp.animation_data.action if temp.animation_data else None
            if action is None:
                raise ValueError('CAST did not produce an animation action.')
            action.use_fake_user = True
            action['apex_clip_fps'] = float(node.properties['fr'])
            action['apex_clip_source'] = str(path)
        if animation_cache.file_fingerprint(path) != source_stamp:
            raise ValueError('This export changed during import. Try again after RSX finishes exporting.')
    except Exception:
        if temp and temp.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        if temp:
            temp.animation_data_clear()
        for created in list(bpy.data.actions):
            if created not in old_actions:
                bpy.data.actions.remove(created, do_unlink=True)
        raise
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
        if original_mode == 'POSE' and active:
            bpy.ops.object.mode_set(mode='POSE')
    library = rig.apex_animation_library
    if not library.has_rest_rotation:
        library.rest_rotation_mode = rig.rotation_mode
        if rig.rotation_mode == 'QUATERNION':
            library.rest_rotation = rig.rotation_quaternion
        elif rig.rotation_mode == 'AXIS_ANGLE':
            library.rest_rotation = rig.rotation_axis_angle
        else:
            library.rest_rotation = (*rig.rotation_euler, 0.0)
        library.has_rest_rotation = True
    rig.animation_data_create()
    previous = rig.animation_data.action
    if previous:
        previous.use_fake_user = True
    rig.animation_data.action = action
    if hasattr(rig.animation_data, 'action_slot') and getattr(action, 'slots', None):
        rig.animation_data.action_slot = action.slots[0]
    for bone in rig.pose.bones:
        bone.rotation_mode = 'QUATERNION'
        bone.matrix_basis.identity()
    item.action, item.stamp = action, stamp
    if fit_timeline:
        scene.frame_start = int(action.frame_range[0])
        scene.frame_end = max(scene.frame_start, int(action.frame_range[1]))
        fps = float(node.properties['fr'])
        scene.render.fps = round(fps)
        scene.render.fps_base = scene.render.fps / fps
        scene.frame_set(scene.frame_start)
    else:
        scene.frame_set(timing[2], subframe=timing[3])
    # Clear only the armature object's local rotation after a successful load,
    # including when reusing an action. Bone animation, rotation mode, location
    # and scale stay intact, and failed imports never reach this step.
    if rig.rotation_mode == 'QUATERNION':
        rig.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    elif rig.rotation_mode == 'AXIS_ANGLE':
        rig.rotation_axis_angle = (0.0, 0.0, 1.0, 0.0)
    else:
        rig.rotation_euler = (0.0, 0.0, 0.0)
    context.view_layer.update()
    if record_history:
        record_recent(library, item)
    return len(missing)
