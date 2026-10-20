import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = GEN_DIR.parent
sys.path.insert(0, str(GEN_DIR))
sys.path.insert(0, str(TOOLS_DIR))

import twno_convert
import twno_writer as w
from twno_writer import Document, Obj

TWNOINFO = TOOLS_DIR / "twnoinfo.py"
CONVERT = TOOLS_DIR / "twno_convert.py"


def build_sample():
    doc = Document()
    doc.add(Obj("Backboard"))
    artboard = doc.add(Obj("Artboard", name="Main", width=400.0, height=300.0))
    group = doc.add(Obj("Node", name="group", parent=artboard, x=10.0, y=20.0))
    shape = doc.add(Obj("Shape", name="body", parent=group))
    doc.add(Obj("Rectangle", name="rect", parent=shape, width=80.0, height=40.0, cornerRadiusTL=6.0))
    fill = doc.add(Obj("Fill", name="paint", parent=shape))
    doc.add(Obj("SolidColor", name="red", parent=fill, colorValue=0xFFFF0000))
    ease = doc.add(Obj("CubicEaseInterpolator", x1=0.25, y1=0.1, x2=0.25, y2=1.0))
    doc.add(Obj("LinearAnimation", name="slide", fps=60, duration=60, loopValue=1))
    doc.add(Obj("KeyedObject", object=group))
    doc.add(Obj("KeyedProperty", propertyKey=13))
    doc.add(Obj("KeyFrameDouble", frame=0, value=10.0, interpolationType=1, interpolator=ease))
    doc.add(Obj("KeyFrameDouble", frame=60, value=200.0, interpolationType=1, interpolator=ease))
    doc.add(Obj("StateMachine", name="machine"))
    flag = doc.add(Obj("StateMachineBool", name="hover", value=False))
    doc.add(Obj("StateMachineTrigger", name="press"))
    doc.add(Obj("StateMachineLayer", name="layer"))
    doc.add(Obj("EntryState"))
    doc.add(Obj("AnyState"))
    doc.add(Obj("ExitState"))
    play = doc.add(Obj("AnimationState", animation="slide"))
    doc.add(Obj("StateTransition", stateTo=play, duration=100))
    doc.add(Obj("TransitionBoolCondition", input=flag, opValue=0))
    second = doc.add(Obj("Artboard", name="Other", width=50.0, height=50.0))
    doc.add(Obj("Ellipse", parent=second, width=10.0, height=10.0))
    return doc


def float32_round(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def run_info(path):
    done = subprocess.run(
        [sys.executable, "-I", str(TWNOINFO), "--json", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(done.stdout)


class TwnoinfoRoundtripTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.doc = build_sample()
        cls.path = Path(cls.folder.name) / "sample.twno"
        cls.doc.write(cls.path)
        cls.info = run_info(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_header(self):
        header = self.info["header"]
        self.assertEqual((header["signature"], header["major"], header["minor"]), ("TWNR", 7, 4))
        self.assertEqual(header["fileId"], 0)
        keys = [entry["key"] for entry in header["table"]]
        self.assertEqual(keys, sorted(set(keys)))

    def test_object_types_and_order(self):
        self.assertEqual(
            [o["typeName"] for o in self.info["objects"]],
            [o.type_name for o in self.doc.objects],
        )

    def test_properties_round_trip(self):
        for read, written in zip(self.info["objects"], self.doc.objects):
            expected = {}
            for key, (field_type, _, raw) in written.entries.items():
                if field_type == "id":
                    continue
                expected[key] = float32_round(raw) if field_type == "double" else raw
            actual = {
                p["key"]: p["value"] for p in read["properties"] if p["fieldType"] != "id"
            }
            self.assertEqual(actual, expected, written)

    def test_slots_match_the_spec_numbering(self):
        for read, written in zip(self.info["objects"], self.doc.objects):
            self.assertEqual(read["slot"], written.slot, written)
            self.assertEqual(read["artboard"], written.artboard, written)

    def test_hierarchy(self):
        main = self.info["artboards"][0]["tree"]
        names = {node["slot"]: node["name"] for node in main}
        parents = {names[n["slot"]]: names.get(n["parentSlot"]) for n in main if n["link"] == "parentId"}
        self.assertEqual(
            parents,
            {"group": "Main", "body": "group", "rect": "body", "paint": "body", "red": "paint"},
        )
        unlinked = [node["typeName"] for node in main if node["link"] not in (None, "parentId")]
        self.assertEqual(unlinked, ["CubicEaseInterpolator"])
        second = self.info["artboards"][1]["tree"]
        self.assertEqual([n["typeName"] for n in second], ["Artboard", "Ellipse"])

    def test_references(self):
        def props(typename, name):
            return [
                p["value"]
                for obj in self.info["objects"]
                if obj["typeName"] == typename
                for p in obj["properties"]
                if p["name"] == name
            ]

        group = next(o for o in self.doc.objects if o.name == "group")
        ease = next(o for o in self.doc.objects if o.type_name == "CubicEaseInterpolator")
        self.assertEqual(props("KeyedObject", "objectId"), [group.slot])
        self.assertEqual(props("KeyFrameDouble", "interpolatorId"), [ease.slot, ease.slot])
        self.assertEqual(props("AnimationState", "animationId"), [0])
        self.assertEqual(props("StateTransition", "stateToId"), [3])
        self.assertEqual(props("TransitionBoolCondition", "inputId"), [0])

    def test_riv_reads_the_same(self):
        riv = Path(self.folder.name) / "sample.riv"
        self.doc.write(riv)
        info = run_info(riv)
        self.assertEqual(info["header"]["signature"], "RIVE")
        self.assertEqual(info["objects"], self.info["objects"])


class ConvertRoundtripTest(unittest.TestCase):
    def test_riv_twno_riv_is_lossless(self):
        doc = build_sample()
        riv = doc.to_bytes(b"RIVE")
        twno = doc.to_bytes(b"TWNR")
        self.assertEqual(twno_convert.riv_to_twno(riv), twno)
        self.assertEqual(twno_convert.twno_to_riv(twno), riv)
        self.assertEqual(twno_convert.twno_to_riv(twno_convert.riv_to_twno(riv)), riv)

    def test_command_line_conversion(self):
        doc = build_sample()
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "a.riv"
            doc.write(source)
            subprocess.run([sys.executable, "-I", str(CONVERT), str(source)], check=True)
            self.assertEqual((Path(folder) / "a.twno").read_bytes(), doc.to_bytes(b"TWNR"))
            back = Path(folder) / "b.riv"
            subprocess.run(
                [sys.executable, "-I", str(CONVERT), str(Path(folder) / "a.twno"), "-o", str(back)],
                check=True,
            )
            self.assertEqual(back.read_bytes(), source.read_bytes())


class SampleDeterminismTest(unittest.TestCase):
    def test_two_builds_are_identical(self):
        self.assertEqual(build_sample().to_bytes(), build_sample().to_bytes())


if __name__ == "__main__":
    unittest.main()
