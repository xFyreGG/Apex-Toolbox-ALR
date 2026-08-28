# -*- coding: utf-8 -*-
"""Auto Texture: capture, resolve, then rebuild.

The operator body used to be three near identical copies of the same
algorithm, one per shader, each of which cleared the material *before* it knew
whether it could texture it.  This module performs the work once:

1. inspect every selected material and capture its semantics;
2. work out which directories are worth searching (:mod:`.roots`);
3. build one cached index of candidate texture files;
4. resolve the roles through the shared resolver;
5. validate the result;
6. build the replacement shader and connect the textures;
7. only then remove the previous nodes.

A material that cannot be resolved is left exactly as the importer made it.

:func:`resolve_for_objects` is the shared entry point.  Auto Texture, Toon and
Recolour all go through it, so there is exactly one texture-discovery
implementation in the add-on.
"""

import os

import bpy

from . import graph
from . import paths
from . import resolver
from . import roles as R
from . import roots as rootfinder
from . import shaders

PREFIX = "[Auto_tex]"

#: Ceiling on how many already-loaded images are offered to the resolver.
MAX_TRACKED_IMAGES = 4000

#: Ceiling on how many other images contribute search directories.
MAX_IMAGE_DIRS = 24


def _log(line):
    print(line)


def _silent(line):
    pass


# --------------------------------------------------------------------------
# Gathering
# --------------------------------------------------------------------------

def material_slots(objects):
    """Unique materials of the given meshes, in a stable order."""
    ordered = []
    seen = set()
    for obj in objects:
        if obj.type != "MESH":
            continue
        for slot in obj.material_slots:
            material = slot.material
            if material is None or material.name in seen:
                continue
            seen.add(material.name)
            ordered.append(material)
    return ordered


def _name_anchors(objects, materials):
    """Datablock names that may reveal the model's export folder name.

    The CAST importer stores no source path, but it does create a collection
    named after the .cast file (``wraith_v20_heist_w_LOD0``), which after the
    LOD suffix is stripped is exactly the RSX export and texture folder name.
    Object and material names are added as weaker fallbacks.
    """
    names = []

    def push(name):
        if name and name not in names:
            names.append(name)

    for obj in objects:
        for collection in obj.users_collection:
            push(collection.name)
    for obj in objects:
        push(obj.name)
        if obj.parent is not None:
            push(obj.parent.name)
    for material in materials:
        push(material.name)
    return names


def _discover_roots(infos, objects, materials, texture_folder,
                    search_subfolders, remembered, extra_roots=()):
    """Work out where to look, without walking anything unnecessarily."""
    material_dirs = []
    for info in infos:
        for directory in info.directories:
            if directory not in material_dirs:
                material_dirs.append(directory)

    image_dirs = []
    for image in bpy.data.images:
        path = graph.image_filepath(image)
        if not path:
            continue
        directory = os.path.dirname(path)
        if directory and directory not in image_dirs:
            image_dirs.append(directory)
        if len(image_dirs) >= MAX_IMAGE_DIRS:
            break

    manual = ""
    if texture_folder:
        manual = os.path.normpath(bpy.path.abspath(texture_folder))

    found = rootfinder.discover(
        material_dirs=list(extra_roots) + material_dirs,
        names=_name_anchors(objects, materials),
        manual=manual,
        search_subfolders=search_subfolders,
        remembered=remembered,
        browsed=browsed_directories(),
        image_dirs=image_dirs,
        blend_dir=os.path.dirname(bpy.data.filepath) if bpy.data.filepath else "",
    )
    return found


def browsed_directories():
    """Folders Blender's file browser has recently been in.

    Read from the user's ``bookmarks.txt``.  The CAST importer records nothing
    about where the file came from, but Blender's own file browser does -- and
    right after a CAST import the newest entry is the model's export folder.
    Read-only; the file is never modified.
    """
    try:
        config = bpy.utils.user_resource('CONFIG')
    except (AttributeError, TypeError):
        return []
    if not config:
        return []
    path = os.path.join(config, "bookmarks.txt")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return []
    recent, bookmarks = rootfinder.parse_bookmarks(text)
    return recent + bookmarks


def _build_index(roots):
    """One shared, cached index of every plausible texture file.

    Already-loaded images go in before the disk scan so that a texture Blender
    already has is reused rather than loaded a second time as a duplicate
    datablock.  Each directory is scanned at most once for the whole run.
    """
    index = paths.TextureIndex()

    for count, image in enumerate(bpy.data.images):
        if count >= MAX_TRACKED_IMAGES:
            break
        path = graph.image_filepath(image)
        if not path:
            continue
        index.add_image(image.name, path, rank=0, image_key=image)

    # ``discover`` already returns the roots best first, so the position in
    # that list *is* the trust order.  Using it as the rank means the export
    # folder the user just imported from beats an older copy of the same model
    # sitting somewhere else on disk.
    for position, root in enumerate(roots):
        index.add_root(root.path, rank=position + 1,
                       recursive=root.recursive)

    return index


