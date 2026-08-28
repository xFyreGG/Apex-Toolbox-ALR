# -*- coding: utf-8 -*-
"""Read the semantic roles out of an imported material's node graph.

This is the highest confidence source Auto_tex has, and the reason RSX GUID
naming works at all: the CAST importer binds each texture to a shader socket
using the material's *shader resource bindings*, so the graph knows that
``0x47BCE128CF.png`` is the normal map even though the file name says nothing.

Everything here is read-only.  Nothing is deleted or rewired; the caller
captures the result first and only rebuilds the material afterwards.

Supported imported graphs
-------------------------
* ``ShaderNodeBsdfPrincipled`` -- what the CAST importer builds for materials
  that expose a ``metal`` slot, and what most other importers produce.
* ``ShaderNodeEeveeSpecular``  -- what the CAST importer builds for Apex
  specular/gloss materials, which is the normal case for RSX exports.
* Apex Toolbox's own node groups -- so re-running Auto_tex, or switching from
  one Apex shader to another, keeps every texture.
* Anything else -- a conservative fallback that only trusts unambiguous
  structures such as ``Image -> Normal Map``.

Nodes are found by ``bl_idname``, never by display name: Blender is free to
call them ``Image Texture``, ``Image Texture.001`` or anything the user typed.
"""

import os

import bpy

from . import roles as R
from . import shaders
from .resolver import GraphHit, SOURCE_GRAPH

TEX_IMAGE = "ShaderNodeTexImage"
NORMAL_MAP = "ShaderNodeNormalMap"
BUMP = "ShaderNodeBump"
INVERT = "ShaderNodeInvert"
MATH = "ShaderNodeMath"
GROUP = "ShaderNodeGroup"
OUTPUT = "ShaderNodeOutputMaterial"

#: Nodes we are willing to look straight through while tracing a socket back
#: to its image, together with the input sockets worth following.
_PASSTHROUGH = {
    NORMAL_MAP: ("Color",),
    BUMP: ("Height", "Color"),
    INVERT: ("Color",),
    "ShaderNodeGamma": ("Color",),
    "ShaderNodeBrightContrast": ("Color",),
    "ShaderNodeHueSaturation": ("Color",),
    "ShaderNodeRGBCurve": ("Color",),
    "ShaderNodeMixRGB": ("Color1", "Color2"),
    "ShaderNodeMix": ("A", "B", "A_Color", "B_Color"),
    "ShaderNodeSeparateColor": ("Color",),
    "ShaderNodeSeparateRGB": ("Image",),
    "ShaderNodeMapRange": ("Value",),
    "ShaderNodeValToRGB": ("Fac",),
}

_MAX_TRACE_DEPTH = 8

#: ``bl_idname -> {input socket name: role}``.
#:
#: The ``Roughness`` socket is deliberately mapped to ``ROUGHNESS``; whether
#: the underlying image is really a gloss map is decided by the inversion the
#: trace walks through (the CAST importer inserts ``Invert`` for gloss).
_SHADER_SOCKETS = {
    "ShaderNodeBsdfPrincipled": {
        "Base Color": R.ALBEDO,
        "Specular": R.SPECULAR,
        "Specular IOR Level": R.SPECULAR,
        "Specular Tint": R.SPECULAR,
        "Roughness": R.ROUGHNESS,
        "Normal": R.NORMAL,
        "Emission": R.EMISSIVE,
        "Emission Color": R.EMISSIVE,
        "Alpha": R.OPACITY,
    },
    "ShaderNodeEeveeSpecular": {
        "Base Color": R.ALBEDO,
        "Specular": R.SPECULAR,
        "Roughness": R.ROUGHNESS,
        "Emissive Color": R.EMISSIVE,
        "Normal": R.NORMAL,
        "Ambient Occlusion": R.AO,
    },
    "ShaderNodeBsdfDiffuse": {
        "Color": R.ALBEDO,
        "Roughness": R.ROUGHNESS,
        "Normal": R.NORMAL,
    },
    "ShaderNodeBsdfGlossy": {
        "Color": R.SPECULAR,
        "Roughness": R.ROUGHNESS,
        "Normal": R.NORMAL,
    },
    "ShaderNodeBsdfAnisotropic": {
        "Color": R.SPECULAR,
        "Roughness": R.ROUGHNESS,
        "Normal": R.NORMAL,
    },
    "ShaderNodeEmission": {
        "Color": R.EMISSIVE,
    },
}


