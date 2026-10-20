import argparse
import hashlib
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_image
import twnoinfo

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME = REPO_ROOT / "runtime"
WEB = REPO_ROOT / "web"
FILE_ASSET_CONTENTS = "FileAssetContents"
BYTES_KEY = 212

THIRD_PARTY_SHA256 = {
    "62dfbbf3a728871e55d3c33a7a46489f16d6171390ad11c9bed21784c2ab58ae": "illustration crediting its author (zombie)",
    "02cba86f8b11b6fdc5dc76ca677c8f4f20fb10ba5f2073acfd155466d606b31c": "third-party logo (Flash icon)",
    "40ef178b46b5a8518db3bebaf2f8d6fa8f9f46655ebada82cfcd57d87a17c201": "third-party logo (Flash icon)",
    "ac24a63751cf4b1be1ad23536cc54e053de3d74479dae84ea37c21b995253fdf": "third-party logo (Rive R logo)",
    "041d845c1b466bb7b9e4a1a70ff18db7ccdddc8ff1284defd796906e5b88caab": "photo of a franchise character figurine",
    "0566f3cc152ef1d44ab20fbd2258733cf41f14d6ba05c835a4e6dde2a9f96232": "photo of a franchise character figurine",
    "335104a01472c6ada9de2827e07cf546c724b89c875be4024bd882c29767c122": "photo of a franchise character figurine",
    "436f6551b96a00b7cf1c6159da951d0e71d5d209461fe6db84b2ae4964056385": "photo of a franchise character figurine",
    "66ae5adbe01702f814e3afd7634a461e93db57311c18f5090b50356819b5d639": "photo of a franchise character figurine",
    "9bee304d51412171c76845326f7dc006bb2940baae62827a5fcee1633c8b8d34": "photo of a franchise character figurine",
    "d207a333be4b0c087158e62c4b804611c0e60315a105f2ac781c19203836a2f6": "photo of a franchise character figurine",
    "e432ee3800c7d609d7d7e8632d614b8efb90c80c22ac4b9b5baff466f09de8e5": "photo of a franchise character figurine",
    "f36b292a3dbec3313b5845a376f9ee8c0852bb37c2b1e62ef8217dde9015fd8a": "photo of a franchise character figurine",
}


def riv_files():
    found = list(RUNTIME.rglob("*.riv"))
    found += [path for path in WEB.rglob("*.riv") if "node_modules" not in path.parts]
    return sorted(found)


def varuint(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def image_size(payload):
    if payload[:8] == test_image.SIGNATURE:
        return "png", struct.unpack(">II", payload[16:24])
    if payload[:2] == bytes([0xFF, 0xD8]):
        position = 2
        while position + 9 < len(payload):
            if payload[position] != 0xFF:
                return None
            marker = payload[position + 1]
            (length,) = struct.unpack(">H", payload[position + 2 : position + 4])
            if marker in (0xC0, 0xC1, 0xC2):
                height, width = struct.unpack(">HH", payload[position + 5 : position + 9])
                return "jpeg", (width, height)
            position += 2 + length
    return None


def asset_payloads(data):
    document = twnoinfo.read_document(data, twnoinfo.load_schema())
    objects = document["objects"]
    found = []
    for index, obj in enumerate(objects):
        if obj["typeName"] != FILE_ASSET_CONTENTS:
            continue
        start = obj["offset"]
        end = objects[index + 1]["offset"] if index + 1 < len(objects) else len(data)
        reader = twnoinfo.Reader(data)
        reader.pos = start
        reader.varuint(31)
        if reader.varuint() != BYTES_KEY:
            continue
        payload = reader.length_prefixed()
        if reader.varuint() != 0 or reader.pos != end:
            continue
        found.append((start, end, payload))
    return found


def in_band_assets(data):
    return [item for item in asset_payloads(data) if image_size(item[2]) is not None]


def neutral_payload(payload):
    kind, (width, height) = image_size(payload)
    if kind == "png":
        return test_image.build_png(width, height)
    return test_image.build_jpeg(width, height)


def replace_images(data, predicate):
    patched = data
    for start, end, payload in reversed(in_band_assets(data)):
        if not predicate(payload):
            continue
        neutral = neutral_payload(payload)
        reader = twnoinfo.Reader(data)
        reader.pos = start
        type_key = reader.varuint(31)
        replacement = varuint(type_key) + varuint(BYTES_KEY) + varuint(len(neutral)) + neutral + varuint(0)
        patched = patched[:start] + replacement + patched[end:]
    return patched


def is_third_party(payload):
    return hashlib.sha256(payload).hexdigest() in THIRD_PARTY_SHA256


def neutralize_file(path):
    path = Path(path)
    original = path.read_bytes()
    count = sum(1 for _, _, payload in in_band_assets(original) if is_third_party(payload))
    if count:
        path.write_bytes(replace_images(original, is_third_party))
    return count


def list_images(paths):
    lines = []
    for path in paths:
        for _, _, payload in in_band_assets(path.read_bytes()):
            kind, (width, height) = image_size(payload)
            digest = hashlib.sha256(payload).hexdigest()
            flag = "tiers" if digest in THIRD_PARTY_SHA256 else "-"
            lines.append(f"{digest[:12]} {kind} {width}x{height} {len(payload)} {flag} {path.name}")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Replace the third-party images embedded in .riv files by neutral generated ones."
    )
    parser.add_argument("files", nargs="*", type=Path)
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    paths = args.files or riv_files()
    if args.list:
        lines = list_images(paths)
        sys.stdout.reconfigure(encoding="utf-8")
        print(f"{len(lines)} embedded images")
        for line in lines:
            print(line)
        return 0
    total = 0
    for path in paths:
        count = neutralize_file(path)
        if count:
            print(f"{path}: {count}")
        total += count
    print(f"{total} images replaced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
