import functools
import sys
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = GEN_DIR.parent
for folder in (GEN_DIR, TOOLS_DIR):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import twnoinfo
from twno_writer import Document, Obj


@functools.cache
def schema():
    return twnoinfo.load_schema()


def document(**kwargs):
    doc = Document(**kwargs)
    doc.add(Obj("Backboard"))
    return doc


def read(data):
    return twnoinfo.read_document(data, schema())


def decode(doc):
    result = []
    for obj in read(doc.to_bytes())["objects"]:
        props = {p["name"]: p["value"] for p in obj["properties"]}
        result.append((obj["typeName"], props, obj["slot"]))
    return result


def props_of(doc, type_name, which=0):
    matches = [props for name, props, _ in decode(doc) if name == type_name]
    return matches[which]


def slots_of(doc):
    return [slot for _, _, slot in decode(doc)]


def prop(obj, name, default=None):
    return next((p["value"] for p in obj["properties"] if p["name"] == name), default)


def channels(color):
    return tuple((color >> shift) & 255 for shift in (16, 8, 0))
