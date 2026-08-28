# -*- coding: utf-8 -*-
"""Texture file name normalisation, role detection and family matching.

Pure Python -- no ``bpy``.  Every rule that used to be an inline
``name.split('_')[-1]`` or ``name.split('.')[1]`` inside the Auto_tex operator
is implemented here once, so that it can be unit tested and so that all three
shader branches share identical behaviour.

Vocabulary
----------
stem
    File name with the directory, the Blender ``.001`` datablock suffix and the
    extension removed.  ``a/b/foo.bar_col.png.001`` -> ``foo.bar_col``.
tokens
    The stem split on separators *and* camel case humps, lower cased.
role
    The semantic meaning of the texture (see :mod:`.roles`).
family
    The tokens that remain once the trailing role / filler / variant tokens
    have been peeled off.  Two textures belonging to the same Apex material
    share a family, whatever naming mode RSX used.
"""

import os
import re

from . import roles as R

#: Extensions Blender can load and that RSX can emit.  Never hard code ".png".
IMAGE_EXTENSIONS = frozenset((
    ".png", ".dds", ".tga", ".tif", ".tiff", ".jpg", ".jpeg",
    ".bmp", ".exr", ".hdr", ".webp", ".jp2", ".cin", ".dpx", ".psd",
))

#: Blender appends ``.001``, ``.002``... when a datablock name collides.
_DATABLOCK_SUFFIX_RE = re.compile(r"\.\d{3}$")

_SEPARATOR_RE = re.compile(r"[\s_\-]+")

# Split "albedoTexture" -> "albedo", "Texture" and "UVDistortion" -> "UV",
# "Distortion" without touching "v20" or "skin42".
_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

#: Longest alias window tried when detecting the role, in tokens.
_MAX_ROLE_WINDOW = 3


# --------------------------------------------------------------------------
# Stem / extension handling
# --------------------------------------------------------------------------

def strip_datablock_suffix(name):
    """Remove Blender's ``.001`` style uniquifying suffix, if present."""
    previous = None
    while previous != name:
        previous = name
        name = _DATABLOCK_SUFFIX_RE.sub("", name)
    return name


def split_name(name):
    """Return ``(stem, extension)`` for a file name or image datablock name.

    Handles multiple periods, ``Image Texture.001``-style datablock suffixes
    and names with no extension at all.  This replaces the old
    ``image.split('.')[1]``, which broke on any name containing more than one
    period.
    """
    base = os.path.basename(name.replace("\\", "/"))
    base = strip_datablock_suffix(base)
    stem, ext = os.path.splitext(base)
    ext = ext.lower()
    if ext and ext not in IMAGE_EXTENSIONS:
        # Not a known image extension: it is part of the name, not a suffix.
        # ``wraith_v20.5_body`` must not lose its ".5".
        stem, ext = base, ""
    return stem, ext


def stem_of(name):
    """Convenience wrapper returning only the stem."""
    return split_name(name)[0]


def is_image_file(name):
    """True when ``name`` carries an extension Blender is able to open."""
    return split_name(name)[1] in IMAGE_EXTENSIONS


# --------------------------------------------------------------------------
# Tokenisation
# --------------------------------------------------------------------------

def tokenize(stem):
    """Split a stem into lower case, separator- and camel-case-free tokens."""
    tokens = []
    for chunk in _SEPARATOR_RE.split(stem.replace(".", "_")):
        if not chunk:
            continue
        for part in _CAMEL_RE.split(chunk):
            if part:
                tokens.append(part.lower())
    return tokens


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------

class TextureName(object):
    """The parsed form of one texture file name."""

    __slots__ = (
        "raw", "stem", "extension", "tokens", "family",
        "role", "role_priority", "role_strength", "role_recognised",
        "binding_index", "variants",
    )

    def __init__(self, raw, stem, extension, tokens, family, role,
                 role_priority, role_strength, role_recognised,
                 binding_index, variants):
        self.raw = raw
        self.stem = stem
        self.extension = extension
        self.tokens = tokens
        self.family = family
        self.role = role
        self.role_priority = role_priority
        self.role_strength = role_strength
        self.role_recognised = role_recognised
        self.binding_index = binding_index
        self.variants = variants

    @property
    def family_key(self):
        return tuple(self.family)

    @property
    def is_variant(self):
        """A mip / LOD / array slice rather than the main image."""
        return bool(self.variants)

    def __repr__(self):  # pragma: no cover - debugging aid
        return "<TextureName %r role=%r family=%r>" % (
            self.stem, self.role, self.family)


