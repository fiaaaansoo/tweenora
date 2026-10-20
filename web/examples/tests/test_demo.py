import json
import re
import sys
import unittest
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parents[1]
DEMO_DIR = EXAMPLES_DIR.parent / "demo"
sys.path.insert(0, str(EXAMPLES_DIR))

import prepare_assets


def prepared_names():
    names = set()
    for _, files in prepare_assets.ASSET_SOURCES:
        for name in files:
            if name.endswith(".riv"):
                names.add(name)
                names.add(name[:-4] + ".twno")
            else:
                names.add(name)
    return names


class DemoTest(unittest.TestCase):
    def setUp(self):
        self.examples = json.loads((DEMO_DIR / "examples.json").read_text(encoding="utf-8"))

    def test_example_ids_are_unique_and_url_safe(self):
        ids = [item["id"] for item in self.examples]
        self.assertEqual(len(ids), len(set(ids)))
        for identifier in ids:
            self.assertRegex(identifier, r"^[\w-]+$")

    def test_every_example_is_prepared_by_prepare_assets(self):
        names = prepared_names()
        for item in self.examples:
            prefix, name = item["file"].rsplit("/", 1)
            self.assertEqual(prefix, "/assets")
            self.assertIn(name, names, item["id"])

    def test_every_example_has_a_title_and_a_description(self):
        for item in self.examples:
            self.assertTrue(item["title"].strip(), item["id"])
            self.assertTrue(item["description"].strip(), item["id"])

    def test_the_demo_names_no_third_party_host(self):
        for path in DEMO_DIR.iterdir():
            if path.suffix in (".html", ".js", ".css", ".json"):
                text = path.read_text(encoding="utf-8")
                hosts = re.findall(r"https?://[^/\"' )]+", text)
                self.assertEqual([h for h in hosts if h != "https://tweenora-demo.pages.dev"], [], path.name)

    def test_the_demo_loads_the_package_from_the_served_domain(self):
        html = (DEMO_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('src="/pkg/rive.js"', html)

    def test_the_demo_has_one_h1_and_a_language(self):
        html = (DEMO_DIR / "index.html").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"<h1[ >]", html)), 1)
        self.assertIn('<html lang="en">', html)


if __name__ == "__main__":
    unittest.main()
