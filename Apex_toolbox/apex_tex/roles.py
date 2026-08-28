# -*- coding: utf-8 -*-
"""Central definition of Apex texture semantic roles and their name aliases.

This module is deliberately free of any ``bpy`` import so that it can be unit
tested with plain CPython.

Background
----------
Apex Toolbox originally assumed a single texture naming convention, the one
produced by Legion / Legion+::

    <blender material name>_albedoTexture.png

RSX (the current Apex asset explorer) can name an exported texture in four
different ways -- ``GUID``, ``Real``, ``Text`` and ``Semantic`` -- so the file
name on disk is no longer a reliable description of what the texture *is*.

Everything that used to be a hard coded string comparison inside the Auto_tex
operator now lives here, as a single alias table shared by every layer of the
resolver and by every shader adapter.
"""

import re

# --------------------------------------------------------------------------
# Canonical roles
# --------------------------------------------------------------------------

ALBEDO = "albedo"
NORMAL = "normal"
SPECULAR = "specular"
GLOSS = "gloss"
ROUGHNESS = "roughness"
EMISSIVE = "emissive"
AO = "ao"
CAVITY = "cavity"
OPACITY = "opacity"
SCATTER = "scatter"
ANISO_SPEC_DIR = "anisoSpecDir"
IRIDESCENCE_RAMP = "iridescenceRamp"

#: Display / node ordering.  The first eleven entries deliberately mirror the
#: legacy ``texSets`` list so that rebuilt materials keep the historical node
#: layout and node names ("0" .. "10").
ROLE_ORDER = [
    ALBEDO,
    SPECULAR,
    EMISSIVE,
    SCATTER,
    OPACITY,
    NORMAL,
    GLOSS,
    AO,
    CAVITY,
    ANISO_SPEC_DIR,
    IRIDESCENCE_RAMP,
    ROUGHNESS,          # not part of the legacy list; appended at the end
]

ALL_ROLES = tuple(ROLE_ORDER)

#: Roles whose image data is colour information.  Everything else is data and
#: is switched to ``Non-Color`` -- this reproduces the historical Auto_tex rule
#: ("index > 2 => Non-Color") exactly, expressed semantically.
COLOR_ROLES = frozenset((ALBEDO, SPECULAR, EMISSIVE))


def is_color_role(role):
    """True when the image for ``role`` must stay in the scene colour space."""
    return role in COLOR_ROLES


# --------------------------------------------------------------------------
# Legacy (Legion+ / RSX "Semantic") canonical file name tokens
# --------------------------------------------------------------------------

#: The exact suffixes the pre-RSX Auto_tex looked for.  These are still probed
#: verbatim by the legacy layer of the resolver, which guarantees that a model
#: exported with Legion+ resolves the way it always did.
LEGACY_TOKENS = {
    ALBEDO: "albedoTexture",
    SPECULAR: "specTexture",
    EMISSIVE: "emissiveTexture",
    SCATTER: "scatterThicknessTexture",
    OPACITY: "opacityMultiplyTexture",
    NORMAL: "normalTexture",
    GLOSS: "glossTexture",
    AO: "aoTexture",
    CAVITY: "cavityTexture",
    ANISO_SPEC_DIR: "anisoSpecDirTexture",
    IRIDESCENCE_RAMP: "iridescenceRampTexture",
}

#: Order in which the legacy layer probes roles (identical to old ``texSets``).
LEGACY_ORDER = [
    ALBEDO, SPECULAR, EMISSIVE, SCATTER, OPACITY, NORMAL,
    GLOSS, AO, CAVITY, ANISO_SPEC_DIR, IRIDESCENCE_RAMP,
]


# --------------------------------------------------------------------------
# Alias table
# --------------------------------------------------------------------------

STRONG = 2
WEAK = 1

#: ``normalised token group -> (role, priority, strength)``
#:
#: * ``role``      -- canonical role, or ``None`` for a *recognised but
#:                    unmapped* suffix (detail maps, masks, ...).  Recording
#:                    them explicitly stops the resolver from mistaking, say,
#:                    ``detailNormalTexture`` for the material's normal map.
#: * ``priority``  -- used to break ties when two files legitimately provide
#:                    the same role (an export folder can hold both
#:                    ``*_albedoTexture.png`` and ``*_col.png``).  Higher wins,
#:                    and the legacy/semantic spellings deliberately outrank
#:                    the short "Real" codes so legacy behaviour is preserved.
#: * ``strength``  -- ``WEAK`` aliases are only accepted when the texture
#:                    family matches the material exactly; they are never used
#:                    for a fuzzy match.
_ALIASES = {}


def _alias(keys, role, priority, strength=STRONG):
    for key in keys:
        _ALIASES[key] = (role, priority, strength)


# -- albedo / diffuse ------------------------------------------------------
_alias(("albedotexture", "albedomap"), ALBEDO, 30)
_alias(("albedo",), ALBEDO, 28)
_alias(("diffusetexture",), ALBEDO, 26)
_alias(("diffuse", "diffusemap"), ALBEDO, 24)
_alias(("basecolor", "basecolour"), ALBEDO, 22)
_alias(("col",), ALBEDO, 20)
_alias(("color", "colour"), ALBEDO, 12, WEAK)

# -- normal ----------------------------------------------------------------
_alias(("normaltexture",), NORMAL, 30)
_alias(("normal", "normalmap"), NORMAL, 28)
_alias(("nml",), NORMAL, 20)
_alias(("nrm", "norm"), NORMAL, 18)

