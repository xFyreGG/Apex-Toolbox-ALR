# -*- coding: utf-8 -*-
"""Shader adapters: how each Apex Toolbox shader wants the resolved roles.

Texture *discovery* happens once, in :mod:`.resolver`.  This module only maps
the resolved semantic roles onto the sockets of whichever node group the user
picked, and knows which representation each socket expects.

The socket names below are the ones the existing Apex Toolbox node groups have
always used; they are reproduced unchanged so that a model textured with the
previous release looks identical after this update.
"""

import bpy

from . import roles as R

#: Shader groups keyed by the ``cust_enum2`` value of the Auto_tex panel.
OP_APEX_SHADER = "OP1"
OP_APEX_SHADER_PLUS = "OP2"
OP_SG_BLENDER = "OP3"


class ShaderDef(object):
    """Description of one Apex Toolbox shader node group."""

    __slots__ = ("key", "group_name", "sockets", "alpha_sockets",
                 "extra_roles", "gloss_expects")

    def __init__(self, key, group_name, sockets, alpha_sockets,
                 extra_roles=(), gloss_expects=R.GLOSS):
        self.key = key
        self.group_name = group_name
        #: ``role -> input socket name`` for the Color output of the image.
        self.sockets = sockets
        #: ``role -> input socket name`` for the Alpha output of the image.
        self.alpha_sockets = alpha_sockets
        #: Roles whose image node is created but intentionally left
        #: unconnected (the shader groups expose no socket for them, but the
        #: node has always been placed in the tree for manual wiring).
        self.extra_roles = tuple(extra_roles)
        #: ``R.GLOSS`` when the socket wants glossiness, ``R.ROUGHNESS`` when
        #: it wants roughness.  All three Apex shaders want glossiness.
        self.gloss_expects = gloss_expects

    @property
    def wanted_roles(self):
        """Every role this shader can consume, in node layout order."""
        wanted = [r for r in R.ROLE_ORDER
                  if r in self.sockets or r in self.extra_roles]
        # Roughness is never a socket of its own; it is resolved so that it can
        # be converted into glossiness when no gloss map exists.
        if R.GLOSS in self.sockets and R.ROUGHNESS not in wanted:
            wanted.append(R.ROUGHNESS)
        return wanted

    def role_for_socket(self, socket_name):
        for role, name in self.sockets.items():
            if name == socket_name:
                return role
        return None


SHADER_DEFS = {
    OP_APEX_SHADER: ShaderDef(
        OP_APEX_SHADER,
        "Apex Shader",
        sockets={
            R.ALBEDO: "Albedo Map",
            R.SPECULAR: "Specular Map",
            R.EMISSIVE: "Emission",
            R.SCATTER: "SSS Map",
            R.OPACITY: "Alpha",
            R.NORMAL: "Normal Map",
            R.GLOSS: "Glossiness Map",
            R.AO: "AO",
        },
        alpha_sockets={
            R.ALBEDO: "Alpha",
            R.SCATTER: "SSS Alpha",
        },
        extra_roles=(R.ANISO_SPEC_DIR, R.IRIDESCENCE_RAMP),
    ),
    OP_APEX_SHADER_PLUS: ShaderDef(
        OP_APEX_SHADER_PLUS,
        "Apex Shader+_v3.4",
        sockets={
            R.ALBEDO: "Albedo",
            R.SPECULAR: "Specular",
            R.EMISSIVE: "Emission",
            # Apex Shader+ calls these "Scatter Thickness (Radius)" and
            # "Alpha (Opacity Multiply)".  The previous release asked for
            # "SSS Map" and "Alpha" -- names this group does not have -- and
            # the failed links vanished into a bare ``except: pass``, so SSS,
            # opacity and alpha were silently never connected.  The names now
            # match the group, which restores the documented capability.
            R.SCATTER: "Scatter Thickness (Radius)",
            R.OPACITY: "Alpha (Opacity Multiply)",
            R.NORMAL: "Normal Map",
            R.GLOSS: "Glossiness",
            R.AO: "Ambient Occlusion",
            R.CAVITY: "Cavity",
        },
        alpha_sockets={
            R.ALBEDO: "Alpha (Opacity Multiply)",
            R.SCATTER: "Scatter Thickness Alpha",
        },
        # "Anis-Spec Dir" exists on this group, but Auto_tex has never driven
        # it and doing so would change how existing models shade.  The node is
        # created and placed for manual wiring, exactly as before.
        extra_roles=(R.ANISO_SPEC_DIR, R.IRIDESCENCE_RAMP),
    ),
    OP_SG_BLENDER: ShaderDef(
        OP_SG_BLENDER,
        "S/G-Blender",
        sockets={
            R.ALBEDO: "Diffuse map",
            R.SPECULAR: "Specular map",
            R.EMISSIVE: "Emission input",
            R.SCATTER: "Subsurface",
            R.OPACITY: "Alpha input",
            R.NORMAL: "Normal map",
            R.GLOSS: "Glossiness map",
            R.AO: "AO map",
            R.CAVITY: "Cavity map",
        },
        alpha_sockets={
            # S/G-Blender names its alpha socket "Alpha input"; the Recolor
            # operator has always used that name, Auto_tex used "Alpha" and the
            # link silently failed inside a bare ``except``.  Both now agree.
            # This group has no scatter alpha socket, so none is listed.
            R.ALBEDO: "Alpha input",
        },
        extra_roles=(R.ANISO_SPEC_DIR, R.IRIDESCENCE_RAMP),
    ),
}

