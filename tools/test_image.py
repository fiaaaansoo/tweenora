import argparse
import math
import struct
import sys
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = REPO_ROOT / "runtime" / "tests" / "unit_tests" / "assets"
NAME = "test_image.png"
WIDTH = 442
HEIGHT = 412
CENTER_X = WIDTH // 2
CENTER_Y = HEIGHT // 2
RADIUS = 190
HALO = 30
CELL = 22
SIGNATURE = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
JPEG_NAME = "test_image.jpg"
JPEG_WIDTH = 350
JPEG_HEIGHT = 200
JPEG_QUANTIZERS = (10, 14)


def pixel(x, y):
    dx = x - CENTER_X
    dy = y - CENTER_Y
    distance = math.isqrt(16 * (dx * dx + dy * dy))
    inner = RADIUS * 4
    outer = (RADIUS + HALO) * 4
    if distance >= outer:
        return 0, 0, 0, 0
    if distance > inner:
        alpha = 96 * (outer - distance) // (outer - inner)
        return 40, 70, 120, alpha
    red = (x * 32 // WIDTH) * 8
    green = (y * 32 // HEIGHT) * 8
    blue = 255 - (red + green) // 2
    if (x // CELL + y // CELL) % 2 == 0:
        red, green, blue = red * 3 // 4, green * 3 // 4, blue * 3 // 4
    alpha = 255 if distance < inner - 4 else 255 * (inner - distance) // 4
    return red, green, blue, alpha


def chunk(kind, body):
    checksum = zlib.crc32(kind + body) & 0xFFFFFFFF
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", checksum)


def build():
    rows = bytearray()
    for y in range(HEIGHT):
        rows.append(0)
        for x in range(WIDTH):
            rows.extend(pixel(x, y))
    header = struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 6, 0, 0, 0)
    return (
        SIGNATURE
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + chunk(b"IEND", b"")
    )


def sized_pixel(x, y, width, height):
    red = 255 * x // max(width - 1, 1)
    green = 255 * y // max(height - 1, 1)
    blue = 255 - (red + green) // 2
    cell = max(1, min(width, height) // 8)
    if (x // cell + y // cell) % 2 == 0:
        return red * 3 // 4, green * 3 // 4, blue * 3 // 4, 255
    return red, green, blue, 255


def build_png(width, height):
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            rows.extend(sized_pixel(x, y, width, height))
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        SIGNATURE
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + chunk(b"IEND", b"")
    )


def jpeg_pixel(x, y, width=JPEG_WIDTH, height=JPEG_HEIGHT):
    dx = x - width // 2
    dy = y - height // 2
    distance = math.isqrt(dx * dx + dy * dy)
    side = min(width, height)
    red = 255 * x // max(width - 1, 1)
    green = 255 * y // max(height - 1, 1)
    blue = 255 - (red + green) // 2
    if side * 25 // 100 < distance < side * 35 // 100:
        return 250, 250, 250
    cell = max(2, side // 8)
    if (x // cell + y // cell) % 2 == 0:
        return red * 4 // 5, green * 4 // 5, blue * 4 // 5
    return red, green, blue


def zigzag():
    order = []
    for total in range(15):
        cells = [(row, total - row) for row in range(8) if 0 <= total - row < 8]
        if total % 2 == 0:
            cells.reverse()
        order.extend(row * 8 + column for row, column in cells)
    return order


DCT = [
    [(math.sqrt(1 / 8) if u == 0 else math.sqrt(2 / 8)) * math.cos((2 * n + 1) * u * math.pi / 16) for n in range(8)]
    for u in range(8)
]


def planes(image_width, image_height):
    width = (image_width + 7) // 8 * 8
    height = (image_height + 7) // 8 * 8
    result = ([], [], [])
    for y in range(height):
        rows = ([], [], [])
        for x in range(width):
            red, green, blue = jpeg_pixel(min(x, image_width - 1), min(y, image_height - 1), image_width, image_height)
            rows[0].append((299 * red + 587 * green + 114 * blue) // 1000)
            rows[1].append(128 + (-169 * red - 331 * green + 500 * blue) // 1000)
            rows[2].append(128 + (500 * red - 419 * green - 81 * blue) // 1000)
        for index in range(3):
            result[index].append(rows[index])
    return result, width, height


def quantized_block(plane, left, top, quantizer):
    shifted = [[plane[top + row][left + column] - 128 for column in range(8)] for row in range(8)]
    rows = [[sum(DCT[u][n] * shifted[row][n] for n in range(8)) for u in range(8)] for row in range(8)]
    out = []
    for v in range(8):
        for u in range(8):
            value = sum(DCT[v][n] * rows[n][u] for n in range(8))
            out.append(int(round(value / quantizer)))
    return out


def category(value):
    return abs(value).bit_length()


class BitWriter:
    def __init__(self):
        self.data = bytearray()
        self.accumulator = 0
        self.count = 0

    def write(self, value, length):
        self.accumulator = (self.accumulator << length) | (value & ((1 << length) - 1))
        self.count += length
        while self.count >= 8:
            self.count -= 8
            byte = (self.accumulator >> self.count) & 0xFF
            self.data.append(byte)
            if byte == 0xFF:
                self.data.append(0)
        self.accumulator &= (1 << self.count) - 1

    def finish(self):
        if self.count:
            self.write((1 << (8 - self.count)) - 1, 8 - self.count)
        return bytes(self.data)


DC_SYMBOLS = list(range(12))
AC_SYMBOLS = [0x00, 0xF0] + [(run << 4) | size for run in range(16) for size in range(1, 11)]
AC_SYMBOLS.sort()


def huffman_codes(symbols, length):
    return {symbol: (index, length) for index, symbol in enumerate(symbols)}


DC_CODES = huffman_codes(DC_SYMBOLS, 4)
AC_CODES = huffman_codes(AC_SYMBOLS, 8)


def put_amplitude(writer, value, size):
    writer.write(value if value > 0 else value + (1 << size) - 1, size)


def encode_block(writer, block, previous, order):
    difference = block[0] - previous
    size = category(difference)
    writer.write(*DC_CODES[size])
    if size:
        put_amplitude(writer, difference, size)
    run = 0
    last = max((i for i in range(1, 64) if block[order[i]] != 0), default=0)
    for index in range(1, last + 1):
        value = block[order[index]]
        if value == 0:
            run += 1
            continue
        while run > 15:
            writer.write(*AC_CODES[0xF0])
            run -= 16
        size = category(value)
        writer.write(*AC_CODES[(run << 4) | size])
        put_amplitude(writer, value, size)
        run = 0
    if last < 63:
        writer.write(*AC_CODES[0x00])
    return block[0]


def segment(marker, body):
    return bytes([0xFF, marker]) + struct.pack(">H", len(body) + 2) + body


def huffman_table(table_class, identifier, symbols, length):
    counts = [0] * 16
    counts[length - 1] = len(symbols)
    return segment(0xC4, bytes([(table_class << 4) | identifier]) + bytes(counts) + bytes(symbols))


def build_jpeg(image_width=JPEG_WIDTH, image_height=JPEG_HEIGHT):
    order = zigzag()
    (luma, blue, red), width, height = planes(image_width, image_height)
    writer = BitWriter()
    previous = [0, 0, 0]
    for top in range(0, height, 8):
        for left in range(0, width, 8):
            for index, plane in enumerate((luma, blue, red)):
                block = quantized_block(plane, left, top, JPEG_QUANTIZERS[0 if index == 0 else 1])
                previous[index] = encode_block(writer, block, previous[index], order)
    scan = writer.finish()
    out = bytearray(bytes([0xFF, 0xD8]))
    out += segment(0xE0, b"JFIF\x00" + bytes([1, 1, 0]) + struct.pack(">HH", 1, 1) + bytes([0, 0]))
    for identifier, quantizer in enumerate(JPEG_QUANTIZERS):
        out += segment(0xDB, bytes([identifier]) + bytes([quantizer] * 64))
    out += segment(0xC0, struct.pack(">BHHB", 8, image_height, image_width, 3) + b"".join(bytes([i + 1, 0x11, 0 if i == 0 else 1]) for i in range(3)))
    for identifier in (0, 1):
        out += huffman_table(0, identifier, DC_SYMBOLS, 4)
        out += huffman_table(1, identifier, AC_SYMBOLS, 8)
    out += segment(0xDA, bytes([3]) + b"".join(bytes([i + 1, 0x00 if i == 0 else 0x11]) for i in range(3)) + bytes([0, 63, 0]))
    out += scan
    out += bytes([0xFF, 0xD9])
    return bytes(out)


def symbol(name):
    return name.replace(".", "_").replace("-", "_")


def header_text(data, name):
    sym = symbol(name)
    return (
        '#include "rive/span.hpp"\n'
        "\n"
        "namespace assets\n"
        "{\n"
        f"constexpr static unsigned int {sym}_len = {len(data)};\n"
        f"extern unsigned char {sym}_data[{sym}_len];\n"
        f"inline static rive::Span<uint8_t> {sym}()\n"
        "{\n"
        f"    return {{{sym}_data, {sym}_len}};\n"
        "}\n"
        "}; // namespace assets\n"
    )


def source_text(data, name):
    sym = symbol(name)
    lines = []
    for start in range(0, len(data), 12):
        lines.append("    " + ", ".join(f"0x{b:02x}" for b in data[start : start + 12]))
    body = ",\n".join(lines)
    return (
        f'#include "{name}.hpp"\n'
        "\n"
        "namespace assets\n"
        "{\n"
        f"unsigned char {sym}_data[] = {{\n"
        f"{body}}};\n"
        "}\n"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Write the neutral test image and its C++ source files."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    data = build()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / NAME).write_bytes(data)
    (args.output / JPEG_NAME).write_bytes(build_jpeg())
    with open(args.output / f"{NAME}.hpp", "w", newline="\n", encoding="utf-8") as f:
        f.write(header_text(data, NAME))
    with open(args.output / f"{NAME}.cpp", "w", newline="\n", encoding="utf-8") as f:
        f.write(source_text(data, NAME))
    print(f"{args.output / NAME}: {len(data)} bytes, {WIDTH}x{HEIGHT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
