import argparse
import hashlib
import re
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import neutral_images

REPO_ROOT = neutral_images.REPO_ROOT
FONT_TAGS = (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf", b"wOFF")
COPYRIGHT = 0
FAMILY = 1
LICENSE = 13
LICENSE_URL = 14
FREE_LICENCE = re.compile(r"open font licen|\bOFL\b|openfontlicense|apache licen", re.IGNORECASE)
PROPRIETARY = re.compile(
    r"monotype|linotype|fontsmith|adobe systems|all rights reserved|property of|hoefler|gotham",
    re.IGNORECASE,
)
UNVERIFIED_FAMILIES = {"Mochiy Pop One", "Do Hyeon", "Oxanium ExtraLight", "Inter"}


def is_font(payload):
    return payload[:4] in FONT_TAGS


def face_names(font, offset):
    count = struct.unpack(">H", font[offset + 4 : offset + 6])[0]
    table = None
    for index in range(count):
        tag, _, start, length = struct.unpack(">4sIII", font[offset + 12 + 16 * index : offset + 28 + 16 * index])
        if tag == b"name":
            table = font[start : start + length]
    if table is None or len(table) < 6:
        return {}
    _, records, strings = struct.unpack(">HHH", table[:6])
    names = {}
    for index in range(records):
        platform, _, language, name_id, length, start = struct.unpack(">HHHHHH", table[6 + 12 * index : 18 + 12 * index])
        raw = table[strings + start : strings + start + length]
        try:
            text = raw.decode("utf-16-be") if platform in (0, 3) else raw.decode("latin-1")
        except UnicodeDecodeError:
            continue
        if name_id not in names or (platform == 3 and language == 0x409):
            names[name_id] = text
    return names


def font_names(font):
    if font[:4] == b"ttcf":
        count = struct.unpack(">I", font[8:12])[0]
        return [face_names(font, struct.unpack(">I", font[12 + 4 * index : 16 + 4 * index])[0]) for index in range(count)]
    return [face_names(font, 0)]


def classify(names):
    licence = " ".join(names.get(key, "") for key in (LICENSE, LICENSE_URL))
    if FREE_LICENCE.search(licence):
        return "free"
    everything = " ".join(names.get(key, "") for key in (COPYRIGHT, 7, 8, LICENSE, LICENSE_URL))
    if PROPRIETARY.search(everything):
        return "proprietary"
    return "unspecified"


def embedded_fonts(data):
    found = []
    for _, _, payload in neutral_images.asset_payloads(data):
        if is_font(payload):
            names = font_names(payload)[0]
            found.append((names.get(FAMILY, ""), names))
    return found


def riv_files():
    return neutral_images.riv_files()


def font_files():
    listing = subprocess.run(
        ["git", "ls-files", "runtime", "web"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    return sorted(
        REPO_ROOT / name
        for name in listing
        if name.lower().endswith((".ttf", ".otf", ".ttc")) and "node_modules" not in name
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="List the fonts embedded in .riv files and their licences.")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    seen = {}
    for path in riv_files():
        for payload in (item[2] for item in neutral_images.asset_payloads(path.read_bytes())):
            if not is_font(payload):
                continue
            digest = hashlib.sha256(payload).hexdigest()
            names = font_names(payload)[0]
            entry = seen.setdefault(digest, {"names": names, "files": []})
            entry["files"].append(path.name)
    print(f"{len(seen)} embedded fonts")
    for digest, entry in seen.items():
        names = entry["names"]
        copyright_line = names.get(COPYRIGHT, "").replace("\n", " ").replace("\r", " ")
        print(f"{digest[:12]} {classify(names)} {names.get(FAMILY, '')} | {copyright_line[:100]} | {', '.join(sorted(set(entry['files'])))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
