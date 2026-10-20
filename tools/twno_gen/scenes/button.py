import scene_kit as kit
from twno_writer import Document, Obj

NAME = "button"
SIZE = 400.0
FPS = 60
CENTRE = SIZE / 2
FACE_WIDTH = 220.0
FACE_HEIGHT = 96.0
KNOB_DIAMETER = 64.0
KNOB_REST_X = -62.0
KNOB_ACTIVE_X = 62.0
RADIUS_REST = 16.0
RADIUS_ACTIVE = 48.0
COLOR_REST = kit.TEAL
COLOR_ACTIVE = kit.INDIGO
KNOB_COLOR = 0xFFF6F7F5
BLEND_MS = 250
PULSE_FRAMES = 24
PULSE_PEAK_FRAME = 8
PULSE_SCALE = 1.12
EASE = (0.42, 0.0, 0.58, 1.0)
TOGGLE = "bascule"
PULSE = "impulsion"
INPUT_BOOL = "actif"
INPUT_TRIGGER = "appui"


def build():
    doc = Document()
    doc.add(Obj("Backboard"))
    artboard = doc.add(Obj("Artboard", name="Bouton", width=SIZE, height=SIZE, defaultStateMachine=TOGGLE))
    group = doc.add(Obj("Node", name="bouton", parent=artboard, x=CENTRE, y=CENTRE))
    knob, _ = kit.solid_shape(doc, group, "pastille", "Ellipse", KNOB_COLOR, x=KNOB_REST_X,
                              width=KNOB_DIAMETER, height=KNOB_DIAMETER)
    _, face_color, face_path = kit.solid_shape(doc, group, "face", "Rectangle", COLOR_REST, with_path=True,
                                               width=FACE_WIDTH, height=FACE_HEIGHT, cornerRadiusTL=RADIUS_REST)
    ease = kit.ease(doc, *EASE)

    rest = kit.hold_animation(doc, "repos", [
        (knob, {"x": KNOB_REST_X}),
        (face_path, {"cornerRadiusTL": RADIUS_REST}),
        (face_color, {"colorValue": COLOR_REST}),
    ], FPS)
    active = kit.hold_animation(doc, "actif", [
        (knob, {"x": KNOB_ACTIVE_X}),
        (face_path, {"cornerRadiusTL": RADIUS_ACTIVE}),
        (face_color, {"colorValue": COLOR_ACTIVE}),
    ], FPS)
    neutral = kit.hold_animation(doc, "neutre", [(group, {"scaleX": 1.0, "scaleY": 1.0})], FPS)
    pulse = doc.add(Obj("LinearAnimation", name="pulsation", fps=FPS, duration=PULSE_FRAMES, loopValue=0))
    scale_frames = [(0, 1.0, ease), (PULSE_PEAK_FRAME, PULSE_SCALE, ease), (PULSE_FRAMES, 1.0, None)]
    kit.animate(doc, group, {"scaleX": scale_frames, "scaleY": scale_frames})

    toggle_rest = Obj("AnimationState", animation=rest)
    toggle_active = Obj("AnimationState", animation=active)
    doc.add(Obj("StateMachine", name=TOGGLE))
    flag = doc.add(Obj("StateMachineBool", name=INPUT_BOOL, value=False))
    doc.add(Obj("StateMachineLayer", name="principal"))
    doc.add(Obj("EntryState"))
    kit.transition(doc, toggle_rest)
    doc.add(Obj("AnyState"))
    doc.add(Obj("ExitState"))
    doc.add(toggle_rest)
    kit.transition(doc, toggle_active, [("bool", flag, kit.BOOL_IS_TRUE)], duration_ms=BLEND_MS)
    doc.add(toggle_active)
    kit.transition(doc, toggle_rest, [("bool", flag, kit.BOOL_IS_FALSE)], duration_ms=BLEND_MS)

    pulse_idle = Obj("AnimationState", animation=neutral)
    pulse_play = Obj("AnimationState", animation=pulse)
    doc.add(Obj("StateMachine", name=PULSE))
    press = doc.add(Obj("StateMachineTrigger", name=INPUT_TRIGGER))
    doc.add(Obj("StateMachineLayer", name="principal"))
    doc.add(Obj("EntryState"))
    kit.transition(doc, pulse_idle)
    doc.add(Obj("AnyState"))
    doc.add(Obj("ExitState"))
    doc.add(pulse_idle)
    kit.transition(doc, pulse_play, [("trigger", press, None)])
    doc.add(pulse_play)
    kit.transition(doc, pulse_idle, exit_at_end=True)
    return doc
