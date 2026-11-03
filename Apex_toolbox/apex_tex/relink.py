"""Preview and rebase this blend's references to a moved RSX export library.

Only referenced files are checked. Building a plan never changes Blender data;
applying one checks the files and RNA owners again before changing any paths.
"""
from collections import Counter
from dataclasses import dataclass, field
import os
from pathlib import Path
import stat

import bpy

from . import animation_cache, animations, cast_index, workflows


def _absolute(value):
    return Path(os.path.abspath(bpy.path.abspath(os.fspath(value))))


def _key(value):
    return os.path.normcase(os.path.normpath(os.fspath(value)))


def _mapped(value, old_root, new_root):
    """Path components, rather than string prefixes, decide containment."""
    if not value:
        return None
    path = _absolute(value)
    try:
        relative = path.relative_to(old_root)
    except ValueError:
        return None
    return new_root / relative


def suggest_old_root(context):
    """Use saved paths even when the old drive or directory is unavailable."""
    rig = workflows.selected_rig(context)
    active = context.active_object
    candidates = []
    for obj in (rig, active):
        if obj:
            candidates.append(obj.get('apex_source_model', ''))
            if obj.type == 'ARMATURE':
                candidates.append(obj.apex_animation_library.rig_file)
    for obj in bpy.data.objects:
        candidates.append(obj.get('apex_source_model', ''))
        if obj.type == 'ARMATURE':
            candidates.append(obj.apex_animation_library.rig_file)
    for value in candidates:
        if not isinstance(value, str) or not value:
            continue
        path = _absolute(value)
        for parent in path.parents:
            if parent.name.casefold() == 'exported_files':
                return str(parent)
        for parent in path.parents:
            if parent.name.casefold() in {'mdl', 'animrig'}:
                return str(parent.parent)
        return str(path.parent)
    return ''


def _pointer(value):
    return value.as_pointer() if value is not None else 0


def _clip_state(item):
    return tuple(getattr(item, name) for name in (
        'name', 'filepath', 'offset', 'fps', 'additive', 'guid', 'sequence_hash',
        'external', 'stamp', 'favourite', 'recent_order', 'menu_name', 'menu_role',
        'menu_source')) + (_pointer(item.action),)


@dataclass
class Change:
    kind: str
    label: str
    old: str
    new: str
    owner: object = field(repr=False)
    owner_pointer: int = field(repr=False)
    stamp: object = field(repr=False)
    clip_index: int = field(default=-1, repr=False)
    clip_pointer: int = field(default=0, repr=False)
    clip_state: tuple = field(default=(), repr=False)
    metadata: object = field(default=None, repr=False)
    field_name: str = field(default='', repr=False)
    skeleton_state: str = field(default='', repr=False)
    image_state: tuple = field(default=(), repr=False)

    def target(self):
        if _pointer(self.owner) != self.owner_pointer or not self.owner.is_editable:
            raise ValueError('An affected model or texture changed. Check the folders again.')
        if self.skeleton_state and animations.rig_signature(self.owner) != self.skeleton_state:
            raise ValueError('An affected skeleton changed. Check the folders again.')
        if self.kind == 'model':
            value = self.owner.get('apex_source_model', '')
            target = self.owner
        elif self.kind == 'image':
            if _image_state(self.owner) != self.image_state or _packed(self.owner):
                raise ValueError('An affected texture changed. Check the folders again.')
            value = self.owner.filepath_raw
            target = self.owner
        elif self.kind == 'rig':
            target = self.owner.apex_animation_library
            value = target.rig_file
        elif self.kind == 'folder':
            target = self.owner.my_prefs
            value = getattr(target, self.field_name)
        else:
            library = self.owner.apex_animation_library
            if self.clip_index >= len(library.clips):
                raise ValueError('An animation library changed. Check the folders again.')
            target = library.clips[self.clip_index]
            if (_pointer(target) != self.clip_pointer or _clip_state(target) != self.clip_state):
                raise ValueError('An animation library changed. Check the folders again.')
            value = target.filepath
        if value != self.old:
            raise ValueError('An affected path changed. Check the folders again.')
        return target


@dataclass
class Plan:
    old_root: str
    new_root: str
    changes: list = field(default_factory=list)
    missing: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    applied: bool = False
    blend_file: str = field(default='', repr=False)

    @property
    def summary(self):
        counts = Counter(change.kind for change in self.changes)
        labels = [('model', 'model path(s)'), ('rig', 'linked rig(s)'),
                  ('clip', 'animation(s)'), ('image', 'texture(s)'), ('folder', 'saved folder(s)')]
        parts = ['%d %s' % (counts[kind], label) for kind, label in labels if counts[kind]]
        message = ', '.join(parts) + ' ready to relink.' if parts else 'No paths ready to relink.'
        if self.missing:
            message += ' %d missing file/folder reference(s) kept.' % len(self.missing)
        if self.warnings:
            message += ' %d reference(s) skipped.' % len(self.warnings)
        return message


