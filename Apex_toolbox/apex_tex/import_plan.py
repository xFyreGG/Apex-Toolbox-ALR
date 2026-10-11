"""Read-only import checks and placement for a chosen group of model exports.

Preflight has no Blender dependency. It only examines chosen CAST files and
nearby texture hints; it does not search an entire export library or import data.
"""
from dataclasses import dataclass, field
import hashlib
import math
import os
from pathlib import Path
import stat

from . import cast_index, model_files, naming, roots


MAX_FOLDER_ENTRIES = 10000
MAX_TEXTURE_ENTRIES = 512
MAX_TEXTURE_REFERENCES = 256
FINGERPRINT_SAMPLE_BYTES = 64 * 1024


@dataclass
class PreflightResult:
    paths: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    texture_warnings: list = field(default_factory=list)
    too_many: bool = False
    fingerprints: dict = field(default_factory=dict)

    @property
    def model_count(self):
        return len(self.paths)

    @property
    def summary(self):
        parts = ['%d model%s ready to import' % (self.model_count,
                                               '' if self.model_count == 1 else 's')]
        if self.issues:
            parts.append('%d issue%s' % (len(self.issues), '' if len(self.issues) == 1 else 's'))
        if self.texture_warnings:
            parts.append('%d texture warning%s' % (len(self.texture_warnings),
                                                  '' if len(self.texture_warnings) == 1 else 's'))
        return '; '.join(parts) + '.'


def _identity(path):
    return os.path.normcase(str(Path(path).resolve()))


def _stat_stamp(path):
    info = os.stat(path)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('Choose a regular CAST file.')
    return [info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_dev, info.st_ino]


def _sample_digest(source, size):
    digest = hashlib.sha256(source.read(FINGERPRINT_SAMPLE_BYTES))
    if size > FINGERPRINT_SAMPLE_BYTES:
        source.seek(max(FINGERPRINT_SAMPLE_BYTES, size - FINGERPRINT_SAMPLE_BYTES))
        digest.update(source.read(FINGERPRINT_SAMPLE_BYTES))
    return digest.hexdigest()


def source_fingerprint(path):
    """JSON-safe source identity and sampled digest without reading mesh buffers.

    File stats detect normal replacement/re-export. A sample of the beginning
    and end adds a content check while reading at most 128 KiB, even for a large
    model. A changing export never receives an accepted stamp.
    """
    before = _stat_stamp(path)
    with Path(path).open('rb') as source:
        digest = _sample_digest(source, before[0])
    if _stat_stamp(path) != before:
        raise ValueError('The CAST changed while checking. Try again after the export finishes.')
    return before + [digest]


def _children(folder):
    """Bound directory enumeration even if a user selects a huge library."""
    with os.scandir(folder) as entries:
        found = []
        for entry in entries:
            if len(found) >= MAX_FOLDER_ENTRIES:
                raise ValueError('This folder contains too many entries. Choose the model folders instead.')
            found.append(Path(entry.path))
    return sorted(found, key=lambda path: path.name.casefold())


def _one_model(folder):
    files = [path for path in _children(folder)
             if path.is_file() and path.suffix.casefold() == '.cast']
    if not files:
        return None
    lod0 = [path for path in files if (match := model_files.LOD_SUFFIX.search(path.stem))
            and int(match.group(1)) == 0]
    if len(lod0) == 1:
        return lod0[0]
    if len(files) == 1:
        return files[0]
    raise ValueError('Several CAST files and no unique LOD0. Select the intended CAST file instead.')


