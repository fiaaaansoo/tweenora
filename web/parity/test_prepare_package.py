import io
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import prepare_package


def make_tgz(path, members):
    with tarfile.open(path, "w:gz") as archive:
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))


FULL = {
    "package/rive.js": b"js",
    "package/rive.wasm": b"wasm",
    "package/rive_fallback.wasm": b"fallback",
    "package/package.json": b"{}",
}


class ExtractTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.tgz = self.dir / "pkg.tgz"
        self.dest = self.dir / "out"

    def test_the_three_runtime_files_are_extracted_flat(self):
        make_tgz(self.tgz, FULL)
        prepare_package.extract_package(self.tgz, self.dest)
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), ["rive.js", "rive.wasm", "rive_fallback.wasm"])
        self.assertEqual((self.dest / "rive.wasm").read_bytes(), b"wasm")

    def test_a_missing_file_is_refused(self):
        make_tgz(self.tgz, {k: v for k, v in FULL.items() if k != "package/rive.wasm"})
        with self.assertRaisesRegex(ValueError, "rive.wasm"):
            prepare_package.extract_package(self.tgz, self.dest)

    def test_a_missing_archive_is_refused(self):
        with self.assertRaises(FileNotFoundError):
            prepare_package.extract_package(self.dir / "none.tgz", self.dest)

    def test_a_second_extraction_replaces_the_files(self):
        make_tgz(self.tgz, FULL)
        prepare_package.extract_package(self.tgz, self.dest)
        make_tgz(self.tgz, {**FULL, "package/rive.js": b"js2"})
        prepare_package.extract_package(self.tgz, self.dest)
        self.assertEqual((self.dest / "rive.js").read_bytes(), b"js2")

    def test_the_digests_are_returned(self):
        make_tgz(self.tgz, FULL)
        digests = prepare_package.extract_package(self.tgz, self.dest)
        self.assertEqual(set(digests), {"rive.js", "rive.wasm", "rive_fallback.wasm"})
        self.assertEqual(len(digests["rive.js"]), 64)


if __name__ == "__main__":
    unittest.main()