class GraphInfo(object):
    """Everything worth knowing about a material before it is rebuilt."""

    __slots__ = ("hits", "role_hints", "images", "image_names",
                 "directories", "source_label", "shader_node")

    def __init__(self):
        self.hits = []
        #: Roles the graph clearly describes but for which no usable image
        #: exists (RSX exported the CAST without exporting the textures).
        self.role_hints = set()
        self.images = []
        self.image_names = []
        self.directories = []
        self.source_label = "unrecognised material"
        self.shader_node = None

    @property
    def roles(self):
        return set(hit.role for hit in self.hits)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def image_filepath(image):
    """Absolute, normalised path of an image datablock (``""`` if unknown)."""
    if image is None:
        return ""
    raw = getattr(image, "filepath_raw", "") or getattr(image, "filepath", "")
    if not raw:
        return ""
    try:
        absolute = bpy.path.abspath(raw, library=image.library)
    except (AttributeError, TypeError):
        absolute = bpy.path.abspath(raw)
    return os.path.normpath(absolute)


def image_is_available(image):
    """True when Blender can actually render this image.

    An image datablock can exist with no pixels at all: the CAST importer
    creates the texture node and the link before it tries to load the file, and
    swallows the ``RuntimeError`` when the file is missing.  That is exactly
    what an RSX export with ``Export Material Textures`` disabled looks like.
    """
    if image is None:
        return False
    if getattr(image, "packed_file", None) is not None:
        return True
    try:
        if tuple(image.size) != (0, 0):
            return True
    except (AttributeError, TypeError):
        pass
    path = image_filepath(image)
    return bool(path) and os.path.isfile(path)


def _is_math_invert(node):
    """``1 - x`` expressed with a Math node."""
    if node.bl_idname != MATH:
        return False
    if node.operation != "SUBTRACT":
        return False
    first = node.inputs[0]
    return not first.links and abs(first.default_value - 1.0) < 1e-6


def _trace(socket, depth=0, inverted=False):
    """Walk backwards from ``socket`` to the image feeding it.

    Returns ``(node, inverted, output_name)`` or ``(None, False, "")``.
    ``inverted`` records whether the value was passed through an inversion,
    which is how a gloss map is distinguished from a roughness map.
    ``output_name`` is the image output the chain started from, so that a link
    taken from another map's ``Alpha`` channel is not mistaken for a texture
    of its own.
    """
    if depth > _MAX_TRACE_DEPTH or not socket.links:
        return None, False, ""
    link = socket.links[0]
    node = link.from_node
    if node.bl_idname == TEX_IMAGE:
        return node, inverted, link.from_socket.name
    if node.bl_idname == INVERT:
        target = node.inputs.get("Color")
        if target is not None:
            return _trace(target, depth + 1, not inverted)
        return None, False, ""
    if _is_math_invert(node):
        return _trace(node.inputs[1], depth + 1, not inverted)
    for name in _PASSTHROUGH.get(node.bl_idname, ()):
        target = node.inputs.get(name)
        if target is not None and target.links:
            found, was_inverted, output_name = _trace(target, depth + 1, inverted)
            if found is not None:
                return found, was_inverted, output_name
    return None, False, ""


def _trace_image(socket):
    """``_trace`` with the "came from another map's alpha channel" guard."""
    node, inverted, output_name = _trace(socket)
    if node is not None and output_name == "Alpha":
        # This socket is fed by the alpha channel of a colour map, not by a
        # texture of its own.  The shader adapters wire those links themselves.
        return None, False
    return node, inverted


