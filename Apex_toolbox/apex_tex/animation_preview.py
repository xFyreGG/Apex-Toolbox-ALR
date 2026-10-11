"""One temporary animation preview, with an explicit commit or full rollback."""
import bpy

from . import animations


_session = None
_MARKER = '_apex_animation_preview'
_TRANSFORMS = ('location', 'rotation_euler', 'rotation_quaternion',
               'rotation_axis_angle', 'scale')


def _transforms(target):
    return target.rotation_mode, {key: tuple(getattr(target, key)) for key in _TRANSFORMS}


def _restore_transforms(target, values):
    target.rotation_mode = values[0]
    for key, value in values[1].items():
        setattr(target, key, value)


class Snapshot:
    def __init__(self, context, rig):
        self.rig, self.scene = rig, context.scene
        animation = rig.animation_data
        self.had_animation_data = animation is not None
        self.action = animation.action if animation else None
        self.action_slot = getattr(animation, 'action_slot', None)
        self.fake_user = self.action.use_fake_user if self.action else False
        self.object_transform = _transforms(rig)
        self.bones = {bone.name: _transforms(bone) for bone in rig.pose.bones}
        scene = self.scene
        self.timing = (scene.frame_start, scene.frame_end, scene.frame_current,
                       scene.frame_subframe, scene.render.fps, scene.render.fps_base)
        library = rig.apex_animation_library
        self.rest = (library.has_rest_rotation, library.rest_rotation_mode,
                     tuple(library.rest_rotation))

    def mark(self):
        # ID pointers are remapped by Blender's Undo system. Keeping the full
        # baseline in the snapshot lets undo_post/redo_post recover a temporary
        # preview recorded by an unrelated Blender editing operation.
        data = {'scene': self.scene, 'owner_uid': self.rig.session_uid,
                'had_animation_data': self.had_animation_data,
                'fake_user': self.fake_user,
                'slot_handle': self.action_slot.handle if self.action_slot else 0,
                'object_mode': self.object_transform[0],
                'object_channels': self.object_transform[1],
                'bones': {name: {'mode': value[0], 'channels': value[1]}
                          for name, value in self.bones.items()},
                'timing': list(self.timing), 'rest_set': self.rest[0],
                'rest_mode': self.rest[1], 'rest_rotation': list(self.rest[2])}
        if self.action is not None:
            data['action'] = self.action
        self.rig[_MARKER] = data

    @classmethod
    def from_marker(cls, rig):
        data = rig[_MARKER]
        result = cls.__new__(cls)
        result.rig, result.scene = rig, data.get('scene')
        result.had_animation_data = data['had_animation_data']
        result.action = data.get('action')
        result.action_slot = next((slot for slot in getattr(result.action, 'slots', ())
                                   if slot.handle == data['slot_handle']), None)
        result.fake_user = data['fake_user']
        result.object_transform = (data['object_mode'], dict(data['object_channels']))
        result.bones = {name: (value['mode'], dict(value['channels']))
                        for name, value in data['bones'].items()}
        timing = data['timing']
        result.timing = (int(timing[0]), int(timing[1]), int(timing[2]),
                         float(timing[3]), int(timing[4]), float(timing[5]))
        result.rest = (data['rest_set'], data['rest_mode'], tuple(data['rest_rotation']))
        return result

    def restore(self, context, preserve_object=False):
        try:
            scene = self.scene
            scene.frame_start, scene.frame_end = self.timing[:2]
            scene.render.fps, scene.render.fps_base = self.timing[4:]
            scene.frame_set(self.timing[2], subframe=self.timing[3])
        except (ReferenceError, AttributeError):
            pass
        try:
            rig = self.rig
            if self.had_animation_data or self.action:
                animation = rig.animation_data_create()
                try:
                    animation.action = self.action
                    if hasattr(animation, 'action_slot'):
                        animation.action_slot = self.action_slot
                    if self.action:
                        self.action.use_fake_user = self.fake_user
                except ReferenceError:
                    animation.action = None
            else:
                rig.animation_data_clear()
            # Evaluate the restored action at the original time before restoring
            # exact channel values, including an unsaved manual pose.
            try:
                scene.frame_set(self.timing[2], subframe=self.timing[3])
            except (ReferenceError, AttributeError):
                pass
            if not preserve_object:
                _restore_transforms(rig, self.object_transform)
            for name, values in self.bones.items():
                bone = rig.pose.bones.get(name)
                if bone is not None:
                    _restore_transforms(bone, values)
            library = rig.apex_animation_library
            library.has_rest_rotation, library.rest_rotation_mode = self.rest[:2]
            library.rest_rotation = self.rest[2]
        except ReferenceError:
            pass  # A preview target can be deleted before the user presses Revert.
        context.view_layer.update()


