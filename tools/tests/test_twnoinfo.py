import functools
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

import twno_convert
import twnoinfo

SCRIPT = TOOLS_DIR / "twnoinfo.py"
UNKNOWN_TYPE = 55555
UNKNOWN_PROPERTY = 60000
EMPTY_ID = 0xFFFFFFFF


@functools.cache
def schema():
    return twnoinfo.load_schema()


def type_key(name):
    return schema().by_name[name]["key"]


def prop_key(owner, name):
    matches = [
        p["key"]
        for p in schema().properties.values()
        if p["owner"] == owner and p["name"] == name
    ]
    assert len(matches) == 1, (owner, name)
    return matches[0]


ARTBOARD = type_key("Artboard")
NODE = type_key("Node")
BACKBOARD = type_key("Backboard")
NODE_X = prop_key("Node", "x")
PARENT_ID = prop_key("Component", "parentId")
COMPONENT_NAME = prop_key("Component", "name")


def varuint(value):
    out = bytearray()
    while True:
        low = value & 0x7F
        value >>= 7
        if value:
            out.append(low | 0x80)
        else:
            out.append(low)
            return bytes(out)


def string(text):
    raw = text.encode("utf-8")
    return varuint(len(raw)) + raw


def header(signature=b"TWNR", major=7, minor=4, file_id=0, table=()):
    out = bytearray(signature)
    out += varuint(major) + varuint(minor) + varuint(file_id)
    for key, _ in table:
        out += varuint(key)
    out += varuint(0)
    for start in range(0, len(table), 4):
        word = 0
        for offset, (_, size_class) in enumerate(table[start : start + 4]):
            word |= size_class << (2 * offset)
        out += struct.pack("<I", word)
    return bytes(out)


def obj(object_type, *props):
    out = bytearray(varuint(object_type))
    for key, raw in props:
        out += varuint(key) + raw
    out += varuint(0)
    return bytes(out)


def parent(index):
    return PARENT_ID, varuint(index)


def name(text):
    return COMPONENT_NAME, string(text)


def node_x(value):
    return NODE_X, struct.pack("<f", value)


def read(data):
    return twnoinfo.read_document(data, schema())


@functools.cache
def reference_files():
    return tuple(sorted((REPO_ROOT / "runtime").rglob("*.riv")))


def slots_of(doc, type_name):
    return [o["slot"] for o in doc["objects"] if o["typeName"] == type_name]


def tree_names(doc, artboard=0):
    return [(n["name"], n["parentSlot"]) for n in doc["artboards"][artboard]["tree"]]


def first_property(field_type):
    return next(
        p
        for p in schema().properties.values()
        if p["fieldType"] == field_type and p["serialized"]
    )


class HeaderTest(unittest.TestCase):
    def test_minimal_backboard_file_of_the_spec(self):
        data = bytes.fromhex("54574e52070400" "00" "17" "00")
        doc = read(data)
        self.assertEqual(doc["header"]["signature"], "TWNR")
        self.assertEqual((doc["header"]["major"], doc["header"]["minor"]), (7, 4))
        self.assertEqual(doc["header"]["fileId"], 0)
        self.assertEqual(doc["header"]["table"], [])
        self.assertEqual([o["typeName"] for o in doc["objects"]], ["Backboard"])

    def test_node_example_of_the_spec_declares_key_13_in_the_table(self):
        data = bytes.fromhex("54574e52070400" "0d00" "02000000" "02" "0d" "0000803f" "00")
        self.assertEqual(len(data), 20)
        doc = read(data)
        self.assertEqual(doc["header"]["table"], [{"key": 13, "sizeClass": "double"}])
        prop = doc["objects"][0]["properties"][0]
        self.assertEqual(
            (doc["objects"][0]["typeName"], prop["name"], prop["value"]), ("Node", "x", 1.0)
        )

    def test_legacy_signature_is_read_and_reported(self):
        doc = read(header(signature=b"RIVE") + obj(BACKBOARD))
        self.assertEqual(doc["header"]["signature"], "RIVE")

    def test_table_packs_four_size_classes_per_word(self):
        table = [(60000 + i, i % 4) for i in range(6)]
        doc = read(header(table=table) + obj(BACKBOARD))
        self.assertEqual(
            [e["sizeClass"] for e in doc["header"]["table"]],
            ["uint", "string", "double", "color", "uint", "string"],
        )

    def test_file_id_above_32_bits(self):
        doc = read(header(file_id=2**40 + 5) + obj(BACKBOARD))
        self.assertEqual(doc["header"]["fileId"], 2**40 + 5)


