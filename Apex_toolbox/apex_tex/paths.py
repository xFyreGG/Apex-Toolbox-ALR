# -*- coding: utf-8 -*-
"""Cross platform discovery and caching of candidate texture files.

Pure Python -- no ``bpy``.

RSX does not guarantee that textures sit next to the model.  Depending on
``Export full asset paths`` and on the chosen texture format, an export can
look like any of::

    model.cast
    model/albedo.png                     # nested, relative CAST path
    model.cast + textures/model/...      # user reorganised the folder
    D:/rsx/exported_files/mdl/...        # absolute path baked into the CAST

Auto_tex therefore never assumes a single directory.  It collects a small,
ordered set of *roots*, indexes each one exactly once (``os.scandir``), and
reuses that index for every material and every shader socket.
"""

import os

from . import naming


class TextureFile(object):
    """One candidate image on disk (or one already-loaded Blender image)."""

    __slots__ = ("path", "name", "analysis", "root_rank", "_size", "image_key")

    def __init__(self, path, name=None, root_rank=0, image_key=None, size=None):
        self.path = path
        self.name = name if name is not None else os.path.basename(path)
        self.analysis = naming.analyze(self.name)
        self.root_rank = root_rank
        self.image_key = image_key
        self._size = size

    @property
    def size(self):
        """File size in bytes; ``-1`` when it cannot be determined.

        Used only as a deterministic tie breaker between two files of the same
        family and role -- it is what makes a full resolution image win over a
        lower mip whose name happened to sort first.
        """
        if self._size is None:
            try:
                self._size = os.path.getsize(self.path)
            except OSError:
                self._size = -1
        return self._size

    def __repr__(self):  # pragma: no cover - debugging aid
        return "<TextureFile %r>" % (self.name,)


def _identity(path):
    """Case- and separator-insensitive identity used for de-duplication."""
    try:
        resolved = os.path.realpath(path)
    except OSError:
        resolved = path
    return os.path.normcase(os.path.normpath(resolved))


