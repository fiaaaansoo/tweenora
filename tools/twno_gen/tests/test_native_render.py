import sys
import tempfile
import unittest
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GEN_DIR))

import render_check
from twno_writer import Document, Obj

ORANGE = (255, 128, 0, 255)
WHITE = (255, 255, 255, 255)


def minimal_document(table="used"):
    doc = Document(table=table)
    doc.add(Obj("Backboard"))
    artboard = doc.add(Obj("Artboard", name="A", width=100.0, height=100.0))
    shape = doc.add(Obj("Shape", parent=artboard, x=50.0, y=50.0))
    doc.add(Obj("Rectangle", parent=shape, width=40.0, height=40.0))
    fill = doc.add(Obj("Fill", parent=shape))
    doc.add(Obj("SolidColor", parent=fill, colorValue=0xFFFF8000))
    return doc


def pixel(image, x, y):
    return tuple(int(v) for v in image[y, x])


class NativeRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            render_check.find_goldens()
            render_check.require_imaging()
        except render_check.RenderUnavailable as error:
            raise unittest.SkipTest(str(error)) from None

    def render(self, doc, name, suffix=".riv"):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / (name + suffix)
            doc.write(path)
            return render_check.render(path)

    def test_shape_has_the_written_color(self):
        image = self.render(minimal_document(), "minimal")
        self.assertEqual(image.shape[:2], (render_check.FRAME_SIZE, render_check.FRAME_SIZE))
        def at(x, y):
            return pixel(image, *render_check.artboard_to_frame(x, y, 100, 100))

        self.assertEqual(at(50, 50), ORANGE)
        for inside, outside in (((31, 50), (29, 50)), ((69, 50), (71, 50)), ((50, 31), (50, 29)), ((50, 69), (50, 71))):
            self.assertEqual(at(*inside), ORANGE, inside)
            self.assertEqual(at(*outside), WHITE, outside)
        self.assertEqual(at(90, 90), WHITE)

    def test_twno_and_riv_render_identically(self):
        riv = self.render(minimal_document(), "minimal", ".riv")
        twno = self.render(minimal_document(), "minimal", ".twno")
        self.assertTrue((riv == twno).all())

    def test_complete_and_minimal_tables_both_load(self):
        complete = self.render(minimal_document("used"), "complete")
        minimal = self.render(minimal_document("minimal"), "minimal")
        self.assertTrue((complete == minimal).all())
        centre = render_check.artboard_to_frame(50, 50, 100, 100)
        self.assertEqual(pixel(minimal, *centre), ORANGE)


if __name__ == "__main__":
    unittest.main()
