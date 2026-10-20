import sys
import tempfile
import unittest
from pathlib import Path

import numpy
from PIL import Image

PARITY_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PARITY_DIR))

import pixeldiff


def write_png(path, array):
    Image.fromarray(array.astype("uint8"), "RGBA").save(path)


class PixelDiffTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.base = numpy.zeros((4, 6, 4), dtype="uint8")
        self.base[..., 3] = 255
        self.base[1, 2] = (10, 20, 30, 255)

    def make(self, name, array):
        path = self.dir / name
        write_png(path, array)
        return path

    def test_identical_images(self):
        a = self.make("a.png", self.base)
        b = self.make("b.png", self.base.copy())
        result = pixeldiff.compare_png(a, b)
        self.assertTrue(result.identical)
        self.assertEqual(result.differing_pixels, 0)
        self.assertEqual(result.max_channel_diff, 0)
        self.assertEqual((result.width, result.height), (6, 4))

    def test_single_pixel_difference_is_detected(self):
        other = self.base.copy()
        other[3, 5, 0] = 7
        a = self.make("a.png", self.base)
        b = self.make("b.png", other)
        result = pixeldiff.compare_png(a, b)
        self.assertFalse(result.identical)
        self.assertEqual(result.differing_pixels, 1)
        self.assertEqual(result.max_channel_diff, 7)

    def test_alpha_channel_counts(self):
        other = self.base.copy()
        other[0, 0, 3] = 254
        result = pixeldiff.compare_png(self.make("a.png", self.base), self.make("b.png", other))
        self.assertFalse(result.identical)
        self.assertEqual(result.max_channel_diff, 1)

    def test_size_mismatch(self):
        small = self.base[:2]
        result = pixeldiff.compare_png(self.make("a.png", self.base), self.make("b.png", small))
        self.assertFalse(result.identical)
        self.assertFalse(result.same_size)

    def test_missing_file_raises(self):
        a = self.make("a.png", self.base)
        with self.assertRaises(FileNotFoundError):
            pixeldiff.compare_png(a, self.dir / "absent.png")

    def test_difference_is_symmetric(self):
        other = self.base.copy()
        other[2, 2] = (255, 255, 255, 255)
        a = self.make("a.png", self.base)
        b = self.make("b.png", other)
        self.assertEqual(
            pixeldiff.compare_png(a, b).max_channel_diff,
            pixeldiff.compare_png(b, a).max_channel_diff,
        )


if __name__ == "__main__":
    unittest.main()
