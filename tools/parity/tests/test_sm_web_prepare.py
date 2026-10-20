import json
import sys
import tempfile
import unittest
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PARITY_DIR))

import sm_web_prepare

FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_trace.py")]


def entry(path):
    return {"path": path, "group": "g", "artboards": ["A"], "state_machines": [{"artboard": 0, "name": "SM"}], "features": [], "parse_error": None}


class ChooseTest(unittest.TestCase):
    def records(self):
        return [
            {"id": "a", "stats": {"events": 2, "inputs": 0, "changed_steps": 1}},
            {"id": "b", "stats": {"events": 0, "inputs": 3, "changed_steps": 1}},
            {"id": "c", "stats": {"events": 0, "inputs": 0, "changed_steps": 4}},
            {"id": "d", "stats": {"events": 0, "inputs": 0, "changed_steps": 0}},
            {"id": "e", "stats": {"events": 0, "inputs": 0, "changed_steps": 2}},
        ]

    def test_files_with_events_or_inputs_are_always_chosen(self):
        chosen = sm_web_prepare.choose(self.records(), others=0)
        self.assertEqual([r["id"] for r in chosen], ["a", "b"])

    def test_other_files_are_added_in_a_stable_order(self):
        first = [r["id"] for r in sm_web_prepare.choose(self.records(), others=2)]
        second = [r["id"] for r in sm_web_prepare.choose(self.records(), others=2)]
        self.assertEqual(first, second)
        self.assertEqual(len(first), 4)
        self.assertTrue({"a", "b"}.issubset(first))

    def test_a_record_without_stats_is_never_chosen(self):
        self.assertEqual(sm_web_prepare.choose([{"id": "x"}], others=3), [])


class PrepareTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.repo = self.dir / "repo"
        self.repo.mkdir()
        for name in ("a.riv", "b.riv"):
            (self.repo / name).write_bytes(b"RIVE" + bytes(range(20)))
        self.out = self.dir / "out"

    def test_scripts_and_native_traces_are_written(self):
        index = sm_web_prepare.prepare([entry("a.riv"), entry("b.riv")], self.repo, FAKE, self.out, others=5, timeout=60)
        self.assertEqual(len(index), 2)
        for record in index:
            self.assertTrue((self.out / f"{record['id']}.script.jsonl").is_file())
            self.assertIn('"end": true', (self.out / f"{record['id']}.native.jsonl").read_text(encoding="utf-8"))
        written = json.loads((self.out / "index.json").read_text(encoding="utf-8"))
        self.assertEqual({r["path"] for r in written}, {"a.riv", "b.riv"})
        self.assertEqual(written[0]["artboard"], "A")
        self.assertEqual(written[0]["stateMachine"], "SM")

    def test_a_file_that_fails_to_describe_is_left_out(self):
        (self.repo / "b.riv").write_bytes(b"RIVE")
        index = sm_web_prepare.prepare([entry("a.riv")], self.repo, [sys.executable, "-c", "import sys; sys.exit(3)"], self.out, others=5, timeout=60)
        self.assertEqual(index, [])

    def test_ids_are_safe_file_names(self):
        (self.repo / "dir").mkdir()
        (self.repo / "dir" / "a b.riv").write_bytes(b"RIVE")
        index = sm_web_prepare.prepare([entry("dir/a b.riv")], self.repo, FAKE, self.out, others=1, timeout=60)
        self.assertRegex(index[0]["id"], r"^[A-Za-z0-9._-]+$")


if __name__ == "__main__":
    unittest.main()