class Session:
    def __init__(self, context, rig):
        self.original = Snapshot(context, rig)
        self.rig, self.scene = rig, context.scene
        self.action = None
        self.action_slot = None
        self.skeleton = animations.rig_signature(rig)
        self.clip_key = None
        self.label = ''


def active(rig=None):
    if rig is None:
        return _session
    try:
        return _session if _session is not None and _session.rig == rig else None
    except ReferenceError:
        return None


def in_scene(context):
    try:
        return _session is not None and _session.scene == context.scene
    except ReferenceError:
        return False


def start(context, rig, item, operator=None):
    global _session
    if _session is not None and (active(rig) is None or not in_scene(context)):
        raise ValueError('Apply or revert the current preview before previewing another model or scene.')
    animations.validate_target(rig)
    session = _session or Session(context, rig)
    library = rig.apex_animation_library
    if _session is None:
        session.original.mark()
    try:
        missing = animations.load_clip(context, rig, item, library.fit_timeline,
                                       library.allow_missing, operator, record_history=False)
    except Exception:
        if _session is None:
            _unmark(rig)
        raise
    session.action = rig.animation_data.action
    session.action_slot = getattr(rig.animation_data, 'action_slot', None)
    session.clip_key = (item.filepath, item.offset)
    session.label = animations.clip_label(item, library)
    _session = session
    return missing


def _stop_playback(context, scene):
    for window in context.window_manager.windows:
        if window.scene == scene and window.screen.is_animation_playing:
            with context.temp_override(window=window):
                bpy.ops.screen.animation_cancel(restore_frame=False)


def revert(context):
    global _session
    session = _session
    if session is None:
        return False
    _session = None
    try:
        _stop_playback(context, session.scene)
    except ReferenceError:
        pass
    session.original.restore(context)
    _unmark(session.rig)
    recover_preview_snapshots()
    return True


def apply(context, undo_baseline=False):
    global _session
    session = _session
    if session is None:
        raise ValueError('Preview an animation first.')
    try:
        rig = session.rig
        animations.validate_target(rig)
        if not in_scene(context):
            raise ValueError('Return to the preview scene to apply this animation, or press Revert.')
        if not rig.animation_data or rig.animation_data.action != session.action:
            raise ValueError('The preview action changed. Revert and preview the animation again.')
        if getattr(rig.animation_data, 'action_slot', None) != session.action_slot:
            raise ValueError('The preview action slot changed. Revert and preview the animation again.')
        if animations.rig_signature(rig) != session.skeleton:
            raise ValueError('The preview skeleton changed. Revert before loading another animation.')
        item = next((clip for clip in rig.apex_animation_library.clips
                     if (clip.filepath, clip.offset) == session.clip_key), None)
        if item is None:
            raise ValueError('The previewed clip is no longer in the library. Press Revert.')
        if undo_baseline and not bpy.app.background and context.window is not None:
            # Preview has no Undo step. Record the exact original scene before
            # the Apply operator records the accepted scene as its Undo result.
            accepted = Snapshot(context, rig)
            session.original.restore(context)
            _unmark(rig)
            try:
                bpy.ops.ed.undo_push(message='Before Applying Animation Preview')
            except Exception:
                session.original.mark()
                raise
            finally:
                accepted.restore(context)
            try:
                if session.original.action:
                    session.original.action.use_fake_user = True
            except ReferenceError:
                pass
        animations.record_recent(rig.apex_animation_library, item)
        for target in bpy.data.objects:
            if _MARKER in target and target[_MARKER].get('owner_uid') == rig.session_uid:
                _unmark(target)
        _session = None
        return session.label
    except ReferenceError as error:
        raise ValueError('The preview model was removed. Press Revert to restore the timeline.') from error


@bpy.app.handlers.persistent
def cancel_preview(_=None):
    """Temporary poses never survive saving, file changes, Undo or disabling."""
    revert(bpy.context)
    recover_preview_snapshots()


def _unmark(rig):
    try:
        if _MARKER in rig:
            del rig[_MARKER]
    except ReferenceError:
        pass


@bpy.app.handlers.persistent
def recover_preview_snapshots(_=None):
    """Never resurrect an uncommitted preview from another tool's Undo step."""
    for rig in bpy.data.objects:
        if rig.type == 'ARMATURE' and _MARKER in rig:
            try:
                copied = rig[_MARKER].get('owner_uid') != rig.session_uid
                Snapshot.from_marker(rig).restore(bpy.context, preserve_object=copied)
            except (KeyError, TypeError, ValueError, AttributeError, ReferenceError):
                pass
            finally:
                _unmark(rig)