#: Node group names Auto_tex recognises as "already an Apex Toolbox material".
KNOWN_GROUP_NAMES = frozenset(d.group_name for d in SHADER_DEFS.values())


def socket_role_map():
    """``group name -> {socket name: role}`` for re-reading our own materials."""
    mapping = {}
    for definition in SHADER_DEFS.values():
        mapping[definition.group_name] = {
            name: role for role, name in definition.sockets.items()}
    return mapping


# --------------------------------------------------------------------------
# Material construction
# --------------------------------------------------------------------------

def _legacy_node_name(role):
    """Historical numeric node name so the layout matches previous releases."""
    if role in R.LEGACY_ORDER:
        return str(R.LEGACY_ORDER.index(role))
    if role == R.ROUGHNESS:
        # Roughness occupies the gloss slot; it is only ever created when no
        # gloss map was found.
        return str(R.LEGACY_ORDER.index(R.GLOSS))
    return role


def _legacy_index(role):
    name = _legacy_node_name(role)
    try:
        return int(name)
    except ValueError:
        return len(R.LEGACY_ORDER)


def apply_colorspace(image, role):
    """Reproduce the historical colour space rule, expressed semantically.

    The old operator switched every texture past index 2 of ``texSets`` to
    ``Non-Color``; indices 0..2 were albedo, specular and emissive.  Colour
    roles are therefore left in the scene colour space and every data map --
    normal, gloss, roughness, AO, cavity, thickness, opacity, masks -- is set
    to ``Non-Color``.  ``CHANNEL_PACKED`` alpha handling is preserved for all.
    """
    if image is None:
        return
    if not R.is_color_role(role):
        try:
            image.colorspace_settings.name = "Non-Color"
        except (TypeError, AttributeError):
            pass
    try:
        image.alpha_mode = "CHANNEL_PACKED"
    except (TypeError, AttributeError):
        pass


