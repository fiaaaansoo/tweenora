import json
import sys
import unittest
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PARITY_DIR))

import trace_compare


def header(**extra):
    return json.dumps({"trace": 1, "file": "a.riv", "artboard": "A", "stateMachine": "SM", **extra})


def step(index, changed=(), inputs=(), events=(), needs=True):
    return json.dumps(
        {
            "step": index,
            "action": {"op": "advance", "dt": 0.25},
            "needsAdvance": needs,
            "changed": [{"layer": layer, "state": state} for layer, state in changed],
            "inputs": [{"name": n, "kind": k, "value": v} for n, k, v in inputs],
            "events": [{"name": n, "delay": d} for n, d in events],
        }
    )


def end(count):
    return json.dumps({"end": True, "steps": count})


def trace(*lines):
    return "\n".join(lines) + "\n"


BASE = trace(
    header(),
    step(0, changed=[(0, "Idle")], inputs=[("go", "bool", False)]),
    step(1, changed=[(0, "Run")], inputs=[("go", "bool", True)], events=[("Ping", 0.0)]),
    end(2),
)


class CompareTest(unittest.TestCase):
    def test_identical_traces(self):
        result = trace_compare.compare_traces(BASE, BASE)
        self.assertEqual(result["status"], "identical")
        self.assertEqual(result["steps"], 2)

    def test_a_missing_event_is_a_difference(self):
        other = BASE.replace('"events": [{"name": "Ping", "delay": 0.0}]', '"events": []')
        result = trace_compare.compare_traces(BASE, other)
        self.assertEqual(result["status"], "different")
        self.assertEqual(result["first"]["step"], 1)
        self.assertEqual(result["first"]["field"], "events")

    def test_an_event_at_another_delay_is_a_difference(self):
        other = BASE.replace('"delay": 0.0', '"delay": 0.016')
        result = trace_compare.compare_traces(BASE, other)
        self.assertEqual(result["status"], "different")
        self.assertEqual(result["first"]["field"], "events")

    def test_a_different_state_is_a_difference(self):
        other = BASE.replace('"Run"', '"Walk"')
        result = trace_compare.compare_traces(BASE, other)
        self.assertEqual(result["first"]["field"], "changed")
        self.assertEqual(result["first"]["step"], 1)

    def test_a_different_input_value_is_a_difference(self):
        other = BASE.replace('"value": true', '"value": false')
        result = trace_compare.compare_traces(BASE, other)
        self.assertEqual(result["first"]["field"], "inputs")

    def test_events_in_another_order_are_a_difference(self):
        two = trace(header(), step(0, events=[("A", 0.0), ("B", 0.0)]), end(1))
        swapped = trace(header(), step(0, events=[("B", 0.0), ("A", 0.0)]), end(1))
        self.assertEqual(trace_compare.compare_traces(two, swapped)["status"], "different")

    def test_a_different_needs_advance_is_a_difference(self):
        other = trace(
            header(),
            step(0, changed=[(0, "Idle")], inputs=[("go", "bool", False)], needs=False),
            step(1, changed=[(0, "Run")], inputs=[("go", "bool", True)], events=[("Ping", 0.0)]),
            end(2),
        )
        result = trace_compare.compare_traces(BASE, other)
        self.assertEqual(result["first"]["field"], "needsAdvance")
        self.assertEqual(result["first"]["step"], 0)

    def test_a_truncated_output_is_reported_as_truncated(self):
        cut = BASE.rsplit("\n", 2)[0] + "\n"
        result = trace_compare.compare_traces(BASE, cut)
        self.assertEqual(result["status"], "truncated")
        self.assertEqual(result["side"], "b")

    def test_a_trace_with_an_extra_step_is_a_difference(self):
        longer = trace(
            header(),
            step(0, changed=[(0, "Idle")], inputs=[("go", "bool", False)]),
            step(1, changed=[(0, "Run")], inputs=[("go", "bool", True)], events=[("Ping", 0.0)]),
            step(2),
            end(3),
        )
        result = trace_compare.compare_traces(BASE, longer)
        self.assertEqual(result["status"], "different")
        self.assertEqual(result["first"]["field"], "steps")

    def test_a_different_header_is_a_difference(self):
        other = BASE.replace('"artboard": "A"', '"artboard": "B"')
        result = trace_compare.compare_traces(BASE, other)
        self.assertEqual(result["status"], "different")
        self.assertEqual(result["first"]["field"], "header")

    def test_an_unknown_version_is_invalid(self):
        other = BASE.replace('"trace": 1', '"trace": 2')
        result = trace_compare.compare_traces(other, other)
        self.assertEqual(result["status"], "invalid")

    def test_a_line_that_is_not_json_is_invalid(self):
        broken = BASE.replace('"step": 1', "garbage")
        result = trace_compare.compare_traces(BASE, broken)
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["side"], "b")

    def test_an_empty_output_is_invalid(self):
        self.assertEqual(trace_compare.compare_traces("", "")["status"], "invalid")

    def test_the_end_marker_must_count_the_steps(self):
        wrong = BASE.replace('"steps": 2', '"steps": 5')
        result = trace_compare.compare_traces(wrong, wrong)
        self.assertEqual(result["status"], "invalid")


