import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parents[1]
ORIGINAL_DIR = EXAMPLES_DIR.parents[1] / "docs" / "examples"
DEMO_DIR = EXAMPLES_DIR.parent / "demo"
sys.path.insert(0, str(EXAMPLES_DIR))

import prepare_assets


def provenance_rows():
    rows = {}
    text = (EXAMPLES_DIR / "ASSETS_PROVENANCE.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        match = re.match(r"^\| `([^`]+)` \|", line)
        if match:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            rows[match.group(1)] = cells
    return rows


class ProvenanceTest(unittest.TestCase):
    def setUp(self):
        self.rows = provenance_rows()
        self.examples = json.loads((DEMO_DIR / "examples.json").read_text(encoding="utf-8"))

    def test_every_prepared_file_has_a_provenance_row(self):
        for _, names in prepare_assets.ASSET_SOURCES:
            for name in names:
                self.assertIn(name, self.rows, name)

    def test_every_row_says_whether_the_file_is_publishable(self):
        for name, cells in self.rows.items():
            self.assertRegex(cells[5], r"^(yes|no|to verify)", name)

    def test_every_example_declares_whether_it_is_publishable(self):
        for item in self.examples:
            self.assertIsInstance(item.get("publishable"), bool, item["id"])

    def test_a_publishable_example_uses_only_publishable_files(self):
        for item in self.examples:
            if not item["publishable"]:
                continue
            stem = item["file"].rsplit("/", 1)[1].rsplit(".", 1)[0]
            self.assertTrue(self.rows[stem + ".riv"][5].startswith("yes"), item["id"])

    def test_a_publishable_file_names_its_proof(self):
        for name, cells in self.rows.items():
            if cells[5].startswith("yes"):
                self.assertTrue(cells[4], name)
                self.assertNotIn("No license", cells[4], name)

    def test_every_provenance_row_matches_a_prepared_file(self):
        prepared = {name for _, names in prepare_assets.ASSET_SOURCES for name in names}
        self.assertEqual(set(self.rows), prepared)


class OriginalExamplesProvenanceTest(unittest.TestCase):
    def setUp(self):
        self.rows = provenance_rows()
        self.examples = json.loads((DEMO_DIR / "examples.json").read_text(encoding="utf-8"))
        self.originals = sorted(ORIGINAL_DIR.glob("*.riv"))

    def entries(self, path):
        stem = path.stem
        return [item for item in self.examples if item["file"] == f"/assets/{stem}.twno"]

    def test_there_are_original_examples(self):
        self.assertTrue(self.originals)

    def test_each_original_example_has_a_yes_row_with_author_licence_proof_and_digest(self):
        for path in self.originals:
            cells = self.rows[path.name]
            self.assertEqual(cells[5], "yes", path.name)
            self.assertTrue(cells[2].startswith("Tweenora"), path.name)
            self.assertIn("MIT", cells[3], path.name)
            self.assertIn("docs/examples/LICENSE", cells[3], path.name)
            self.assertIn("tools/twno_gen", cells[4], path.name)
            self.assertIn("regeneration", cells[4], path.name)
            self.assertNotIn("No license", cells[4], path.name)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
            self.assertEqual(cells[6], f"`{digest}`", path.name)

    def test_each_original_example_is_listed_once_as_publishable(self):
        for path in self.originals:
            entries = self.entries(path)
            self.assertEqual(len(entries), 1, path.name)
            self.assertIs(entries[0]["publishable"], True, path.name)
            self.assertTrue(entries[0]["title"] and entries[0]["description"], path.name)

    def test_the_original_examples_come_first_in_the_list(self):
        leading = [item["file"] for item in self.examples[: len(self.originals)]]
        self.assertEqual(sorted(leading), sorted(f"/assets/{path.stem}.twno" for path in self.originals))

    def test_every_entry_outside_the_original_examples_stays_unpublishable(self):
        originals = {f"/assets/{path.stem}.twno" for path in self.originals}
        for item in self.examples:
            if item["file"] not in originals:
                self.assertIs(item["publishable"], False, item["id"])

    def test_only_the_original_examples_and_open_fonts_are_marked_yes(self):
        originals = {path.name for path in self.originals}
        for name, cells in self.rows.items():
            if cells[5].startswith("yes") and name not in originals:
                self.assertEqual(Path(name).suffix, ".ttf", name)
                self.assertIn("SIL Open Font License", cells[3], name)

    def test_the_licence_named_in_the_rows_exists_and_names_the_holder(self):
        text = (ORIGINAL_DIR / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License", text)
        self.assertIn("fiaaaansoo", text)
        for path in self.originals:
            self.assertIn("fiaaaansoo", self.rows[path.name][3], path.name)


if __name__ == "__main__":
    unittest.main()