def build_material(material, definition, images, log=None, plug_alpha=True):
    """Rebuild ``material`` around ``definition`` using ``images``.

    :param images: ``role -> bpy.types.Image``.  The role always describes what
                   the image *is*; any conversion the target socket needs (a
                   roughness map feeding a glossiness socket) is added here, in
                   the node graph, never to the source image.

    The existing nodes are removed only *after* the replacement graph has been
    built successfully, so a failure part way through leaves the imported
    material usable.
    """
    group_tree = bpy.data.node_groups.get(definition.group_name)
    if group_tree is None:
        raise RuntimeError(
            "Shader node group '%s' is not available" % definition.group_name)

    if not material.is_editable:
        raise RuntimeError("Linked material is read-only; make it local first")
    # Enabling nodes creates defaults on non-node materials. Restore the flag
    # on failure so even that material keeps its previous appearance.
    used_nodes = material.use_nodes
    material.use_nodes = True
    tree = material.node_tree
    previous_nodes = list(tree.nodes)
    previous_active = tree.nodes.active
    previous_outputs = [n for n in previous_nodes
                        if n.bl_idname == 'ShaderNodeOutputMaterial'
                        and n.is_active_output]
    image_settings = {image: (image.colorspace_settings.name, image.alpha_mode)
                      for image in images.values() if image is not None}

    created = []
    texture_nodes = {}

    try:
        for role, image in sorted(images.items(),
                                  key=lambda kv: _legacy_index(kv[0])):
            if image is None:
                continue
            node = tree.nodes.new("ShaderNodeTexImage")
            created.append(node)
            node.image = image
            node.name = _legacy_node_name(role)
            node.label = role
            node.location = (-50, 50 - 260 * _legacy_index(role))
            texture_nodes[role] = node

        group_node = tree.nodes.new("ShaderNodeGroup")
        created.append(group_node)
        group_node.node_tree = group_tree
        group_node.location = (300, 0)

        required = {definition.sockets.get(R.GLOSS if r == R.ROUGHNESS else r)
                    for r in texture_nodes if r not in definition.extra_roles}
        if plug_alpha:
            required.update(name for role, name in definition.alpha_sockets.items()
                            if role in texture_nodes)
        missing = [name for name in required
                   if name and name not in group_node.inputs]
        if missing or not group_node.outputs:
            raise RuntimeError("Shader is missing sockets: %s"
                               % (", ".join(sorted(missing)) or "surface output"))

        output_node = tree.nodes.new("ShaderNodeOutputMaterial")
        created.append(output_node)
        output_node.location = (500, 0)
        tree.links.new(output_node.inputs[0], group_node.outputs[0])

        # Alpha first, then colour, so that an explicit opacity map still wins
        # over the albedo alpha channel -- the order the old operator used.
        # ``plug_alpha`` is Recolour's "Plug Alpha" switch.
        if plug_alpha:
            for role, socket_name in definition.alpha_sockets.items():
                node = texture_nodes.get(role)
                if node is None or socket_name not in group_node.inputs:
                    continue
                tree.links.new(group_node.inputs[socket_name],
                               node.outputs["Alpha"])

        for role, node in texture_nodes.items():
            socket_name = definition.sockets.get(role)
            needs_invert = False
            # The resolver reports what the image *is*; the adapter knows what
            # its socket *wants*.  Only the mismatch is converted, and a real
            # gloss map is never inverted.
            if role == R.ROUGHNESS and definition.gloss_expects == R.GLOSS:
                socket_name = definition.sockets.get(R.GLOSS)
                needs_invert = True
            elif role == R.GLOSS and definition.gloss_expects == R.ROUGHNESS:
                socket_name = definition.sockets.get(R.ROUGHNESS)
                needs_invert = True
            if not socket_name or socket_name not in group_node.inputs:
                continue
            source = node.outputs["Color"]
            if needs_invert:
                # gloss = 1 - roughness, done in the graph so that the source
                # image on disk is never modified.
                invert = tree.nodes.new("ShaderNodeInvert")
                created.append(invert)
                invert.location = (node.location.x + 180, node.location.y)
                invert.label = "roughness -> gloss"
                tree.links.new(invert.inputs["Color"], source)
                source = invert.outputs["Color"]
            tree.links.new(group_node.inputs[socket_name], source)

        for role, image in images.items():
            apply_colorspace(image, role)

    except Exception:
        for node in created:
            try:
                tree.nodes.remove(node)
            except RuntimeError:
                pass
        for image, (colorspace, alpha_mode) in image_settings.items():
            image.colorspace_settings.name = colorspace
            image.alpha_mode = alpha_mode
        for node in previous_outputs:
            node.is_active_output = True
        tree.nodes.active = previous_active
        material.use_nodes = used_nodes
        raise

    # Success: retire the imported / previous graph.
    for node in previous_nodes:
        try:
            tree.nodes.remove(node)
        except RuntimeError:
            pass

    # Free the historic names only after the old graph has gone. Re-running
    # previously produced 0.001 / 6.001, breaking downstream numeric lookups.
    for role, node in texture_nodes.items():
        node.name = _legacy_node_name(role)
    output_node.is_active_output = True
    tree.nodes.active = group_node

    # ``blend_method`` disappeared in Blender 4.3 (EEVEE Next); setting it is
    # best effort so Auto_tex keeps working on both sides of that change.
    try:
        material.blend_method = "HASHED"
    except (AttributeError, TypeError):
        pass
    if log is not None:
        log("rebuilt with %d texture node(s)" % len(texture_nodes))
    return texture_nodes
