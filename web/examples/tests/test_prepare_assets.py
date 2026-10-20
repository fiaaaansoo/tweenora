import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = EXAMPLES_DIR.parents[1]
sys.path.insert(0, str(EXAMPLES_DIR))

import prepare_assets

sys.path.insert(0, str(REPO_ROOT / "tools"))
import twno_convert

ORIGINAL_EXAMPLES = REPO_ROOT / "docs" / "examples"
SCRIPT = EXAMPLES_DIR / "prepare_assets.py"
BODY = bytes(range(256))


def write_riv(directory, name, body=BODY):
    path = directory / name
    path.write_bytes(b"RIVE" + body)
    return path


class PrepareTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.source = self.tmp / "source"
        self.source.mkdir()
        self.dest = self.tmp / "dest"

    def test_copies_riv_and_writes_twno(self):
        write_riv(self.source, "a.riv")
        written = prepare_assets.prepare([(self.source, ("a.riv",))], self.dest)
        self.assertEqual((self.dest / "a.riv").read_bytes(), b"RIVE" + BODY)
        self.assertEqual((self.dest / "a.twno").read_bytes(), b"TWNR" + BODY)
        self.assertEqual(sorted(p.name for p in written), ["a.riv", "a.twno"])

    def test_creates_destination_directory(self):
        write_riv(self.source, "a.riv")
        prepare_assets.prepare(
            [(self.source, ("a.riv",))], self.dest / "nested" / "deep"
        )
        self.assertTrue((self.dest / "nested" / "deep" / "a.twno").is_file())

    def test_is_idempotent(self):
        write_riv(self.source, "a.riv")
        sources = [(self.source, ("a.riv",))]
        prepare_assets.prepare(sources, self.dest)
        write_riv(self.source, "a.riv", BODY[::-1])
        prepare_assets.prepare(sources, self.dest)
        self.assertEqual((self.dest / "a.riv").read_bytes(), b"RIVE" + BODY[::-1])
        self.assertEqual((self.dest / "a.twno").read_bytes(), b"TWNR" + BODY[::-1])

    def test_missing_source_fails_and_names_the_file(self):
        with self.assertRaises(prepare_assets.PrepareError) as raised:
            prepare_assets.prepare([(self.source, ("absent.riv",))], self.dest)
        self.assertIn("absent.riv", str(raised.exception))

    def test_rejects_a_file_without_the_riv_signature(self):
        (self.source / "bad.riv").write_bytes(b"NOPE" + BODY)
        with self.assertRaises(prepare_assets.PrepareError) as raised:
            prepare_assets.prepare([(self.source, ("bad.riv",))], self.dest)
        self.assertIn("bad.riv", str(raised.exception))

    def test_copies_audio_files_without_converting_them(self):
        for name in ("a.wav", "b.mp3"):
            (self.source / name).write_bytes(BODY)
        written = prepare_assets.prepare(
            [(self.source, ("a.wav", "b.mp3"))], self.dest
        )
        self.assertEqual(sorted(p.name for p in written), ["a.wav", "b.mp3"])
        self.assertEqual((self.dest / "a.wav").read_bytes(), BODY)

    def test_copies_a_font_without_converting_it(self):
        (self.source / "f.ttf").write_bytes(BODY)
        written = prepare_assets.prepare([(self.source, ("f.ttf",))], self.dest)
        self.assertEqual((self.dest / "f.ttf").read_bytes(), BODY)
        self.assertEqual([p.name for p in written], ["f.ttf"])
        self.assertFalse((self.dest / "f.twno").exists())

    def test_rejects_a_name_without_the_riv_suffix(self):
        (self.source / "a.txt").write_bytes(BODY)
        with self.assertRaises(prepare_assets.PrepareError):
            prepare_assets.prepare([(self.source, ("a.txt",))], self.dest)

    def test_rejects_a_name_that_escapes_the_directory(self):
        write_riv(self.tmp, "a.riv")
        with self.assertRaises(prepare_assets.PrepareError):
            prepare_assets.prepare([(self.source, ("../a.riv",))], self.dest)

    def test_rejects_the_same_name_from_two_sources(self):
        other = self.tmp / "other"
        other.mkdir()
        write_riv(self.source, "a.riv")
        write_riv(other, "a.riv")
        with self.assertRaises(prepare_assets.PrepareError):
            prepare_assets.prepare(
                [(self.source, ("a.riv",)), (other, ("a.riv",))], self.dest
            )


