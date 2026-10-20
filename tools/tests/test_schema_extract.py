import functools
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

import schema_extract

SCRIPT = TOOLS_DIR / "schema_extract.py"
HEADERS_DIR = REPO_ROOT / "runtime" / "include" / "rive" / "generated"
COMMITTED = REPO_ROOT / "docs" / "schema" / "schema.json"
FIELD_TYPES = {
    "bool",
    "bytes",
    "callback",
    "color",
    "double",
    "id",
    "int",
    "string",
    "uint",
}


@functools.cache
def schema():
    return schema_extract.extract_schema(HEADERS_DIR)


@functools.cache
def base_headers():
    return tuple(sorted(HEADERS_DIR.rglob("*_base.hpp")))


@functools.cache
def raw_type_keys():
    pattern = re.compile(r"static const uint16_t typeKey = (\d+);")
    return sorted(
        int(m.group(1))
        for path in base_headers()
        for m in pattern.finditer(path.read_text(encoding="utf-8"))
    )


@functools.cache
def raw_property_keys():
    pattern = re.compile(r"static const uint16_t (\w+)PropertyKey = (\d+);")
    return sorted(
        int(m.group(2))
        for path in base_headers()
        for m in pattern.finditer(path.read_text(encoding="utf-8"))
    )


def by_key(entries):
    return {entry["key"]: entry for entry in entries}


class CoverageTest(unittest.TestCase):
    def test_every_type_key_of_the_generated_headers_is_listed(self):
        keys = [t["key"] for t in schema()["types"]]
        self.assertEqual(keys, raw_type_keys())
        self.assertEqual(len(keys), 356)
        self.assertEqual(max(keys), 1071)

    def test_every_property_key_of_the_generated_headers_is_listed(self):
        keys = [p["key"] for p in schema()["properties"]]
        self.assertEqual(keys, raw_property_keys())
        self.assertEqual(len(keys), 664)
        self.assertEqual(max(keys), 1099)

    def test_keys_are_globally_unique(self):
        keys = [p["key"] for p in schema()["properties"]]
        self.assertEqual(len(keys), len(set(keys)))
        names = [t["name"] for t in schema()["types"]]
        self.assertEqual(len(names), len(set(names)))


class StructureTest(unittest.TestCase):
    def test_every_property_belongs_to_a_declared_owner(self):
        owners = {t["name"] for t in schema()["types"]}
        owners |= {m["name"] for m in schema()["mixins"]}
        for prop in schema()["properties"]:
            with self.subTest(prop=prop["name"], key=prop["key"]):
                self.assertIn(prop["owner"], owners)

    def test_type_property_lists_match_the_property_table(self):
        props = by_key(schema()["properties"])
        for entry in schema()["types"] + schema()["mixins"]:
            for key in entry["properties"]:
                with self.subTest(owner=entry["name"], key=key):
                    self.assertEqual(props[key]["owner"], entry["name"])
        listed = sorted(
            key
            for entry in schema()["types"] + schema()["mixins"]
            for key in entry["properties"]
        )
        self.assertEqual(listed, raw_property_keys())

    def test_parents_resolve_and_never_loop(self):
        types = {t["name"]: t for t in schema()["types"]}
        for entry in types.values():
            seen = set()
            current = entry
            while current["parent"] is not None:
                with self.subTest(type=entry["name"], parent=current["parent"]):
                    self.assertIn(current["parent"], types)
                    self.assertNotIn(current["parent"], seen)
                seen.add(current["parent"])
                current = types[current["parent"]]

    def test_mixins_listed_by_a_type_exist(self):
        mixins = {m["name"] for m in schema()["mixins"]}
        for entry in schema()["types"]:
            for mixin in entry["mixins"]:
                with self.subTest(type=entry["name"], mixin=mixin):
                    self.assertIn(mixin, mixins)

    def test_header_paths_point_to_existing_files(self):
        for entry in schema()["types"] + schema()["mixins"]:
            with self.subTest(type=entry["name"]):
                self.assertTrue((REPO_ROOT / entry["header"]).is_file())


