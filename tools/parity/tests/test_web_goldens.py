import json
import sys
import tempfile
import unittest
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PARITY_DIR))

import web_goldens

FAKE = [sys.executable, str(Path(__file__).resolve().parent / "fake_goldens.py")]


def sample_entry(id, path="a.riv", advance=0, artboard=None, state_machine=None):
    entry = {"id": id, "path": path, "advance": advance}
    if artboard is not None:
        entry["artboard"] = artboard
    if state_machine is not None:
        entry["stateMachine"] = state_machine
    return entry


class LoadSampleTest(unittest.TestCase):
    def write(self, data):
        directory = Path(tempfile.mkdtemp())
        path = directory / "sample.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_a_valid_sample_is_loaded(self):
        path = self.write({"entries": [sample_entry("a"), sample_entry("b", advance=60)]})
        self.assertEqual([e["id"] for e in web_goldens.load_sample(path)], ["a", "b"])

    def test_duplicate_ids_are_refused(self):
        path = self.write({"entries": [sample_entry("a"), sample_entry("a", advance=60)]})
        with self.assertRaisesRegex(ValueError, "duplicate"):
            web_goldens.load_sample(path)

    def test_an_id_must_be_a_safe_file_name(self):
        path = self.write({"entries": [sample_entry("../a")]})
        with self.assertRaisesRegex(ValueError, "id"):
            web_goldens.load_sample(path)

    def test_the_advance_must_be_a_non_negative_integer(self):
        path = self.write({"entries": [sample_entry("a", advance=-1)]})
        with self.assertRaisesRegex(ValueError, "advance"):
            web_goldens.load_sample(path)

    def test_an_empty_sample_is_refused(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            web_goldens.load_sample(self.write({"entries": []}))


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.repo = self.dir / "repo"
        self.repo.mkdir()
        (self.repo / "a.riv").write_bytes(b"RIVE" + bytes(range(40)))
        (self.repo / "b.riv").write_bytes(b"RIVE" + bytes(range(50)))
        self.out = self.dir / "golden"

    def render(self, entries, exe=FAKE, jobs=2):
        return web_goldens.render_goldens(entries, self.repo, exe, self.out, jobs=jobs, timeout=60)

    def test_each_entry_gets_its_own_png_and_an_index(self):
        entries = [sample_entry("a0", "a.riv"), sample_entry("b60", "b.riv", advance=60)]
        index = self.render(entries)
        self.assertEqual({r["id"] for r in index}, {"a0", "b60"})
        self.assertTrue((self.out / "a0.png").is_file())
        self.assertTrue((self.out / "b60.png").is_file())
        written = json.loads((self.out / "index.json").read_text(encoding="utf-8"))
        self.assertEqual({r["status"] for r in written}, {"rendered"})
        self.assertEqual(len(written[0]["sha256"]), 64)

    def test_two_entries_of_one_file_do_not_overwrite_each_other(self):
        entries = [sample_entry("x0", "a.riv", advance=0), sample_entry("x60", "a.riv", advance=60)]
        index = self.render(entries)
        by_id = {r["id"]: r["sha256"] for r in index}
        self.assertNotEqual(by_id["x0"], by_id["x60"])

    def test_a_failing_render_is_reported_not_raised(self):
        import os

        os.environ["FAKE_MODE"] = "fail"
        try:
            index = self.render([sample_entry("a0", "a.riv")])
        finally:
            del os.environ["FAKE_MODE"]
        self.assertEqual(index[0]["status"], "error")
        self.assertFalse((self.out / "a0.png").exists())

    def test_a_missing_source_is_reported(self):
        index = self.render([sample_entry("n", "none.riv")])
        self.assertEqual(index[0]["status"], "error")

    def test_the_index_keeps_the_order_of_the_sample(self):
        entries = [sample_entry(f"e{i}", "a.riv", advance=i) for i in range(5)]
        index = self.render(entries, jobs=3)
        self.assertEqual([r["id"] for r in index], [f"e{i}" for i in range(5)])


class OpacityTest(unittest.TestCase):
    def png(self, transparent):
        from PIL import Image

        image = Image.new("RGBA", (6, 6), (40, 40, 40, 255))
        for point in transparent:
            image.putpixel(point, (0, 0, 0, 0))
        path = Path(tempfile.mkdtemp()) / "x.png"
        image.save(path)
        return path

    def test_an_opaque_image_is_usable(self):
        self.assertTrue(web_goldens.is_opaque(self.png([])))

    def test_one_transparent_pixel_makes_it_unusable(self):
        self.assertFalse(web_goldens.is_opaque(self.png([(2, 3)])))


class TransparentGoldenTest(unittest.TestCase):
    def test_a_transparent_native_image_is_an_error(self):
        import os

        directory = Path(tempfile.mkdtemp())
        repo = directory / "repo"
        repo.mkdir()
        (repo / "a.riv").write_bytes(b"RIVE" + bytes(range(40)))
        os.environ["FAKE_ALPHA"] = "0"
        try:
            index = web_goldens.render_goldens([sample_entry("a0", "a.riv")], repo, FAKE, directory / "golden", jobs=1, timeout=60)
        finally:
            del os.environ["FAKE_ALPHA"]
        self.assertEqual(index[0]["status"], "error")
        self.assertIn("transparent", index[0]["detail"])
        self.assertFalse((directory / "golden" / "a0.png").exists())


if __name__ == "__main__":
    unittest.main()