def _match_role(work):
    """Find the role described by the trailing tokens of ``work``.

    Returns ``(role, priority, strength, recognised, window_length, index)``.

    The longest alias window wins, which is what keeps ``opacityMultiply`` from
    degrading into ``multiply`` and ``anisoSpecDir`` from degrading into
    ``spec``.  When only a shorter window matches, the token in front of it is
    checked against :data:`roles.BLOCKING_MODIFIERS` so that, for example,
    ``detail_normal`` never resolves to the material's normal map.
    """
    limit = min(_MAX_ROLE_WINDOW, len(work))
    for length in range(limit, 0, -1):
        window = work[len(work) - length:]
        key = "".join(window)
        entry = R.lookup_alias(key)
        index = None
        if entry is None:
            trimmed, index = R.split_trailing_index(key)
            if index is not None:
                entry = R.lookup_alias(trimmed)
            if entry is None:
                continue
        if length < limit:
            previous = work[len(work) - length - 1]
            if previous in R.BLOCKING_MODIFIERS:
                # e.g. "detail" + "normal": a recognised map, but not ours.
                return None, 0, 0, True, 0, None
        role, priority, strength = entry
        return role, priority, strength, True, length, index
    return None, 0, 0, False, 0, None


def analyze(name):
    """Parse a file name / image datablock name into a :class:`TextureName`."""
    stem, extension = split_name(name)
    tokens = tokenize(stem)

    work = list(tokens)
    variants = []
    binding_index = None

    # Peel trailing fillers, mip/array markers and binding indices.  These are
    # variants of the same texture and must never be read as a role.
    while work:
        token = work[-1]
        if R.is_variant(token):
            variants.append(work.pop())
            continue
        if R.is_filler(token):
            index = R.filler_index(token)
            if index is not None and binding_index is None:
                binding_index = index
            work.pop()
            continue
        if token.isdigit() and len(work) > 1:
            # 1-2 digit trailing group: an RSX binding index ("albedoTexture1").
            if binding_index is None:
                binding_index = int(token)
            work.pop()
            continue
        break

    role, priority, strength, recognised, window, index = _match_role(work)
    if index is not None and binding_index is None:
        binding_index = index

    family = work[:len(work) - window] if window else list(work)

    return TextureName(
        raw=name,
        stem=stem,
        extension=extension,
        tokens=tokens,
        family=family,
        role=role,
        role_priority=priority,
        role_strength=strength,
        role_recognised=recognised,
        binding_index=binding_index,
        variants=list(reversed(variants)),
    )


def family_of(name):
    """Family tokens for an arbitrary name (a material name, for instance)."""
    return analyze(name).family


# --------------------------------------------------------------------------
# Family matching
# --------------------------------------------------------------------------

#: Deterministic family match grades.  Anything below ``FAMILY_MIN_ACCEPT`` is
#: considered too weak to connect automatically.
FAMILY_EXACT = 100
FAMILY_INDEXED = 80
FAMILY_SAME_TAIL = 60
FAMILY_LOOSE = 35
FAMILY_NONE = 0

FAMILY_MIN_ACCEPT = 50


def _jaccard(a, b):
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return float(len(sa & sb)) / float(len(sa | sb))


def family_score(seed, candidate):
    """Grade how strongly ``candidate`` family belongs to ``seed`` family.

    The grades are intentionally coarse and conservative.  A wrong texture is
    worse than an unresolved one, so anything that is not either an exact
    match, an indexed sibling of an exact match, or a same-length name sharing
    the body-part tail is rejected outright.
    """
    seed = list(seed)
    candidate = list(candidate)
    if not seed or not candidate:
        return FAMILY_NONE

    if seed == candidate:
        return FAMILY_EXACT

    # ``foo_bar_gear`` vs ``foo_bar_gear_1``: RSX numbers repeated bindings of
    # the same Apex material.  Related, but never preferred over the exact one.
    shorter, longer = (seed, candidate) if len(seed) < len(candidate) else (candidate, seed)
    if longer[:len(shorter)] == shorter:
        extra = longer[len(shorter):]
        if extra and all(token.isdigit() for token in extra):
            return FAMILY_INDEXED
        return FAMILY_NONE

    # Same number of parts and the same trailing part (body / head / gear...)
    # with heavy overlap.  Covers a material renamed slightly by the importer.
    if len(seed) == len(candidate) and seed[-1] == candidate[-1]:
        if _jaccard(seed, candidate) >= 0.7:
            return FAMILY_SAME_TAIL
        return FAMILY_LOOSE

    if _jaccard(seed, candidate) >= 0.5:
        return FAMILY_LOOSE

    return FAMILY_NONE
