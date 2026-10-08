"""Attach an imported prop rig to a posed legend's attachment bone."""


SOCKET_BONES = {
    'LEFT_HAND': ('ja_l_propHand', 'prop_hand_l', 'prop_hand.L'),
    'RIGHT_HAND': ('ja_r_propHand', 'prop_hand_r', 'prop_hand.R'),
    'WEAPON': ('ja_c_propGun', 'prop_gun'),
}


def socket_bone(rig, socket):
    """Find a known socket without guessing a nearby deform bone."""
    for name in SOCKET_BONES[socket]:
        bone = rig.pose.bones.get(name)
        if bone is not None:
            return bone
    return None


def attach_item(context, item, legend, bone_name):
    """Snap an entire prop armature to a pose bone; its child meshes follow it."""
    if item is None or legend is None or item.type != 'ARMATURE' or legend.type != 'ARMATURE':
        raise ValueError('Choose an item rig and a legend rig.')
    if item == legend:
        raise ValueError('The item and legend must be different rigs.')
    if not item.is_editable or not legend.is_editable:
        raise ValueError('Both rigs must be editable.')
    if legend in item.children_recursive:
        raise ValueError('The legend is already inside the item hierarchy.')
    bone = legend.pose.bones.get(bone_name)
    if bone is None:
        raise ValueError("Bone '%s' was not found on the legend rig." % bone_name)
    if any(constraint.mute is False for constraint in item.constraints):
        raise ValueError('The item rig has active object constraints. Disable them before pairing.')

    context.view_layer.update()
    target_matrix = legend.matrix_world @ bone.matrix
    item.parent = legend
    item.parent_type = 'BONE'
    item.parent_bone = bone.name
    item.matrix_parent_inverse.identity()
    item.matrix_world = target_matrix
    context.view_layer.update()
    return bone.name