def _texture_hints(path, document, texture_folder=''):
    materials = cast_index.nodes_of(document, b'matl')
    if not materials:
        return []
    references = []
    for material in materials:
        for node in material.descendants(b'file'):
            value = node.properties.get('p')
            if isinstance(value, str) and value and value not in references:
                references.append(value)
                if len(references) >= MAX_TEXTURE_REFERENCES:
                    break
        if len(references) >= MAX_TEXTURE_REFERENCES:
            break
    clean = roots.clean_model_name(path.stem)
    nearby = [path.parent, path.parent / clean, path.parent / 'Materials',
              path.parent / '_images', path.parent / 'textures']
    if texture_folder:
        nearby.insert(0, Path(texture_folder))
    images, indexed = set(), set()
    truncated = False
    for folder in nearby:
        try:
            identity = _identity(folder)
            if identity in indexed or not folder.is_dir():
                continue
            indexed.add(identity)
            with os.scandir(folder) as entries:
                for index, entry in enumerate(entries):
                    if index >= MAX_TEXTURE_ENTRIES:
                        truncated = True
                        break
                    if (Path(entry.name).suffix.casefold() in naming.IMAGE_EXTENSIONS
                            and entry.is_file()):
                        images.add(Path(entry.name).stem.casefold())
        except OSError:
            # An unreadable hint folder is handled by Auto Texture's full report.
            continue
    missing = 0
    for value in references:
        ref = Path(value.replace('\\', '/'))
        candidates = [ref, path.parent / ref] if ref.is_absolute() else [path.parent / ref]
        if any(candidate.is_file() for candidate in candidates):
            continue
        if ref.stem.casefold() not in images:
            missing += 1
    if references and missing:
        return ['%s: %d referenced texture%s not found nearby. Auto Texture will search other configured folders.'
                % (path.name, missing, '' if missing == 1 else 's')]
    if not references and not images:
        return ['%s: No texture images found nearby%s. Choose a Texture Folder if needed.'
                % (path.name, ' in the quick check' if truncated else '')]
    return []


def inspect(folders=(), files=(), texture_folder=''):
    """Choose each model's LOD0, validate metadata and report skipped inputs.

    A selected parent is searched one directory level deep. Invalid individual
    selections do not discard usable siblings. More than 50 distinct candidates
    blocks the whole batch, so no model is silently omitted from an import.
    """
    result = PreflightResult()
    candidates, seen = [], set()

    def issue(source, error):
        result.issues.append('%s: %s' % (source, error))

    def add(path):
        identity = _identity(path)
        if identity in seen:
            return
        seen.add(identity)
        candidates.append(Path(path).resolve())
        if len(candidates) > model_files.MAX_BATCH_MODELS:
            result.too_many = True
            raise OverflowError

    try:
        for value in files:
            path = Path(value)
            try:
                if path.suffix.casefold() != '.cast' or not path.is_file():
                    raise ValueError('Choose an existing CAST model file.')
                add(path)
            except (OSError, ValueError) as error:
                issue(path, error)
        for value in folders:
            folder = Path(value)
            try:
                if not folder.is_dir():
                    raise ValueError('Model folder does not exist.')
                if folder.name.casefold().startswith('anims_'):
                    raise ValueError('Animation sequence folder. Choose model folders from mdl.')
                direct = _one_model(folder)
                if direct:
                    add(direct)
                    continue
                children = [child for child in _children(folder)
                            if child.is_dir() and not child.name.casefold().startswith('anims_')]
                if not children:
                    raise ValueError('No model CAST files found in this folder.')
                found = False
                for child in children:
                    try:
                        model = _one_model(child)
                        if model:
                            add(model)
                            found = True
                        else:
                            issue(child, 'No model CAST files found in this folder.')
                    except (OSError, ValueError) as error:
                        issue(child, error)
                if not found and not result.issues:
                    issue(folder, 'No model CAST files found in this folder.')
            except (OSError, ValueError) as error:
                issue(folder, error)
    except OverflowError:
        result.issues.append('More than %d models selected. Choose fewer folders or files.'
                             % model_files.MAX_BATCH_MODELS)
        return result

    for path in candidates:
        try:
            before = _stat_stamp(path)
            document = cast_index.read_cast(path)
            models = cast_index.nodes_of(document, b'modl')
            if not models or not any(list(model.descendants(b'mesh')) for model in models):
                raise ValueError('No model meshes. Use the animation importer for rigs or sequences.')
            if cast_index.nodes_of(document, b'anim') or cast_index.nodes_of(document, b'inst'):
                raise ValueError('Choose a model-only CAST export, without animations or instances.')
            # Static props may omit a skeleton or export an empty one. The
            # bounded reader validates its structure without requiring bones.
            fingerprint = source_fingerprint(path)
            if fingerprint[:-1] != before:
                raise ValueError('The CAST changed while checking. Try again after the export finishes.')
        except (OSError, ValueError, UnicodeError) as error:
            issue(path, error)
            continue
        result.paths.append(str(path))
        result.fingerprints[str(path)] = fingerprint
        try:
            result.texture_warnings.extend(_texture_hints(path, document, texture_folder))
        except (OSError, ValueError, UnicodeError) as error:
            result.texture_warnings.append('%s: The quick texture check could not finish (%s). '
                                           'The model can still be imported.' % (path.name, error))
    if not candidates and not result.issues:
        result.issues.append('Choose at least one model folder or CAST file.')
    return result


