import tempfile
import unittest
from collections import deque
from pathlib import Path

from support import channels, prop, read

import render_check
import scene_kit as kit
from schema_index import SchemaIndex
from scenes import button

BOOL_NAMES = {kit.BOOL_IS_TRUE: "true", kit.BOOL_IS_FALSE: "false"}
INPUT_FOR_CONDITION = {
    "TransitionBoolCondition": "StateMachineBool",
    "TransitionNumberCondition": "StateMachineNumber",
    "TransitionTriggerCondition": "StateMachineTrigger",
}
INPUT_KINDS = ("StateMachineBool", "StateMachineTrigger", "StateMachineNumber")
REST_ANIMATIONS = ("repos", "actif")
PULSE_ANIMATIONS = ("neutre", "pulsation")
SETTLE_FRAMES = 3


def parse_machines(document):
    animations = [o for o in document["objects"] if o["typeName"] == "LinearAnimation"]
    machines = []
    machine = layer = state = transition = None
    for obj in document["objects"]:
        kind = obj["typeName"]
        if kind == "StateMachine":
            machine = {"name": prop(obj, "name"), "inputs": [], "layers": []}
            machines.append(machine)
        elif kind in INPUT_KINDS:
            machine["inputs"].append({"name": prop(obj, "name"), "type": kind, "value": prop(obj, "value")})
        elif kind == "StateMachineLayer":
            layer = {"name": prop(obj, "name"), "states": [], "transitions": []}
            machine["layers"].append(layer)
        elif kind in ("EntryState", "AnyState", "ExitState", "AnimationState"):
            state = {
                "type": kind,
                "index": len(layer["states"]),
                "animation": prop(obj, "animationId"),
                "out": [],
            }
            layer["states"].append(state)
        elif kind == "StateTransition":
            transition = {
                "from": state["index"],
                "to": prop(obj, "stateToId"),
                "duration": prop(obj, "duration", 0),
                "flags": prop(obj, "flags", 0),
                "exitTime": prop(obj, "exitTime", 0),
                "conditions": [],
            }
            state["out"].append(transition)
            layer["transitions"].append(transition)
        elif kind in INPUT_FOR_CONDITION:
            condition = {"type": kind, "input": prop(obj, "inputId"), "op": prop(obj, "opValue", 0)}
            transition["conditions"].append(condition)
    return animations, machines


class ButtonGraphTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = read(button.build().to_bytes(b"RIVE"))
        cls.animations, cls.machines = parse_machines(cls.document)
        cls.by_name = {m["name"]: m for m in cls.machines}

    def test_machines_and_inputs(self):
        self.assertEqual([m["name"] for m in self.machines], [button.TOGGLE, button.PULSE])
        self.assertEqual(
            self.by_name[button.TOGGLE]["inputs"],
            [{"name": button.INPUT_BOOL, "type": "StateMachineBool", "value": False}],
        )
        self.assertEqual(
            self.by_name[button.PULSE]["inputs"],
            [{"name": button.INPUT_TRIGGER, "type": "StateMachineTrigger", "value": None}],
        )
        default = prop(self.document["objects"][1], "defaultStateMachineId")
        self.assertEqual(self.machines[default]["name"], button.TOGGLE)

    def test_graph_is_consistent(self):
        for machine in self.machines:
            self.assertTrue(machine["layers"])
            for layer in machine["layers"]:
                kinds = [s["type"] for s in layer["states"]]
                self.assertEqual(kinds.count("EntryState"), 1)
                self.assertEqual(kinds.count("AnyState"), 1)
                self.assertEqual(kinds.count("ExitState"), 1)
                for state in layer["states"]:
                    if state["type"] == "AnimationState":
                        self.assertLess(state["animation"], len(self.animations))
                for transition in layer["transitions"]:
                    self.assertLess(transition["to"], len(layer["states"]))
                    self.assertNotEqual(layer["states"][transition["to"]]["type"], "EntryState")
                    for condition in transition["conditions"]:
                        self.assertLess(condition["input"], len(machine["inputs"]))
                        expected = INPUT_FOR_CONDITION[condition["type"]]
                        self.assertEqual(machine["inputs"][condition["input"]]["type"], expected)

    def test_every_animation_state_is_reachable_from_the_entry(self):
        for machine in self.machines:
            for layer in machine["layers"]:
                entry = next(s for s in layer["states"] if s["type"] == "EntryState")
                seen = {entry["index"]}
                queue = deque([entry])
                while queue:
                    for transition in queue.popleft()["out"]:
                        target = layer["states"][transition["to"]]
                        if target["index"] not in seen:
                            seen.add(target["index"])
                            queue.append(target)
                playable = {s["index"] for s in layer["states"] if s["type"] == "AnimationState"}
                self.assertTrue(playable <= seen, machine["name"])
                self.assertEqual(len(entry["out"]), 1)
                self.assertEqual(entry["out"][0]["conditions"], [])

    def test_every_state_that_can_be_left_is_left_by_a_condition_or_an_exit_time(self):
        for machine in self.machines:
            for layer in machine["layers"]:
                for transition in layer["transitions"]:
                    source = layer["states"][transition["from"]]
                    if source["type"] == "EntryState":
                        continue
                    self.assertTrue(transition["conditions"] or transition["flags"] & kit.TRANSITION_ENABLE_EXIT_TIME)

    def test_no_animation_state_is_a_dead_end_or_loops_on_itself(self):
        for machine in self.machines:
            for layer in machine["layers"]:
                for state in layer["states"]:
                    if state["type"] == "AnimationState":
                        self.assertTrue(state["out"], (machine["name"], state["index"]))
                for transition in layer["transitions"]:
                    self.assertNotEqual(transition["from"], transition["to"])

    def keyed_properties(self):
        objects = self.document["objects"]
        slots = {o["slot"]: o for o in objects if o["slot"] is not None}
        result = {}
        animation = target = None
        for obj in objects:
            kind = obj["typeName"]
            if kind == "LinearAnimation":
                animation = prop(obj, "name")
                result[animation] = set()
            elif kind == "KeyedObject":
                target = slots[prop(obj, "objectId")]["name"]
            elif kind == "KeyedProperty":
                result[animation].add((target, prop(obj, "propertyKey")))
        return result

    def test_each_animation_keys_exactly_its_properties(self):
        schema = SchemaIndex.default()
        x = schema.property_key("Node", "x")
        radius = schema.property_key("Rectangle", "cornerRadiusTL")
        color = schema.property_key("SolidColor", "colorValue")
        scale_x = schema.property_key("Node", "scaleX")
        scale_y = schema.property_key("Node", "scaleY")
        keyed = self.keyed_properties()
        look = {("pastille", x), ("face path", radius), ("face color", color)}
        scale = {("bouton", scale_x), ("bouton", scale_y)}
        self.assertEqual(keyed["repos"], look)
        self.assertEqual(keyed["actif"], look)
        self.assertEqual(keyed["neutre"], scale)
        self.assertEqual(keyed["pulsation"], scale)

    def test_the_two_machines_animate_disjoint_properties(self):
        keyed = self.keyed_properties()
        toggle = set().union(*(keyed[name] for name in REST_ANIMATIONS))
        pulse = set().union(*(keyed[name] for name in PULSE_ANIMATIONS))
        self.assertFalse(toggle & pulse)

    def test_toggle_transitions(self):
        layer = self.by_name[button.TOGGLE]["layers"][0]
        transitions = layer["transitions"]
        self.assertEqual(len(transitions), 3)
        _, to_active, back = transitions
        self.assertEqual([BOOL_NAMES[c["op"]] for c in to_active["conditions"]], ["true"])
        self.assertEqual([BOOL_NAMES[c["op"]] for c in back["conditions"]], ["false"])
        self.assertEqual(layer["states"][to_active["from"]]["animation"], 0)
        self.assertEqual(layer["states"][back["from"]]["animation"], 1)
        self.assertEqual((to_active["duration"], back["duration"]), (button.BLEND_MS, button.BLEND_MS))
        self.assertEqual(layer["states"][to_active["to"]]["animation"], 1)
        self.assertEqual(layer["states"][back["to"]]["animation"], 0)
        self.assertEqual(len(self.animations), 4)

    def test_pulse_returns_to_rest_through_an_exit_time(self):
        layer = self.by_name[button.PULSE]["layers"][0]
        _, press, back = layer["transitions"]
        self.assertEqual([c["type"] for c in press["conditions"]], ["TransitionTriggerCondition"])
        self.assertEqual(back["conditions"], [])
        self.assertEqual(back["flags"], kit.TRANSITION_EXIT_TIME_PERCENT)
        self.assertEqual(back["exitTime"], 100)
        self.assertEqual(layer["states"][press["from"]]["animation"], 2)
        self.assertEqual(layer["states"][back["from"]]["animation"], 3)
        self.assertEqual(layer["states"][back["to"]]["animation"], 2)
        self.assertEqual(layer["states"][press["to"]]["animation"], 3)

    def test_animation_values(self):
        objects = self.document["objects"]
        slots = {o["slot"]: o for o in objects if o["slot"] is not None}
        keyed = {}
        current = None
        animation = None
        for obj in objects:
            kind = obj["typeName"]
            if kind == "LinearAnimation":
                animation = prop(obj, "name")
                keyed[animation] = {}
            elif kind == "KeyedObject":
                current = slots[prop(obj, "objectId")]["name"]
            elif kind == "KeyedProperty":
                key = prop(obj, "propertyKey")
                keyed[animation].setdefault(current, {})[key] = []
                last = keyed[animation][current][key]
            elif kind in ("KeyFrameDouble", "KeyFrameColor"):
                last.append((prop(obj, "frame"), prop(obj, "value")))
        self.assertEqual(list(keyed), ["repos", "actif", "neutre", "pulsation"])
        schema = SchemaIndex.default()
        x = schema.property_key("Node", "x")
        radius = schema.property_key("Rectangle", "cornerRadiusTL")
        color = schema.property_key("SolidColor", "colorValue")
        scale_x = schema.property_key("Node", "scaleX")
        scale_y = schema.property_key("Node", "scaleY")
        self.assertAlmostEqual(keyed["repos"]["pastille"][x][0][1], button.KNOB_REST_X)
        self.assertAlmostEqual(keyed["actif"]["pastille"][x][0][1], button.KNOB_ACTIVE_X)
        self.assertAlmostEqual(keyed["repos"]["face path"][radius][0][1], button.RADIUS_REST)
        self.assertAlmostEqual(keyed["actif"]["face path"][radius][0][1], button.RADIUS_ACTIVE)
        self.assertEqual(keyed["repos"]["face color"][color][0][1], button.COLOR_REST)
        self.assertEqual(keyed["actif"]["face color"][color][0][1], button.COLOR_ACTIVE)
        pulse = keyed["pulsation"]["bouton"]
        self.assertEqual([f for f, _ in pulse[scale_x]], [0, button.PULSE_PEAK_FRAME, button.PULSE_FRAMES])
        self.assertEqual([round(v, 4) for _, v in pulse[scale_x]], [1.0, button.PULSE_SCALE, 1.0])
        self.assertEqual(pulse[scale_x], pulse[scale_y])

    def test_static_pose_equals_the_rest_animation(self):
        objects = {o["name"]: o for o in self.document["objects"] if o["name"]}
        self.assertAlmostEqual(prop(objects["pastille"], "x"), button.KNOB_REST_X)
        self.assertAlmostEqual(prop(objects["face path"], "cornerRadiusTL"), button.RADIUS_REST)
        self.assertEqual(prop(objects["face color"], "colorValue"), button.COLOR_REST)

    def test_regeneration_is_identical(self):
        self.assertEqual(button.build().to_bytes(b"RIVE"), button.build().to_bytes(b"RIVE"))


class NativeButtonRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            render_check.find_goldens()
            render_check.require_imaging()
        except render_check.RenderUnavailable as error:
            raise unittest.SkipTest(str(error)) from None
        cls.folder = tempfile.TemporaryDirectory()
        cls.riv = Path(cls.folder.name) / "button.riv"
        cls.riv.write_bytes(button.build().to_bytes(b"RIVE"))
        cls.twno = Path(cls.folder.name) / "button-twno.riv"
        cls.twno.write_bytes(button.build().to_bytes(b"TWNR"))

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def render(self, path, machine):
        return render_check.render(path, advance=SETTLE_FRAMES, state_machine=machine)

    def pixel(self, image, x, y):
        column, row = render_check.artboard_to_frame(x, y, button.SIZE, button.SIZE)
        return tuple(int(v) for v in image[row, column][:3])

    def test_the_file_loads_and_shows_the_static_rest_pose(self):
        for machine in (button.TOGGLE, button.PULSE):
            with self.subTest(machine=machine):
                image = self.render(self.riv, machine)
                centre = button.CENTRE
                self.assertEqual(self.pixel(image, centre, centre), channels(button.COLOR_REST))
                self.assertEqual(
                    self.pixel(image, centre + button.KNOB_REST_X, centre), channels(button.KNOB_COLOR)
                )
                self.assertEqual(
                    self.pixel(image, centre + button.KNOB_ACTIVE_X, centre), channels(button.COLOR_REST)
                )
                corner = (centre - button.FACE_WIDTH / 2 + 7, centre - button.FACE_HEIGHT / 2 + 8)
                self.assertEqual(self.pixel(image, *corner), channels(button.COLOR_REST))

    def test_twno_renders_like_riv(self):
        for machine in (button.TOGGLE, button.PULSE):
            with self.subTest(machine=machine):
                riv = self.render(self.riv, machine)
                twno = self.render(self.twno, machine)
                self.assertTrue((riv == twno).all())


if __name__ == "__main__":
    unittest.main()
