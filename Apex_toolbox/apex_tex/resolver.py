# -*- coding: utf-8 -*-
"""The shared Auto_tex texture resolver.

Pure Python -- no ``bpy`` -- so the whole ranking algorithm can be unit tested
without Blender.  The Blender side (:mod:`.graph`, :mod:`.autotex`) only feeds
it facts and consumes :class:`Resolution` objects.

Resolution hierarchy
--------------------
1. ``graph``    -- a role the CAST importer already established in the node
                   graph.  Highest confidence: it survives *any* RSX naming
                   mode, including GUID file names, because it does not look at
                   the file name at all.
2. ``image``    -- an image datablock already loaded whose file reference is
                   still valid (no reload, no duplicate datablock).
3. ``legacy``   -- the historical ``<material>_<role>Texture.<ext>`` probe.
                   Kept verbatim so Legion+ exports behave exactly as before.
4. ``family``   -- normalised texture-family matching: same family tokens,
                   recognised role suffix, deterministic ranking.
5. ``ambiguous``/``unresolved`` -- reported, never guessed.

A wrong texture is worse than an unresolved texture, so nothing below
:data:`naming.FAMILY_MIN_ACCEPT` is ever connected automatically.
"""

from . import naming
from . import roles as R

# -- resolution sources ----------------------------------------------------

SOURCE_GRAPH = "graph semantic"
SOURCE_IMAGE = "existing image"
SOURCE_LEGACY = "legacy exact"
SOURCE_FAMILY = "family match"

STATUS_RESOLVED = "resolved"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_UNRESOLVED = "unresolved"
STATUS_MISSING = "missing source file"

CONFIDENCE = {
    SOURCE_GRAPH: 100,
    SOURCE_IMAGE: 90,
    SOURCE_LEGACY: 80,
    SOURCE_FAMILY: 70,
}


class GraphHit(object):
    """A role the imported material graph already tells us about."""

    __slots__ = ("role", "image_key", "display", "path", "inverted",
                 "missing", "origin")

    def __init__(self, role, image_key=None, display="", path="",
                 inverted=False, missing=False, origin=SOURCE_GRAPH):
        self.role = role
        self.image_key = image_key
        self.display = display or (path or "")
        self.path = path
        self.inverted = inverted
        self.missing = missing
        self.origin = origin


class Seed(object):
    """A family the current material is known (or believed) to belong to."""

    __slots__ = ("tokens", "origin", "rank")

    def __init__(self, tokens, origin, rank):
        self.tokens = list(tokens)
        self.origin = origin
        self.rank = rank

    @property
    def key(self):
        return tuple(self.tokens)

    def __repr__(self):  # pragma: no cover - debugging aid
        return "<Seed %r from %s>" % (self.tokens, self.origin)


class Resolution(object):
    """The outcome for one role."""

    __slots__ = ("role", "status", "source", "confidence", "image_key",
                 "path", "display", "note", "alternatives", "inverted")

    def __init__(self, role, status=STATUS_UNRESOLVED, source=None,
                 confidence=0, image_key=None, path="", display="",
                 note="", alternatives=None, inverted=False):
        self.role = role
        self.status = status
        self.source = source
        self.confidence = confidence
        self.image_key = image_key
        self.path = path
        self.display = display
        self.note = note
        self.alternatives = alternatives or []
        self.inverted = inverted

    @property
    def resolved(self):
        return self.status == STATUS_RESOLVED

    def __repr__(self):  # pragma: no cover - debugging aid
        return "<Resolution %s %s %r>" % (self.role, self.status, self.display)


# --------------------------------------------------------------------------
# Seeds
# --------------------------------------------------------------------------

SEED_GRAPH = "graph image"
SEED_MATERIAL_IMAGE = "material image"
SEED_MATERIAL_NAME = "material name"
SEED_EXTRA = "extra"

_SEED_RANKS = {
    SEED_GRAPH: 0,
    SEED_MATERIAL_IMAGE: 1,
    SEED_MATERIAL_NAME: 2,
    SEED_EXTRA: 3,
}