def _load_image(path, log):
    """Load ``path`` reusing an existing datablock when there is one."""
    try:
        return bpy.data.images.load(path, check_existing=True)
    except RuntimeError as error:
        log("%s could not load %s (%s)" % (PREFIX, path, error))
        return None


def _images_for(results, log):
    """Turn resolutions into ``role -> bpy.types.Image`` for the builder."""
    images = {}
    for role, result in results.items():
        if not result.resolved:
            continue
        image = result.image_key
        if image is None and result.path:
            image = _load_image(result.path, log)
        if image is None:
            result.status = resolver.STATUS_MISSING
            result.note = "file disappeared before it could be loaded"
            continue
        images[role] = image
    return images


def _drop_redundant_roughness(results):
    """A gloss map and a roughness map cannot both drive the same socket."""
    gloss = results.get(R.GLOSS)
    rough = results.get(R.ROUGHNESS)
    if gloss is not None and gloss.resolved and rough is not None:
        if rough.resolved:
            rough.status = resolver.STATUS_UNRESOLVED
            rough.note = "superseded by the gloss map"


# --------------------------------------------------------------------------
# Shared resolution
# --------------------------------------------------------------------------

class Batch(object):
    """The result of resolving one selection."""

    __slots__ = ("materials", "infos", "index", "roots", "results", "images",
                 "successful_dirs", "resolved_total")

    def __init__(self):
        self.materials = []
        self.infos = []
        self.index = None
        self.roots = []
        #: ``material -> {role: Resolution}``
        self.results = {}
        #: ``material -> {role: bpy.types.Image}``
        self.images = {}
        self.successful_dirs = []
        self.resolved_total = 0


def resolve_for_objects(objects, wanted_roles, texture_folder="",
                        search_subfolders=False, remembered_roots=None,
                        extra_roots=None, materials=None, log=_log,
                        report_lines=True):
    """Resolve ``wanted_roles`` for every material of ``objects``.

    This is the one texture-discovery path in the add-on.  Auto Texture, Toon
    and Recolour all call it, so a fix here fixes all three.

    ``remembered_roots`` and ``extra_roots`` accept ``None`` as "nothing"; the
    defaults are immutable rather than shared mutable lists.
    """
    remembered_roots = list(remembered_roots or ())
    extra_roots = list(extra_roots or ())
    objects = list(objects)
    if materials is None:
        materials = material_slots(objects)

    batch = Batch()
    batch.materials = materials
    if not materials:
        return batch

    batch.infos = [graph.inspect_material(material) for material in materials]
    batch.roots = _discover_roots(batch.infos, objects, materials,
                                  texture_folder, search_subfolders,
                                  remembered_roots, extra_roots)
    batch.index = _build_index(batch.roots)

    automatic = [r for r in batch.roots if r.rank != rootfinder.RANK_MANUAL]
    if automatic:
        log("%s Search root automatically detected: %s"
            % (PREFIX, rootfinder.describe(automatic)))
    elif texture_folder:
        log("%s Automatic texture root unavailable." % PREFIX)
        log("%s Using manual Texture Search Folder." % PREFIX)
    else:
        log("%s Automatic texture root unavailable and no Texture Search "
            "Folder is set." % PREFIX)

    for material, info in zip(materials, batch.infos):
        seeds = resolver.build_seeds(
            material.name,
            graph_hits=info.hits,
            material_image_names=info.image_names,
        )
        results = resolver.resolve_roles(
            material.name,
            wanted_roles,
            batch.index,
            graph_hits=info.hits,
            seeds=seeds,
            image_by_name=lambda name: bpy.data.images.get(name),
        )
        _drop_redundant_roughness(results)

        # Roles the imported material named but whose file RSX did not export.
        for role in info.role_hints:
            result = results.get(role)
            if result is not None and result.status == resolver.STATUS_UNRESOLVED:
                result.status = resolver.STATUS_MISSING
                result.note = ("referenced by the imported material but the "
                               "source file is unavailable")

        images = _images_for(results, log)
        batch.results[material.name] = results
        batch.images[material.name] = images
        batch.resolved_total += len(images)

        for result in results.values():
            if result.resolved and result.path:
                directory = os.path.dirname(result.path)
                if directory and directory not in batch.successful_dirs:
                    batch.successful_dirs.append(directory)

        if report_lines:
            for line in resolver.format_report(
                    material.name, info.source_label, results,
                    order=wanted_roles, prefix=PREFIX):
                log(line)

    return batch