class FieldTypeTest(unittest.TestCase):
    def test_every_property_has_a_known_field_type(self):
        for prop in schema()["properties"]:
            with self.subTest(prop=prop["name"], key=prop["key"]):
                self.assertIn(prop["fieldType"], FIELD_TYPES)

    def test_wire_type_agrees_with_the_core_registry(self):
        registry = schema_extract.registry_field_types(
            HEADERS_DIR / "core_registry.hpp"
        )
        for prop in schema()["properties"]:
            expected = registry.get((prop["owner"], prop["name"]))
            if expected is not None:
                with self.subTest(prop=prop["name"], key=prop["key"]):
                    self.assertEqual(prop["fieldType"], expected)

    def test_serialized_flag_matches_the_deserialize_switch(self):
        headers = {
            entry["name"]: (REPO_ROOT / entry["header"]).read_text(encoding="utf-8")
            for entry in schema()["types"] + schema()["mixins"]
        }
        for prop in schema()["properties"]:
            in_switch = f"case {prop['name']}PropertyKey:" in headers[prop["owner"]]
            with self.subTest(prop=prop["name"], key=prop["key"]):
                self.assertEqual(prop["serialized"], in_switch)

    def test_packed_properties_point_to_their_storage(self):
        names = {}
        for prop in schema()["properties"]:
            names.setdefault(prop["owner"], set()).add(prop["name"])
        for prop in schema()["properties"]:
            for packing in (prop["bitmask"], prop["bitField"]):
                if packing is None:
                    continue
                with self.subTest(prop=prop["name"], key=prop["key"]):
                    self.assertIsNotNone(packing["storage"])
                    self.assertTrue(
                        packing["storage"] in names[prop["owner"]]
                        or packing["storage"] == "colorValue"
                    )
                    self.assertGreater(packing["mask"], 0)


class KnownPropertiesTest(unittest.TestCase):
    def prop(self, owner, name):
        matches = [
            p
            for p in schema()["properties"]
            if p["owner"] == owner and p["name"] == name
        ]
        self.assertEqual(len(matches), 1, (owner, name))
        return matches[0]

    def test_artboard_origin_x(self):
        origin = self.prop("Artboard", "originX")
        self.assertEqual(origin["key"], 11)
        self.assertEqual(origin["fieldType"], "double")
        self.assertEqual(origin["default"], 0.0)
        self.assertTrue(origin["serialized"])

    def test_component_name_lives_in_a_sidecar_and_defaults_to_empty(self):
        name = self.prop("Component", "name")
        self.assertEqual(name["key"], 4)
        self.assertEqual(name["fieldType"], "string")
        self.assertEqual(name["default"], "")

    def test_node_x_is_key_13(self):
        node_x = self.prop("Node", "x")
        self.assertEqual(node_x["key"], 13)
        self.assertEqual(node_x["fieldType"], "double")

    def test_id_property_keeps_its_symbolic_default(self):
        prop = self.prop("Artboard", "defaultStateMachineId")
        self.assertEqual(prop["fieldType"], "id")
        self.assertIsNone(prop["default"])
        self.assertEqual(prop["defaultExpr"], "kEmptyId")

    def test_bitmask_flag_points_to_its_storage_property(self):
        dither = self.prop("BitmapCache", "dither")
        self.assertEqual(dither["bitmask"]["storage"], "cacheFlags")
        self.assertEqual(dither["bitmask"]["mask"], 2)
        self.assertFalse(dither["serialized"])

    def test_color_channel_is_a_bit_field_of_the_color_value(self):
        red = self.prop("ColorChannels", "colorRed")
        self.assertEqual(red["bitField"]["offset"], 16)
        self.assertEqual(red["bitField"]["mask"], 0xFF0000)

    def test_bytes_properties_are_typed(self):
        self.assertEqual(self.prop("FileAssetContents", "bytes")["fieldType"], "bytes")

    def test_callback_property(self):
        self.assertEqual(self.prop("Event", "trigger")["fieldType"], "callback")

    def test_artboard_inherits_from_layout_component(self):
        types = {t["name"]: t for t in schema()["types"]}
        self.assertEqual(types["Artboard"]["key"], 1)
        self.assertEqual(types["Artboard"]["parent"], "LayoutComponent")
        self.assertEqual(types["Node"]["key"], 2)

    def test_solid_color_lists_the_color_channels_mixin(self):
        types = {t["name"]: t for t in schema()["types"]}
        self.assertEqual(types["SolidColor"]["mixins"], ["ColorChannels"])


