import scene_kit as kit
from twno_writer import Document, Obj

NAME = "bouncing-ball"
MACHINE = "loop"
SIZE = 400.0
FPS = 60
DURATION = 96
CONTACT_IN = 42
SQUASH = 48
CONTACT_OUT = 54
RADIUS = 40.0
FLOOR_TOP = 340.0
FLOOR_HEIGHT = 6.0
FLOOR_WIDTH = 260.0
SHADOW_RAISE = 2.0
APEX_Y = 90.0
CONTACT_Y = FLOOR_TOP - RADIUS
SQUASH_SCALE_Y = 0.8
SQUASH_SCALE_X = 1.2
SQUASH_Y = FLOOR_TOP - RADIUS * SQUASH_SCALE_Y
EASE_IN = (1 / 3, 0.0, 2 / 3, 1 / 3)
EASE_OUT = (1 / 3, 2 / 3, 2 / 3, 1.0)
SHADOW_SCALE_APEX = 0.6
SHADOW_SCALE_CONTACT = 1.0
SHADOW_SCALE_SQUASH = 1.1

BALL_TRACKS = {
    "y": (
        (0, APEX_Y, "in"),
        (CONTACT_IN, CONTACT_Y, None),
        (SQUASH, SQUASH_Y, None),
        (CONTACT_OUT, CONTACT_Y, "out"),
        (DURATION, APEX_Y, None),
    ),
    "scaleX": (
        (0, 1.0, None),
        (CONTACT_IN, 1.0, None),
        (SQUASH, SQUASH_SCALE_X, None),
        (CONTACT_OUT, 1.0, None),
        (DURATION, 1.0, None),
    ),
    "scaleY": (
        (0, 1.0, None),
        (CONTACT_IN, 1.0, None),
        (SQUASH, SQUASH_SCALE_Y, None),
        (CONTACT_OUT, 1.0, None),
        (DURATION, 1.0, None),
    ),
}
SHADOW_SCALES = (
    (0, SHADOW_SCALE_APEX, "in"),
    (CONTACT_IN, SHADOW_SCALE_CONTACT, None),
    (SQUASH, SHADOW_SCALE_SQUASH, None),
    (CONTACT_OUT, SHADOW_SCALE_CONTACT, "out"),
    (DURATION, SHADOW_SCALE_APEX, None),
)


def build(loop=1):
    doc = Document()
    doc.add(Obj("Backboard"))
    artboard = doc.add(Obj("Artboard", name="Bouncing ball", width=SIZE, height=SIZE, defaultStateMachine=MACHINE))
    ball = doc.add(Obj("Node", name="ball", parent=artboard, x=SIZE / 2, y=APEX_Y))
    kit.solid_shape(doc, ball, "highlight", "Ellipse", kit.TEAL_LIGHT,
                    x=-14.0, y=-16.0, width=16.0, height=11.0, rotation=-0.6)
    kit.solid_shape(doc, ball, "body", "Ellipse", kit.TEAL, width=2 * RADIUS, height=2 * RADIUS)
    shadow, _ = kit.solid_shape(doc, artboard, "shadow", "Ellipse", kit.SHADOW,
                                x=SIZE / 2, y=FLOOR_TOP - SHADOW_RAISE, width=110.0, height=16.0)
    kit.solid_shape(doc, artboard, "floor", "Rectangle", kit.GROUND,
                    x=SIZE / 2, y=FLOOR_TOP + FLOOR_HEIGHT / 2, width=FLOOR_WIDTH, height=FLOOR_HEIGHT,
                    cornerRadiusTL=FLOOR_HEIGHT / 2)
    ease_in = kit.ease(doc, *EASE_IN)
    ease_out = kit.ease(doc, *EASE_OUT)
    how = {"in": ease_in, "out": ease_out, None: None}
    bounce = doc.add(Obj("LinearAnimation", name="bounce", fps=FPS, duration=DURATION, loopValue=loop))
    kit.animate(doc, ball, {name: [(f, v, how[h]) for f, v, h in frames] for name, frames in BALL_TRACKS.items()})
    shadow_frames = [(f, v, how[h]) for f, v, h in SHADOW_SCALES]
    kit.animate(doc, shadow, {"scaleX": shadow_frames, "scaleY": shadow_frames})
    kit.loop_machine(doc, MACHINE, bounce)
    return doc