def build_seeds(material_name, graph_hits=(), material_image_names=(),
                extra_names=()):
    """Derive the family seeds for a material, best first.

    The material name is *one* seed, not the only one.  RSX "Real" naming makes
    the texture basename the original Apex asset name, which frequently has
    nothing to do with the Blender material name -- but any image the CAST
    importer already attached is, by definition, one of this material's
    textures, so its family is the strongest seed available.
    """
    seeds = []
    seen = set()

    def push(name, origin):
        if not name:
            return
        family = naming.analyze(name).family
        if not family:
            return
        key = tuple(family)
        if key in seen:
            return
        seen.add(key)
        seeds.append(Seed(family, origin, _SEED_RANKS[origin]))

    for hit in graph_hits:
        push(hit.display or hit.path, SEED_GRAPH)
    for name in material_image_names:
        push(name, SEED_MATERIAL_IMAGE)
    push(material_name, SEED_MATERIAL_NAME)
    for name in extra_names:
        push(name, SEED_EXTRA)

    seeds.sort(key=lambda s: s.rank)
    return seeds


# --------------------------------------------------------------------------
# Candidate ranking
# --------------------------------------------------------------------------

class _Candidate(object):
    __slots__ = ("file", "family_score", "seed", "sort_key")

    def __init__(self, texture_file, family_score, seed):
        self.file = texture_file
        self.family_score = family_score
        self.seed = seed
        analysis = texture_file.analysis
        self.sort_key = (
            family_score,                       # family strength first
            -texture_file.root_rank,            # nearer/earlier root wins
            analysis.role_priority,             # canonical spelling wins
            -len(analysis.variants),            # full image over a mip
            -(analysis.binding_index or 0),     # primary binding over _1/_2
            texture_file.size,                  # full resolution wins
        )

    @property
    def grade(self):
        """The part of the sort key that decides ambiguity.

        Everything except the file size: size is the last-resort tie breaker
        and two genuinely different textures must not be separated by it.
        """
        return self.sort_key[:-1]


def _collect(role, texture_files, seeds):
    """All acceptable candidates for ``role``, best first."""
    candidates = []
    near_misses = []
    for texture_file in texture_files:
        analysis = texture_file.analysis
        if analysis.role != role:
            continue
        best_score = naming.FAMILY_NONE
        best_seed = None
        for seed in seeds:
            score = naming.family_score(seed.tokens, analysis.family)
            if score > best_score:
                best_score = score
                best_seed = seed
        if best_score < naming.FAMILY_MIN_ACCEPT:
            if best_score > naming.FAMILY_NONE:
                near_misses.append(texture_file)
            continue
        if analysis.role_strength == R.WEAK and best_score < naming.FAMILY_EXACT:
            # "alpha", "color", "scatter" only count on an exact family match.
            near_misses.append(texture_file)
            continue
        candidates.append(_Candidate(texture_file, best_score, best_seed))

    # Every component of ``sort_key`` is already oriented so that "bigger is
    # better", hence one reverse sort.  Sorting by path first, and relying on
    # Python's stable sort, makes the outcome independent of the order in which
    # the directories happened to be scanned.
    candidates.sort(key=lambda c: c.file.path.lower())
    candidates.sort(key=lambda c: c.sort_key, reverse=True)
    return candidates, near_misses


def _describe(texture_file):
    return texture_file.name


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------

def resolve_roles(material_name, wanted_roles, texture_index,
                  graph_hits=(), seeds=None, image_by_name=None,
                  legacy_extensions=(".png",)):
    """Resolve every role in ``wanted_roles`` for one material.

    :param material_name:  Blender material name (``.001`` suffixes tolerated).
    :param wanted_roles:   iterable of role constants the shader can use.
    :param texture_index:  :class:`paths.TextureIndex` holding the candidates.
    :param graph_hits:     :class:`GraphHit` objects captured from the imported
                           material *before* anything was modified.
    :param seeds:          pre-built :class:`Seed` list; built from the graph
                           hits and the material name when omitted.
    :param image_by_name:  optional ``name -> image_key`` callable so an already
                           loaded datablock is reused instead of reloaded.
    :param legacy_extensions: extensions the legacy exact probe tries, in
                           order, when the material offers no better hint.
    """
    hits = {}
    for hit in graph_hits:
        if hit.role and hit.role not in hits:
            hits[hit.role] = hit

    if seeds is None:
        seeds = build_seeds(material_name, graph_hits=graph_hits)

    files = texture_index.files
    results = {}

    for role in wanted_roles:
        results[role] = _resolve_one(
            role, material_name, hits.get(role), files, seeds,
            texture_index, image_by_name, legacy_extensions)

    return results