def _output_shader(tree):
    """The surface shader node of ``tree``, or ``None``."""
    outputs = [n for n in tree.nodes if n.bl_idname == OUTPUT]
    if not outputs:
        return None
    output = None
    for node in outputs:
        if getattr(node, "is_active_output", False):
            output = node
            break
    if output is None:
        output = outputs[0]
    surface = output.inputs.get("Surface")
    if surface is None and len(output.inputs):
        surface = output.inputs[0]
    if surface is None or not surface.links:
        return None
    return surface.links[0].from_node


def _hit_from_node(role, node, inverted):
    image = node.image
    display = image.name if image is not None else ""
    return GraphHit(
        role=role,
        image_key=image,
        display=display,
        path=image_filepath(image),
        inverted=inverted,
        missing=not image_is_available(image),
        origin=SOURCE_GRAPH,
    )


# --------------------------------------------------------------------------
# Inspection
# --------------------------------------------------------------------------

def inspect_material(material):
    """Capture the semantic information of ``material`` without touching it."""
    info = GraphInfo()
    tree = getattr(material, "node_tree", None)
    if tree is None:
        info.source_label = "material without a node tree"
        return info

    # Every image in the tree, whatever the node is called and whether or not
    # it is connected.  Used for search roots and as family seeds.
    for node in tree.nodes:
        if node.bl_idname != TEX_IMAGE or node.image is None:
            continue
        info.images.append(node.image)
        if node.image.name not in info.image_names:
            info.image_names.append(node.image.name)
        directory = os.path.dirname(image_filepath(node.image))
        if directory and directory not in info.directories:
            info.directories.append(directory)

    shader = _output_shader(tree)
    info.shader_node = shader

    raw = {}

    if shader is not None and shader.bl_idname == GROUP:
        group_name = getattr(shader.node_tree, "name", "")
        mapping = shaders.socket_role_map().get(group_name)
        if mapping is not None:
            info.source_label = "existing Apex Toolbox material (%s)" % group_name
            for socket_name, role in mapping.items():
                socket = shader.inputs.get(socket_name)
                if socket is None:
                    continue
                node, inverted = _trace_image(socket)
                if node is None:
                    continue
                if role == R.GLOSS and inverted:
                    # We built this graph on a previous run from a roughness
                    # map.  Report the image as what it is so the next rebuild
                    # inverts it exactly once again.
                    role = R.ROUGHNESS
                raw.setdefault(role, (node, False))
    elif shader is not None and shader.bl_idname in _SHADER_SOCKETS:
        friendly = {
            "ShaderNodeEeveeSpecular": "RSX/CAST specular material",
            "ShaderNodeBsdfPrincipled": "imported Principled material",
        }
        info.source_label = friendly.get(shader.bl_idname,
                                         "imported %s material" % shader.bl_idname)
        for socket_name, role in _SHADER_SOCKETS[shader.bl_idname].items():
            socket = shader.inputs.get(socket_name)
            if socket is None or not socket.links:
                continue
            node, inverted = _trace_image(socket)
            if node is None:
                continue
            if role == R.ROUGHNESS and inverted:
                # Image -> Invert -> Roughness is how a gloss map reaches a
                # roughness socket.  It is a gloss texture, not a roughness one.
                role = R.GLOSS
                inverted = False
            raw.setdefault(role, (node, inverted))

    # Conservative structural fallback: a Normal Map node fed by an image is
    # unambiguous whatever shader sits in front of it.
    if R.NORMAL not in raw:
        for node in tree.nodes:
            if node.bl_idname != NORMAL_MAP:
                continue
            colour = node.inputs.get("Color")
            if colour is None:
                continue
            found, _inverted = _trace_image(colour)
            if found is not None:
                raw[R.NORMAL] = (found, False)
                break

    for role, (node, inverted) in raw.items():
        if node.image is None:
            # The importer created the binding but could not load the file.
            info.role_hints.add(role)
            continue
        hit = _hit_from_node(role, node, inverted)
        if hit.missing:
            info.role_hints.add(role)
            continue
        info.hits.append(hit)

    if not info.hits and not info.role_hints and info.source_label.startswith(
            "unrecognised"):
        if shader is not None:
            info.source_label = "material with no texture bindings (%s)" % (
                shader.bl_idname,)

    return info