RAW_WIRE_TYPES = {
    "Bool": "bool",
    "Bytes": "bytes",
    "Color": "color",
    "Double": "double",
    "Id": "id",
    "Int": "int",
    "String": "string",
    "Uint": "uint",
}


@functools.cache
def header_texts():
    return {
        entry["name"]: (REPO_ROOT / entry["header"]).read_text(encoding="utf-8")
        for entry in schema()["types"] + schema()["mixins"]
    }


class RawHeaderTest(unittest.TestCase):
    def test_parent_is_the_first_base_class_of_the_declaration(self):
        pattern = re.compile(r"^class\s+(\w+)Base\s*:\s*public\s+(\w+)", re.M)
        raw = {}
        for name, text in header_texts().items():
            match = pattern.search(text)
            if match:
                self.assertEqual(match.group(1), name)
                raw[name] = match.group(2)
        types = {t["name"]: t for t in schema()["types"]}
        self.assertEqual(set(raw), set(types))
        for name, parent in raw.items():
            with self.subTest(type=name):
                self.assertEqual(types[name]["parent"], None if parent == "Core" else parent)
        roots = sorted(name for name, parent in raw.items() if parent == "Core")
        self.assertEqual(sorted(t["name"] for t in types.values() if t["parent"] is None), roots)

    def test_field_type_is_the_type_read_by_the_deserialize_switch(self):
        checked = 0
        for prop in schema()["properties"]:
            if not prop["serialized"]:
                continue
            text = header_texts()[prop["owner"]]
            match = re.search(
                rf"case {prop['name']}PropertyKey:\s*[^;]*?Core(\w+)Type::", text
            )
            with self.subTest(prop=prop["name"], key=prop["key"]):
                self.assertIsNotNone(match)
                self.assertEqual(prop["fieldType"], RAW_WIRE_TYPES[match.group(1)])
            checked += 1
        self.assertEqual(checked, 605)

    def test_default_is_the_member_initializer_of_the_header(self):
        checked = 0
        for prop in schema()["properties"]:
            text = header_texts()[prop["owner"]]
            member = "m_" + prop["name"][0].upper() + prop["name"][1:]
            match = re.search(
                rf"^\s+(?!return\b)[A-Za-z_][\w:<>]*\s+{member}\s*=\s*([^;]+);", text, re.M
            )
            if match is None:
                continue
            raw = match.group(1)
            with self.subTest(prop=prop["name"], key=prop["key"]):
                self.assertEqual(prop["defaultExpr"], raw)
                if re.fullmatch(r"-?\d+\.\d*f", raw):
                    self.assertEqual(prop["default"], float(raw[:-1]))
                elif re.fullmatch(r"-?\d+", raw):
                    self.assertEqual(prop["default"], int(raw))
                elif raw in ("true", "false"):
                    self.assertEqual(prop["default"], raw == "true")
                elif raw == '""':
                    self.assertEqual(prop["default"], "")
                elif re.fullmatch(r"k\w+|Core::\w+", raw):
                    self.assertIsNone(prop["default"])
            checked += 1
        self.assertGreater(checked, 500)


class AbstractTypeTest(unittest.TestCase):
    def test_abstract_types_are_the_ones_the_registry_cannot_instantiate(self):
        text = (HEADERS_DIR / "core_registry.hpp").read_text(encoding="utf-8")
        instantiable = set(re.findall(r"return new (\w+)\(\);", text))
        types = {t["name"]: t for t in schema()["types"]}
        self.assertTrue(instantiable <= set(types))
        for name, entry in types.items():
            with self.subTest(type=name):
                self.assertEqual(entry["abstract"], name not in instantiable)
        self.assertEqual(sum(t["abstract"] for t in types.values()), 62)

    def test_known_abstract_and_concrete_types(self):
        types = {t["name"]: t for t in schema()["types"]}
        for name in ("Component", "BindableProperty", "KeyFrameInterpolator"):
            with self.subTest(type=name):
                self.assertTrue(types[name]["abstract"])
        for name in ("Artboard", "Node", "Backboard", "CubicEaseInterpolator"):
            with self.subTest(type=name):
                self.assertFalse(types[name]["abstract"])


