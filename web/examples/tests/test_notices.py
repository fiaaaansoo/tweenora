import json
import re
import unittest
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[3]
PACKAGE_DIR = REPO_DIR / "web" / "rive-wasm" / "js" / "npm" / "webgl2"
DEMO_DIR = REPO_DIR / "web" / "demo"

LINKED_LIBRARIES = [
    "HarfBuzz",
    "SheenBidi",
    "miniaudio",
    "Yoga",
    "Luau",
    "libhydrogen",
    "Emscripten",
    "musl",
    "libc++",
    "Skia",
]


class NoticesTest(unittest.TestCase):
    def setUp(self):
        self.package = json.loads((PACKAGE_DIR / "package.json").read_text(encoding="utf-8"))

    def test_the_package_ships_its_licence_and_the_third_party_notices(self):
        files = self.package["files"]
        self.assertIn("LICENSE", files)
        self.assertIn("THIRD_PARTY_NOTICES", files)
        self.assertTrue((PACKAGE_DIR / "THIRD_PARTY_NOTICES").is_file())

    def test_the_notices_cover_every_linked_library_and_the_upstream_copyright(self):
        text = (PACKAGE_DIR / "THIRD_PARTY_NOTICES").read_text(encoding="utf-8")
        for name in LINKED_LIBRARIES:
            self.assertIn(name, text, name)
        self.assertIn("Copyright (c) 2020 Rive", text)

    def test_the_notices_name_no_library_the_package_does_not_link(self):
        text = (PACKAGE_DIR / "THIRD_PARTY_NOTICES").read_text(encoding="utf-8")
        for name in ("libpng", "libjpeg", "libwebp"):
            self.assertNotRegex(text, re.compile(name, re.IGNORECASE), name)

    def test_the_demo_footer_credits_rive_and_links_to_the_notices(self):
        html = (DEMO_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn("Derived from an MIT-licensed upstream runtime; independent project, not affiliated with or endorsed by its authors", html)
        self.assertRegex(html, r'href="/pkg/THIRD_PARTY_NOTICES"')


if __name__ == "__main__":
    unittest.main()
