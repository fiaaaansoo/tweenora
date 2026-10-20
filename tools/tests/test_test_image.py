import re
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

import test_image

SCRIPT = TOOLS_DIR / "test_image.py"
ASSETS = REPO_ROOT / "runtime" / "tests" / "unit_tests" / "assets"
SIGNATURE = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])


def chunks(data):
    position = len(SIGNATURE)
    while position < len(data):
        (length,) = struct.unpack(">I", data[position : position + 4])
        kind = data[position + 4 : position + 8]
        body = data[position + 8 : position + 8 + length]
        (crc,) = struct.unpack(">I", data[position + 8 + length : position + 12 + length])
        yield kind, body, crc
        position += 12 + length


def decode(data):
    parts = list(chunks(data))
    width, height, depth, color, _, _, _ = struct.unpack(">IIBBBBB", parts[0][1])
    raw = zlib.decompress(b"".join(body for kind, body, _ in parts if kind == b"IDAT"))
    stride = width * 4 + 1
    rows = []
    for y in range(height):
        row = raw[y * stride : (y + 1) * stride]
        rows.append((row[0], row[1:]))
    return width, height, depth, color, rows


class PngTest(unittest.TestCase):
    def test_signature_and_chunk_order(self):
        data = test_image.build()
        self.assertEqual(data[:8], SIGNATURE)
        kinds = [kind for kind, _, _ in chunks(data)]
        self.assertEqual(kinds[0], b"IHDR")
        self.assertEqual(kinds[-1], b"IEND")
        self.assertIn(b"IDAT", kinds)

    def test_every_chunk_has_a_valid_checksum(self):
        for kind, body, crc in chunks(test_image.build()):
            self.assertEqual(crc, zlib.crc32(kind + body) & 0xFFFFFFFF)

    def test_dimensions_and_format(self):
        width, height, depth, color, rows = decode(test_image.build())
        self.assertEqual((width, height), (test_image.WIDTH, test_image.HEIGHT))
        self.assertEqual((depth, color), (8, 6))
        self.assertEqual(len(rows), test_image.HEIGHT)
        for filter_type, pixels in rows:
            self.assertEqual(filter_type, 0)
            self.assertEqual(len(pixels), test_image.WIDTH * 4)

    def test_has_transparent_translucent_and_opaque_pixels(self):
        _, _, _, _, rows = decode(test_image.build())
        alphas = set()
        for _, pixels in rows:
            alphas.update(pixels[3::4])
        self.assertIn(0, alphas)
        self.assertIn(255, alphas)
        self.assertTrue(any(0 < a < 255 for a in alphas))

    def test_has_many_distinct_colors(self):
        _, _, _, _, rows = decode(test_image.build())
        colors = set()
        for _, pixels in rows:
            for x in range(0, len(pixels), 4):
                colors.add(pixels[x : x + 4])
        self.assertGreater(len(colors), 200)

    def test_deterministic(self):
        self.assertEqual(test_image.build(), test_image.build())


def jpeg_segments(data):
    assert data[:2] == bytes([0xFF, 0xD8])
    position = 2
    while position < len(data):
        assert data[position] == 0xFF
        marker = data[position + 1]
        if marker == 0xD9:
            yield marker, b""
            return
        (length,) = struct.unpack(">H", data[position + 2 : position + 4])
        yield marker, data[position + 4 : position + 2 + length]
        position += 2 + length
        if marker == 0xDA:
            end = data.rindex(bytes([0xFF, 0xD9]))
            position = end


class JpegTest(unittest.TestCase):
    def test_starts_and_ends_with_the_jpeg_markers(self):
        data = test_image.build_jpeg()
        self.assertEqual(data[:2], bytes([0xFF, 0xD8]))
        self.assertEqual(data[-2:], bytes([0xFF, 0xD9]))

    def test_frame_header_gives_dimensions_and_three_components(self):
        segments = dict(jpeg_segments(test_image.build_jpeg()))
        precision, height, width, components = struct.unpack(">BHHB", segments[0xC0][:6])
        self.assertEqual((precision, height, width, components), (8, test_image.JPEG_HEIGHT, test_image.JPEG_WIDTH, 3))

    def test_declares_quantization_and_huffman_tables_before_the_scan(self):
        markers = [marker for marker, _ in jpeg_segments(test_image.build_jpeg())]
        self.assertEqual(markers.count(0xDB), 2)
        self.assertEqual(markers.count(0xC4), 4)
        self.assertLess(markers.index(0xC4), markers.index(0xDA))

    def test_entropy_data_has_no_unescaped_marker_byte(self):
        data = test_image.build_jpeg()
        start = data.index(bytes([0xFF, 0xDA]))
        header_length = struct.unpack(">H", data[start + 2 : start + 4])[0]
        scan = data[start + 2 + header_length : -2]
        for index in range(len(scan) - 1):
            if scan[index] == 0xFF:
                self.assertEqual(scan[index + 1], 0x00)

    def test_deterministic(self):
        self.assertEqual(test_image.build_jpeg(), test_image.build_jpeg())


class SourceTest(unittest.TestCase):
    def test_header_declares_the_symbol_and_the_length(self):
        text = test_image.header_text(b"abc", "test_image.png")
        self.assertIn('#include "rive/span.hpp"', text)
        self.assertIn("test_image_png_len = 3;", text)
        self.assertIn("extern unsigned char test_image_png_data[test_image_png_len];", text)
        self.assertIn("inline static rive::Span<uint8_t> test_image_png()", text)

    def test_source_lists_every_byte(self):
        data = bytes(range(30))
        text = test_image.source_text(data, "test_image.png")
        self.assertIn('#include "test_image.png.hpp"', text)
        listed = [int(token, 16) for token in re.findall(r"0x([0-9a-f]{2})", text)]
        self.assertEqual(bytes(listed), data)


class CommittedFilesTest(unittest.TestCase):
    def test_committed_jpeg_is_what_the_script_generates(self):
        self.assertEqual((ASSETS / "test_image.jpg").read_bytes(), test_image.build_jpeg())

    def test_committed_png_has_the_pixels_the_script_generates(self):
        committed = (ASSETS / "test_image.png").read_bytes()
        self.assertEqual(decode(committed), decode(test_image.build()))

    def test_committed_sources_match_the_committed_png(self):
        data = (ASSETS / "test_image.png").read_bytes()
        self.assertEqual(
            (ASSETS / "test_image.png.hpp").read_text(), test_image.header_text(data, "test_image.png")
        )
        self.assertEqual(
            (ASSETS / "test_image.png.cpp").read_text(), test_image.source_text(data, "test_image.png")
        )

    def test_command_line_writes_consistent_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, "-I", str(SCRIPT), "-o", tmp], check=True)
            self.assertEqual((Path(tmp) / "test_image.jpg").read_bytes(), test_image.build_jpeg())
            written = (Path(tmp) / "test_image.png").read_bytes()
            self.assertEqual(decode(written), decode((ASSETS / "test_image.png").read_bytes()))
            self.assertEqual(
                (Path(tmp) / "test_image.png.hpp").read_text(),
                test_image.header_text(written, "test_image.png"),
            )
            self.assertEqual(
                (Path(tmp) / "test_image.png.cpp").read_text(),
                test_image.source_text(written, "test_image.png"),
            )


if __name__ == "__main__":
    unittest.main()
