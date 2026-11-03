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
import os
import re

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
        extra_roles=(R.CAVITY, R.ANISO_SPEC_DIR, R.IRIDESCENCE_RAMP),
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

CORNEA_DEF = ShaderDef(
    'CORNEA', 'ALR Cornea',
    {R.ALBEDO: 'Albedo Map', R.NORMAL: 'Normal Map'}, {},
)


def is_cornea(material, images):
    names = [material.name]
    albedo = images.get(R.ALBEDO)
    if albedo is not None:
        names.append(albedo.filepath_raw or albedo.filepath or albedo.name)
    return any(re.search(r'(?:^|_)eyecornea(?:_|$)',
                         os.path.splitext(name.replace('\\', '/').rsplit('/', 1)[-1])[0].casefold())
               for name in names)


def ensure_cornea_group():
    """Thin clear eye surface, with Fresnel reflections and packed RG normals.

    Black albedo is a game placeholder, not a black tint. Retain its input for
    role discovery/recolour but do not use it to darken the eye underneath.
    """
    existing = bpy.data.node_groups.get(CORNEA_DEF.group_name)
    if existing is not None:
        return existing
    group = bpy.data.node_groups.new(CORNEA_DEF.group_name, 'ShaderNodeTree')
    try:
        for name, kind in [('Albedo Map', 'NodeSocketColor'), ('Normal Map', 'NodeSocketColor')]:
            socket = group.interface.new_socket(name=name, in_out='INPUT', socket_type=kind)
            socket.default_value = (0.5, 0.5, 0.0, 1.0) if name == 'Normal Map' else (0, 0, 0, 1)
        group.interface.new_socket(name='BSDF', in_out='OUTPUT', socket_type='NodeSocketShader')
        nodes, links = group.nodes, group.links
        source = nodes.new('NodeGroupInput')
        output = nodes.new('NodeGroupOutput')
        separate = nodes.new('ShaderNodeSeparateXYZ')
        links.new(source.outputs['Normal Map'], separate.inputs[0])

        def math_node(operation, a, b=None):
            node = nodes.new('ShaderNodeMath')
            node.operation = operation
            for i, value in enumerate((a, b)):
                if value is None:
                    continue
                if isinstance(value, (int, float)):
                    node.inputs[i].default_value = value
                else:
                    links.new(value, node.inputs[i])
            return node.outputs[0]

        x = math_node('SUBTRACT', math_node('MULTIPLY', separate.outputs['X'], 2), 1)
        y = math_node('SUBTRACT', math_node('MULTIPLY', separate.outputs['Y'], 2), 1)
        squared = math_node('ADD', math_node('MULTIPLY', x, x), math_node('MULTIPLY', y, y))
        z = math_node('SQRT', math_node('MAXIMUM', math_node('SUBTRACT', 1, squared), 0))
        packed_z = math_node('ADD', math_node('MULTIPLY', z, 0.5), 0.5)
        combine = nodes.new('ShaderNodeCombineXYZ')
        links.new(separate.outputs['X'], combine.inputs['X'])
        links.new(separate.outputs['Y'], combine.inputs['Y'])
        links.new(packed_z, combine.inputs['Z'])
        normal = nodes.new('ShaderNodeNormalMap')
        links.new(combine.outputs[0], normal.inputs['Color'])
        transparent = nodes.new('ShaderNodeBsdfTransparent')
        reflection = nodes.new('ShaderNodeBsdfGlossy')
        reflection.inputs['Color'].default_value = (1, 1, 1, 1)
        reflection.inputs['Roughness'].default_value = 0.05
        links.new(normal.outputs['Normal'], reflection.inputs['Normal'])
        fresnel = nodes.new('ShaderNodeFresnel')
        fresnel.inputs['IOR'].default_value = 1.376
        links.new(normal.outputs['Normal'], fresnel.inputs['Normal'])
        mix = nodes.new('ShaderNodeMixShader')
        links.new(fresnel.outputs[0], mix.inputs[0])
        links.new(transparent.outputs[0], mix.inputs[1])
        links.new(reflection.outputs[0], mix.inputs[2])
        links.new(mix.outputs[0], output.inputs[0])
        # Keep the generated graph readable when inspected in the node editor.
        for i, node in enumerate(nodes):
            node.location = ((i % 5) * 210, -(i // 5) * 180)
        return group
    except Exception:
        bpy.data.node_groups.remove(group)
        raise


#: Node group names Auto_tex recognises as "already an Apex Toolbox material".
KNOWN_GROUP_NAMES = frozenset(d.group_name for d in (*SHADER_DEFS.values(), CORNEA_DEF))


def socket_role_map():
    """``group name -> {socket name: role}`` for re-reading our own materials."""
    mapping = {}
    for definition in (*SHADER_DEFS.values(), CORNEA_DEF):
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


# These masks cover solid harness/cuff/zipper and equipment surfaces, not
# transparency in our surface shaders. Match the exported texture, not a broad
# legend/material substring, so unrelated Wattson skins keep their cutouts.
_SURFACE_OPACITY_EXCEPTIONS = frozenset({
    'wattson_lgnd_v24_onesie_suit_opacitymultiplytexture',
    'wattson_lgnd_v24_onesie_gear_opacitymultiplytexture',
})


def skip_surface_opacity(material, image):
    if image is None or material.get('apex_force_opacity_map', False):
        return False
    path = image.filepath_raw or image.filepath or image.name
    stem = os.path.splitext(path.replace('\\', '/').rsplit('/', 1)[-1])[0]
    return stem.casefold() in _SURFACE_OPACITY_EXCEPTIONS


def fragmented_albedo_alpha(image):
    """Reject only sparse, isolated specks, never infer intent from alpha alone.

    Bound memory and traversal cost. Unknown/large images keep their alpha.
    No cache: generated images and reloaded files must be checked afresh.
    """
    import numpy as np
    width, height = image.size
    total = width * height
    if image.channels != 4 or not 65536 <= total <= 4194304:
        return False
    pixels = np.empty(total * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    alpha = pixels[3::4]
    if not np.isfinite(alpha).all():
        return False
    indices = np.flatnonzero(alpha < 0.99)
    if not 32 <= len(indices) <= total * 0.01:
        return False
    remaining = set(indices.tolist())
    components = 0
    # Large coherent cutouts, including narrow strands, retain transparency.
    limit = max(16, int(total * 0.00015))
    while remaining:
        pending = [remaining.pop()]
        count = 0
        components += 1
        while pending:
            index = pending.pop()
            count += 1
            if count > limit:
                return False
            x = index % width
            neighbours = [index - width, index + width]
            if x:
                neighbours.extend((index - 1, index - width - 1, index + width - 1))
            if x + 1 < width:
                neighbours.extend((index + 1, index - width + 1, index + width + 1))
            for neighbour in neighbours:
                if neighbour in remaining:
                    remaining.remove(neighbour)
                    pending.append(neighbour)
    return components >= 32


def arrange_material_nodes(texture_nodes, group_node, output_node):
    """Lay out only generated nodes, in texture -> adjustment -> shader order."""
    ordered = sorted(texture_nodes.items(), key=lambda pair: _legacy_index(pair[0]))
    for row, (role, node) in enumerate(ordered):
        node.width = 260
        node.location = (-760, -100 * row)
        # Compact rows keep large texture sets readable; expand a node to inspect it.
        node.hide = True
        for link in node.outputs['Color'].links:
            target = link.to_node
            if ((target.get('apex_hair_multiply') and link.to_socket == target.inputs[1])
                    or target.bl_idname == 'ShaderNodeInvert'):
                target.width = 210
                target.hide = True
                target.location = (-370, node.location.y)
    group_node.width = 310
    group_node.location = (0, 80)
    output_node.width = 190
    output_node.location = (450, group_node.location.y)


def set_hair_fix(material, enabled):
    """Explicit per-material adjustment; never infer it from the material name."""
    tree = material.node_tree if material.use_nodes else None
    if tree is None:
        raise ValueError('Texture the active material with Apex Toolbox first.')
    tagged = [n for n in tree.nodes if n.get('apex_hair_multiply')]
    if not enabled:
        for node in tagged:
            source = node.inputs[1].links[0].from_socket if node.inputs[1].links else None
            destinations = [link.to_socket for link in node.outputs[0].links]
            if source is not None:
                for destination in destinations:
                    tree.links.new(source, destination)
            tree.nodes.remove(node)
        material['apex_hair_fix'] = False
        return
    group = next((n for n in tree.nodes if n.type == 'GROUP'
                  and n.node_tree and n.node_tree.name in KNOWN_GROUP_NAMES), None)
    definition = next((d for d in SHADER_DEFS.values()
                       if group and d.group_name == group.node_tree.name), None)
    if definition is None:
        raise ValueError('Choose an Apex surface shader for this material first.')
    cavity = next((n for n in tree.nodes if n.type == 'TEX_IMAGE' and n.image
                   and (n.get('apex_texture_role') == R.CAVITY
                        or n.name == _legacy_node_name(R.CAVITY))), None)
    if cavity is None:
        raise ValueError('This material needs a cavity texture before applying the hair fix.')
    plans = []
    for role in (R.ALBEDO, R.SPECULAR):
        socket = group.inputs.get(definition.sockets[role])
        if socket is None or not socket.links:
            raise ValueError('This material needs both albedo and specular textures.')
        source = socket.links[0].from_socket
        if source.node.get('apex_hair_multiply'):
            continue
        plans.append((role, source, socket))
    # Validate every input before changing either channel.
    for role, source, socket in plans:
        node = tree.nodes.new('ShaderNodeMixRGB')
        node.blend_type = 'MULTIPLY'
        node.inputs[0].default_value = 1.0
        node.label = 'Hair ' + role + ' x cavity'
        node['apex_hair_multiply'] = True
        node.width = 210
        node.hide = True
        node.location = (source.node.location.x + source.node.width + 130, source.node.location.y)
        tree.links.new(source, node.inputs[1])
        tree.links.new(cavity.outputs['Color'], node.inputs[2])
        tree.links.new(node.outputs[0], socket)
    material['apex_hair_fix'] = True


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
    cornea = is_cornea(material, images)
    if cornea:
        ensure_cornea_group()
        definition = CORNEA_DEF
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
    alpha_note = ("Clear cornea shader: black placeholder albedo retained but not used as a surface tint."
                  if cornea else "")
    skip_opacity = skip_surface_opacity(material, images.get(R.OPACITY))

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
            node["apex_texture_role"] = role
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
                if (role == R.ALBEDO and (images.get(R.OPACITY) is None or skip_opacity)
                        and not material.get('apex_force_albedo_alpha', False)
                        and not any(word in material.name.casefold()
                                    for word in ('hair', 'lash', 'fur', 'lace'))
                        and fragmented_albedo_alpha(node.image)):
                    group_node.inputs[socket_name].default_value = 1.0
                    alpha_note = ('Albedo alpha left disconnected: sparse isolated specks. '
                                  'Set material custom property apex_force_albedo_alpha '
                                  'to True and retexture to override.')
                    node.label = role + ' (fragmented alpha ignored)'
                    continue
                tree.links.new(group_node.inputs[socket_name],
                               node.outputs["Alpha"])

        for role, node in texture_nodes.items():
            if role == R.OPACITY and not plug_alpha:
                continue
            if role == R.OPACITY and skip_opacity:
                node.label = role + ' (surface mask, not transparency)'
                note = ('Opacity map left disconnected: known Wattson onesie surface mask '
                        'removes solid parts. Set material custom property '
                        'apex_force_opacity_map to True and retexture to override.')
                alpha_note = (alpha_note + ' ' + note).strip()
                # Keep albedo alpha if present, otherwise use an opaque surface.
                socket = group_node.inputs.get(definition.sockets.get(R.OPACITY, ''))
                if socket is not None and not socket.is_linked:
                    socket.default_value = 1.0
                continue
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
            if (material.get('apex_hair_fix', False) and role in {R.ALBEDO, R.SPECULAR}
                    and R.CAVITY in texture_nodes):
                multiply = tree.nodes.new('ShaderNodeMixRGB')
                created.append(multiply)
                multiply.blend_type = 'MULTIPLY'
                multiply.inputs[0].default_value = 1.0
                multiply.label = 'Hair ' + role + ' x cavity'
                multiply['apex_hair_multiply'] = True
                multiply.location = (node.location.x + 180, node.location.y)
                tree.links.new(multiply.inputs[1], source)
                tree.links.new(multiply.inputs[2], texture_nodes[R.CAVITY].outputs['Color'])
                source = multiply.outputs['Color']
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

        arrange_material_nodes(texture_nodes, group_node, output_node)

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
    material['apex_alpha_note'] = alpha_note

    # ``blend_method`` disappeared in Blender 4.3 (EEVEE Next); setting it is
    # best effort so Auto_tex keeps working on both sides of that change.
    try:
        material.blend_method = "HASHED"
    except (AttributeError, TypeError):
        pass
    if log is not None:
        log("rebuilt with %d texture node(s)" % len(texture_nodes))
        if alpha_note:
            log(alpha_note)
    return texture_nodes