class HandCheckedPropertiesTest(unittest.TestCase):
    def prop(self, owner, name):
        matches = [
            p
            for p in schema()["properties"]
            if p["owner"] == owner and p["name"] == name
        ]
        self.assertEqual(len(matches), 1, (owner, name))
        return matches[0]

    def test_transition_property_comparators_inherit_from_their_common_parent(self):
        types = {t["name"]: t for t in schema()["types"]}
        for name in (
            "TransitionPropertyArtboardComparator",
            "TransitionPropertyViewModelComparator",
            "TransitionPropertyComponentComparator",
        ):
            with self.subTest(type=name):
                self.assertEqual(types[name]["parent"], "TransitionPropertyComparator")
        self.assertEqual(types["TransitionPropertyComparator"]["key"], 478)
        self.assertEqual(types["TransitionPropertyComparator"]["parent"], "TransitionComparator")

    def test_layer_mask_flags_default_and_packed_flags(self):
        self.assertEqual(self.prop("LayerMask", "maskFlags")["default"], 4)
        visible = self.prop("LayerMask", "isVisible")
        self.assertEqual(visible["bitmask"], {"storage": "maskFlags", "mask": 4})
        mode = self.prop("LayerMask", "maskModeValue")
        self.assertEqual(mode["bitField"], {"storage": "maskFlags", "offset": 0, "mask": 3})

    def test_symbolic_defaults_keep_their_expression(self):
        for owner in ("DataBind", "KeyedProperty"):
            with self.subTest(owner=owner):
                prop = self.prop(owner, "propertyKey")
                self.assertIsNone(prop["default"])
                self.assertEqual(prop["defaultExpr"], "Core::invalidPropertyKey")
        self.assertEqual(
            self.prop("TransitionPropertyComponentComparator", "propertyKey")["default"], 0
        )

    def test_sidecar_defaults(self):
        border = self.prop("LayoutComponentStyle", "borderLeft")
        self.assertEqual(border["fieldType"], "double")
        self.assertEqual(border["default"], 0.0)
        self.assertEqual(self.prop("LayoutComponentStyle", "linkCornerRadius")["default"], True)

    def test_solid_color_default(self):
        color = self.prop("SolidColor", "colorValue")
        self.assertEqual(color["fieldType"], "color")
        self.assertEqual(color["default"], 0xFF747474)


class OutputTest(unittest.TestCase):
    def test_rendering_is_deterministic(self):
        first = schema_extract.render(schema_extract.extract_schema(HEADERS_DIR))
        second = schema_extract.render(schema_extract.extract_schema(HEADERS_DIR))
        self.assertEqual(first, second)
        self.assertTrue(first.endswith("\n"))
        self.assertEqual(json.loads(first), schema())

    def test_committed_schema_is_up_to_date(self):
        self.assertTrue(COMMITTED.is_file(), "run tools/schema_extract.py")
        self.assertEqual(
            COMMITTED.read_text(encoding="utf-8"),
            schema_extract.render(schema()),
        )

    def test_output_does_not_depend_on_the_machine(self):
        text = schema_extract.render(schema())
        self.assertNotIn(str(REPO_ROOT), text)
        self.assertNotIn("\\\\", text)


class CommandLineTest(unittest.TestCase):
    def run_tool(self, *args):
        return subprocess.run(
            [sys.executable, "-I", str(SCRIPT), *args],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )

    def test_writes_the_requested_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nested" / "schema.json"
            result = self.run_tool("-o", str(out))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(out.read_text(encoding="utf-8"), COMMITTED.read_text(encoding="utf-8"))

    def test_check_passes_when_the_committed_file_is_current(self):
        result = self.run_tool("--check")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_check_fails_when_the_file_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / "schema.json"
            stale.write_text("{}\n", encoding="utf-8")
            result = self.run_tool("--check", "-o", str(stale))
            self.assertEqual(result.returncode, 1)
            self.assertEqual(stale.read_text(encoding="utf-8"), "{}\n")

    def test_missing_headers_directory_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_tool("--headers", str(Path(tmp) / "nope"))
            self.assertEqual(result.returncode, 1)
            self.assertIn("nope", result.stderr)


if __name__ == "__main__":
    unittest.main()
