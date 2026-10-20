import json
import sys
import tempfile
import unittest
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PARITY_DIR))

import sm_web_compare

HEADER = '{"trace": 1, "file": "a.riv", "artboard": "A", "stateMachine": "SM"}'


def trace(step_inputs, events=(), extra=""):
    step = {"step": 0, "action": {"op": "advance", "dt": 0.25}, "inputs": step_inputs, "events": list(events)}
    if extra:
        step["needsAdvance"] = extra == "true"
        step["changed"] = [{"index": 0, "state": 61}]
    return "\n".join([HEADER, json.dumps(step), '{"end": true, "steps": 1}']) + "\n"


class CompareDirTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "index.json").write_text(json.dumps([{"id": "a", "path": "a.riv"}, {"id": "b", "path": "b.riv"}]), encoding="utf-8")

    def write(self, name, native, web):
        (self.dir / f"{name}.native.jsonl").write_text(native, encoding="utf-8")
        if web is not None:
            (self.dir / f"{name}.web.jsonl").write_text(web, encoding="utf-8")

    def test_the_common_fields_are_compared_and_the_native_only_fields_ignored(self):
        inputs = [{"name": "n", "kind": "number", "value": 27.8432617}]
        self.write("a", trace(inputs, extra="true"), trace([{"name": "n", "kind": "number", "value": 27.84326171875}]))
        self.write("b", trace([]), trace([]))
        records = sm_web_compare.compare_dir(self.dir)
        self.assertEqual({r["status"] for r in records}, {"identical"})

    def test_a_missing_event_on_the_web_is_a_difference(self):
        self.write("a", trace([], events=[{"name": "E", "delay": 0.1}]), trace([]))
        self.write("b", trace([]), trace([]))
        records = {r["id"]: r for r in sm_web_compare.compare_dir(self.dir)}
        self.assertEqual(records["a"]["status"], "different")
        self.assertEqual(records["a"]["first"]["field"], "events")

    def test_a_missing_web_trace_is_reported(self):
        self.write("a", trace([]), None)
        self.write("b", trace([]), trace([]))
        records = {r["id"]: r for r in sm_web_compare.compare_dir(self.dir)}
        self.assertEqual(records["a"]["status"], "missing_web")

    def test_an_explained_difference_does_not_fail(self):
        self.write("a", trace([], events=[{"name": "E", "delay": 0.1}]), trace([]))
        self.write("b", trace([]), trace([]))
        records = sm_web_compare.compare_dir(self.dir)
        report = sm_web_compare.build_report(records, {"a.riv": {"status": "different", "reason": "known"}})
        self.assertEqual(report["exit_code"], 0)
        self.assertEqual(report["summary"]["explained"], 1)

    def test_an_unexplained_difference_fails(self):
        self.write("a", trace([], events=[{"name": "E", "delay": 0.1}]), trace([]))
        self.write("b", trace([]), trace([]))
        report = sm_web_compare.build_report(sm_web_compare.compare_dir(self.dir), {})
        self.assertEqual(report["exit_code"], 1)

    def test_an_empty_index_fails(self):
        (self.dir / "index.json").write_text("[]", encoding="utf-8")
        self.assertEqual(sm_web_compare.build_report(sm_web_compare.compare_dir(self.dir), {})["exit_code"], 1)


if __name__ == "__main__":
    unittest.main()
