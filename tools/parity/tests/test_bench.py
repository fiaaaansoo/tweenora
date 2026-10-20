import os
import sys
import tempfile
import unittest
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PARITY_DIR))

import bench

FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_goldens.py")]


class BenchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.files = []
        for name, payload in (("one.riv", b"aaa"), ("two.riv", b"bbbb")):
            path = self.dir / name
            path.write_bytes(payload)
            self.files.append(path)
        self.old = os.environ.get("FAKE_MODE")
        self.addCleanup(self.restore)

    def restore(self):
        if self.old is None:
            os.environ.pop("FAKE_MODE", None)
        else:
            os.environ["FAKE_MODE"] = self.old

    def test_stable_renderer_is_deterministic(self):
        os.environ["FAKE_MODE"] = "stable"
        records = bench.check_determinism(FAKE, self.files, self.dir / "w", advance=5)
        self.assertEqual([r["status"] for r in records], ["deterministic", "deterministic"])
        self.assertTrue(all(len(r["sha256"]) == 64 for r in records))

    def test_clock_dependent_renderer_is_flagged(self):
        os.environ["FAKE_MODE"] = "clock"
        records = []
        for _ in range(6):
            records = bench.check_determinism(FAKE, self.files[:1], self.dir / "w", advance=5)
            if records[0]["status"] == "non_deterministic":
                break
        self.assertEqual(records[0]["status"], "non_deterministic")

    def test_failing_renderer_is_reported_not_raised(self):
        os.environ["FAKE_MODE"] = "fail"
        records = bench.check_determinism(FAKE, self.files, self.dir / "w", advance=0)
        self.assertEqual([r["status"] for r in records], ["error", "error"])
        self.assertIn("boom", records[0]["detail"])

    def test_compare_identical_builds(self):
        os.environ["FAKE_MODE"] = "stable"
        records = bench.compare_builds(FAKE, FAKE, self.files, self.dir / "w", advance=3)
        self.assertEqual([r["status"] for r in records], ["identical", "identical"])

    def test_compare_detects_a_different_build(self):
        os.environ["FAKE_MODE"] = "stable"
        records = bench.compare_builds(FAKE, FAKE, self.files, self.dir / "w", advance=3, env_b={"FAKE_MODE": "shift"})
        self.assertEqual([r["status"] for r in records], ["different", "different"])
        self.assertGreater(records[0]["differing_pixels"], 0)

    def test_one_side_failing_is_attributed(self):
        os.environ["FAKE_MODE"] = "stable"
        records = bench.compare_builds(FAKE, FAKE, self.files, self.dir / "w", advance=1, env_b={"FAKE_MODE": "fail"})
        self.assertEqual([r["status"] for r in records], ["error_b", "error_b"])
        self.assertIsNone(records[0]["detail"]["a"])
        self.assertIn("boom", records[0]["detail"]["b"]["message"])

    def test_both_sides_failing(self):
        os.environ["FAKE_MODE"] = "fail"
        records = bench.compare_builds(FAKE, FAKE, self.files, self.dir / "w", advance=1)
        self.assertEqual([r["status"] for r in records], ["same_failure", "same_failure"])

    def test_corrupt_png_does_not_abort_the_batch(self):
        os.environ["FAKE_MODE"] = "stable"
        records = bench.compare_builds(FAKE, FAKE, self.files, self.dir / "w", advance=1, env_b={"FAKE_MODE": "corrupt"})
        self.assertEqual([r["status"] for r in records], ["compare_error", "compare_error"])

    def test_zero_exit_without_png_is_an_error(self):
        os.environ["FAKE_MODE"] = "nopng"
        records = bench.check_determinism(FAKE, self.files, self.dir / "w", advance=1)
        self.assertEqual([r["status"] for r in records], ["error", "error"])

    def test_stale_png_is_not_reused(self):
        os.environ["FAKE_MODE"] = "stable"
        first = bench.check_determinism(FAKE, self.files[:1], self.dir / "w", advance=1)
        self.assertEqual(first[0]["status"], "deterministic")
        os.environ["FAKE_MODE"] = "nopng"
        again = bench.check_determinism(FAKE, self.files[:1], self.dir / "w", advance=1)
        self.assertEqual(again[0]["status"], "error")

    def test_summary_counts(self):
        records = [{"status": "identical"}, {"status": "different"}, {"status": "identical"}]
        self.assertEqual(bench.summarize(records), {"identical": 2, "different": 1})


if __name__ == "__main__":
    unittest.main()
