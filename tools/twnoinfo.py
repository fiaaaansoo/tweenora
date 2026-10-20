import argparse
import json
import math
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = REPO_ROOT / "docs" / "schema" / "schema.json"
SIGNATURES = (b"TWNR", b"RIVE")
SUPPORTED_MAJOR = 7
MAX_PROPERTY_KEY = 65535
MAX_VARUINT_BYTES = 10
EMPTY_ID = 0xFFFFFFFF
SIZE_CLASSES = ("uint", "string", "double", "color")
ARTBOARD = "Artboard"
PARENT_ID = "parentId"
NAME = "name"
SLOT_FAMILIES = ("KeyFrameInterpolator", "UserInput")
NO_SLOT_COMPONENTS = ("ScrollPhysics",)
LINK_MARKS = {"none": " (no parentId)", "invalid": " (invalid parentId)"}


class TwnoError(Exception):
    def __init__(self, message, offset):
        super().__init__(message)
        self.offset = offset


class Reader:
    def __init__(self, data):
        self.data = data
        self.pos = 0

    def at_end(self):
        return self.pos >= len(self.data)

    def raw(self, count):
        if count > len(self.data) - self.pos:
            missing = count - (len(self.data) - self.pos)
            raise TwnoError(f"{missing} byte(s) missing before the end of the file", self.pos)
        chunk = self.data[self.pos : self.pos + count]
        self.pos += count
        return chunk

    def varuint(self, bits=64):
        start = self.pos
        value = 0
        for index in range(MAX_VARUINT_BYTES):
            if self.pos >= len(self.data):
                raise TwnoError("varuint truncated by the end of the file", start)
            byte = self.data[self.pos]
            self.pos += 1
            value |= (byte & 0x7F) << (7 * index)
            if not byte & 0x80:
                if value >= 1 << bits:
                    raise TwnoError(f"varuint of more than {bits} bits", start)
                return value
        raise TwnoError("varuint of more than 10 bytes", start)

    def uint32(self):
        return struct.unpack("<I", self.raw(4))[0]

    def float32(self):
        return struct.unpack("<f", self.raw(4))[0]

    def length_prefixed(self):
        start = self.pos
        length = self.varuint()
        remaining = len(self.data) - self.pos
        if length > remaining:
            raise TwnoError(
                f"{length} bytes announced but only {remaining} remain", start
            )
        return self.raw(length)

    def string(self):
        return self.length_prefixed().decode("utf-8", errors="replace")

    def bytes_value(self):
        return {"bytes": len(self.length_prefixed())}


class Schema:
    def __init__(self, raw):
        self.types = {t["key"]: t for t in raw["types"]}
        self.by_name = {t["name"]: t for t in raw["types"]}
        self.properties = {p["key"]: p for p in raw["properties"]}
        self.families = {key: self.ancestry(t["name"]) for key, t in self.types.items()}

    def ancestry(self, name):
        names = []
        while name is not None:
            names.append(name)
            name = self.by_name[name]["parent"]
        return frozenset(names)

    def type_name(self, key):
        entry = self.types.get(key)
        return entry["name"] if entry else f"unknown({key})"

    def property_name(self, key):
        entry = self.properties.get(key)
        return entry["name"] if entry else f"unknown({key})"

    def takes_slot(self, key, parent_id):
        entry = self.types.get(key)
        if entry is None or entry["abstract"]:
            return True
        if entry["name"] == ARTBOARD:
            return False
        family = self.families[key]
        if any(name in family for name in NO_SLOT_COMPONENTS):
            return False
        if "Component" in family:
            if any(name.startswith("ScriptInput") for name in family):
                return parent_id not in (None, 0)
            return True
        return any(name in family for name in SLOT_FAMILIES)


def load_schema(path=DEFAULT_SCHEMA):
    return Schema(json.loads(Path(path).read_text(encoding="utf-8")))


def finite(value):
    return value if math.isfinite(value) else str(value)


def decode_by_type(reader, field_type):
    if field_type == "uint" or field_type == "id":
        return reader.varuint(32)
    if field_type == "int":
        raw = reader.varuint(32)
        return (raw >> 1) ^ -(raw & 1)
    if field_type == "bool":
        return reader.raw(1)[0] == 1
    if field_type == "double":
        return finite(reader.float32())
    if field_type == "string":
        return reader.string()
    if field_type == "bytes":
        return reader.bytes_value()
    return reader.uint32()


