import re
import unittest
from pathlib import Path

LOADING_DIR = Path(__file__).resolve().parents[1] / "loading"


class ZeroSizePageTest(unittest.TestCase):
    def setUp(self):
        self.page = (LOADING_DIR / "zero-size.html").read_text(encoding="utf-8")

    def test_the_page_reopens_on_the_same_canvas_and_resizes_in_on_load(self):
        self.assertIn("first.cleanup()", self.page)
        self.assertIn("second.resizeDrawingSurfaceToCanvas()", self.page)

    def test_the_canvas_is_hidden_unless_asked_otherwise(self):
        self.assertRegex(self.page, r'canvas\.style\.display = "none"')
        self.assertIn('"visible"', self.page)

    def test_the_page_publishes_the_outcome_for_the_scripted_check(self):
        self.assertIn("twnoCheck.resize", self.page)

    def test_the_index_links_the_page(self):
        index = (LOADING_DIR / "index.html").read_text(encoding="utf-8")
        self.assertTrue(re.search(r'href="zero-size\.html\?', index))


if __name__ == "__main__":
    unittest.main()