def _resolve_one(role, material_name, hit, files, seeds, texture_index,
                 image_by_name, legacy_extensions):
    # ---- layer 1 + 2: what the imported graph already knows -------------
    if hit is not None:
        if hit.missing:
            return Resolution(
                role,
                status=STATUS_MISSING,
                source=hit.origin,
                display=hit.display,
                path=hit.path,
                note="referenced by the imported material but the file is "
                     "not available",
            )
        return Resolution(
            role,
            status=STATUS_RESOLVED,
            source=hit.origin,
            confidence=CONFIDENCE.get(hit.origin, CONFIDENCE[SOURCE_GRAPH]),
            image_key=hit.image_key,
            path=hit.path,
            display=hit.display,
            inverted=hit.inverted,
        )

    # ---- layer 4 first, so that layer 3 can be compared against it -------
    candidates, near_misses = _collect(role, files, seeds)

    # ---- layer 3: legacy Legion+ exact file name ------------------------
    # The historical probe still wins whenever it is at least as close as the
    # best family match.  It is *not* allowed to reach past a nearer search
    # root, though: a Legion export of the same model sitting elsewhere on
    # disk must not beat the RSX export the user just imported.
    legacy_token = R.LEGACY_TOKENS.get(role)
    if legacy_token:
        base = naming.strip_datablock_suffix(material_name)
        stem = base + "_" + legacy_token
        matches = texture_index.by_stem(stem)
        if matches:
            best = sorted(
                matches,
                key=lambda f: (f.root_rank, -f.size, f.path.lower()))[0]
            if not candidates or best.root_rank <= candidates[0].file.root_rank:
                return Resolution(
                    role,
                    status=STATUS_RESOLVED,
                    source=SOURCE_LEGACY,
                    confidence=CONFIDENCE[SOURCE_LEGACY],
                    image_key=best.image_key,
                    path=best.path,
                    display=_describe(best),
                )
        elif image_by_name is not None:
            for extension in legacy_extensions:
                key = image_by_name(stem + extension)
                if key is not None:
                    return Resolution(
                        role,
                        status=STATUS_RESOLVED,
                        source=SOURCE_IMAGE,
                        confidence=CONFIDENCE[SOURCE_IMAGE],
                        image_key=key,
                        display=stem + extension,
                    )

    # ---- layer 4: normalised texture-family matching --------------------
    if not candidates:
        note = ""
        if near_misses:
            note = "closest rejected: " + ", ".join(
                sorted(_describe(f) for f in near_misses)[:3])
        return Resolution(role, status=STATUS_UNRESOLVED, note=note)

    best = candidates[0]
    if len(candidates) > 1:
        runner_up = candidates[1]
        if (runner_up.grade == best.grade
                and runner_up.file.analysis.family_key
                != best.file.analysis.family_key):
            return Resolution(
                role,
                status=STATUS_AMBIGUOUS,
                alternatives=[_describe(best.file), _describe(runner_up.file)],
                note="two equally strong candidates from different texture "
                     "families",
            )

    confidence = CONFIDENCE[SOURCE_FAMILY]
    if best.family_score < naming.FAMILY_EXACT:
        confidence -= 10
    if best.family_score < naming.FAMILY_INDEXED:
        confidence -= 5

    return Resolution(
        role,
        status=STATUS_RESOLVED,
        source=SOURCE_FAMILY,
        confidence=confidence,
        image_key=best.file.image_key,
        path=best.file.path,
        display=_describe(best.file),
    )


# --------------------------------------------------------------------------
# Diagnostics
# --------------------------------------------------------------------------

def format_report(material_name, source_label, results, order=None,
                  prefix="[Auto_tex]"):
    """Build the concise per-material summary printed to the console."""
    lines = ["%s Material: %s" % (prefix, material_name),
             "%s Source: %s" % (prefix, source_label)]
    for role in (order or R.ROLE_ORDER):
        result = results.get(role)
        if result is None:
            continue
        if result.status == STATUS_RESOLVED:
            detail = "%s [%s]" % (result.display, result.source)
            if result.inverted:
                detail += " (gloss from inverted roughness)"
        elif result.status == STATUS_AMBIGUOUS:
            detail = "ambiguous: " + ", ".join(result.alternatives)
        elif result.status == STATUS_MISSING:
            detail = "%s [source file unavailable]" % (result.display,)
        else:
            detail = "unresolved"
            if result.note:
                detail += " (%s)" % result.note
        lines.append("%s %s -> %s" % (prefix, role, detail))
    return lines
