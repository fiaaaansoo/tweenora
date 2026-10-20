import json
import sys
import unittest
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PARITY_DIR))

import sm_actions
import trace_compare


def description(inputs=(), width=500.0, height=400.0):
    return {
        "artboard": "A",
        "stateMachine": "SM",
        "width": width,
        "height": height,
        "inputs": [{"name": n, "kind": k} for n, k in inputs],
    }


def ops(actions, op):
    return [a for a in actions if a["op"] == op]


class GenerateTest(unittest.TestCase):
    def test_every_script_is_valid(self):
        desc = description([("b", "bool"), ("n", "number"), ("t", "trigger")])
        text = sm_actions.script_text(sm_actions.generate(desc))
        self.assertGreater(len(trace_compare.parse_script(text)), 10)

    def test_a_bool_is_set_to_both_values(self):
        actions = sm_actions.generate(description([("b", "bool")]))
        values = [a["value"] for a in ops(actions, "bool")]
        self.assertIn(True, values)
        self.assertIn(False, values)

    def test_a_number_takes_the_boundary_values(self):
        actions = sm_actions.generate(description([("n", "number")]))
        values = {a["value"] for a in ops(actions, "number")}
        self.assertTrue({0, 1, -1, 100}.issubset(values))

    def test_each_trigger_is_fired_alone(self):
        actions = sm_actions.generate(description([("t1", "trigger"), ("t2", "trigger")]))
        fired = [a["name"] for a in ops(actions, "trigger")]
        self.assertIn("t1", fired)
        self.assertIn("t2", fired)
        index = next(i for i, a in enumerate(actions) if a["op"] == "trigger" and a["name"] == "t1")
        self.assertEqual(actions[index + 1]["op"], "advance")

    def test_every_input_change_is_followed_by_an_advance(self):
        actions = sm_actions.generate(description([("b", "bool"), ("n", "number"), ("t", "trigger")]))
        for index, action in enumerate(actions):
            if action["op"] in ("bool", "number", "trigger"):
                self.assertEqual(actions[index + 1]["op"], "advance")

    def test_pointer_events_stay_inside_the_artboard(self):
        actions = sm_actions.generate(description(width=500.0, height=400.0))
        pointers = ops(actions, "pointer")
        self.assertGreater(len(pointers), 0)
        for action in pointers:
            self.assertTrue(0 <= action["x"] <= 500)
            self.assertTrue(0 <= action["y"] <= 400)

    def test_each_down_is_released(self):
        actions = sm_actions.generate(description())
        kinds = [a["kind"] for a in ops(actions, "pointer")]
        self.assertEqual(kinds.count("down"), kinds.count("up"))

    def test_the_script_starts_and_ends_with_an_advance(self):
        actions = sm_actions.generate(description([("b", "bool")]))
        self.assertEqual(actions[0]["op"], "advance")
        self.assertEqual(actions[-1]["op"], "advance")

    def test_generation_is_deterministic(self):
        desc = description([("b", "bool"), ("n", "number"), ("t", "trigger")])
        first = sm_actions.script_text(sm_actions.generate(desc))
        second = sm_actions.script_text(sm_actions.generate(json.loads(json.dumps(desc))))
        self.assertEqual(first, second)

    def test_the_total_time_is_bounded(self):
        desc = description([("n%d" % i, "number") for i in range(6)] + [("t%d" % i, "trigger") for i in range(6)])
        actions = sm_actions.generate(desc)
        total = sum(a["dt"] for a in ops(actions, "advance"))
        self.assertLess(total, 60)
        self.assertLessEqual(len(actions), sm_actions.MAX_ACTIONS)

    def test_the_number_of_actions_is_capped(self):
        desc = description([("n%d" % i, "number") for i in range(200)])
        self.assertLessEqual(len(sm_actions.generate(desc)), sm_actions.MAX_ACTIONS)

    def test_unknown_input_kinds_are_skipped(self):
        actions = sm_actions.generate(description([("x", "other"), ("b", "bool")]))
        self.assertNotIn("x", [a.get("name") for a in actions])

    def test_a_description_without_a_state_machine_gives_no_script(self):
        self.assertIsNone(sm_actions.generate(None))

    def test_a_zero_size_artboard_has_no_pointer_events(self):
        actions = sm_actions.generate(description(width=0.0, height=0.0))
        self.assertEqual(ops(actions, "pointer"), [])


if __name__ == "__main__":
    unittest.main()
