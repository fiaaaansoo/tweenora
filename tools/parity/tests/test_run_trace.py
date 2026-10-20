import os
import sys
import tempfile
import unittest
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PARITY_DIR))

import run_trace

FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_trace.py")]
SCRIPT = '{"op": "advance", "dt": 0.016}\n{"op": "trigger", "name": "go"}\n{"op": "advance", "dt": 0.5}\n'


class RunTraceTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.source = self.dir / "a.riv"
        self.source.write_bytes(b"RIVE")
        self.script = self.dir / "a.jsonl"
        self.script.write_text(SCRIPT, encoding="utf-8")

    def run_pair(self, env_fork=None, env_ref=None, fork=FAKE, ref=FAKE):
        return run_trace.run_pair(fork, ref, self.source, self.script, env_fork=env_fork, env_ref=env_ref, timeout=60)

    def test_identical_traces(self):
        result = self.run_pair()
        self.assertEqual(result["status"], "identical")
        self.assertEqual(result["steps"], 3)

    def test_a_dropped_event_on_the_fork_is_detected(self):
        result = self.run_pair(env_fork={"FAKE_TRACE_MODE": "drop_event"})
        self.assertEqual(result["status"], "different")
        self.assertEqual(result["first"]["field"], "events")

    def test_an_event_at_another_delay_on_the_reference_is_detected(self):
        result = self.run_pair(env_ref={"FAKE_TRACE_MODE": "late_event"})
        self.assertEqual(result["status"], "different")

    def test_a_truncated_output_is_detected(self):
        result = self.run_pair(env_fork={"FAKE_TRACE_MODE": "truncate"})
        self.assertEqual(result["status"], "truncated")
        self.assertEqual(result["side"], "a")

    def test_a_failing_binary_is_an_error_on_its_side(self):
        result = self.run_pair(env_ref={"FAKE_TRACE_MODE": "fail"})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["side"], "b")

    def test_both_failing_is_still_an_error(self):
        result = self.run_pair(env_fork={"FAKE_TRACE_MODE": "fail"}, env_ref={"FAKE_TRACE_MODE": "fail"})
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["side"], "both")

    def test_an_invalid_script_is_refused_before_running(self):
        self.script.write_text('{"op": "jump"}\n', encoding="utf-8")
        with self.assertRaises(run_trace.trace_compare.TraceError):
            self.run_pair()

    def test_the_traces_are_kept_in_the_result(self):
        result = self.run_pair()
        self.assertIn('"end": true', result["trace_a"])


class ShippedCasesTest(unittest.TestCase):
    def test_every_case_has_a_valid_script_and_an_existing_source(self):
        cases = run_trace.load_cases(run_trace.DEFAULT_CASES)
        self.assertGreaterEqual(len(cases), 3)
        for case in cases:
            script = run_trace.SM_TRACE_DIR / "scripts" / case["script"]
            self.assertTrue(script.is_file(), case["id"])
            run_trace.trace_compare.parse_script(script.read_text(encoding="utf-8"))
            self.assertTrue((run_trace.REPO_ROOT / case["path"]).is_file(), case["id"])

    def test_case_ids_are_unique(self):
        ids = [case["id"] for case in run_trace.load_cases(run_trace.DEFAULT_CASES)]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