class SlotTest(unittest.TestCase):
    def numbered(self, *objects):
        return read(header(table=[(UNKNOWN_PROPERTY, 0)]) + obj(ARTBOARD) + b"".join(objects))

    def test_components_interpolators_and_user_inputs_take_a_slot(self):
        for family in ("Node", "CubicEaseInterpolator", "KeyboardInput"):
            with self.subTest(type=family):
                doc = self.numbered(obj(type_key(family)))
                self.assertEqual(slots_of(doc, family), [1])

    def test_scroll_physics_never_takes_a_slot(self):
        for family in ("ClampedScrollPhysics", "ElasticScrollPhysics"):
            with self.subTest(type=family):
                doc = self.numbered(obj(type_key(family)), obj(NODE))
                self.assertEqual(slots_of(doc, family), [None])
                self.assertEqual(slots_of(doc, "Node"), [1])

    def test_script_input_counts_only_with_a_parent(self):
        script_input = type_key("ScriptInputNumber")
        without = self.numbered(obj(script_input), obj(NODE))
        self.assertEqual(slots_of(without, "ScriptInputNumber"), [None])
        self.assertEqual(slots_of(without, "Node"), [1])
        zero = self.numbered(obj(script_input, parent(0)), obj(NODE))
        self.assertEqual(slots_of(zero, "ScriptInputNumber"), [None])
        with_parent = self.numbered(obj(NODE), obj(script_input, parent(1)))
        self.assertEqual(slots_of(with_parent, "ScriptInputNumber"), [2])

    def test_abstract_type_takes_a_slot(self):
        abstract = schema().by_name["BindableProperty"]
        self.assertTrue(abstract["abstract"])
        doc = self.numbered(obj(abstract["key"]), obj(NODE))
        self.assertEqual(slots_of(doc, "BindableProperty"), [1])
        self.assertEqual(slots_of(doc, "Node"), [2])

    def test_animations_do_not_take_a_slot_and_are_listed_apart(self):
        doc = self.numbered(obj(type_key("LinearAnimation")), obj(NODE))
        self.assertEqual(slots_of(doc, "LinearAnimation"), [None])
        self.assertEqual(slots_of(doc, "Node"), [1])
        self.assertEqual(
            [o["typeName"] for o in doc["artboards"][0]["others"]], ["LinearAnimation"]
        )

    def test_unknown_object_still_takes_a_slot(self):
        doc = self.numbered(
            obj(UNKNOWN_TYPE, (UNKNOWN_PROPERTY, varuint(7))),
            obj(NODE, name("a"), parent(0)),
            obj(NODE, name("b"), parent(2)),
        )
        unknown = doc["objects"][1]
        self.assertEqual((unknown["typeName"], unknown["slot"]), (f"unknown({UNKNOWN_TYPE})", 1))
        self.assertEqual(slots_of(doc, "Node"), [2, 3])

    def test_objects_before_the_first_artboard_are_global(self):
        doc = read(header() + obj(BACKBOARD) + obj(ARTBOARD) + obj(NODE, parent(0)))
        self.assertEqual([o["typeName"] for o in doc["globalObjects"]], ["Backboard"])
        self.assertIsNone(doc["objects"][0]["slot"])

    def test_two_artboards_have_independent_numbering(self):
        doc = read(
            header()
            + obj(ARTBOARD, name("one"))
            + obj(NODE, name("n1"), parent(0))
            + obj(ARTBOARD, name("two"))
            + obj(NODE, name("n2"), parent(0))
        )
        self.assertEqual([a["name"] for a in doc["artboards"]], ["one", "two"])
        self.assertEqual(doc["objects"][3]["slot"], 1)
        self.assertEqual(tree_names(doc, 1), [("two", None), ("n2", 0)])


