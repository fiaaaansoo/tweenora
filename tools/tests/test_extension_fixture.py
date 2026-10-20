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

import extension_fixture
import twnoinfo

SCRIPT = TOOLS_DIR / "extension_fixture.py"
CPP_TEST = (
    REPO_ROOT
    / "runtime"
    / "tests"
    / "unit_tests"
    / "runtime"
    / "extension_keys_test.cpp"
)
EXTENSION_RANGE = range(50000, 60000)
SCHEMA_PATH = REPO_ROOT / "docs" / "schema" / "schema.json"


def read(data):
    return twnoinfo.read_document(data, twnoinfo.load_schema())


def named(doc):
    return {o["name"]: o for o in doc["objects"] if o["name"] is not None}


class GeneratorTest(unittest.TestCase):
    def test_every_variant_is_a_twno_file_the_reader_accepts(self):
        for variant in ("declared", "bare-object"):
            with self.subTest(variant=variant):
                doc = read(extension_fixture.build(variant))
                self.assertEqual(doc["header"]["signature"], "TWNR")
                self.assertEqual(len(doc["artboards"]), 1)

    def test_declared_variant_lists_every_extension_property_in_the_table(self):
        doc = read(extension_fixture.build("declared"))
        self.assertEqual(
            [(e["key"], e["sizeClass"]) for e in doc["header"]["table"]],
            [(50001, "uint"), (50002, "string"), (50003, "double"), (50004, "color")],
        )

    def test_extension_keys_are_in_the_reserved_range_and_free_in_the_schema(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        used = {t["key"] for t in schema["types"]} | {p["key"] for p in schema["properties"]}
        keys = extension_fixture.EXTENSION_KEYS
        self.assertTrue(keys)
        for key in keys:
            with self.subTest(key=key):
                self.assertIn(key, EXTENSION_RANGE)
                self.assertNotIn(key, used)

    def test_extension_object_sits_among_components_and_takes_a_slot(self):
        doc = read(extension_fixture.build("declared"))
        objects = named(doc)
        extension = next(o for o in doc["objects"] if o["typeName"] == "unknown(50000)")
        self.assertEqual(extension["slot"], 2)
        self.assertEqual(objects["b"]["slot"], 3)
        self.assertEqual(objects["c"]["slot"], 4)
        parent = next(p["value"] for p in objects["c"]["properties"] if p["name"] == "parentId")
        self.assertEqual(parent, objects["b"]["slot"])

    def test_official_object_carries_an_extension_property(self):
        doc = read(extension_fixture.build("declared"))
        names = [p["name"] for p in named(doc)["a"]["properties"]]
        self.assertIn("unknown(50001)", names)
        self.assertIn("x", names)

    def test_bare_variant_has_an_object_without_properties_and_no_table(self):
        doc = read(extension_fixture.build("bare-object"))
        self.assertEqual(doc["header"]["table"], [])
        extension = next(o for o in doc["objects"] if o["typeName"] == "unknown(50000)")
        self.assertEqual(extension["properties"], [])
        self.assertEqual(extension["slot"], 2)

    def test_undeclared_variant_is_rejected_by_the_reader(self):
        with self.assertRaises(twnoinfo.TwnoError) as caught:
            read(extension_fixture.build("undeclared-property"))
        self.assertIn("50001", str(caught.exception))

    def test_unknown_variant_is_an_error(self):
        with self.assertRaises(ValueError):
            extension_fixture.build("nope")

    def test_output_is_deterministic(self):
        for variant in extension_fixture.VARIANTS:
            self.assertEqual(extension_fixture.build(variant), extension_fixture.build(variant))


class CppArrayTest(unittest.TestCase):
    def test_array_format(self):
        text = extension_fixture.cpp_array("kBytes", b"\x00\x01\xff")
        self.assertIn("static const uint8_t kBytes[] = {", text)
        self.assertIn("0x00, 0x01, 0xff", text)

    def test_committed_cpp_test_embeds_the_generated_bytes(self):
        self.assertTrue(CPP_TEST.is_file(), "run tools/extension_fixture.py --cpp")
        source = CPP_TEST.read_text(encoding="utf-8")
        for variant in extension_fixture.VARIANTS:
            name = extension_fixture.cpp_name(variant)
            with self.subTest(variant=variant):
                expected = extension_fixture.cpp_array(name, extension_fixture.build(variant))
                self.assertIn(expected, source)

    def test_cpp_test_has_no_other_embedded_array(self):
        source = CPP_TEST.read_text(encoding="utf-8")
        arrays = re.findall(r"static const uint8_t (\w+)\[\]", source)
        self.assertEqual(
            sorted(arrays),
            sorted(extension_fixture.cpp_name(v) for v in extension_fixture.VARIANTS),
        )


class CommandLineTest(unittest.TestCase):
    def run_tool(self, *args):
        return subprocess.run(
            [sys.executable, "-I", str(SCRIPT), *args],
            capture_output=True,
            cwd=REPO_ROOT,
        )

    def test_writes_the_binary_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "nested" / "ext.twno"
            result = self.run_tool("declared", "-o", str(out))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(out.read_bytes(), extension_fixture.build("declared"))

    def test_cpp_option_prints_the_arrays(self):
        result = self.run_tool("--cpp")
        self.assertEqual(result.returncode, 0, result.stderr)
        text = result.stdout.decode("utf-8")
        for variant in extension_fixture.VARIANTS:
            self.assertIn(extension_fixture.cpp_name(variant), text)

    def test_check_flag_compares_the_committed_cpp_test(self):
        result = self.run_tool("--check")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_check_flag_fails_when_the_cpp_test_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / "t.cpp"
            stale.write_text("// nothing\n", encoding="utf-8")
            result = self.run_tool("--check", "--cpp-file", str(stale))
            self.assertEqual(result.returncode, 1)

    def test_unknown_variant_is_a_clean_error(self):
        result = self.run_tool("nope", "-o", "x")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(b"Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
