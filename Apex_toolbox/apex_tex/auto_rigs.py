"""Find and link exported legend animation libraries after model imports.

Discovery stays within the model's export and folders chosen by the user.
Matching a name only queues a library scan; CAST bone validation still decides
whether that library can actually be linked to the imported armature.
"""
from dataclasses import dataclass
from pathlib import Path

import bpy

from . import animations, autotex, model_files


def _path(value):
    if not value:
        return None
    try:
        return Path(bpy.path.abspath(str(value))).resolve()
    except (OSError, RuntimeError, TypeError, ValueError):
        return None


def _key(path):
    return animations.export_path_key(path)


def _source_root(source):
    path = _path(source)
    if path is None:
        return None
    mdl = next((parent for parent in (path.parent, *path.parents)
                if parent.name.casefold() == 'mdl'), None)
    return mdl.parent / 'animrig' if mdl else None


def _chosen_root(value, explicit=False):
    """Accept an animrig folder, one of its exports, or an RSX sibling.

    An explicit saved folder may have a custom name. Recent browser folders
    must identify an RSX export location instead of searching unrelated paths.
    """
    path = _path(value)
    if path is None:
        return None
    if path.suffix.casefold() == '.cast':
        path = path.parent
    for parent in (path, *path.parents):
        if parent.name.casefold() == 'animrig':
            return parent
    if explicit:
        name = path.name.casefold()
        if name == 'mdl':
            return path.parent / 'animrig'
        if name == 'exported_files':
            return path / 'animrig'
        # Saved manual linking can point into a rig export rather than its
        # parent directory, including custom-named animrig roots.
        if name.startswith(('pilot_', 'holo_', 'nova_')):
            return path.parent
        return path
    for parent in (path, *path.parents):
        name = parent.name.casefold()
        if name == 'mdl':
            return parent.parent / 'animrig'
        if name == 'exported_files':
            return parent / 'animrig'
    return None


def _fallback_roots(context):
    roots = []
    prefs = getattr(context.scene, 'my_prefs', None)
    roots.append(_chosen_root(getattr(prefs, 'animation_parent_folder', ''), explicit=True))
    try:
        bookmarks = bpy.utils.user_resource('CONFIG', path='bookmarks.txt')
        roots.append(_chosen_root(model_files.bookmarked_animrig(bookmarks), explicit=True))
    except (OSError, RuntimeError, TypeError, ValueError):
        pass
    try:
        roots.extend(_chosen_root(value) for value in autotex.browsed_directories())
    except (OSError, RuntimeError, TypeError, ValueError):
        pass
    return roots


def _description(rig):
    try:
        return rig.name
    except (AttributeError, ReferenceError):
        return 'Removed model'


def _set_summary(rig, summary):
    try:
        rig.apex_animation_library.summary = summary
    except (AttributeError, ReferenceError, RuntimeError):
        pass


def plan(context, rigs):
    """Return unambiguous matching targets and readable per-model notices.

    A model's sibling animrig folder outranks the saved animation folder, which
    outranks bookmarks and recent RSX folders. Ambiguity in a higher-priority
    folder stops the search so another export cannot silently win instead.
    """
    targets, notices = [], []
    fallback = _fallback_roots(context)
    candidate_cache, seen_rigs = {}, set()
    for rig in rigs:
        try:
            if rig.type != 'ARMATURE' or not rig.is_editable:
                continue
            pointer = rig.as_pointer()
            if pointer in seen_rigs:
                continue
            seen_rigs.add(pointer)
            library = rig.apex_animation_library
            if library.rig_file:
                continue
            source = rig.get('apex_source_model', '')
            legend = model_files.model_legend(source, object_names=(rig.name, rig.data.name))
        except (AttributeError, ReferenceError, RuntimeError):
            continue
        if not legend:
            continue
        roots = [_source_root(source), *fallback]
        checked = set()
        matched, reason = None, 'no_match'
        unreadable = False
        for root in roots:
            if root is None:
                continue
            key = _key(root)
            if key in checked:
                continue
            checked.add(key)
            if key not in candidate_cache:
                try:
                    candidate_cache[key] = (model_files.legend_animation_rigs(root), False)
                except (OSError, RuntimeError, ValueError):
                    candidate_cache[key] = ([], True)
            candidates, failed = candidate_cache[key]
            unreadable |= failed
            matched, reason = model_files.choose_animation_rig(legend, candidates)
            if matched or reason == 'ambiguous':
                break
        label = model_files.model_group_label(legend, 'LEGENDS')
        if matched:
            targets.append((rig, matched))
            summary = '%s animation rig found. Waiting to link animations.' % label
        elif reason == 'ambiguous':
            summary = 'Several animation rigs match %s. Use Link Animation Rig to choose one.' % label
        else:
            summary = 'No animation rig found for %s. Use Link Animation Rig to choose an export.' % label
            if unreadable:
                summary += ' An export folder could not be read.'
        _set_summary(rig, summary)
        notices.append('%s: %s' % (_description(rig), summary))
    return targets, notices


