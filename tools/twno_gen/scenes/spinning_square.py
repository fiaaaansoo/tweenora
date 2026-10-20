import math

import scene_kit as kit
from twno_writer import Document, Obj

NAME = "spinning-square"
MACHINE = "loop"
SIZE = 400.0
FPS = 60
DURATION = 120
HALF = DURATION // 2
SIDE = 140.0
MARK_OFFSET = 42.0
SCALE_LOW = 0.85
TURN = 2 * math.pi
EASE = (0.42, 0.0, 0.58, 1.0)

ROTATION = ((0, 0.0), (DURATION, TURN))
SCALE = ((0, 1.0), (HALF, SCALE_LOW), (DURATION, 1.0))
COLORS = ((0, kit.TEAL), (HALF, kit.INDIGO), (DURATION, kit.TEAL))


def build(loop=1):
    doc = Document()
    doc.add(Obj("Backboard"))
    artboard = doc.add(Obj("Artboard", name="Spinning square", width=SIZE, height=SIZE, defaultStateMachine=MACHINE))
    pivot = doc.add(Obj("Node", name="pivot", parent=artboard, x=SIZE / 2, y=SIZE / 2))
    kit.solid_shape(doc, pivot, "mark", "Ellipse", kit.AMBER, x=MARK_OFFSET, width=26.0, height=26.0)
    _, body_color = kit.solid_shape(doc, pivot, "square", "Rectangle", kit.TEAL,
                                    width=SIDE, height=SIDE, cornerRadiusTL=18.0)
    ease = kit.ease(doc, *EASE)
    spin = doc.add(Obj("LinearAnimation", name="spin", fps=FPS, duration=DURATION, loopValue=loop))
    kit.animate(doc, pivot, {
        "rotation": [(f, v, None) for f, v in ROTATION],
        "scaleX": [(f, v, ease) for f, v in SCALE],
        "scaleY": [(f, v, ease) for f, v in SCALE],
    })
    kit.animate(doc, body_color, {"colorValue": [(f, v, None) for f, v in COLORS]})
    kit.loop_machine(doc, MACHINE, spin)
    return doc
