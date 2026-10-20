import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import twno_writer as w
from support import decode, props_of
from twno_writer import Document, Obj, WriteError

SPEC_BACKBOARD = "54574e52" "07" "04" "00" "00" "17" "00"
SPEC_NODE = "54574e52" "070400" "0d00" "02000000" "02" "0d" "0000803f" "00"


def read_varuint(data, position):
    value = shift = 0
    while True:
        byte = data[position]
        position += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return value, position


def read_table(data):
    position = 7
    keys = []
    while True:
        key, position = read_varuint(data, position)
        if key == 0:
            break
        keys.append(key)
    classes = []
    for index in range(len(keys)):
        start = position + 4 * (index // 4)
        word = int.from_bytes(data[start : start + 4], "little")
        classes.append((word >> (2 * (index % 4))) & 3)
    return keys, classes


def document(**kwargs):
    doc = Document(**kwargs)
    doc.add(Obj("Backboard"))
    return doc


def doc_with(*objs):
    doc = Document()
    for obj in objs:
        doc.add(obj)
    return doc


class SpecExamplesTest(unittest.TestCase):
    def test_minimal_backboard(self):
        data = doc_with(Obj("Backboard")).to_bytes()
        self.assertEqual(data.hex(), SPEC_BACKBOARD)

    def test_node_with_declared_table_is_twenty_bytes(self):
        data = doc_with(Obj("Node", x=1.0)).to_bytes()
        self.assertEqual(len(data), 20)
        self.assertEqual(data.hex(), SPEC_NODE)

    def test_hand_assembled_artboard(self):
        doc = Document()
        doc.add(Obj("Backboard"))
        artboard = doc.add(Obj("Artboard", name="A", width=100.0, height=50.0))
        doc.add(Obj("Node", parent=artboard, x=2.0))
        expected = bytes.fromhex(
            "54574e52070400"
            "040507080d00"
            "a1000000"
            "02000000"
            "1700"
            "01" "040141" "07" "0000c842" "08" "00004842" "00"
            "02" "0500" "0d" "00000040" "00"
        )
        self.assertEqual(doc.to_bytes(), expected)


class RefusalTest(unittest.TestCase):
    def test_unknown_type(self):
        with self.assertRaisesRegex(WriteError, "unknown type"):
            Obj("NoSuchType")

    def test_abstract_type(self):
        with self.assertRaisesRegex(WriteError, "abstract"):
            Obj("Drawable")

    def test_property_outside_type(self):
        with self.assertRaisesRegex(WriteError, "fps"):
            Document().add(Obj("Rectangle", fps=60))

    def test_property_of_parent_and_mixin_is_accepted(self):
        doc = Document()
        doc.add(Obj("Rectangle", x=1.0, name="r", opacity=0.5, cornerRadiusTL=4.0))
        doc.add(Obj("SolidColor", colorRed=10))
        values = [props for _, props, _ in decode(doc)]
        self.assertEqual(
            values[0],
            {"x": 1.0, "name": "r", "opacity": 0.5, "cornerRadiusTL": 4.0},
        )
        self.assertEqual(values[1], {"colorValue": 0xFF0A7474})

    def test_wrong_field_type(self):
        cases = [
            ("Rectangle", {"width": "3"}),
            ("Rectangle", {"width": True}),
            ("Rectangle", {"linkCornerRadius": 1}),
            ("Node", {"name": 3}),
            ("LinearAnimation", {"fps": 1.5}),
            ("LinearAnimation", {"fps": -1}),
            ("LinearAnimation", {"fps": 2**32}),
            ("SolidColor", {"colorValue": -1}),
            ("SolidColor", {"colorValue": "red"}),
            ("Node", {"parent": 3}),
        ]
        for type_name, props in cases:
            with self.subTest(type=type_name, props=props), self.assertRaises(WriteError):
                doc = document()
                doc.add(Obj("Artboard"))
                doc.add(Obj(type_name, **props))
                doc.to_bytes()

    def test_runtime_only_properties_are_refused(self):
        with self.assertRaisesRegex(WriteError, "not serialized"):
            Document().add(Obj("Node", xArtboard=3.0))

    def test_callbacks_are_refused(self):
        with self.assertRaisesRegex(WriteError, "callbacks are never written"):
            Document().add(Obj("Event", trigger=1))

    def test_extension_property_needs_declaration(self):
        with self.assertRaisesRegex(WriteError, "tweenoraTag"):
            Document().add(Obj("Node", tweenoraTag=3))
        doc = Document()
        doc.declare_property(50001, "uint", name="tweenoraTag")
        doc.add(Obj("Node", tweenoraTag=3))
        data = doc.to_bytes()
        self.assertIn(w.varuint(50001) + w.varuint(3), data)

    def test_extension_declaration_rules(self):
        doc = Document()
        bad = (
            (49999, "uint", "a"),
            (60000, "uint", "b"),
            (50001, "weird", "c"),
            (13, "uint", "d"),
            (50001, "uint", ""),
            (50001, "uint", "x"),
        )
        for key, size_class, name in bad:
            with self.subTest(key=key, name=name), self.assertRaises(WriteError):
                doc.declare_property(key, size_class, name=name)
        doc.declare_property(50002, "uint", name="tweenoraOne")
        with self.assertRaises(WriteError):
            doc.declare_property(50003, "uint", name="tweenoraOne")
        with self.assertRaises(WriteError):
            doc.declare_property(50002, "uint", name="tweenoraTwo")

    def test_extension_property_value_types(self):
        doc = Document()
        doc.declare_property(50010, "double", name="tweenoraD")
        doc.declare_property(50011, "string", name="tweenoraS")
        doc.declare_property(50012, "color", name="tweenoraC")
        doc.add(Obj("Node", tweenoraD=1.5, tweenoraS="é", tweenoraC=0xFF000000))
        data = doc.to_bytes()
        self.assertIn(w.varuint(50010) + w.float32(1.5), data)
        self.assertIn(w.varuint(50011) + w.string_value("é"), data)
        self.assertIn(w.varuint(50012) + w.color_word(0xFF000000), data)
        wrong = Document()
        wrong.declare_property(50010, "double", name="tweenoraD")
        with self.assertRaises(WriteError):
            wrong.add(Obj("Node", tweenoraD="x"))

    def test_reference_to_absent_object(self):
        ghost = Obj("Node")
        doc = document()
        doc.add(Obj("Artboard"))
        doc.add(Obj("Node", parent=ghost))
        with self.assertRaisesRegex(WriteError, "not in this document"):
            doc.to_bytes()

    def test_reference_by_unknown_name(self):
        doc = document()
        doc.add(Obj("Artboard", name="A"))
        doc.add(Obj("Node", parent="nowhere"))
        with self.assertRaisesRegex(WriteError, "nowhere"):
            doc.to_bytes()

    def test_reference_by_ambiguous_name(self):
        doc = document()
        doc.add(Obj("Artboard", name="A"))
        doc.add(Obj("Node", name="dup"))
        doc.add(Obj("Node", name="dup"))
        doc.add(Obj("Node", parent="dup"))
        with self.assertRaisesRegex(WriteError, "ambiguous"):
            doc.to_bytes()

    def test_raw_integer_for_id_is_refused(self):
        doc = document()
        doc.add(Obj("Artboard"))
        with self.assertRaises(WriteError):
            doc.add(Obj("Node", parent=0))
            doc.to_bytes()

    def test_same_object_added_twice(self):
        node = Obj("Node")
        doc = Document()
        doc.add(node)
        with self.assertRaises(WriteError):
            doc.add(node)
        with self.assertRaises(WriteError):
            Document().add(node)

    def test_reference_across_artboards_is_refused(self):
        doc = document()
        doc.add(Obj("Artboard", name="A"))
        node = doc.add(Obj("Node", name="n"))
        doc.add(Obj("Artboard", name="B"))
        doc.add(Obj("Node", parent=node))
        with self.assertRaisesRegex(WriteError, "another artboard"):
            doc.to_bytes()


class BitFieldTest(unittest.TestCase):
    def solid(self, **props):
        doc = Document()
        doc.add(Obj("SolidColor", **props))
        return doc

    def test_channels_fold_into_storage(self):
        doc = self.solid(colorRed=0x11, colorGreen=0x22, colorBlue=0x33, colorAlpha=0xFF)
        self.assertEqual(props_of(doc, "SolidColor"), {"colorValue": 0xFF112233})

    def test_channel_over_explicit_storage(self):
        doc = self.solid(colorValue=0xFF000000, colorGreen=0x80)
        self.assertEqual(props_of(doc, "SolidColor"), {"colorValue": 0xFF008000})

    def test_channel_over_default_storage(self):
        doc = self.solid(colorRed=0)
        self.assertEqual(props_of(doc, "SolidColor"), {"colorValue": 0xFF007474})

    def test_channel_out_of_range(self):
        with self.assertRaises(WriteError):
            self.solid(colorRed=256)

    def test_bitmask_flags_fold_into_storage(self):
        doc = doc_with(Obj("LayerMask", isVisible=True, sourceDraws=True))
        self.assertEqual(props_of(doc, "LayerMask"), {"maskFlags": 12})
        doc = doc_with(Obj("LayerMask", isVisible=False))
        self.assertEqual(props_of(doc, "LayerMask"), {"maskFlags": 0})

    def test_bit_field_and_mask_share_storage(self):
        doc = doc_with(Obj("LayerMask", maskModeValue=2, isVisible=True, useCustomBounds=True))
        self.assertEqual(props_of(doc, "LayerMask"), {"maskFlags": 2 | 4 | 16})


class NumberingTest(unittest.TestCase):
    def test_slots_follow_stream_order(self):
        doc = Document()
        backboard = doc.add(Obj("Backboard"))
        artboard = doc.add(Obj("Artboard", name="A"))
        node = doc.add(Obj("Node", parent=artboard))
        shape = doc.add(Obj("Shape", parent=node))
        rectangle = doc.add(Obj("Rectangle", parent=shape))
        fill = doc.add(Obj("Fill", parent=shape))
        color = doc.add(Obj("SolidColor", parent=fill))
        interpolator = doc.add(Obj("CubicEaseInterpolator"))
        animation = doc.add(Obj("LinearAnimation", name="a"))
        keyed = doc.add(Obj("KeyedObject", object=node))
        prop = doc.add(Obj("KeyedProperty", propertyKey=13))
        frame = doc.add(Obj("KeyFrameDouble", frame=0, value=1.0, interpolator=interpolator))
        machine = doc.add(Obj("StateMachine", name="m"))
        data = doc.to_bytes()
        doc.to_bytes()
        self.assertIsNone(backboard.slot)
        self.assertEqual(
            [o.slot for o in (artboard, node, shape, rectangle, fill, color, interpolator)],
            [0, 1, 2, 3, 4, 5, 6],
        )
        for obj in (animation, keyed, prop, frame, machine):
            self.assertIsNone(obj.slot)
        self.assertEqual(animation.index, 0)
        self.assertEqual(machine.index, 0)
        self.assertIn(w.varuint(51) + w.varuint(1), data)
        self.assertIn(w.varuint(69) + w.varuint(6), data)

    def test_second_artboard_restarts_numbering(self):
        doc = document()
        doc.add(Obj("Artboard", name="A"))
        doc.add(Obj("Node"))
        second = doc.add(Obj("Artboard", name="B"))
        node = doc.add(Obj("Node"))
        doc.to_bytes()
        self.assertEqual((second.slot, node.slot), (0, 1))
        self.assertEqual((second.artboard, node.artboard), (1, 1))

    def test_objects_before_first_artboard_are_global(self):
        doc = document()
        node = doc.add(Obj("Node"))
        doc.add(Obj("Artboard"))
        doc.to_bytes()
        self.assertIsNone(node.slot)
        self.assertIsNone(node.artboard)

    def test_scroll_physics_takes_no_slot(self):
        doc = document()
        doc.add(Obj("Artboard"))
        physics = doc.add(Obj("ElasticScrollPhysics"))
        node = doc.add(Obj("Node"))
        doc.to_bytes()
        self.assertIsNone(physics.slot)
        self.assertEqual(node.slot, 1)

    def test_user_input_takes_a_slot(self):
        doc = document()
        doc.add(Obj("Artboard"))
        doc.add(Obj("Node"))
        keyboard = doc.add(Obj("KeyboardInput"))
        doc.to_bytes()
        self.assertEqual(keyboard.slot, 2)


class StateMachineReferenceTest(unittest.TestCase):
    def build(self):
        doc = Document()
        doc.add(Obj("Backboard"))
        doc.add(Obj("Artboard", name="A", width=10.0, height=10.0))
        first = doc.add(Obj("LinearAnimation", name="first"))
        second = doc.add(Obj("LinearAnimation", name="second"))
        machine = doc.add(Obj("StateMachine", name="m"))
        flag = doc.add(Obj("StateMachineBool", name="flag"))
        trigger = doc.add(Obj("StateMachineTrigger", name="go"))
        layer = doc.add(Obj("StateMachineLayer", name="L"))
        entry = doc.add(Obj("EntryState"))
        doc.add(Obj("AnyState"))
        doc.add(Obj("ExitState"))
        s_first = doc.add(Obj("AnimationState", animation="first"))
        s_second = doc.add(Obj("AnimationState", animation=second))
        doc.add(Obj("StateTransition", stateTo=s_second))
        doc.add(Obj("TransitionBoolCondition", input=flag))
        return doc, locals()

    def test_indices(self):
        doc, names = self.build()
        data = doc.to_bytes()
        self.assertEqual(names["first"].index, 0)
        self.assertEqual(names["second"].index, 1)
        self.assertEqual(names["flag"].index, 0)
        self.assertEqual(names["trigger"].index, 1)
        self.assertEqual(names["entry"].index, 0)
        self.assertEqual(names["s_second"].index, 4)
        self.assertIn(w.varuint(151) + w.varuint(4), data)
        self.assertIn(w.varuint(149) + w.varuint(1), data)
        self.assertIn(w.varuint(149) + w.varuint(0), data)
        self.assertIn(w.varuint(155) + w.varuint(0), data)

    def test_states_of_another_layer_are_refused(self):
        doc = document()
        doc.add(Obj("Artboard"))
        doc.add(Obj("StateMachine", name="m"))
        doc.add(Obj("StateMachineLayer", name="L1"))
        other = doc.add(Obj("AnimationState"))
        doc.add(Obj("StateMachineLayer", name="L2"))
        doc.add(Obj("AnimationState"))
        doc.add(Obj("StateTransition", stateTo=other))
        with self.assertRaisesRegex(WriteError, "another"):
            doc.to_bytes()


class HeaderTest(unittest.TestCase):
    def test_table_is_sorted_and_deduplicated(self):
        doc = document()
        doc.add(Obj("Artboard", width=1.0))
        doc.add(Obj("Node", x=1.0, y=2.0))
        doc.add(Obj("Node", x=3.0))
        keys, _ = read_table(doc.to_bytes())
        self.assertEqual(keys, [7, 13, 14])

    def test_size_classes_pack_four_per_word(self):
        doc = document()
        doc.add(Obj("Artboard", name="n", width=1.0, clip=True))
        doc.add(Obj("SolidColor", colorValue=0xFF000000))
        keys, classes = read_table(doc.to_bytes())
        self.assertEqual(keys, [4, 7, 37, 196])
        self.assertEqual(classes, [1, 2, 3, 0])

    def test_five_keys_use_two_words(self):
        doc = document()
        doc.add(Obj("Artboard", name="n", width=1.0, height=2.0, clip=True))
        doc.add(Obj("Node", x=1.0))
        data = doc.to_bytes()
        keys, classes = read_table(data)
        self.assertEqual(keys, [4, 7, 8, 13, 196])
        self.assertEqual(classes, [1, 2, 2, 2, 0])

    def test_minimal_table_keeps_only_extension_keys(self):
        doc = Document(table="minimal")
        doc.declare_property(50001, "uint", name="tweenoraTag")
        doc.add(Obj("Node", x=1.0, tweenoraTag=2))
        expected = (
            bytes.fromhex("54574e52070400")
            + w.varuint(50001)
            + b"\x00"
            + bytes(4)
            + b"\x02"
            + b"\x0d"
            + w.float32(1.0)
            + w.varuint(50001)
            + b"\x02"
            + b"\x00"
        )
        self.assertEqual(doc.to_bytes(), expected)

    def test_minimal_table_for_plain_file_is_empty(self):
        doc = Document(table="minimal")
        doc.add(Obj("Node", x=1.0))
        self.assertEqual(doc.to_bytes()[7], 0)

    def test_declared_but_unused_extension_keys_are_listed(self):
        doc = Document()
        doc.declare_property(50001, "uint", name="tweenoraTag")
        doc.add(Obj("Backboard"))
        self.assertEqual(doc.to_bytes()[7:11], w.varuint(50001) + b"\x00")

    def test_versions_and_file_id(self):
        doc = Document(minor=2, file_id=300)
        doc.add(Obj("Backboard"))
        self.assertEqual(doc.to_bytes()[:8].hex(), "54574e52" "07" "02" "ac02")

    def test_bad_header_parameters(self):
        for kwargs in ({"minor": -1}, {"file_id": -1}, {"table": "full"}, {"minor": 1.0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(WriteError):
                Document(**kwargs)


class OutputTest(unittest.TestCase):
    def build(self):
        doc = Document()
        doc.add(Obj("Backboard"))
        artboard = doc.add(Obj("Artboard", name="A", width=100.0, height=100.0))
        shape = doc.add(Obj("Shape", parent=artboard, x=50.0, y=50.0))
        doc.add(Obj("Rectangle", parent=shape, width=40.0, height=40.0))
        fill = doc.add(Obj("Fill", parent=shape))
        doc.add(Obj("SolidColor", parent=fill, colorValue=0xFFFF0000))
        return doc

    def test_deterministic(self):
        self.assertEqual(self.build().to_bytes(), self.build().to_bytes())
        doc = self.build()
        self.assertEqual(doc.to_bytes(), doc.to_bytes())

    def test_twno_and_riv_differ_only_by_signature(self):
        doc = self.build()
        twno = doc.to_bytes(b"TWNR")
        riv = doc.to_bytes(b"RIVE")
        self.assertEqual(twno[:4], b"TWNR")
        self.assertEqual(riv[:4], b"RIVE")
        self.assertEqual(twno[4:], riv[4:])

    def test_bad_signature(self):
        with self.assertRaises(WriteError):
            self.build().to_bytes(b"ABCD")

    def test_write_picks_signature_from_extension(self):
        doc = self.build()
        with tempfile.TemporaryDirectory() as folder:
            twno, riv, other = (Path(folder) / name for name in ("a.twno", "a.riv", "a.bin"))
            doc.write(twno)
            doc.write(riv)
            self.assertEqual(twno.read_bytes()[:4], b"TWNR")
            self.assertEqual(riv.read_bytes()[:4], b"RIVE")
            self.assertEqual(twno.read_bytes()[4:], riv.read_bytes()[4:])
            with self.assertRaises(WriteError):
                doc.write(other)
            self.assertFalse(other.exists())

    def test_write_creates_parent_folders(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "deep" / "er" / "a.twno"
            self.build().write(target)
            self.assertTrue(target.is_file())

    def test_failed_validation_writes_nothing(self):
        doc = document()
        doc.add(Obj("Artboard"))
        doc.add(Obj("Node", parent="ghost"))
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "a.twno"
            with self.assertRaises(WriteError):
                doc.write(target)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