def resolve_from_folder(material, wanted_roles, folder, name_override=None,
                        log=_silent):
    """Resolve one material's roles from a single, explicitly chosen folder.

    Recolour uses this: the user has already picked *which* skin folder to
    re-texture from, so there is nothing to discover -- but the file lookup
    inside that folder is the same problem Auto Texture solves.  Sharing the
    resolver means Recolour also understands RSX naming, mip and array
    variants, formats other than PNG, and refuses ambiguous matches, instead
    of the hardcoded ``<name>_<role>Texture.png`` probe it used to carry.

    :param name_override: the skin's base name, when it differs from the
                          material name (which is the normal Recolour case).
    """
    index = paths.TextureIndex()
    index.add_root(folder, rank=0)

    seed_name = name_override or material.name
    results = resolver.resolve_roles(
        seed_name,
        wanted_roles,
        index,
        graph_hits=(),
        seeds=resolver.build_seeds(seed_name),
        image_by_name=lambda name: bpy.data.images.get(name),
    )
    _drop_redundant_roughness(results)
    return results, _images_for(results, log)


def learn_roots(batch, remembered_roots, remember_callback):
    """Record where this run found textures, for the next model."""
    remembered_roots = list(remembered_roots or ())
    if not batch.successful_dirs or remember_callback is None:
        return
    learned = []
    for directory in batch.successful_dirs:
        for base in rootfinder.library_roots(directory):
            if base not in learned:
                learned.append(base)
    if learned:
        remember_callback(rootfinder.remember(remembered_roots, learned))


# --------------------------------------------------------------------------
# Auto Texture operator body
# --------------------------------------------------------------------------

def run(context, shader_key, append_node_group,
        texture_folder="", search_subfolders=False, operator=None,
        remembered_roots=None, remember_callback=None):
    """Entry point used by the ``BUTTON_CUSTOM`` operator.

    :param remembered_roots: export folders previous runs succeeded in.
                             ``None`` means "none yet"; the default is
                             immutable, never a shared list.
    :param remember_callback: called with the updated list once this run has
                              resolved something, so the next model of the same
                              export needs no interaction at all.
    """
    remembered_roots = list(remembered_roots or ())
    definition = shaders.SHADER_DEFS.get(shader_key)
    if definition is None:
        if operator is not None:
            operator.report({"ERROR"}, "Unknown shader option %r" % shader_key)
        return {"CANCELLED"}

    selected = list(context.selected_objects)
    materials = material_slots(selected)
    if not materials:
        message = "Select a mesh with at least one material first."
        _log("%s %s" % (PREFIX, message))
        if operator is not None:
            operator.report({"WARNING"}, message)
        return {"CANCELLED"}

    _log("")
    _log("%s ######## TEXTURING MODEL (%s) ########"
         % (PREFIX, definition.group_name))

    wanted = definition.wanted_roles
    batch = resolve_for_objects(
        selected, wanted,
        texture_folder=texture_folder,
        search_subfolders=search_subfolders,
        remembered_roots=remembered_roots,
        materials=materials,
    )

    # Appending the node group changes the selection, so it happens after the
    # capture pass and the selection is restored immediately afterwards.
    if bpy.data.node_groups.get(definition.group_name) is None:
        append_node_group(definition.group_name, selected)
    if bpy.data.node_groups.get(definition.group_name) is None:
        message = "Could not append the '%s' node group from ApexShader.blend." \
                  % definition.group_name
        _log("%s %s" % (PREFIX, message))
        if operator is not None:
            operator.report({"ERROR"}, message)
        return {"CANCELLED"}

    textured = 0
    skipped = 0

    for material, info in zip(batch.materials, batch.infos):
        results = batch.results.get(material.name, {})
        images = batch.images.get(material.name, {})

        if not images:
            skipped += 1
            missing = [r for r in results.values()
                       if r.status == resolver.STATUS_MISSING]
            if missing or info.role_hints:
                _log("%s Material textures referenced by CAST but source "
                     "files are unavailable. Re-export from RSX with "
                     "'Export Material Textures' enabled, or set a Texture "
                     "Search Folder." % PREFIX)
            else:
                _log("%s No textures could be resolved for '%s'. The imported "
                     "material was left untouched." % (PREFIX, material.name))
            continue

        try:
            shaders.build_material(material, definition, images)
        except (RuntimeError, KeyError, AttributeError) as error:
            skipped += 1
            _log("%s Failed to rebuild '%s': %s. The imported material was "
                 "left untouched." % (PREFIX, material.name, error))
            continue

        textured += 1
        _log("%s Textured %s" % (PREFIX, material.name))
        _log("")

    if batch.resolved_total:
        _log("%s %d texture(s) resolved automatically."
             % (PREFIX, batch.resolved_total))
    learn_roots(batch, remembered_roots, remember_callback)

    summary = "Auto Texture: %d material(s) textured, %d left untouched." % (
        textured, skipped)
    _log("%s %s" % (PREFIX, summary))
    if operator is not None:
        if textured:
            operator.report({"INFO"}, summary)
        else:
            operator.report(
                {"WARNING"},
                summary + " See the console; set a Texture Search Folder if "
                          "the textures live somewhere Auto Texture cannot see.")
    return {"FINISHED"}
