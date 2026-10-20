import tempfile
import unittest
from pathlib import Path

from support import channels, prop, read
from twno_writer import varuint

import render_check
from schema_index import SchemaIndex
from scenes import tinted_shape

FRESH_INSTANCE_COLOR = 0xFF000000


class TintedShapeStructureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = tinted_shape.build().to_bytes(b"RIVE")
        cls.objects = read(cls.data)["objects"]
        cls.kinds = [o["typeName"] for o in cls.objects]
        index = SchemaIndex.default()
        cls.path_key = index.property_key("DataBindContext", "sourcePathIds")
        cls.color_key = index.property_key("SolidColor", "colorValue")

    def of_kind(self, kind):
        return [o for o in self.objects if o["typeName"] == kind]

    def test_view_model_objects_precede_the_artboard_in_order(self):
        order = [
            "Backboard",
            "ViewModel",
            "ViewModelPropertyColor",
            "ViewModelPropertyColor",
            "ViewModelInstance",
            "ViewModelInstanceColor",
            "ViewModelInstanceColor",
            "Artboard",
        ]
        self.assertEqual(self.kinds[: len(order)], order)

    def test_artboard_and_instance_point_at_the_view_model(self):
        self.assertEqual(prop(self.of_kind("Artboard")[0], "viewModelId"), 0)
        self.assertEqual(prop(self.of_kind("ViewModelInstance")[0], "viewModelId"), 0)

    def test_instance_values_name_each_property_by_rank(self):
        values = {
            prop(v, "viewModelPropertyId"): prop(v, "propertyValue") for v in self.of_kind("ViewModelInstanceColor")
        }
        self.assertEqual(values, {0: tinted_shape.ACCENT_COLOR, 1: tinted_shape.DEFAULT_COLOR})

    def bind_path(self, position):
        starts = [o["offset"] for o in self.objects] + [len(self.data)]
        bind = self.of_kind("DataBindContext")[position]
        end = starts[starts.index(bind["offset"]) + 1]
        chunk = self.data[bind["offset"] : end]
        marker = varuint(self.path_key) + bytes([2])
        at = chunk.index(marker) + len(marker)
        return tuple(chunk[at : at + 2])

    def test_each_data_bind_follows_the_solid_color_it_targets_and_reads_its_value(self):
        positions = [i for i, kind in enumerate(self.kinds) if kind == "DataBindContext"]
        self.assertEqual(len(positions), 2)
        instance = {
            prop(v, "viewModelPropertyId"): prop(v, "propertyValue") for v in self.of_kind("ViewModelInstanceColor")
        }
        for number, position in enumerate(positions):
            target = self.objects[position - 1]
            self.assertEqual(target["typeName"], "SolidColor")
            view_model, property_rank = self.bind_path(number)
            self.assertEqual(view_model, 0)
            self.assertEqual(prop(target, "colorValue"), instance[property_rank])
        self.assertEqual([self.bind_path(n)[1] for n in range(2)], [0, 1])

    def test_data_binds_target_the_color_value_from_source_to_target(self):
        for bind in self.of_kind("DataBindContext"):
            self.assertEqual(prop(bind, "propertyKey"), self.color_key)
            self.assertEqual(prop(bind, "flags", 0), 0)

    def test_data_binds_and_view_model_objects_take_no_slot_in_the_artboard(self):
        for kind in ("DataBindContext", "ViewModel", "ViewModelInstance"):
            for obj in self.of_kind(kind):
                self.assertIsNone(obj["slot"], kind)


class NativeTintedShapeRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            render_check.find_goldens()
            render_check.require_imaging()
        except render_check.RenderUnavailable as error:
            raise unittest.SkipTest(str(error)) from None
        cls.folder = tempfile.TemporaryDirectory()
        cls.paths = {}
        for label, bound, signature in (("riv", True, b"RIVE"), ("twno", True, b"TWNR"), ("free", False, b"RIVE")):
            path = Path(cls.folder.name) / f"{label}.riv"
            path.write_bytes(tinted_shape.build(bound).to_bytes(signature))
            cls.paths[label] = path

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def center(self, label):
        image = render_check.render(self.paths[label], advance=2)
        height, width = image.shape[:2]
        return tuple(int(v) for v in image[height // 2, width // 2])

    def test_without_a_data_bind_the_shape_keeps_its_own_color(self):
        self.assertEqual(self.center("free"), (*channels(tinted_shape.DEFAULT_COLOR), 255))

    def test_with_the_data_bind_the_shape_takes_the_color_of_the_view_model_instance(self):
        self.assertEqual(self.center("riv"), (*channels(FRESH_INSTANCE_COLOR), 255))

    def test_twno_renders_like_riv(self):
        self.assertEqual(self.center("twno"), self.center("riv"))


if __name__ == "__main__":
    unittest.main()
