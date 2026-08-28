# -*- coding: utf-8 -*-
"""Automatic discovery of the directories Auto_tex should search.

Pure Python -- no ``bpy``.  The Blender side gathers the raw facts (image
paths, collection names, remembered roots) and hands them here.

Why this exists
---------------
Beta 3 resolved textures perfectly once it had a directory to look in, but it
could only find that directory from images the CAST importer had already
loaded.  When an RSX CAST carries no texture bindings at all -- which is what
``Real`` and ``GUID`` naming modes produce -- the imported material holds no
images, so there was nothing to anchor the search to and the user had to pick
the folder by hand.

The CAST importer stores no source path on the objects or collections it
creates (verified against io_scene_cast 1.6.7), so there is no single field to
read.  What it *does* leave behind is a **collection named after the .cast
file**, e.g. ``wraith_v20_heist_w_LOD0``.  Strip the LOD suffix and that is
exactly the name of both the RSX export folder and the texture folder inside
it::

    <export library>/wraith_v20_heist_w/wraith_v20_heist_w_LOD0.cast
    <export library>/wraith_v20_heist_w/wraith_v20_heist_w/*.png

So the strategy is: derive the model name from what the importer named things,
then *probe* a small set of known RSX layouts under every base directory we
have any reason to believe in -- including bases remembered from previous
successful runs.  Probing is a handful of ``os.path.isdir`` calls; no directory
is walked unless a probe has already matched or the user explicitly asked for
a recursive search.
"""

import os
import re

#: Search ranks.  Lower is more trustworthy; the resolver only uses these to
#: break ties that family matching has already declared equal.
RANK_MATERIAL_IMAGE = 0     # directory of an image this material already has
RANK_MODEL_NEIGHBOUR = 1    # beside/below that directory
RANK_MANUAL = 2             # the folder the user picked
RANK_PROBED = 3             # a model folder found by probing a known layout
RANK_REMEMBERED = 4         # a base directory a previous run succeeded in
RANK_BROWSED = 5            # a folder the Blender file browser was last in
RANK_LOADED_IMAGE = 6       # directory of any other image in the blend
RANK_BLEND = 7              # next to the .blend file

_LOD_RE = re.compile(r"_lod\d+$", re.IGNORECASE)
_MESH_INDEX_RE = re.compile(r"^(?:body|mesh)_\d+_", re.IGNORECASE)

#: Directory names RSX and Legion+ use for the layer above a model folder.
_LIBRARY_DIRS = ("mdl", "models", "exported_files", "Materials", "materials")

#: Layouts probed under a base directory for a model called ``N``.
#: ``{n}`` is the model name.  Ordered cheapest/most likely first.
_LAYOUTS = (
    "{n}/{n}",          # RSX: <export>/<model>/<model>/*.png
    "{n}",              # textures directly inside the model folder
    "{n}/Materials",    # Legion+ style
    "{n}/_images",      # Legion+ style
    "mdl/{n}/{n}",      # base is the RSX exported_files folder
    "mdl/{n}",
)

MAX_REMEMBERED = 8


class Root(object):
    """One directory Auto_tex will index."""

    __slots__ = ("path", "rank", "recursive", "origin")

    def __init__(self, path, rank, recursive=False, origin=""):
        self.path = path
        self.rank = rank
        self.recursive = recursive
        self.origin = origin

    def __repr__(self):  # pragma: no cover - debugging aid
        return "<Root %s rank=%d %s>" % (self.path, self.rank, self.origin)


# --------------------------------------------------------------------------
# Model names
# --------------------------------------------------------------------------

def clean_model_name(name):
    """Turn a Blender datablock name into a plausible export folder name.

    ``wraith_v20_heist_w_LOD0``      -> ``wraith_v20_heist_w``
    ``body_0_wraith_..._body``       -> ``wraith_..._body``
    ``wraith_v20_heist_w_LOD0.001``  -> ``wraith_v20_heist_w``
    """
    if not name:
        return ""
    name = re.sub(r"\.\d{3}$", "", name.strip())
    name = _MESH_INDEX_RE.sub("", name)
    name = _LOD_RE.sub("", name)
    return name


def model_names(raw_names):
    """Ordered, de-duplicated model-folder candidates from datablock names."""
    found = []
    for raw in raw_names:
        cleaned = clean_model_name(raw)
        if cleaned and cleaned not in found:
            found.append(cleaned)
    return found


# --------------------------------------------------------------------------
# Probing
# --------------------------------------------------------------------------

def _isdir(path, isdir):
    try:
        return isdir(path)
    except OSError:
        return False


def probe(base, names, isdir=os.path.isdir):
    """Existing directories matching a known RSX/Legion layout under ``base``.

    Only ``os.path.isdir`` calls -- nothing is walked.  Returns paths in the
    order the layouts are listed, best first, de-duplicated.
    """
    found = []
    if not base or not _isdir(base, isdir):
        return found
    for name in names:
        if not name:
            continue
        for layout in _LAYOUTS:
            candidate = os.path.normpath(
                os.path.join(base, *layout.format(n=name).split("/")))
            if candidate not in found and _isdir(candidate, isdir):
                found.append(candidate)
    return found


def ancestors(directory, levels=2):
    """``directory`` and up to ``levels`` parents, nearest first."""
    result = []
    current = os.path.normpath(directory) if directory else ""
    for _ in range(levels + 1):
        if not current or current in result:
            break
        result.append(current)
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return result


