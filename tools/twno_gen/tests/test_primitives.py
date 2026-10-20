import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import twno_writer as w


class VaruintTest(unittest.TestCase):
    def test_boundaries(self):
        cases = {
            0: "00",
            127: "7f",
            128: "8001",
            300: "ac02",
            2**32 - 1: "ffffffff0f",
            2**64 - 1: "ffffffffffffffffff01",
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(w.varuint(value).hex(), expected)

    def test_rejects_out_of_range(self):
        for value in (-1, 2**64):
            with self.subTest(value=value), self.assertRaises(w.WriteError):
                w.varuint(value)

    def test_rejects_non_integers(self):
        for value in (1.0, "1", True, None):
            with self.subTest(value=value), self.assertRaises(w.WriteError):
                w.varuint(value)


class ZigzagTest(unittest.TestCase):
    def test_signed_values(self):
        cases = {0: "00", -1: "01", 1: "02", -2: "03", 2**31 - 1: "feffffff0f", -(2**31): "ffffffff0f"}
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(w.signed_varint(value).hex(), expected)

    def test_rejects_out_of_range(self):
        for value in (2**31, -(2**31) - 1):
            with self.subTest(value=value), self.assertRaises(w.WriteError):
                w.signed_varint(value)


class Float32Test(unittest.TestCase):
    def test_encoding(self):
        self.assertEqual(w.float32(1.0).hex(), "0000803f")
        self.assertEqual(w.float32(-2).hex(), "000000c0")
        self.assertEqual(w.float32(0.1).hex(), "cdcccc3d")

    def test_rejects_non_finite_and_overflow(self):
        for value in (math.nan, math.inf, 1e39):
            with self.subTest(value=value), self.assertRaises(w.WriteError):
                w.float32(value)

    def test_rejects_non_numbers(self):
        for value in ("1.0", True, None):
            with self.subTest(value=value), self.assertRaises(w.WriteError):
                w.float32(value)


class ColorTest(unittest.TestCase):
    def test_encoding_is_little_endian_argb(self):
        self.assertEqual(w.color_word(0xFF112233).hex(), "332211ff")

    def test_helpers(self):
        self.assertEqual(w.argb(255, 17, 34, 51), 0xFF112233)
        self.assertEqual(w.rgb(0x112233), 0xFF112233)
        self.assertEqual(w.rgb("#112233"), 0xFF112233)
        self.assertEqual(w.rgb("#112233", alpha=0x80), 0x80112233)

    def test_rejects_bad_values(self):
        for value in (-1, 2**32, 1.5):
            with self.subTest(value=value), self.assertRaises(w.WriteError):
                w.color_word(value)
        for call in (lambda: w.argb(256, 0, 0, 0), lambda: w.rgb("#12345"), lambda: w.rgb(2**24)):
            with self.assertRaises(w.WriteError):
                call()


class StringTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(w.string_value("").hex(), "00")

    def test_ascii(self):
        self.assertEqual(w.string_value("abc"), b"\x03abc")

    def test_non_ascii_counts_utf8_bytes(self):
        self.assertEqual(w.string_value("é"), b"\x02\xc3\xa9")
        self.assertEqual(w.string_value("日本"), b"\x06" + "日本".encode("utf-8"))

    def test_long_string_uses_multibyte_length(self):
        encoded = w.string_value("a" * 200)
        self.assertEqual(encoded[:2].hex(), "c801")
        self.assertEqual(len(encoded), 202)

    def test_rejects_non_strings_and_lone_surrogates(self):
        for value in (b"abc", 1, None, "\ud800"):
            with self.subTest(value=value), self.assertRaises(w.WriteError):
                w.string_value(value)


class BytesTest(unittest.TestCase):
    def test_prefixed(self):
        self.assertEqual(w.bytes_value(b"\x00\xff"), b"\x02\x00\xff")
        self.assertEqual(w.bytes_value(b""), b"\x00")

    def test_rejects_str(self):
        with self.assertRaises(w.WriteError):
            w.bytes_value("abc")


class BoolTest(unittest.TestCase):
    def test_single_byte(self):
        self.assertEqual(w.bool_value(True), b"\x01")
        self.assertEqual(w.bool_value(False), b"\x00")

    def test_rejects_integers(self):
        for value in (0, 1, "true", None):
            with self.subTest(value=value), self.assertRaises(w.WriteError):
                w.bool_value(value)


if __name__ == "__main__":
    unittest.main()