# -- specular --------------------------------------------------------------
_alias(("spectexture", "speculartexture"), SPECULAR, 30)
_alias(("specular",), SPECULAR, 28)
_alias(("spec",), SPECULAR, 26)
_alias(("spc",), SPECULAR, 20)

# -- gloss -----------------------------------------------------------------
_alias(("glosstexture", "glossinesstexture"), GLOSS, 30)
_alias(("gloss", "glossiness"), GLOSS, 28)
_alias(("gls",), GLOSS, 20)

# -- roughness -------------------------------------------------------------
_alias(("roughnesstexture",), ROUGHNESS, 30)
_alias(("roughness",), ROUGHNESS, 28)
_alias(("rough",), ROUGHNESS, 24)
_alias(("rgh",), ROUGHNESS, 20)

# -- emissive --------------------------------------------------------------
_alias(("emissivetexture", "emissiontexture"), EMISSIVE, 30)
_alias(("emissive", "emission"), EMISSIVE, 28)
_alias(("ilm", "illum", "illumination"), EMISSIVE, 20)

# -- ambient occlusion -----------------------------------------------------
_alias(("aotexture", "ambientocclusiontexture", "occlusiontexture"), AO, 30)
_alias(("ambientocclusion", "occlusion"), AO, 28)
_alias(("ao",), AO, 26)

# -- cavity ----------------------------------------------------------------
_alias(("cavitytexture",), CAVITY, 30)
_alias(("cavity",), CAVITY, 28)
_alias(("cav",), CAVITY, 20)

# -- opacity ---------------------------------------------------------------
# ``opacityMultiplyTexture`` is the Apex shader binding Toolbox has always
# used.  Bare "alpha"/"opacity" are intentionally WEAK: in Apex they routinely
# mean something other than the alpha the shader wants.
_alias(("opacitymultiplytexture",), OPACITY, 30)
_alias(("opacitymultiply",), OPACITY, 28)
_alias(("opa",), OPACITY, 20)
_alias(("opacity", "alpha"), OPACITY, 10, WEAK)

# -- scatter / thickness ---------------------------------------------------
_alias(("scatterthicknesstexture",), SCATTER, 30)
_alias(("scatterthickness",), SCATTER, 28)
_alias(("thickness",), SCATTER, 22)
_alias(("thk", "sctr"), SCATTER, 20)
_alias(("scatter",), SCATTER, 16, WEAK)

# -- remaining Apex specific maps -----------------------------------------
_alias(("anisospecdirtexture",), ANISO_SPEC_DIR, 30)
_alias(("anisospecdir",), ANISO_SPEC_DIR, 28)
_alias(("asd",), ANISO_SPEC_DIR, 20)
_alias(("iridescenceramptexture",), IRIDESCENCE_RAMP, 30)
_alias(("iridescenceramp",), IRIDESCENCE_RAMP, 28)

# -- recognised, deliberately unmapped ------------------------------------
# These show up in real RSX exports.  Mapping them to ``None`` means "this is a
# texture role we understand and do not want" -- which is very different from
# "unknown", because it stops a shorter alias inside the same name from being
# picked up by accident.
_alias((
    "detail", "detailtexture", "detailnormal", "detailnormaltexture",
    "detail2", "detail2texture", "detailnormal2texture",
    "uvdistortion", "uvdistortiontexture", "uvdistortion2texture",
    "layerblend", "layerblendtexture",
    "transmittancetint", "transmittancetinttexture",
    "tintmask", "tintmasktexture", "tint", "tnt",
    "emissivemultiply", "emissivemultiplytexture",
    "mask", "msk", "det", "vxd", "bm", "mul", "asa", "ehm", "ehl",
    "multiply", "distortion", "blend", "cubemap", "lightmap",
), None, 0)


#: Tokens that, when they immediately precede a *shortened* alias match, make
#: that match untrustworthy.  Safety net for combinations not listed above.
BLOCKING_MODIFIERS = frozenset((
    "detail", "detail2", "uv", "layer", "tint", "transmittance",
    "sub", "back", "under", "second", "secondary", "alt", "multiply",
    "mask", "msk", "blend",
))

#: Filler words that carry no meaning of their own.
_FILLER_RE = re.compile(r"^(texture|tex|map|maps|image|img)(\d{0,2})$")

#: Mip / LOD / array markers RSX can append.  They identify a *variant of the
#: same texture*, never a role.
_VARIANT_RE = re.compile(r"^(level|lvl|mip|lod|array|slice|layer)(\d+)$")

_TRAILING_DIGITS_RE = re.compile(r"^(.*?)(\d{1,2})$")


def lookup_alias(key):
    """Return ``(role, priority, strength)`` for a normalised token group.

    ``None`` is returned when the group is not a recognised texture role word
    at all.  A tuple whose ``role`` is ``None`` means "recognised, but not a
    role Auto_tex maps".
    """
    return _ALIASES.get(key)


def is_filler(token):
    """``texture``/``map``/... -- carries no role information."""
    return _FILLER_RE.match(token) is not None


def filler_index(token):
    """Trailing index embedded in a filler token (``albedoTexture1`` -> 1)."""
    match = _FILLER_RE.match(token)
    if match and match.group(2):
        return int(match.group(2))
    return None


def is_variant(token):
    """``_level1`` / ``_mip2`` / ``_001`` style markers."""
    if _VARIANT_RE.match(token):
        return True
    return token.isdigit() and len(token) >= 3


def split_trailing_index(key):
    """``normal2`` -> ``("normal", 2)``; ``normal`` -> ``("normal", None)``."""
    match = _TRAILING_DIGITS_RE.match(key)
    if match and match.group(1):
        return match.group(1), int(match.group(2))
    return key, None