@dataclass
class _Target:
    rig: object
    path: Path
    bones: frozenset
    identity: tuple
    name: str
    scan: object = None
    error: str = ''


def _target_error(target):
    try:
        rig = target.rig
        if rig.type != 'ARMATURE' or not rig.is_editable:
            return 'The model armature is no longer editable.'
        if frozenset(animations.bone_names(rig)) != target.bones:
            return 'The model bones changed during linking. Link the animation rig again.'
        if animations.library_identity(rig.apex_animation_library) != target.identity:
            return 'The animation library changed during linking. Its current link was kept.'
    except (AttributeError, ReferenceError, RuntimeError):
        return 'The model armature was removed during linking.'
    return ''


class BatchScan(animations.IncrementalScan):
    """Index imported models cooperatively and commit their links together.

    The initiating armature may disappear without cancelling other targets.
    The UI timer should use ``is_batch`` instead of testing that one armature.
    Identical exports and bone sets share an index, while every target is still
    checked again by LibraryScan.commit before its own library is replaced.
    """
    is_batch = True

    def __init__(self, rig, filepath, targets=None):
        self.path = _path(filepath)
        self.status = 'Finding matching animation libraries…'
        self.done = self.cancelled = False
        self._committed = False
        self.records, self.scans = [], []
        self.notices = []
        seen = set()
        for target_rig, target_path in (targets if targets is not None else [(rig, filepath)]):
            try:
                pointer = target_rig.as_pointer()
                if pointer in seen:
                    continue
                seen.add(pointer)
                library = target_rig.apex_animation_library
                if library.rig_file:
                    continue
                path = _path(target_path)
                if path is None:
                    raise ValueError('The animation rig export path is unavailable.')
                self.records.append(_Target(
                    target_rig, path, frozenset(animations.bone_names(target_rig)),
                    animations.library_identity(library), target_rig.name))
            except (AttributeError, ReferenceError, RuntimeError, ValueError) as error:
                self.notices.append('%s: %s' % (_description(target_rig), error))
        self._steps = self._scan()

    def _scan(self):
        grouped = {}
        for target in self.records:
            grouped.setdefault((_key(target.path), target.bones), []).append(target)
        total = len(grouped)
        for index, targets in enumerate(grouped.values(), start=1):
            valid = []
            for target in targets:
                target.error = _target_error(target)
                if not target.error:
                    valid.append(target)
            if not valid:
                yield
                continue
            scan = None
            try:
                scan = animations.LibraryScan(valid[0].rig, str(valid[0].path))
                self.scans.append(scan)
                while not scan.done:
                    self.status = 'Linking animation library %d of %d · %s' % (index, total, scan.status)
                    scan.step(seconds=0.01)
                    yield
                for target in valid:
                    target.scan = scan
            except Exception as error:
                for target in valid:
                    target.error = str(error)
                if scan is not None:
                    scan.close()
                yield
        self.status = 'Animation libraries are ready to link.'

    def commit(self, rig_ignored=None):
        if not self.done or self.cancelled:
            raise ValueError('Finish indexing before linking animation libraries.')
        if self._committed:
            raise ValueError('These animation libraries were already linked.')
        linked, skipped, warnings = 0, len(self.notices), 0
        for target in self.records:
            error = target.error or _target_error(target)
            if not error and target.scan is None:
                error = 'No animation index was available. Use Link Animation Rig to try again.'
            if not error:
                try:
                    message, warning = target.scan.commit(target.rig)
                    linked += 1
                    warnings += bool(warning)
                    self.notices.append('%s: %s' % (target.name, message))
                    continue
                except Exception as failure:
                    error = str(failure)
            skipped += 1
            self.notices.append('%s: %s' % (target.name, error))
            # Do not overwrite a new manual link with a stale batch notice.
            try:
                if animations.library_identity(target.rig.apex_animation_library) == target.identity:
                    _set_summary(target.rig, 'Animation rig was not linked: %s' % error)
            except (AttributeError, ReferenceError, RuntimeError):
                pass
        self._committed = True
        message = 'Linked animation libraries for %d model%s.' % (linked, '' if linked == 1 else 's')
        if skipped:
            message += ' %d model%s skipped; imported models were kept.' % (skipped, '' if skipped == 1 else 's')
        if warnings:
            message += ' %d librar%s had export warnings.' % (warnings, 'y' if warnings == 1 else 'ies')
        return message, bool(skipped or warnings)

    def close(self):
        self._steps.close()
        for scan in self.scans:
            scan.close()
        if not self._committed:
            self.cancelled = True
            for target in self.records:
                try:
                    if animations.library_identity(target.rig.apex_animation_library) == target.identity:
                        _set_summary(target.rig, 'Animation linking cancelled. Imported models were kept.')
                except (AttributeError, ReferenceError, RuntimeError):
                    pass
