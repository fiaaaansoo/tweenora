import functools
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

import twno_convert

SCRIPT = TOOLS_DIR / "twno_convert.py"
BODY = bytes(range(256)) * 4


@functools.cache
def reference_files():
    return tuple(sorted((REPO_ROOT / "runtime").rglob("*.riv")))


DIRECTIONS = (
    (twno_convert.riv_to_twno, b"RIVE", b"TWNR"),
    (twno_convert.twno_to_riv, b"TWNR", b"RIVE"),
)


class SignatureRewriteTest(unittest.TestCase):
    def test_replaces_only_the_signature(self):
        for convert, source, target in DIRECTIONS:
            with self.subTest(convert=convert.__name__):
                self.assertEqual(convert(source + BODY), target + BODY)
                self.assertEqual(convert(source), target)

    def test_rejects_the_other_format_and_unknown_signatures(self):
        for convert, source, target in DIRECTIONS:
            for data in (target + BODY, b"JUNK" + BODY, b"rive" + BODY):
                with self.subTest(convert=convert.__name__, data=data[:4]):
                    with self.assertRaises(twno_convert.ConversionError):
                        convert(data)

    def test_rejects_files_shorter_than_a_signature(self):
        for convert, source, target in DIRECTIONS:
            for data in (b"", source[:3]):
                with self.subTest(convert=convert.__name__, data=data):
                    with self.assertRaises(twno_convert.ConversionError):
                        convert(data)

    def test_signatures_match_the_runtime_header(self):
        header = (REPO_ROOT / "runtime/include/rive/runtime_header.hpp").read_text()
        current = re.search(r'kRuntimeHeaderFingerprint\[\]\s*=\s*"(\w{4})"', header)
        legacy = re.search(r'kRuntimeHeaderLegacyFingerprint\[\]\s*=\s*"(\w{4})"', header)
        self.assertEqual(current.group(1).encode(), twno_convert.TWNO_SIGNATURE)
        self.assertEqual(legacy.group(1).encode(), twno_convert.RIV_SIGNATURE)


class RoundTripTest(unittest.TestCase):
    def test_reference_corpus_has_475_files(self):
        self.assertEqual(len(reference_files()), 475)

    def test_round_trip_is_byte_identical_on_every_reference_file(self):
        failures = []
        for path in reference_files():
            original = path.read_bytes()
            twno = twno_convert.riv_to_twno(original)
            if twno[:4] != b"TWNR" or twno_convert.twno_to_riv(twno) != original:
                failures.append(str(path))
        self.assertEqual(failures, [])


class CommandLineTest(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-I", str(SCRIPT), *map(str, args)],
            capture_output=True,
            text=True,
        )

    def test_converts_riv_to_twno_next_to_the_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "scene.riv"
            src.write_bytes(b"RIVE" + BODY)
            result = self.run_cli(src)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((Path(tmp) / "scene.twno").read_bytes(), b"TWNR" + BODY)
            self.assertEqual(src.read_bytes(), b"RIVE" + BODY)

    def test_converts_twno_to_riv_next_to_the_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "scene.twno"
            src.write_bytes(b"TWNR" + BODY)
            result = self.run_cli(src)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((Path(tmp) / "scene.riv").read_bytes(), b"RIVE" + BODY)

    def test_output_option_sets_the_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "scene.riv"
            dst = Path(tmp) / "renamed.twno"
            src.write_bytes(b"RIVE" + BODY)
            result = self.run_cli(src, "-o", dst)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(dst.read_bytes(), b"TWNR" + BODY)

    def test_out_dir_collects_several_conversions(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.riv"
            b = Path(tmp) / "b.riv"
            out = Path(tmp) / "out"
            a.write_bytes(b"RIVE" + b"a")
            b.write_bytes(b"RIVE" + b"b")
            result = self.run_cli(a, b, "--out-dir", out)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((out / "a.twno").read_bytes(), b"TWNRa")
            self.assertEqual((out / "b.twno").read_bytes(), b"TWNRb")

    def test_refuses_to_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "scene.riv"
            dst = Path(tmp) / "scene.twno"
            src.write_bytes(b"RIVE" + BODY)
            dst.write_bytes(b"keep")
            result = self.run_cli(src)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(dst.read_bytes(), b"keep")
            result = self.run_cli(src, "--force")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(dst.read_bytes(), b"TWNR" + BODY)

    def test_fails_on_wrong_signature_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "scene.riv"
            src.write_bytes(b"JUNK" + BODY)
            result = self.run_cli(src)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((Path(tmp) / "scene.twno").exists())

    def test_fails_on_unknown_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "scene.bin"
            src.write_bytes(b"RIVE" + BODY)
            result = self.run_cli(src)
            self.assertNotEqual(result.returncode, 0)

    def test_unknown_extension_fails_even_with_output_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "scene.bin"
            dst = Path(tmp) / "x.riv"
            src.write_bytes(b"TWNR" + BODY)
            result = self.run_cli(src, "-o", dst)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(dst.exists())

    def test_refuses_to_convert_a_file_onto_itself(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "scene.riv"
            src.write_bytes(b"RIVE" + BODY)
            result = self.run_cli(src, "-o", src, "--force")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(src.read_bytes(), b"RIVE" + BODY)

    def test_output_option_must_carry_the_target_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            riv = Path(tmp) / "scene.riv"
            twno = Path(tmp) / "scene.twno"
            riv.write_bytes(b"RIVE" + BODY)
            twno.write_bytes(b"TWNR" + BODY)
            cases = ((riv, "scene.txt"), (riv, "other.riv"), (twno, "other.twno"))
            for source, name in cases:
                with self.subTest(source=source.name, output=name):
                    destination = Path(tmp) / name
                    result = self.run_cli(source, "-o", destination)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(destination.exists())

    def test_output_option_accepts_the_target_extension_in_any_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "scene.riv"
            dst = Path(tmp) / "scene.TWNO"
            src.write_bytes(b"RIVE" + BODY)
            result = self.run_cli(src, "-o", dst)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(dst.read_bytes(), b"TWNR" + BODY)

    def test_filesystem_errors_are_reported_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "scene.riv"
            blocker = Path(tmp) / "blocker"
            src.write_bytes(b"RIVE" + BODY)
            blocker.write_bytes(b"x")
            directory = Path(tmp) / "dir.twno"
            directory.mkdir()
            cases = (
                (src, "--out-dir", blocker),
                (src, "-o", directory, "--force"),
            )
            for args in cases:
                with self.subTest(args=[str(a) for a in args]):
                    result = self.run_cli(*args)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("twno-convert:", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_one_failing_input_does_not_stop_the_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.riv"
            good = Path(tmp) / "good.riv"
            bad.write_bytes(b"JUNK")
            good.write_bytes(b"RIVE" + BODY)
            result = self.run_cli(bad, good)
            self.assertEqual(result.returncode, 1)
            self.assertEqual((Path(tmp) / "good.twno").read_bytes(), b"TWNR" + BODY)

    def test_fails_on_missing_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_cli(Path(tmp) / "absent.riv")
            self.assertNotEqual(result.returncode, 0)

    def test_output_option_rejects_several_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.riv"
            b = Path(tmp) / "b.riv"
            a.write_bytes(b"RIVE")
            b.write_bytes(b"RIVE")
            result = self.run_cli(a, b, "-o", Path(tmp) / "x.twno")
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