def decode_by_size_class(reader, size_class):
    if size_class == "uint":
        return reader.varuint()
    if size_class == "string":
        return reader.string()
    if size_class == "double":
        return finite(reader.float32())
    return reader.uint32()


def read_header(reader):
    signature = reader.raw(4) if len(reader.data) >= 4 else None
    if signature not in SIGNATURES:
        raise TwnoError("missing or unknown signature (TWNR or RIVE expected)", 0)
    major = reader.varuint(31)
    if major != SUPPORTED_MAJOR:
        raise TwnoError(
            f"unsupported major version {major} ({SUPPORTED_MAJOR} expected)", 4
        )
    minor = reader.varuint(31)
    file_id = reader.varuint()
    keys = []
    while True:
        key = reader.varuint(31)
        if key == 0:
            break
        keys.append(key)
    table = []
    for start in range(0, len(keys), 4):
        word = reader.uint32()
        for offset, key in enumerate(keys[start : start + 4]):
            table.append({"key": key, "sizeClass": SIZE_CLASSES[(word >> (2 * offset)) & 3]})
    return {
        "signature": signature.decode("ascii"),
        "major": major,
        "minor": minor,
        "fileId": file_id,
        "table": table,
    }


def read_object(reader, schema, table):
    offset = reader.pos
    type_key = reader.varuint(31)
    properties = []
    while True:
        property_start = reader.pos
        key = reader.varuint()
        if key == 0:
            break
        if key > MAX_PROPERTY_KEY:
            raise TwnoError(f"property key {key} above {MAX_PROPERTY_KEY}", property_start)
        known = schema.properties.get(key)
        if known is not None and known["fieldType"] != "callback":
            field_type = known["fieldType"]
            value = decode_by_type(reader, field_type)
        elif key in table:
            field_type = table[key]
            value = decode_by_size_class(reader, field_type)
        else:
            raise TwnoError(
                f"property {key} (object of type {type_key}) unknown to both the schema and the table",
                property_start,
            )
        properties.append(
            {
                "key": key,
                "name": schema.property_name(key),
                "fieldType": field_type,
                "value": value,
            }
        )
    return {
        "offset": offset,
        "type": type_key,
        "typeName": schema.type_name(type_key),
        "properties": properties,
    }


def property_value(obj, name):
    found = None
    for prop in obj["properties"]:
        if prop["name"] == name:
            found = prop["value"]
    return found


def resolve_parents(members):
    parents, links = {}, {}
    for slot, obj in members.items():
        if slot == 0:
            continue
        value = property_value(obj, PARENT_ID)
        if value is None:
            parents[slot], links[slot] = 0, "none"
        elif value in members and value != slot:
            parents[slot], links[slot] = value, "parentId"
        else:
            parents[slot], links[slot] = 0, "invalid"
    state = {0: 2}
    for start in parents:
        path = []
        current = start
        while current not in state:
            state[current] = 1
            path.append(current)
            current = parents[current]
        if state[current] == 1:
            parents[current], links[current] = 0, "invalid"
        for slot in path:
            state[slot] = 2
    return parents, links


def build_tree(members):
    parents, links = resolve_parents(members)
    children = {slot: [] for slot in members}
    for slot in sorted(parents):
        children[parents[slot]].append(slot)
    tree = []
    stack = [(0, None, 0)]
    while stack:
        slot, parent, depth = stack.pop()
        obj = members[slot]
        tree.append(
            {
                "slot": slot,
                "typeName": obj["typeName"],
                "name": obj["name"],
                "parentSlot": parent,
                "depth": depth,
                "link": links.get(slot),
            }
        )
        stack.extend((child, slot, depth + 1) for child in reversed(children[slot]))
    return tree


def read_document(data, schema):
    reader = Reader(data)
    header = read_header(reader)
    table = {entry["key"]: entry["sizeClass"] for entry in header["table"]}
    objects, global_objects, scopes = [], [], []
    current = None
    while not reader.at_end():
        obj = read_object(reader, schema, table)
        objects.append(obj)
        obj["name"] = property_value(obj, NAME)
        obj["slot"] = None
        obj["artboard"] = None
        if obj["typeName"] == ARTBOARD:
            current = {"index": len(scopes), "members": {0: obj}, "others": []}
            scopes.append(current)
            obj["slot"] = 0
            obj["artboard"] = current["index"]
        elif current is None:
            global_objects.append(obj)
        else:
            obj["artboard"] = current["index"]
            if schema.takes_slot(obj["type"], property_value(obj, PARENT_ID)):
                obj["slot"] = len(current["members"])
                current["members"][obj["slot"]] = obj
            else:
                current["others"].append(obj)
    return {
        "header": header,
        "globalObjects": global_objects,
        "artboards": [
            {
                "index": scope["index"],
                "name": scope["members"][0]["name"],
                "tree": build_tree(scope["members"]),
                "others": scope["others"],
            }
            for scope in scopes
        ],
        "objects": objects,
    }


