import json
import sys
import tempfile
import unittest
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PARITY_DIR))

import sm_compare

FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_trace.py")]


def entry(path, machines=1):
    return {
        "path": path,
        "group": "unit_tests_root",
        "artboards": ["A"],
        "state_machines": [{"artboard": 0, "name": f"SM{i}"} for i in range(machines)],
        "features": [],
        "parse_error": None,
    }


class SelectTest(unittest.TestCase):
    def test_only_files_with_a_state_machine_are_selected(self):
        entries = [entry("a.riv"), entry("b.riv", machines=0), entry("c.riv", machines=2)]
        self.assertEqual([e["path"] for e in sm_compare.select_files(entries)], ["a.riv", "c.riv"])

    def test_a_file_with_a_parse_error_is_not_selected(self):
        broken = entry("a.riv")
        broken["parse_error"] = "bad"
        self.assertEqual(sm_compare.select_files([broken]), [])

    def test_a_sample_is_deterministic_and_bounded(self):
        entries = [entry(f"f{i}.riv") for i in range(30)]
        first = [e["path"] for e in sm_compare.select_files(entries, sample=5)]
        second = [e["path"] for e in sm_compare.select_files(entries, sample=5)]
        self.assertEqual(first, second)
        self.assertEqual(len(first), 5)


class CompareFileTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.repo = self.dir / "repo"
        self.repo.mkdir()
        (self.repo / "a.riv").write_bytes(b"RIVE" + bytes(range(30)))
        self.work = self.dir / "work"

    def compare(self, fmt="riv", env_fork=None, env_ref=None):
        return sm_compare.compare_file(
            entry("a.riv"), self.repo, FAKE, FAKE, self.work, fmt=fmt, env_fork=env_fork, env_ref=env_ref, timeout=60
        )

    def test_identical(self):
        record = self.compare()
        self.assertEqual(record["status"], "identical")
        self.assertGreater(record["steps"], 10)

    def test_the_record_counts_what_the_trace_exercised(self):
        record = self.compare()
        self.assertEqual(record["stats"]["events"], 1)
        self.assertEqual(record["stats"]["inputs"], 0)
        self.assertEqual(record["stats"]["changed_steps"], 0)

    def test_a_difference_is_reported(self):
        record = self.compare(env_fork={"FAKE_TRACE_MODE": "drop_event"})
        self.assertEqual(record["status"], "different")
        self.assertEqual(record["first"]["field"], "events")

    def test_a_failing_describe_on_both_sides_is_a_common_failure(self):
        both = {"FAKE_TRACE_MODE": "fail"}
        record = self.compare(env_fork=both, env_ref=both)
        self.assertEqual(record["status"], "same_failure")

    def test_a_failing_describe_on_one_side_is_an_error(self):
        record = self.compare(env_ref={"FAKE_TRACE_MODE": "fail"})
        self.assertEqual(record["status"], "error")

    def test_twno_mode_runs_the_fork_on_a_signed_copy(self):
        record = self.compare(fmt="twno")
        self.assertEqual(record["status"], "identical")
        self.assertEqual(record["format"], "twno")

    def test_a_missing_source_is_an_error(self):
        record = sm_compare.compare_file(entry("none.riv"), self.repo, FAKE, FAKE, self.work, timeout=60)
        self.assertEqual(record["status"], "error")


class ReportTest(unittest.TestCase):
    def test_the_exit_code_is_one_for_an_unexplained_difference(self):
        records = [{"path": "a.riv", "status": "identical"}, {"path": "b.riv", "status": "different"}]
        report = sm_compare.build_report(records, {})
        self.assertEqual(report["exit_code"], 1)
        self.assertEqual(report["summary"]["unexplained"], 1)

    def test_an_explained_difference_does_not_fail(self):
        records = [{"path": "b.riv", "status": "different"}]
        report = sm_compare.build_report(records, {"b.riv": {"status": "different", "reason": "known"}})
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["summary"]["explained"], 1)

    def test_an_explanation_for_another_status_is_ignored(self):
        records = [{"path": "b.riv", "status": "error"}]
        report = sm_compare.build_report(records, {"b.riv": {"status": "different", "reason": "known"}})
        self.assertEqual(report["exit_code"], 1)

    def test_a_common_failure_does_not_fail(self):
        report = sm_compare.build_report([{"path": "a.riv", "status": "same_failure"}], {})
        self.assertEqual(report["exit_code"], 0)

    def test_an_empty_campaign_fails(self):
        self.assertEqual(sm_compare.build_report([], {})["exit_code"], 1)


if __name__ == "__main__":
    unittest.main()
