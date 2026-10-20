from schema_index import SchemaIndex
from twno_writer import Obj, WriteError

TEAL = 0xFF14907F
TEAL_LIGHT = 0xFF5CC9B3
AMBER = 0xFFF2B84B
INDIGO = 0xFF4C6FE0
SHADOW = 0x40707A74
GROUND = 0xFF8A938C

KEYFRAME_TYPES = {"double": "KeyFrameDouble", "color": "KeyFrameColor"}
INTERPOLATION_LINEAR = 1
INTERPOLATION_CUBIC = 2
TRANSITION_ENABLE_EXIT_TIME = 4
TRANSITION_EXIT_TIME_PERCENT = TRANSITION_ENABLE_EXIT_TIME | 8
BOOL_IS_TRUE = 0
BOOL_IS_FALSE = 1
CONDITION_TYPES = {
    "bool": "TransitionBoolCondition",
    "trigger": "TransitionTriggerCondition",
}


def ease(doc, x1, y1, x2, y2):
    return doc.add(Obj("CubicEaseInterpolator", x1=x1, y1=y1, x2=x2, y2=y2))


def keyframe_kind(target, property_name):
    index = SchemaIndex.default()
    key = index.property_key(target.type_name, property_name)
    if key is None:
        raise WriteError(f"{target.type_name} has no property {property_name!r}")
    field_type = index.property(key)["fieldType"]
    if field_type not in KEYFRAME_TYPES:
        raise WriteError(f"{target.type_name}.{property_name} ({field_type}) cannot be keyed")
    return key, KEYFRAME_TYPES[field_type]


def animate(doc, target, tracks):
    resolved = [(*keyframe_kind(target, name), frames) for name, frames in tracks.items()]
    doc.add(Obj("KeyedObject", object=target))
    for key, frame_type, frames in resolved:
        doc.add(Obj("KeyedProperty", propertyKey=key))
        for frame, value, interpolator in frames:
            props = {"frame": frame, "value": value}
            if interpolator is None:
                props["interpolationType"] = INTERPOLATION_LINEAR
            else:
                props["interpolationType"] = INTERPOLATION_CUBIC
                props["interpolator"] = interpolator
            doc.add(Obj(frame_type, **props))


def solid_shape(doc, parent, name, path_type, color, with_path=False, **path_props):
    placement = {key: path_props.pop(key) for key in ("x", "y", "rotation") if key in path_props}
    shape = doc.add(Obj("Shape", name=name, parent=parent, **placement))
    path = doc.add(Obj(path_type, name=name + " path", parent=shape, **path_props))
    fill = doc.add(Obj("Fill", name=name + " fill", parent=shape))
    paint = doc.add(Obj("SolidColor", name=name + " color", parent=fill, colorValue=color))
    return (shape, paint, path) if with_path else (shape, paint)


def loop_machine(doc, name, animation):
    play = Obj("AnimationState", animation=animation)
    doc.add(Obj("StateMachine", name=name))
    doc.add(Obj("StateMachineLayer", name="main"))
    doc.add(Obj("EntryState"))
    transition(doc, play)
    doc.add(Obj("AnyState"))
    doc.add(Obj("ExitState"))
    return doc.add(play)


def hold_animation(doc, name, target_tracks, fps):
    animation = doc.add(Obj("LinearAnimation", name=name, fps=fps, duration=1, loopValue=0))
    for target, tracks in target_tracks:
        animate(doc, target, {prop: [(0, value, None)] for prop, value in tracks.items()})
    return animation


def transition(doc, to_state, conditions=(), duration_ms=0, exit_at_end=False):
    props = {"stateTo": to_state}
    if duration_ms:
        props["duration"] = duration_ms
    if exit_at_end:
        props["flags"] = TRANSITION_EXIT_TIME_PERCENT
        props["exitTime"] = 100
    doc.add(Obj("StateTransition", **props))
    for kind, input_obj, op in conditions:
        extra = {"opValue": op} if kind == "bool" else {}
        doc.add(Obj(CONDITION_TYPES[kind], input=input_obj, **extra))