class CommonFieldsTest(unittest.TestCase):
    def test_a_difference_outside_the_chosen_fields_is_ignored(self):
        other = BASE.replace('"Run"', '"Walk"').replace('"needsAdvance": true', '"needsAdvance": false')
        result = trace_compare.compare_traces(BASE, other, fields=("inputs", "events"))
        self.assertEqual(result["status"], "identical")

    def test_a_difference_inside_the_chosen_fields_is_reported(self):
        other = BASE.replace('"delay": 0.0', '"delay": 0.016')
        result = trace_compare.compare_traces(BASE, other, fields=("inputs", "events"))
        self.assertEqual(result["status"], "different")
        self.assertEqual(result["first"]["field"], "events")

    def test_the_header_is_compared_on_the_artboard_and_the_state_machine_only(self):
        other = BASE.replace('"file": "a.riv"', '"file": "b.riv"')
        result = trace_compare.compare_traces(BASE, other, fields=("inputs",))
        self.assertEqual(result["status"], "identical")
        renamed = BASE.replace('"stateMachine": "SM"', '"stateMachine": "Other"')
        self.assertEqual(trace_compare.compare_traces(BASE, renamed, fields=("inputs",))["status"], "different")

    def test_a_float_tolerance_accepts_single_precision_noise(self):
        a = trace(header(), step(0, inputs=[("n", "number", 27.8432617)]), end(1))
        b = trace(header(), step(0, inputs=[("n", "number", 27.84326171875)]), end(1))
        self.assertEqual(trace_compare.compare_traces(a, b)["status"], "different")
        self.assertEqual(trace_compare.compare_traces(a, b, float_tolerance=1e-6)["status"], "identical")

    def test_the_tolerance_does_not_hide_a_real_difference(self):
        a = trace(header(), step(0, events=[("E", 0.1)]), end(1))
        b = trace(header(), step(0, events=[("E", 0.116)]), end(1))
        self.assertEqual(trace_compare.compare_traces(a, b, float_tolerance=1e-6)["status"], "different")

    def test_the_tolerance_does_not_equate_a_bool_and_a_number(self):
        a = trace(header(), step(0, inputs=[("b", "bool", True)]), end(1))
        b = trace(header(), step(0, inputs=[("b", "bool", 1)]), end(1))
        self.assertEqual(trace_compare.compare_traces(a, b, float_tolerance=1e-6)["status"], "different")

    def test_unknown_fields_are_refused(self):
        with self.assertRaises(ValueError):
            trace_compare.compare_traces(BASE, BASE, fields=("nothing",))


class FormatTest(unittest.TestCase):
    def test_a_valid_trace_parses(self):
        parsed = trace_compare.parse_trace(BASE)
        self.assertEqual(parsed["header"]["trace"], 1)
        self.assertEqual(len(parsed["steps"]), 2)

    def test_the_format_version_is_one(self):
        self.assertEqual(trace_compare.FORMAT_VERSION, 1)

    def test_steps_must_be_numbered_in_order(self):
        bad = trace(header(), step(0), step(2), end(2))
        with self.assertRaises(trace_compare.TraceError):
            trace_compare.parse_trace(bad)


class ScriptTest(unittest.TestCase):
    def test_a_valid_script_is_accepted(self):
        lines = [
            '{"op": "advance", "dt": 0.25}',
            '{"op": "bool", "name": "go", "value": true}',
            '{"op": "number", "name": "n", "value": 3}',
            '{"op": "trigger", "name": "t"}',
            '{"op": "pointer", "kind": "down", "x": 1, "y": 2}',
        ]
        self.assertEqual(len(trace_compare.parse_script("\n".join(lines))), 5)

    def test_an_unknown_operation_is_refused(self):
        with self.assertRaises(trace_compare.TraceError):
            trace_compare.parse_script('{"op": "jump"}')

    def test_a_negative_delta_is_refused(self):
        with self.assertRaises(trace_compare.TraceError):
            trace_compare.parse_script('{"op": "advance", "dt": -1}')

    def test_a_pointer_kind_must_be_known(self):
        with self.assertRaises(trace_compare.TraceError):
            trace_compare.parse_script('{"op": "pointer", "kind": "tap", "x": 0, "y": 0}')

    def test_an_input_operation_needs_a_name(self):
        with self.assertRaises(trace_compare.TraceError):
            trace_compare.parse_script('{"op": "bool", "value": true}')

    def test_blank_lines_are_ignored(self):
        self.assertEqual(len(trace_compare.parse_script('\n{"op": "advance", "dt": 0}\n\n')), 1)


if __name__ == "__main__":
    unittest.main()