class TreeTest(unittest.TestCase):
    def tree(self, *objects):
        return tree_names(read(header() + obj(ARTBOARD, name("root")) + b"".join(objects)))

    def test_children_hang_from_their_parent_in_stream_order(self):
        result = self.tree(
            obj(NODE, name("a"), parent(0)),
            obj(NODE, name("b"), parent(1)),
            obj(NODE, name("c"), parent(0)),
        )
        self.assertEqual(result, [("root", None), ("a", 0), ("b", 1), ("c", 0)])

    def test_node_without_parent_id_is_attached_to_the_artboard_and_marked(self):
        doc = read(header() + obj(ARTBOARD) + obj(NODE, name("a")))
        node = doc["artboards"][0]["tree"][1]
        self.assertEqual((node["parentSlot"], node["link"]), (0, "none"))
        self.assertIn("(no parentId)", twnoinfo.render_text(doc, "x"))

    def test_self_parent_dangling_and_empty_parent_are_attached_and_marked(self):
        cases = {
            "self": obj(NODE, name("a"), parent(1)),
            "dangling": obj(NODE, name("a"), parent(99)),
            "empty": obj(NODE, name("a"), (PARENT_ID, varuint(EMPTY_ID))),
        }
        for label, node in cases.items():
            with self.subTest(case=label):
                doc = read(header() + obj(ARTBOARD) + node)
                tree_node = doc["artboards"][0]["tree"][1]
                self.assertEqual((tree_node["parentSlot"], tree_node["link"]), (0, "invalid"))
                self.assertIn("(invalid parentId)", twnoinfo.render_text(doc, "x"))

    def test_cycle_is_broken_once_and_its_tail_keeps_its_parent(self):
        doc = read(
            header()
            + obj(ARTBOARD)
            + obj(NODE, name("tail"), parent(2))
            + obj(NODE, name("x"), parent(3))
            + obj(NODE, name("y"), parent(2))
        )
        nodes = {n["slot"]: n for n in doc["artboards"][0]["tree"]}
        self.assertEqual(len(nodes), 4)
        self.assertEqual(nodes[1]["parentSlot"], 2)
        for slot in nodes:
            current = slot
            for _ in range(10):
                if current == 0:
                    break
                current = nodes[current]["parentSlot"]
            self.assertEqual(current, 0, slot)

    def test_last_parent_id_of_an_object_wins(self):
        doc = read(
            header()
            + obj(ARTBOARD)
            + obj(NODE, name("a"), parent(0))
            + obj(NODE, name("b"), parent(0), parent(1))
        )
        self.assertEqual(doc["artboards"][0]["tree"][2]["parentSlot"], 1)

    def test_deep_chain_is_fast_and_serializes(self):
        count = 5000
        objects = [obj(NODE, parent(index)) for index in range(count)]
        doc = read(header() + obj(ARTBOARD) + b"".join(objects))
        tree = doc["artboards"][0]["tree"]
        self.assertEqual(len(tree), count + 1)
        self.assertEqual(tree[-1]["depth"], count)
        self.assertTrue(twnoinfo.render_json([{"file": "x", **doc}]))
        self.assertTrue(twnoinfo.render_text(doc, "x", True))

    def test_wide_fan_out(self):
        objects = b"".join(obj(NODE, parent(0)) for _ in range(20000))
        doc = read(header() + obj(ARTBOARD) + objects)
        self.assertEqual(len(doc["artboards"][0]["tree"]), 20001)


