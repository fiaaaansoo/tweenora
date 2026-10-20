import struct
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

import embedded_fonts

SCRIPT = TOOLS_DIR / "embedded_fonts.py"
ASSETS = REPO_ROOT / "runtime" / "tests" / "unit_tests" / "assets"


def font_with_names(records):
    strings = b""
    entries = b""
    for name_id, text in records:
        raw = text.encode("utf-16-be")
        entries += struct.pack(">HHHHHH", 3, 1, 0x409, name_id, len(raw), len(strings))
        strings += raw
    table = struct.pack(">HHH", 0, len(records), 6 + 12 * len(records)) + entries + strings
    header = struct.pack(">IHHHH", 0x00010000, 1, 16, 0, 0)
    directory = struct.pack(">4sIII", b"name", 0, 12 + 16, len(table))
    return header + directory + table


class NameTableTest(unittest.TestCase):
    def test_reads_the_name_records(self):
        names = embedded_fonts.font_names(font_with_names([(0, "Copyright 1 A"), (1, "Fam"), (13, "Licence X")]))
        self.assertEqual(names[0][1], "Fam")
        self.assertEqual(names[0][0], "Copyright 1 A")

    def test_reads_every_face_of_a_collection(self):
        data = (ASSETS / "fonts" / "two_faces.ttc").read_bytes()
        families = [face.get(1) for face in embedded_fonts.font_names(data)]
        self.assertEqual(families, ["Inter 24pt", "Inter 18pt ExtraLight"])

    def test_rejects_non_fonts(self):
        self.assertFalse(embedded_fonts.is_font(b"\x89PNG\r\n\x1a\n"))
        self.assertTrue(embedded_fonts.is_font(font_with_names([(1, "F")])))


class ClassificationTest(unittest.TestCase):
    def test_open_licences_are_free(self):
        self.assertEqual(embedded_fonts.classify({0: "Copyright 2016 The X Authors", 13: "This Font Software is licensed under the SIL Open Font License, Version 1.1."}), "free")
        self.assertEqual(embedded_fonts.classify({0: "Copyright (c) 2010 Z. All rights reserved.", 13: "Licensed under the Apache License, Version 2.0"}), "free")

    def test_commercial_owner_is_proprietary(self):
        self.assertEqual(
            embedded_fonts.classify({0: "Copyright 2008-2025 Monotype GmbH. All rights reserved.", 13: "This font software is the property of Monotype GmbH"}),
            "proprietary",
        )

    def test_all_rights_reserved_without_licence_is_proprietary(self):
        self.assertEqual(embedded_fonts.classify({0: "Copyright 2010 Someone. All rights reserved."}), "proprietary")

    def test_no_licence_field_is_unverified(self):
        self.assertEqual(embedded_fonts.classify({0: "Copyright 2016 The Inter Project Authors"}), "unspecified")


class CorpusTest(unittest.TestCase):
    def test_no_proprietary_font_is_embedded_in_a_riv(self):
        found = []
        for path in embedded_fonts.riv_files():
            for family, names in embedded_fonts.embedded_fonts(path.read_bytes()):
                if embedded_fonts.classify(names) == "proprietary":
                    found.append((path.name, family))
        self.assertEqual(found, [])

    def test_no_proprietary_font_file_is_tracked(self):
        found = []
        for path in embedded_fonts.font_files():
            for names in embedded_fonts.font_names(path.read_bytes()):
                if embedded_fonts.classify(names) == "proprietary":
                    found.append(path.name)
        self.assertEqual(found, [])

    def test_unverified_fonts_are_the_known_ones(self):
        unverified = set()
        for path in embedded_fonts.riv_files():
            for family, names in embedded_fonts.embedded_fonts(path.read_bytes()):
                if embedded_fonts.classify(names) == "unspecified":
                    unverified.add(family)
        self.assertEqual(unverified, embedded_fonts.UNVERIFIED_FAMILIES)


class CommandLineTest(unittest.TestCase):
    def test_list_option_runs(self):
        completed = subprocess.run(
            [sys.executable, "-I", str(SCRIPT), "--list"], capture_output=True, text=True, encoding="utf-8", check=True
        )
        self.assertIn("embedded fonts", completed.stdout)


if __name__ == "__main__":
    unittest.main()