def library_roots(texture_dir, isdir=os.path.isdir):
    """Base directories worth remembering after a successful resolution.

    From ``…/mdl/wraith_v20_heist_w/wraith_v20_heist_w`` this yields
    ``…/mdl/wraith_v20_heist_w`` and ``…/mdl`` -- the levels from which the
    layout probes above can find *other* models of the same export.
    """
    remembered = []
    for candidate in ancestors(texture_dir, levels=2)[1:]:
        if _isdir(candidate, isdir):
            remembered.append(candidate)
    # A recognised library directory ("mdl", "models", ...) is the most useful
    # base of all, because every *other* model of the export sits under it.
    # Move it to the front whether or not it was already collected.
    for candidate in ancestors(texture_dir, levels=4):
        if os.path.basename(candidate) in _LIBRARY_DIRS:
            if candidate in remembered:
                remembered.remove(candidate)
            remembered.insert(0, candidate)
            break
    return remembered


#: Only the head of each list is considered, so a long history costs nothing.
MAX_RECENT = 12
MAX_BOOKMARKS = 8


def parse_bookmarks(text, max_recent=MAX_RECENT, max_bookmarks=MAX_BOOKMARKS):
    """Directories out of Blender's ``bookmarks.txt``, most useful first.

    Blender's file browser records the folders the user has recently browsed
    (``[Recent]``) and their saved bookmarks (``[Bookmarks]``) in a plain text
    file in the user config directory.  After importing a CAST the top of the
    recent list *is* the model's export folder, which is the one thing the CAST
    importer itself does not record anywhere.

    Reading it is local and read-only; nothing is written back.
    """
    recent = []
    bookmarks = []
    section = None
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("["):
            section = line.strip("[]").lower()
            continue
        if section == "recent":
            recent.append(line)
        elif section == "bookmarks":
            bookmarks.append(line)
    return recent[:max_recent], bookmarks[:max_bookmarks]


def remember(existing, new_paths, limit=MAX_REMEMBERED):
    """Most-recent-first, case-insensitively de-duplicated root memory."""
    ordered = []
    seen = set()
    for path in list(new_paths) + list(existing):
        if not path:
            continue
        normalised = os.path.normpath(path)
        key = os.path.normcase(normalised)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalised)
        if len(ordered) >= limit:
            break
    return ordered


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------

def discover(material_dirs=(), names=(), manual="", search_subfolders=False,
             remembered=(), browsed=(), image_dirs=(), blend_dir="",
             isdir=os.path.isdir):
    """Build the ordered list of directories Auto_tex should index.

    :param material_dirs: directories of images already in the materials being
                          textured -- the strongest anchor there is.
    :param names:         model-name candidates (collections, objects,
                          materials) used for layout probing.
    :param manual:        the optional *Texture Search Folder*.
    :param search_subfolders: index ``manual`` recursively.
    :param remembered:    base directories previous runs succeeded in.
    :param image_dirs:    directories of every other image in the blend.
    :param blend_dir:     directory of the saved .blend, if any.
    """
    roots = []
    seen = set()

    def push(path, rank, recursive=False, origin=""):
        if not path:
            return
        normalised = os.path.normpath(path)
        key = os.path.normcase(normalised)
        if key in seen or not _isdir(normalised, isdir):
            return
        seen.add(key)
        roots.append(Root(normalised, rank, recursive, origin))

    cleaned = model_names(names)

    # 1. The material already tells us where its textures live.
    for directory in material_dirs:
        push(directory, RANK_MATERIAL_IMAGE, origin="material image")

    # 2. Beside and below those directories: RSX nests textures one level in.
    for directory in material_dirs:
        for base in ancestors(directory, levels=2)[1:]:
            for probed in probe(base, cleaned, isdir):
                push(probed, RANK_MODEL_NEIGHBOUR, origin="beside the model")

    # 3. The folder the user picked, plus the model folders inside it.
    if manual:
        push(manual, RANK_MANUAL, recursive=bool(search_subfolders),
             origin="Texture Search Folder")
        for probed in probe(manual, cleaned, isdir):
            push(probed, RANK_PROBED, recursive=True,
                 origin="model folder in the search folder")

    # 4. Anywhere a previous run succeeded -- this is what makes the second and
    #    every later model of an export library resolve with no interaction.
    for base in remembered:
        for probed in probe(base, cleaned, isdir):
            push(probed, RANK_PROBED, recursive=True,
                 origin="model folder in a remembered export folder")
    for base in remembered:
        push(base, RANK_REMEMBERED, origin="remembered export folder")

    # 5. Where Blender's file browser has recently been.  After importing a
    #    CAST the top of that list is the model's own export folder, which is
    #    what makes a cold first run resolve with no interaction at all.
    # The parent is probed as well as the folder itself: a user who last
    # browsed <library>/<some other model>/ has, without knowing it, told us
    # where the whole export library lives.
    for base in browsed:
        for candidate in ancestors(base, levels=1):
            for probed in probe(candidate, cleaned, isdir):
                push(probed, RANK_PROBED, recursive=True,
                     origin="model folder in a recently browsed folder")
    for index, base in enumerate(browsed):
        push(base, RANK_BROWSED,
             recursive=False,
             origin="recently browsed folder")
        if index >= 3:
            break

    # 6. Directories of any other image in the blend.
    for directory in image_dirs:
        push(directory, RANK_LOADED_IMAGE, origin="loaded image")

    # 6. Last resort.
    push(blend_dir, RANK_BLEND, origin="blend file folder")

    return roots


def describe(roots, limit=3):
    """Short human summary of where Auto_tex is going to look."""
    if not roots:
        return "no texture folder could be determined"
    parts = []
    for root in roots[:limit]:
        parts.append("%s (%s)" % (root.path, root.origin or "root"))
    if len(roots) > limit:
        parts.append("+%d more" % (len(roots) - limit))
    return "; ".join(parts)