class ValueTest(unittest.TestCase):
    def decoded(self, prop, raw):
        data = header() + obj(ARTBOARD) + obj(type_key(prop["owner"]), (prop["key"], raw))
        return read(data)["objects"][1]["properties"][0]

    def test_double_and_color_and_empty_id(self):
        self.assertEqual(self.decoded(schema().properties[NODE_X], struct.pack("<f", 1.5))["value"], 1.5)
        color = self.decoded(
            schema().properties[prop_key("SolidColor", "colorValue")], struct.pack("<I", 0xFF112233)
        )
        self.assertEqual((color["fieldType"], color["value"]), ("color", 0xFF112233))
        ident = self.decoded(schema().properties[prop_key("Image", "assetId")], varuint(EMPTY_ID))
        self.assertEqual((ident["fieldType"], ident["value"]), ("id", EMPTY_ID))

    def test_bool_is_one_byte(self):
        flag = first_property("bool")
        for raw, expected in ((b"\x01", True), (b"\x00", False), (b"\x02", False)):
            with self.subTest(raw=raw):
                self.assertEqual(self.decoded(flag, raw)["value"], expected)

    def test_int_is_zigzag(self):
        flag = first_property("int")
        cases = ((0, 0), (1, -1), (2, 1), (3, -2), (4294967294, 2147483647), (4294967295, -2147483648))
        for encoded, expected in cases:
            with self.subTest(encoded=encoded):
                self.assertEqual(self.decoded(flag, varuint(encoded))["value"], expected)

    def test_bytes_property_reports_its_length(self):
        prop = schema().properties[prop_key("FileAssetContents", "bytes")]
        self.assertEqual(self.decoded(prop, varuint(3) + b"abc")["value"], {"bytes": 3})

    def test_callback_key_needs_a_table_entry(self):
        key = prop_key("Event", "trigger")
        with self.assertRaises(twnoinfo.TwnoError):
            read(header() + obj(type_key("Event"), (key, varuint(1))))
        doc = read(header(table=[(key, 0)]) + obj(type_key("Event"), (key, varuint(1))))
        self.assertEqual(doc["objects"][0]["properties"][0]["value"], 1)

    def test_nan_and_infinity_become_strings(self):
        for bits, expected in ((0x7FC00000, "nan"), (0x7F800000, "inf")):
            with self.subTest(expected=expected):
                doc = read(header() + obj(NODE, (NODE_X, struct.pack("<I", bits))))
                self.assertEqual(doc["objects"][0]["properties"][0]["value"], expected)
                json.loads(twnoinfo.render_json([{"file": "x", **doc}]))

    def test_unknown_property_is_skipped_by_size_class(self):
        cases = (
            (0, varuint(300)),
            (1, string("héllo")),
            (2, struct.pack("<f", 2.5)),
            (3, struct.pack("<I", 0xFF112233)),
        )
        for size_class, raw in cases:
            with self.subTest(size_class=size_class):
                data = (
                    header(table=[(UNKNOWN_PROPERTY, size_class)])
                    + obj(BACKBOARD, (UNKNOWN_PROPERTY, raw))
                    + obj(ARTBOARD)
                )
                doc = read(data)
                self.assertEqual([o["typeName"] for o in doc["objects"]], ["Backboard", "Artboard"])
                self.assertEqual(
                    doc["objects"][0]["properties"][0]["name"], f"unknown({UNKNOWN_PROPERTY})"
                )

    def test_invalid_utf8_in_a_string_is_tolerated(self):
        raw = varuint(3) + b"\xff\xfe\x00"
        doc = read(header(table=[(UNKNOWN_PROPERTY, 1)]) + obj(BACKBOARD, (UNKNOWN_PROPERTY, raw)))
        self.assertEqual(len(doc["objects"]), 1)
        named = read(header() + obj(ARTBOARD, (COMPONENT_NAME, varuint(2) + b"\xe9a")))
        self.assertTrue(named["artboards"][0]["name"].endswith("a"))