class TextureIndex(object):
    """An ordered, de-duplicated, cached index of candidate texture files.

    ``root_rank`` records how trustworthy the directory a file came from is
    (0 = directory of an image this material already references, higher =
    progressively more speculative).  The resolver uses it only as a late tie
    breaker, never to override a family match.
    """

    #: Hard ceiling so that pointing Auto_tex at a huge export tree can never
    #: turn into a multi-minute recursive walk.
    MAX_FILES = 40000
    MAX_DEPTH = 6
    MAX_ENTRIES = 100000
    MAX_DIRECTORIES = 4096

    def __init__(self):
        self._files = []
        self._seen_files = set()
        self._seen_roots = set()
        self._entries = 0
        self._directories = 0
        self.warnings = []
        self._by_path = {}

    def _warn(self, message):
        if message not in self.warnings:
            self.warnings.append(message)

    # -- roots -------------------------------------------------------------

    def add_root(self, directory, rank=0, recursive=False):
        """Index ``directory``.  Returns the number of new files added."""
        if not directory:
            return 0
        key = (_identity(directory), bool(recursive))
        if key in self._seen_roots:
            return 0
        # A non-recursive scan of a directory already walked recursively adds
        # nothing new.
        if not recursive and (_identity(directory), True) in self._seen_roots:
            return 0
        self._seen_roots.add(key)

        if not os.path.isdir(directory):
            return 0

        added = 0
        pending = [(directory, 0)]
        while pending:
            if len(self._files) >= self.MAX_FILES:
                self._warn("Texture limit reached; choose a smaller search folder.")
                break
            if (self._entries >= self.MAX_ENTRIES
                    or self._directories >= self.MAX_DIRECTORIES):
                self._warn("Search limit reached; choose a smaller search folder.")
                break
            current, depth = pending.pop()
            self._directories += 1
            entries = []
            try:
                with os.scandir(current) as scan:
                    for entry in scan:
                        if self._entries >= self.MAX_ENTRIES:
                            self._warn("Search limit reached; choose a smaller search folder.")
                            break
                        self._entries += 1
                        entries.append(entry)
                directories = []
                for entry in sorted(entries, key=lambda e: (e.name.casefold(), e.name)):
                    if entry.is_dir(follow_symlinks=False):
                        if recursive and depth < self.MAX_DEPTH:
                            directories.append((entry.path, depth + 1))
                        elif recursive:
                            self._warn("Depth limit reached; choose a folder closer to the textures.")
                    elif (entry.is_file(follow_symlinks=False)
                          and naming.is_image_file(entry.name)):
                        if self.add_file(entry.path, rank=rank):
                            added += 1
                        if len(self._files) >= self.MAX_FILES:
                            self._warn("Texture limit reached; choose a smaller search folder.")
                            break
                pending.extend(reversed(directories))
            except OSError as error:
                self._warn("Could not read %s: %s" % (current, error))
        return added

    def _add_files(self, directory, names, rank):
        added = 0
        for name in names:
            if not naming.is_image_file(name):
                continue
            path = os.path.join(directory, name)
            if not os.path.isfile(path):
                continue
            if self.add_file(path, rank=rank):
                added += 1
            if len(self._files) >= self.MAX_FILES:
                break
        return added

    # -- individual entries -------------------------------------------------

    def add_file(self, path, rank=0, image_key=None, name=None):
        """Add a single file (or already loaded image).  ``True`` when new."""
        identity = _identity(path)
        if identity in self._seen_files:
            entry = self._by_path[identity]
            entry.root_rank = min(entry.root_rank, rank)
            if image_key is not None:
                entry.image_key = image_key
            return False
        if len(self._files) >= self.MAX_FILES:
            self._warn("Texture limit reached; choose a smaller search folder.")
            return False
        self._seen_files.add(identity)
        entry = TextureFile(path, name=name, root_rank=rank, image_key=image_key)
        self._files.append(entry)
        self._by_path[identity] = entry
        return True

    def add_image(self, name, path, rank=0, image_key=None, size=None):
        """Register an image datablock that may not exist on disk any more."""
        identity = _identity(path) if path else ("<image>" + name)
        if identity in self._seen_files:
            entry = self._by_path[identity]
            entry.root_rank = min(entry.root_rank, rank)
            if image_key is not None:
                entry.image_key = image_key
            return False
        if len(self._files) >= self.MAX_FILES:
            self._warn("Texture limit reached; choose a smaller search folder.")
            return False
        self._seen_files.add(identity)
        entry = TextureFile(path or name, name=name, root_rank=rank,
                            image_key=image_key, size=size)
        self._files.append(entry)
        self._by_path[identity] = entry
        return True

    # -- queries -----------------------------------------------------------

    @property
    def files(self):
        return self._files

    def __len__(self):
        return len(self._files)

    def by_stem(self, stem):
        """Case-insensitive exact stem lookup (the legacy layer uses this)."""
        wanted = stem.lower()
        return [f for f in self._files if f.analysis.stem.lower() == wanted]


# --------------------------------------------------------------------------
# Path helpers
# --------------------------------------------------------------------------

def directory_of(path):
    """Directory containing ``path``, or ``""``."""
    if not path:
        return ""
    return os.path.dirname(os.path.abspath(path))


def resolve_relative(base_file, relative):
    """Resolve a CAST-style relative asset path against the model file.

    Mirrors the CAST importer's own ``utilityBuildPath``: absolute paths are
    kept, everything else is joined to the *directory* of the referring file.
    """
    if not relative:
        return ""
    if os.path.isabs(relative):
        return os.path.normpath(relative)
    return os.path.normpath(os.path.join(directory_of(base_file), relative))


def sibling_directories(directory, limit=8):
    """Directories one level below and beside ``directory``.

    An RSX export is normally ``<model>/<model>/<textures>``; the CAST file
    sits one level above its texture folder.  Looking one level down (and, for
    reorganised folders, at the immediate siblings) finds the textures without
    a recursive walk of the whole export tree.
    """
    found = []
    if not directory or not os.path.isdir(directory):
        return found
    try:
        entries = sorted(os.listdir(directory))
    except OSError:
        return found
    for name in entries:
        candidate = os.path.join(directory, name)
        if os.path.isdir(candidate):
            found.append(candidate)
        if len(found) >= limit:
            break
    return found