def original_names():
    return sorted(path.name for path in ORIGINAL_EXAMPLES.glob("*.riv"))


class OriginalExamplesSourceTest(unittest.TestCase):
    def test_the_versioned_examples_are_a_source_of_their_own(self):
        declared = [names for directory, names in prepare_assets.ASSET_SOURCES if directory == ORIGINAL_EXAMPLES]
        self.assertEqual(len(declared), 1)
        self.assertEqual(sorted(declared[0]), original_names())
        self.assertTrue(original_names())

    def test_each_original_example_gives_a_riv_and_the_twno_of_that_riv(self):
        with tempfile.TemporaryDirectory() as folder:
            sources = [(ORIGINAL_EXAMPLES, tuple(original_names()))]
            written = prepare_assets.prepare(sources, folder)
            self.assertEqual(len(written), 2 * len(original_names()))
            for name in original_names():
                riv = (Path(folder) / name).read_bytes()
                self.assertEqual(riv, (ORIGINAL_EXAMPLES / name).read_bytes())
                twno = (Path(folder) / name).with_suffix(".twno").read_bytes()
                self.assertEqual(twno, twno_convert.riv_to_twno(riv))

    def test_an_upstream_file_with_the_name_of_an_original_example_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            clash = write_riv(Path(folder), original_names()[0])
            sources = [(ORIGINAL_EXAMPLES, tuple(original_names())), (clash.parent, (clash.name,))]
            with self.assertRaises(prepare_assets.PrepareError):
                prepare_assets.prepare(sources, Path(folder) / "out")


class DeclaredAssetsTest(unittest.TestCase):
    def test_every_declared_asset_exists_upstream_and_is_unique(self):
        names = []
        for directory, files in prepare_assets.ASSET_SOURCES:
            for name in files:
                self.assertTrue((directory / name).is_file(), str(directory / name))
                names.append(name)
        self.assertEqual(len(names), len(set(names)))

    def test_domain_assets_of_the_task_are_declared(self):
        names = {n for _, files in prepare_assets.ASSET_SOURCES for n in files}
        self.assertTrue(
            {
                "two_artboards.riv",
                "multiple_state_machines.riv",
                "hosted_image_file.riv",
                "kablammo.ttf",
                "what.wav",
                "sound2.riv",
                "hosted_audio_file.riv",
            }
            <= names
        )

    def test_removed_third_party_files_are_not_sources(self):
        for _, files in prepare_assets.ASSET_SOURCES:
            for name in files:
                self.assertFalse(name.startswith("echo_"), name)
                self.assertFalse(name.endswith(".mp3"), name)

    def test_default_destination_is_ignored_by_git(self):
        result = subprocess.run(
            ["git", "check-ignore", "-q", "web/examples/assets/x.riv"],
            cwd=REPO_ROOT,
        )
        self.assertEqual(result.returncode, 0)


class CommandLineTest(unittest.TestCase):
    def test_runs_into_the_given_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, "-I", str(SCRIPT), "--out-dir", tmp],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(tmp) / "two_artboards.twno").is_file())
            self.assertTrue((Path(tmp) / "two_artboards.riv").is_file())

    def test_fails_with_a_message_when_a_source_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = (
                "import sys\n"
                "sys.path.insert(0, sys.argv[1])\n"
                "import prepare_assets\n"
                "from pathlib import Path\n"
                "prepare_assets.ASSET_SOURCES = [(Path(sys.argv[2]), ('x.riv',))]\n"
                "sys.exit(prepare_assets.main(['--out-dir', sys.argv[2]]))\n"
            )
            result = subprocess.run(
                [sys.executable, "-I", "-c", code, str(EXAMPLES_DIR), tmp],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("x.riv", result.stderr)


if __name__ == "__main__":
    unittest.main()