class ErrorTest(unittest.TestCase):
    def assertRejected(self, data, fragment):
        with self.assertRaises(twnoinfo.TwnoError) as caught:
            read(data)
        self.assertIn(fragment, str(caught.exception))

    def test_bad_signature_and_short_files(self):
        self.assertRejected(b"JUNK" + header()[4:] + obj(BACKBOARD), "signature")
        self.assertRejected(b"", "signature")
        self.assertRejected(b"TWN", "signature")

    def test_wrong_major_version(self):
        self.assertRejected(header(major=8) + obj(BACKBOARD), "version")

    def test_truncations(self):
        self.assertRejected(header(table=[(60000, 0)])[:-2], "byte")
        full = header() + obj(ARTBOARD, name("main"))
        self.assertRejected(full[:-3], "byte")
        self.assertRejected(full[:-1], "varuint")

    def test_every_truncation_of_a_real_file_is_a_clean_error_or_a_valid_file(self):
        path = next(p for p in reference_files() if p.name == "two_artboards.riv")
        data = path.read_bytes()
        valid = 0
        for cut in range(len(data)):
            try:
                read(data[:cut])
            except twnoinfo.TwnoError:
                continue
            valid += 1
        self.assertLess(valid, len(data) // 10)

    def test_property_key_known_to_neither_schema_nor_table(self):
        self.assertRejected(
            header() + obj(BACKBOARD, (UNKNOWN_PROPERTY, varuint(1))), str(UNKNOWN_PROPERTY)
        )

    def test_property_key_above_65535(self):
        data = header(table=[(65536, 0)]) + obj(BACKBOARD, (65536, varuint(1)))
        self.assertRejected(data, "65535")

    def test_string_longer_than_the_file(self):
        data = header() + obj(ARTBOARD, (COMPONENT_NAME, varuint(500) + b"ab"))
        self.assertRejected(data, "byte")

    def test_varuint_limits(self):
        self.assertRejected(header()[:4] + b"\xff" * 11, "varuint")
        self.assertRejected(header(minor=2**31) + obj(BACKBOARD), "31 bits")
        self.assertRejected(header(table=[(2**31, 0)]) + obj(BACKBOARD), "31 bits")
        self.assertRejected(header() + varuint(2**31) + varuint(0), "31 bits")
        self.assertRejected(header() + obj(NODE, (PARENT_ID, varuint(2**32))), "32 bits")
        self.assertRejected(header(file_id=2**64), "64 bits")

    def test_error_carries_the_offset(self):
        with self.assertRaises(twnoinfo.TwnoError) as caught:
            read(header() + obj(ARTBOARD)[:-1])
        self.assertGreater(caught.exception.offset, 0)


class RenderTest(unittest.TestCase):
    def document(self):
        return read(
            header(table=[(UNKNOWN_PROPERTY, 2)])
            + obj(BACKBOARD)
            + obj(ARTBOARD, name("main"))
            + obj(NODE, name("a"), node_x(2.0), parent(0))
            + obj(NODE, name("b"), parent(1))
            + obj(type_key("LinearAnimation"))
        )

    def test_text_shows_header_table_tree_and_other_objects(self):
        text = twnoinfo.render_text(self.document(), "demo.twno")
        expected = (
            "demo.twno",
            "TWNR",
            "7.4",
            str(UNKNOWN_PROPERTY),
            "double",
            'Artboard "main"',
            "Global objects",
            "Other objects",
            "LinearAnimation",
        )
        for fragment in expected:
            self.assertIn(fragment, text)
        lines = text.splitlines()
        a_line = next(l for l in lines if 'Node "a"' in l)
        b_line = next(l for l in lines if 'Node "b"' in l)
        self.assertGreater(len(b_line) - len(b_line.lstrip()), len(a_line) - len(a_line.lstrip()))

    def test_children_are_printed_in_stream_order(self):
        doc = read(
            header()
            + obj(ARTBOARD)
            + obj(NODE, name("first"), parent(0))
            + obj(NODE, name("second"), parent(0))
        )
        text = twnoinfo.render_text(doc, "x")
        self.assertLess(text.index("first"), text.index("second"))

    def test_properties_are_listed_only_on_request(self):
        doc = self.document()
        self.assertNotIn("x = 2", twnoinfo.render_text(doc, "demo.twno"))
        self.assertIn("- x = 2", twnoinfo.render_text(doc, "demo.twno", properties=True))

    def test_empty_id_and_colors_are_readable(self):
        doc = read(
            header()
            + obj(ARTBOARD)
            + obj(type_key("Image"), (prop_key("Image", "assetId"), varuint(EMPTY_ID)), parent(0))
            + obj(
                type_key("SolidColor"),
                (prop_key("SolidColor", "colorValue"), struct.pack("<I", 0xFF112233)),
                parent(0),
            )
        )
        text = twnoinfo.render_text(doc, "x", properties=True)
        self.assertIn("assetId = none", text)
        self.assertIn("colorValue = 0xFF112233", text)

    def test_control_characters_in_names_cannot_forge_lines(self):
        doc = read(header() + obj(ARTBOARD, name("a\nFake [9]\x1b[31m")))
        text = twnoinfo.render_text(doc, "x")
        self.assertNotIn("\x1b", text)
        self.assertNotIn("\nFake", text)
        self.assertIn("\\x0aFake", text)

    def test_json_is_valid_and_has_a_flat_tree(self):
        data = json.loads(twnoinfo.render_json([{"file": "demo.twno", **self.document()}]))
        self.assertEqual(data["file"], "demo.twno")
        self.assertEqual(data["header"]["major"], 7)
        self.assertEqual([n["depth"] for n in data["artboards"][0]["tree"]], [0, 1, 2])

    def test_json_of_several_files_is_one_array(self):
        docs = [{"file": "a", **self.document()}, {"file": "b", **self.document()}]
        data = json.loads(twnoinfo.render_json(docs))
        self.assertEqual([d["file"] for d in data], ["a", "b"])


class ReferenceFilesTest(unittest.TestCase):
    def test_every_riv_and_twno_file_gives_the_same_report(self):
        files = reference_files()
        self.assertEqual(len(files), 475)
        for path in files:
            riv = path.read_bytes()
            with self.subTest(path=path.relative_to(REPO_ROOT).as_posix()):
                a = read(riv)
                b = read(twno_convert.riv_to_twno(riv))
                twnoinfo.render_text(a, path.name, True)
                twnoinfo.render_json([{"file": path.name, **a}])
                self.assertEqual(a["header"]["signature"], "RIVE")
                self.assertEqual(b["header"]["signature"], "TWNR")
                a["header"]["signature"] = b["header"]["signature"] = ""
                self.assertEqual(a, b)

    def test_two_artboards_file(self):
        path = next(p for p in reference_files() if p.name == "two_artboards.riv")
        doc = read(path.read_bytes())
        self.assertEqual(len(doc["objects"]), 23)
        self.assertEqual([a["name"] for a in doc["artboards"]], ["Two", "One"])
        self.assertEqual([o["typeName"] for o in doc["globalObjects"]], ["Backboard"])

    def test_references_land_on_objects_of_the_right_kind(self):
        interpolators = {
            prop_key("InterpolatingKeyFrame", "interpolatorId"),
            prop_key("StateTransition", "interpolatorId"),
        }
        checked = {"parent": 0, "interpolator": 0}
        for path in reference_files():
            doc = read(path.read_bytes())
            members = {
                (o["artboard"], o["slot"]): o for o in doc["objects"] if o["slot"] is not None
            }
            for o in doc["objects"]:
                if o["artboard"] is None:
                    continue
                for prop in o["properties"]:
                    if prop["key"] == PARENT_ID and o["slot"] is not None:
                        checked["parent"] += 1
                        target = members.get((o["artboard"], prop["value"]))
                        self.assertIsNotNone(target, (path.name, o["slot"]))
                    elif prop["key"] in interpolators and prop["value"] != EMPTY_ID:
                        checked["interpolator"] += 1
                        target = members.get((o["artboard"], prop["value"]))
                        self.assertIsNotNone(target, (path.name, prop["key"]))
                        self.assertIn(
                            "KeyFrameInterpolator", schema().families[target["type"]], path.name
                        )
        self.assertGreater(checked["parent"], 80000)
        self.assertGreater(checked["interpolator"], 9000)


class CommandLineTest(unittest.TestCase):
    def run_tool(self, *args):
        return subprocess.run(
            [sys.executable, "-I", str(SCRIPT), *args], capture_output=True, cwd=REPO_ROOT
        )

    def text(self, result):
        return result.stdout.decode("utf-8"), result.stderr.decode("utf-8")

    def write(self, directory, filename, data):
        path = Path(directory) / filename
        path.write_bytes(data)
        return str(path)

    def test_reads_a_file_and_prints_the_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = header() + obj(BACKBOARD) + obj(ARTBOARD, name("main"))
            result = self.run_tool(self.write(tmp, "a.twno", data))
            out, err = self.text(result)
            self.assertEqual(result.returncode, 0, err)
            self.assertIn('Artboard "main"', out)
            self.assertEqual(err, "")

    def test_output_uses_unix_line_endings_and_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_tool(self.write(tmp, "a.twno", header() + obj(ARTBOARD, name("é"))))
            self.assertNotIn(b"\r", result.stdout)
            self.assertIn("é".encode("utf-8"), result.stdout)

    def test_json_option_with_one_and_two_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            one = self.write(tmp, "a.twno", header() + obj(BACKBOARD))
            two = self.write(tmp, "b.twno", header() + obj(ARTBOARD))
            single = json.loads(self.text(self.run_tool("--json", one))[0])
            self.assertEqual(single["header"]["signature"], "TWNR")
            both = json.loads(self.text(self.run_tool("--json", one, two))[0])
            self.assertEqual(len(both), 2)

    def test_properties_option(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = header() + obj(ARTBOARD) + obj(NODE, node_x(3.0), parent(0))
            out = self.text(self.run_tool("--properties", self.write(tmp, "a.twno", data)))[0]
            self.assertIn("x = 3", out)

    def test_truncated_and_missing_files_are_clean_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            cut = self.write(tmp, "cut.twno", (header() + obj(ARTBOARD, name("main")))[:-3])
            for target in (cut, "does-not-exist.twno", tmp):
                with self.subTest(target=target):
                    result = self.run_tool(target)
                    err = self.text(result)[1]
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(Path(target).name, err)
                    self.assertNotIn("Traceback", err)

    def test_deep_chain_does_not_crash_in_any_output_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            nodes = b"".join(obj(NODE, parent(i)) for i in range(5000))
            path = self.write(tmp, "deep.twno", header() + obj(ARTBOARD) + nodes)
            for option in ("--json", "--properties"):
                with self.subTest(option=option):
                    result = self.run_tool(option, path)
                    self.assertEqual(result.returncode, 0, self.text(result)[1][-300:])

    def test_one_bad_file_does_not_stop_the_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = self.write(tmp, "good.twno", header() + obj(ARTBOARD, name("main")))
            bad = self.write(tmp, "bad.twno", b"JUNK")
            result = self.run_tool(bad, good)
            out, err = self.text(result)
            self.assertEqual(result.returncode, 1)
            self.assertIn('Artboard "main"', out)
            self.assertIn("bad.twno", err)

    def test_invalid_schema_option_is_a_clean_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            schema_path = self.write(tmp, "s.json", b"[]")
            good = self.write(tmp, "good.twno", header() + obj(BACKBOARD))
            result = self.run_tool("--schema", schema_path, good)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", self.text(result)[1])

    def test_riv_file_of_the_repository(self):
        path = next(p for p in reference_files() if p.name == "two_artboards.riv")
        out = self.text(self.run_tool(str(path)))[0]
        self.assertIn("RIVE", out)
        self.assertEqual(sum(l.startswith("Artboard") for l in out.splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
