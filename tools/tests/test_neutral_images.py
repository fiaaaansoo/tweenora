import hashlib
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

import neutral_images
import test_image
import twnoinfo

SCRIPT = TOOLS_DIR / "neutral_images.py"
ASSETS = REPO_ROOT / "runtime" / "tests" / "unit_tests" / "assets"
IN_BAND = ASSETS / "in_band_asset.riv"


def png_size(data):
    return struct.unpack(">II", data[16:24])


def jpeg_size(data):
    position = 2
    while position < len(data):
        marker = data[position + 1]
        (length,) = struct.unpack(">H", data[position + 2 : position + 4])
        if marker == 0xC0:
            height, width = struct.unpack(">HH", data[position + 5 : position + 9])
            return width, height
        position += 2 + length
    raise AssertionError("no frame header")


class SizedImageTest(unittest.TestCase):
    def test_png_has_the_requested_size(self):
        data = test_image.build_png(37, 21)
        self.assertEqual(data[:8], test_image.SIGNATURE)
        self.assertEqual(png_size(data), (37, 21))

    def test_jpeg_has_the_requested_size(self):
        data = test_image.build_jpeg(45, 19)
        self.assertEqual(data[:2], bytes([0xFF, 0xD8]))
        self.assertEqual(jpeg_size(data), (45, 19))

    def test_default_jpeg_is_unchanged(self):
        self.assertEqual(test_image.build_jpeg(), test_image.build_jpeg(test_image.JPEG_WIDTH, test_image.JPEG_HEIGHT))

    def test_sized_images_are_deterministic(self):
        self.assertEqual(test_image.build_png(30, 20), test_image.build_png(30, 20))
        self.assertEqual(test_image.build_jpeg(30, 20), test_image.build_jpeg(30, 20))


class InBandAssetsTest(unittest.TestCase):
    def test_lists_the_embedded_image_of_a_file(self):
        found = neutral_images.in_band_assets(IN_BAND.read_bytes())
        self.assertEqual(len(found), 1)
        start, end, payload = found[0]
        self.assertEqual(payload[:8], test_image.SIGNATURE)
        self.assertEqual(len(payload), 308)
        self.assertLess(start, end)

    def test_replacement_keeps_the_size_and_the_format(self):
        original = IN_BAND.read_bytes()
        patched = neutral_images.replace_images(original, lambda payload: True)
        self.assertNotEqual(patched, original)
        (start, end, payload), = neutral_images.in_band_assets(patched)
        self.assertEqual(payload[:8], test_image.SIGNATURE)
        self.assertEqual(png_size(payload), png_size(neutral_images.in_band_assets(original)[0][2]))

    def test_replacement_leaves_the_rest_of_the_file_alone(self):
        original = IN_BAND.read_bytes()
        patched = neutral_images.replace_images(original, lambda payload: True)
        start, end, _ = neutral_images.in_band_assets(original)[0]
        new_start, new_end, _ = neutral_images.in_band_assets(patched)[0]
        self.assertEqual(original[:start], patched[:new_start])
        self.assertEqual(original[end:], patched[new_end:])

    def test_patched_file_is_still_readable(self):
        patched = neutral_images.replace_images(IN_BAND.read_bytes(), lambda payload: True)
        doc = twnoinfo.read_document(patched, twnoinfo.load_schema())
        self.assertEqual([o["typeName"] for o in doc["globalObjects"]], ["Backboard", "ImageAsset", "FileAssetContents"])

    def test_predicate_can_skip_an_image(self):
        original = IN_BAND.read_bytes()
        self.assertEqual(neutral_images.replace_images(original, lambda payload: False), original)

    def test_file_without_images_is_unchanged(self):
        data = (ASSETS / "hello_world.riv").read_bytes()
        self.assertEqual(neutral_images.replace_images(data, lambda payload: True), data)

    def test_non_image_contents_are_skipped(self):
        data = (REPO_ROOT / "web" / "rive-wasm" / "js" / "test" / "assets" / "fallback_fonts_test.riv").read_bytes()
        self.assertEqual(neutral_images.in_band_assets(data), [])


class CorpusTest(unittest.TestCase):
    def test_no_known_third_party_image_remains_in_the_repository(self):
        remaining = []
        for path in neutral_images.riv_files():
            for _, _, payload in neutral_images.in_band_assets(path.read_bytes()):
                digest = hashlib.sha256(payload).hexdigest()
                if digest in neutral_images.THIRD_PARTY_SHA256:
                    remaining.append((path.name, digest[:12]))
        self.assertEqual(remaining, [])

    def test_every_listed_hash_has_a_reason(self):
        for digest, reason in neutral_images.THIRD_PARTY_SHA256.items():
            self.assertEqual(len(digest), 64)
            self.assertTrue(reason)


class CommandLineTest(unittest.TestCase):
    def test_applies_to_a_file_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "a.riv"
            target.write_bytes(IN_BAND.read_bytes())
            digest = hashlib.sha256(neutral_images.in_band_assets(target.read_bytes())[0][2]).hexdigest()
            neutral_images.THIRD_PARTY_SHA256[digest] = "test"
            try:
                first = neutral_images.neutralize_file(target)
                second = neutral_images.neutralize_file(target)
            finally:
                del neutral_images.THIRD_PARTY_SHA256[digest]
            self.assertEqual(first, 1)
            self.assertEqual(second, 0)

    def test_list_option_runs(self):
        completed = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), "--list"], capture_output=True, text=True, encoding="utf-8", check=True
        )
        self.assertIn("embedded images", completed.stdout)


if __name__ == "__main__":
    unittest.main()