def escape_char(char):
    if char.isprintable() or char == " ":
        return char
    code = ord(char)
    return f"\\x{code:02x}" if code < 256 else f"\\u{code:04x}"


def printable(text):
    return "".join(escape_char(char) for char in text)


def format_value(prop):
    value = prop["value"]
    if prop["fieldType"] == "id" and value == EMPTY_ID:
        return "none"
    if prop["fieldType"] == "color" and isinstance(value, int):
        return f"0x{value:08X}"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(value, ".9g")
    if isinstance(value, dict):
        return f"<{value['bytes']} bytes>"
    if isinstance(value, str):
        return printable(value)
    return str(value)


def label(type_name, name, slot=None):
    text = type_name if name is None else f'{type_name} "{printable(name)}"'
    return text if slot is None else f"{text} [{slot}]"


def render_text(doc, file_name, properties=False):
    header = doc["header"]
    lines = [
        f"File: {printable(file_name)}",
        f"Signature: {header['signature']}",
        f"Version: {header['major']}.{header['minor']}",
        f"File id: {header['fileId']}",
        f"Property table: {len(header['table'])} key(s)",
    ]
    lines += [f"  {entry['key']}  {entry['sizeClass']}" for entry in header["table"]]
    lines.append(
        f"Objects: {len(doc['objects'])} "
        f"({len(doc['globalObjects'])} global, {len(doc['artboards'])} artboard(s))"
    )

    def add_properties(obj, indent):
        if properties:
            lines.extend(
                f"{indent}    - {p['name']} = {format_value(p)}" for p in obj["properties"]
            )

    if doc["globalObjects"]:
        lines += ["", "Global objects"]
        for obj in doc["globalObjects"]:
            lines.append("  " + label(obj["typeName"], obj["name"]))
            add_properties(obj, "  ")
    members = {
        (obj["artboard"], obj["slot"]): obj for obj in doc["objects"] if obj["slot"] is not None
    }
    for artboard in doc["artboards"]:
        lines.append("")
        for node in artboard["tree"]:
            obj = members[(artboard["index"], node["slot"])]
            indent = "  " * node["depth"]
            if node["depth"] == 0:
                lines.append(label(node["typeName"], node["name"]) + f" (object {node['slot']})")
            else:
                lines.append(
                    indent
                    + label(node["typeName"], node["name"], node["slot"])
                    + LINK_MARKS.get(node["link"], "")
                )
            add_properties(obj, indent)
        if artboard["others"]:
            lines.append("  Other objects")
            for obj in artboard["others"]:
                lines.append("    " + label(obj["typeName"], obj["name"]))
                add_properties(obj, "    ")
    return "\n".join(lines) + "\n"


def render_json(docs):
    if isinstance(docs, dict):
        docs = [docs]
    payload = docs[0] if len(docs) == 1 else docs
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def build_parser():
    parser = argparse.ArgumentParser(
        description="Show the header, property table and object tree of .twno and .riv files."
    )
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument(
        "--json",
        action="store_true",
        help="write JSON instead of text (an array when there are several files)",
    )
    parser.add_argument(
        "-p", "--properties", action="store_true", help="list the properties of each object"
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", newline="\n")
    try:
        schema = load_schema(args.schema)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(f"error: schema {args.schema}: {error}", file=sys.stderr)
        return 1
    status = 0
    documents = []
    for path in args.files:
        try:
            documents.append((str(path), read_document(path.read_bytes(), schema)))
        except OSError as error:
            print(f"error: {path}: {error.strerror or error}", file=sys.stderr)
            status = 1
        except TwnoError as error:
            print(f"error: {path}: {error} (byte {error.offset})", file=sys.stderr)
            status = 1
    if args.json:
        if documents:
            sys.stdout.write(render_json([{"file": name, **doc} for name, doc in documents]))
    else:
        sys.stdout.write(
            "\n".join(render_text(doc, name, args.properties) for name, doc in documents)
        )
    return status


if __name__ == "__main__":
    sys.exit(main())