def _translate(context, objects, shift):
    from mathutils import Matrix
    members = set(objects)
    for obj in objects:
        if obj.parent not in members:
            obj.matrix_world = Matrix.Translation(shift) @ obj.matrix_world
    context.view_layer.update()


def arrange(context, groups, layout='ROW', columns=5, gap=0.5, separate_collections=False,
            import_collections=()):
    """Place only the supplied imports and optionally give each its own collection.

    The first model stays in place. Rows align model centres in Y and their
    lowest points in Z. Grid cells use maximum widths/depths, so models of
    different sizes and scales cannot overlap. Gap is a minimum in Blender units.
    import_collections must contain only collections created by these imports;
    their empty containers can be removed after grouping, without touching the
    user's existing collections.
    """
    import bpy
    from mathutils import Vector
    from . import workflows

    groups = [list(group) for group in groups if group]
    layout = str(layout).upper()
    if layout not in {'ROW', 'GRID', 'NONE'}:
        raise ValueError('Choose Row, Grid or Original Positions for the import layout.')
    if not math.isfinite(gap) or gap < 0:
        raise ValueError('Model spacing must be a finite, non-negative number.')
    columns = int(columns)
    if columns < 1:
        raise ValueError('Grid columns must be at least one.')
    objects = [obj for group in groups for obj in group]
    if len(set(objects)) != len(objects):
        raise ValueError('An object appears in more than one import group.')
    context.view_layer.update()
    bounds = [workflows.model_bounds(group) for group in groups] if layout != 'NONE' else []
    if layout == 'ROW' and len(groups) > 1:
        workflows.arrange_models_in_row(context, groups)
        previous_right = bounds[0][1].x
        for group in groups[1:]:
            minimum, maximum = workflows.model_bounds(group)
            shift_x = max(0.0, previous_right + gap - minimum.x)
            if shift_x:
                _translate(context, group, Vector((shift_x, 0, 0)))
            previous_right = maximum.x + shift_x
    elif layout == 'GRID' and len(groups) > 1:
        columns = min(columns, len(groups))
        widths = [max(high.x - low.x for index, (low, high) in enumerate(bounds)
                      if index % columns == column) for column in range(columns)]
        rows = [bounds[index:index + columns] for index in range(0, len(bounds), columns)]
        depths = [max(high.y - low.y for low, high in row) for row in rows]
        first_low, first_high = bounds[0]
        lefts = [first_low.x]
        for width in widths[:-1]:
            lefts.append(lefts[-1] + width + gap)
        centres = [(first_low.y + first_high.y) / 2]
        for previous, depth in zip(depths, depths[1:]):
            centres.append(centres[-1] + previous / 2 + gap + depth / 2)
        for index, group in enumerate(groups[1:], 1):
            low, high = bounds[index]
            shift = Vector((lefts[index % columns] - low.x,
                            centres[index // columns] - (low.y + high.y) / 2,
                            first_low.z - low.z))
            _translate(context, group, shift)
    created = []
    if separate_collections:
        for group in groups:
            source = next((obj.get('apex_source_model') for obj in group
                           if obj.get('apex_source_model')), '')
            path = Path(source) if source else None
            name = ((path.parent.name if path.parent.name.casefold() != 'mdl'
                     else roots.clean_model_name(path.stem)) if path else group[0].name)
            collection = bpy.data.collections.new(name or 'Imported Model')
            context.scene.collection.children.link(collection)
            for obj in group:
                collection.objects.link(obj)
                for old in list(obj.users_collection):
                    if old != collection:
                        old.objects.unlink(obj)
            created.append(collection)
        pending = list(import_collections)
        while pending:
            removed = False
            for collection in list(pending):
                try:
                    if bpy.data.collections.get(collection.name) != collection:
                        pending.remove(collection)
                        continue
                    if not collection.is_editable or collection.library:
                        pending.remove(collection)
                        continue
                    if not collection.objects and not collection.children:
                        pending.remove(collection)
                        bpy.data.collections.remove(collection)
                        removed = True
                except ReferenceError:
                    pending.remove(collection)
            if not removed:
                break
    return created