def _packed(image):
    return bool(image.packed_file or getattr(image, 'packed_files', ()))


def _stamp(change):
    if change.kind == 'image':
        return _image_stamp(change.owner, Path(change.new))
    if change.kind != 'folder':
        return animation_cache.file_fingerprint(change.new)
    return _directory_stamp(change.new)


def _image_state(image):
    return (image.source, tuple(tile.number for tile in image.tiles)
            if image.source == 'TILED' else ())


def _image_stamp(image, destination):
    if image.source == 'TILED':
        value = str(destination)
        if '<UDIM>' not in value and '<UVTILE>' not in value:
            return None
        paths = [value.replace('<UDIM>', str(tile.number)).replace('<UVTILE>',
                  'u%d_v%d' % ((tile.number - 1001) % 10 + 1, (tile.number - 1001) // 10 + 1))
                 for tile in image.tiles]
    else:
        paths = [str(destination)]
    stamps = [(path, animation_cache.file_fingerprint(path)) for path in paths]
    return stamps if stamps and all(stamp is not None for _, stamp in stamps) else None


def _directory_stamp(path):
    try:
        info = os.stat(path)
        return [info.st_dev, info.st_ino] if stat.S_ISDIR(info.st_mode) else None
    except OSError:
        return None


class _Files:
    def __init__(self):
        self.metadata = {}
        self.clips = {}

    def cast(self, path):
        key = _key(path)
        if key not in self.metadata:
            before = animation_cache.file_fingerprint(path)
            if before is None:
                raise OSError('The file is missing or is not a regular file.')
            roots = cast_index.read_cast(path)
            if animation_cache.file_fingerprint(path) != before:
                raise ValueError('The export changed while it was being checked.')
            self.metadata[key] = (roots, before)
        return self.metadata[key]

    def matching_clips(self, path, roots, name):
        key = _key(path)
        if key not in self.clips:
            grouped = {}
            for node in cast_index.nodes_of(roots, b'anim'):
                value = animations.clip_from_node(path, node)
                grouped.setdefault(value.name, []).append(value)
            self.clips[key] = grouped
        return self.clips[key].get(name, ())


def _check_skeleton(roots, owner):
    bones = {node.properties.get('n', '').casefold()
             for node in cast_index.nodes_of(roots, b'bone')}
    if not bones:
        raise ValueError('The target CAST has no skeleton.')
    if owner.type == 'ARMATURE':
        current = animations.bone_names(owner)
        matched = current & bones
        if not matched or len(matched) < min(len(current), len(bones)) / 2:
            raise ValueError('The target skeleton does not match this model.')


def _check_models(roots, source_roots):
    if source_roots is None:
        return
    names = lambda values: {node.properties.get('n') for node in
                           cast_index.nodes_of(values, b'modl') if node.properties.get('n')}
    old_names, new_names = names(source_roots), names(roots)
    if old_names and new_names and old_names != new_names:
        raise ValueError('The target CAST contains a different model or rig.')


def _matching_clip(item, values):
    matches = []
    for value in values:
        if (value.name == item.name
                and (not item.guid or value.guid.casefold() == item.guid.casefold())
                and (not item.sequence_hash or
                     value.sequence_hash.casefold() == item.sequence_hash.casefold())):
            matches.append(value)
    if len(matches) != 1:
        raise ValueError('The target export has %s matching clips; refresh this rig separately.' %
                         ('no' if not matches else 'multiple'))
    return matches[0]


def build(context, old_root, new_root):
    """Return a checked, non-mutating preview for all local .blend references."""
    if not old_root or not new_root:
        raise ValueError('Choose the previous RSX folder and its new location.')
    old_root, new_root = _absolute(old_root), _absolute(new_root)
    if _key(old_root) == _key(new_root):
        raise ValueError('Choose a different folder for the new location.')
    if not new_root.is_dir():
        raise ValueError('The new RSX folder does not exist.')
    plan, files = Plan(str(old_root), str(new_root), blend_file=bpy.data.filepath), _Files()

    def add(kind, owner, old, index=-1, field_name=''):
        if not isinstance(old, str):
            return
        destination = _mapped(old, old_root, new_root)
        if destination is None:
            return
        label = owner.name
        if field_name:
            label += ' / ' + field_name.replace('_', ' ')
        if index >= 0:
            label += ' / ' + owner.apex_animation_library.clips[index].name
        detail = '%s: %s' % (label, destination)
        if not owner.is_editable:
            plan.warnings.append(detail + ' (linked data is read-only)')
            return
        stamp = (_directory_stamp(destination) if kind == 'folder' else
                 _image_stamp(owner, destination) if kind == 'image' else
                 animation_cache.file_fingerprint(destination))
        if stamp is None:
            plan.missing.append(detail)
            return
        try:
            metadata = None
            if kind not in {'image', 'folder'}:
                roots, stamp = files.cast(destination)
                if kind == 'clip':
                    item = owner.apex_animation_library.clips[index]
                    metadata = _matching_clip(item, files.matching_clips(destination, roots, item.name))
                else:
                    if cast_index.nodes_of(roots, b'anim') or cast_index.nodes_of(roots, b'inst'):
                        raise ValueError('Choose a model or rig CAST, not an animation or scene export.')
                    if kind == 'model' and not cast_index.nodes_of(roots, b'mesh'):
                        raise ValueError('The target CAST has no model meshes.')
                    if kind == 'rig' or owner.type == 'ARMATURE':
                        _check_skeleton(roots, owner)
                    source_roots = None
                    if animation_cache.file_fingerprint(_absolute(old)) is not None:
                        source_roots, _ = files.cast(_absolute(old))
                    _check_models(roots, source_roots)
            change = Change(kind, label, old, str(destination), owner, _pointer(owner), stamp,
                            clip_index=index, metadata=metadata, field_name=field_name)
            if kind in {'model', 'rig'} and owner.type == 'ARMATURE':
                change.skeleton_state = animations.rig_signature(owner)
            if kind == 'image':
                change.image_state = _image_state(owner)
            if index >= 0:
                item = owner.apex_animation_library.clips[index]
                change.clip_pointer, change.clip_state = _pointer(item), _clip_state(item)
            plan.changes.append(change)
        except (OSError, ValueError, UnicodeError) as error:
            plan.warnings.append(detail + ' (' + str(error) + ')')

    for obj in bpy.data.objects:
        add('model', obj, obj.get('apex_source_model', ''))
        if obj.type == 'ARMATURE':
            library = obj.apex_animation_library
            add('rig', obj, library.rig_file)
            for index, item in enumerate(library.clips):
                add('clip', obj, item.filepath, index)
    for image in bpy.data.images:
        if image.source not in {'FILE', 'SEQUENCE', 'TILED', 'MOVIE'} or _packed(image):
            # Packed and generated images do not rely on the export location.
            continue
        add('image', image, image.filepath_raw)
    for scene in bpy.data.scenes:
        for field_name in ('model_parent_folder', 'animation_parent_folder', 'autotex_folder'):
            add('folder', scene, getattr(scene.my_prefs, field_name), field_name=field_name)
    return plan


def apply(plan):
    """Apply the preview atomically; never rescan a changed export or guess."""
    if plan.applied:
        raise ValueError('This folder change was already applied. Check the folders again.')
    if bpy.data.filepath != plan.blend_file:
        raise ValueError('The blend file changed. Check the folders again.')
    checked = []
    try:
        for change in plan.changes:
            target = change.target()
            if _stamp(change) != change.stamp:
                raise ValueError('A target file changed or disappeared. Check the folders again.')
            checked.append((change, target))
    except ReferenceError as error:
        raise ValueError('An affected model or texture was removed. Check the folders again.') from error
    undo = []
    try:
        for change, target in checked:
            if _stamp(change) != change.stamp:
                raise ValueError('A target file changed or disappeared. Check the folders again.')
            if change.kind == 'model':
                undo.append((target, 'apex_source_model', target['apex_source_model'], True))
                target['apex_source_model'] = change.new
            else:
                attribute = (change.field_name if change.kind == 'folder' else
                             {'rig': 'rig_file', 'image': 'filepath_raw', 'clip': 'filepath'}[change.kind])
                undo.append((target, attribute, getattr(target, attribute), False))
                setattr(target, attribute, change.new)
                if change.kind == 'clip':
                    for attribute in ('offset', 'fps', 'additive', 'guid', 'sequence_hash', 'stamp'):
                        undo.append((target, attribute, getattr(target, attribute), False))
                        setattr(target, attribute, '' if attribute == 'stamp' else
                                getattr(change.metadata, attribute))
        if any(_stamp(change) != change.stamp for change, _ in checked):
            raise ValueError('An export changed during relinking. Check the folders again.')
    except Exception:
        for target, attribute, value, custom in reversed(undo):
            if custom:
                target[attribute] = value
            else:
                setattr(target, attribute, value)
        raise
    plan.applied = True
    message = 'Relinked %d file/folder reference(s).' % len(plan.changes)
    warning = bool(plan.missing or plan.warnings)
    if warning:
        message += ' Kept %d missing or unchecked reference(s).' % (len(plan.missing) + len(plan.warnings))
    return message, warning
