import json
import sys
import unittest
from collections import Counter
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PARITY_DIR.parent
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(PARITY_DIR))
sys.path.insert(0, str(TOOLS_DIR))

import manifest

COMMITTED = PARITY_DIR / "manifest.json"
EXPECTED_TOTAL = 475
EXPECTED_BY_GROUP = {"unit_tests_root": 380, "unit_tests_sub": 75, "web_scripting": 20}


class CollectTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paths = manifest.collect_files(REPO_ROOT)

    def test_exactly_475_files(self):
        self.assertEqual(len(self.paths), EXPECTED_TOTAL)

    def test_no_duplicates(self):
        self.assertEqual(len(set(self.paths)), len(self.paths))

    def test_every_path_exists_and_is_relative_posix(self):
        for rel in self.paths:
            self.assertNotIn("\\", rel)
            self.assertFalse(Path(rel).is_absolute(), rel)
            self.assertTrue((REPO_ROOT / rel).is_file(), rel)

    def test_sorted(self):
        self.assertEqual(self.paths, sorted(self.paths))

    def test_group_counts(self):
        counts = Counter(manifest.group_of(rel) for rel in self.paths)
        self.assertEqual(dict(counts), EXPECTED_BY_GROUP)

    def test_only_riv_files(self):
        self.assertTrue(all(rel.endswith(".riv") for rel in self.paths))


class GroupTest(unittest.TestCase):
    def test_groups(self):
        self.assertEqual(
            manifest.group_of("runtime/tests/unit_tests/assets/a.riv"), "unit_tests_root"
        )
        self.assertEqual(
            manifest.group_of("runtime/tests/unit_tests/assets/sub/dir/a.riv"), "unit_tests_sub"
        )
        self.assertEqual(
            manifest.group_of("runtime/tests/web_scripting/fixture/a.riv"), "web_scripting"
        )

    def test_unknown_location_is_rejected(self):
        with self.assertRaises(ValueError):
            manifest.group_of("elsewhere/a.riv")


class FeaturesTest(unittest.TestCase):
    def test_empty_document_has_no_features(self):
        self.assertEqual(manifest.features_of([]), [])

    def test_detects_known_features_sorted(self):
        names = ["Artboard", "Shape", "StateMachine", "Text", "ImageAsset", "ScriptAsset"]
        self.assertEqual(
            manifest.features_of(names),
            ["image", "scripting", "state_machine", "text", "vector"],
        )

    def test_detects_data_binding_layout_mesh(self):
        self.assertEqual(
            manifest.features_of(["ViewModel", "LayoutComponent", "Mesh"]),
            ["data_binding", "layout", "mesh"],
        )

    def test_unknown_names_are_ignored(self):
        self.assertEqual(manifest.features_of(["Artboard", "unknown(99999)"]), [])


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.built = manifest.build_manifest(REPO_ROOT)

    def test_shape(self):
        self.assertEqual(self.built["count"], EXPECTED_TOTAL)
        self.assertEqual(len(self.built["files"]), EXPECTED_TOTAL)
        self.assertEqual(self.built["groups"], EXPECTED_BY_GROUP)

    def test_entry_fields(self):
        for entry in self.built["files"]:
            self.assertEqual(
                set(entry),
                {
                    "path",
                    "group",
                    "size",
                    "sha256",
                    "artboards",
                    "state_machines",
                    "features",
                    "parse_error",
                },
                entry["path"],
            )
            self.assertEqual(len(entry["sha256"]), 64)

    def test_render_is_stable(self):
        first = manifest.render(self.built)
        second = manifest.render(manifest.build_manifest(REPO_ROOT))
        self.assertEqual(first, second)
        self.assertTrue(first.endswith("\n"))
        self.assertNotIn("\r", first)

    def test_some_file_has_a_state_machine_and_several_artboards(self):
        self.assertTrue(any(e["state_machines"] for e in self.built["files"]))
        self.assertTrue(any(len(e["artboards"]) > 1 for e in self.built["files"]))

    def test_committed_manifest_matches_regeneration(self):
        self.assertTrue(COMMITTED.is_file(), "manifest.json absent: lancer manifest.py")
        self.assertEqual(COMMITTED.read_text(encoding="utf-8"), manifest.render(self.built))

    def test_committed_manifest_is_valid_json_with_475_entries(self):
        data = json.loads(COMMITTED.read_text(encoding="utf-8"))
        self.assertEqual(data["count"], EXPECTED_TOTAL)


if __name__ == "__main__":
    unittest.main()
