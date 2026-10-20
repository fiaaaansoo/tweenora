import argparse
import json
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "docs" / "schema" / "schema.json"
CPP_TEST = (
    REPO_ROOT / "runtime" / "tests" / "unit_tests" / "runtime" / "extension_keys_test.cpp"
)
VARIANTS = ("declared", "bare-object", "undeclared-property")
EXTENSION_TYPE = 50000
EXTENSION_UINT = 50001
EXTENSION_STRING = 50002
EXTENSION_DOUBLE = 50003
EXTENSION_COLOR = 50004
EXTENSION_KEYS = (
    EXTENSION_TYPE,
    EXTENSION_UINT,
    EXTENSION_STRING,
    EXTENSION_DOUBLE,
    EXTENSION_COLOR,
)
EXTENSION_RANGE = range(50000, 60000)
TABLE = (
    (EXTENSION_UINT, 0),
    (EXTENSION_STRING, 1),
    (EXTENSION_DOUBLE, 2),
    (EXTENSION_COLOR, 3),
)
BYTES_PER_LINE = 12


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


def load_keys():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    types = {t["name"]: t["key"] for t in schema["types"]}
    properties = {(p["owner"], p["name"]): p["key"] for p in schema["properties"]}
    taken = set(types.values()) | set(properties.values())
    clashes = [key for key in EXTENSION_KEYS if key in taken or key not in EXTENSION_RANGE]
    if clashes:
        raise ValueError(f"extension keys {clashes} are not free in the reserved range")
    return types, properties


def header(table):
    out = bytearray(b"TWNR" + varuint(7) + varuint(4) + varuint(0))
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
    return bytes(out + varuint(0))


def build(variant):
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}, expected one of {VARIANTS}")
    types, properties = load_keys()
    name = properties[("Component", "name")]
    parent_id = properties[("Component", "parentId")]
    node_x = properties[("Node", "x")]
    with_properties = variant != "bare-object"
    table = TABLE if variant == "declared" else ()
    on_node = [(EXTENSION_UINT, varuint(300))] if with_properties else []
    on_extension = (
        [
            (EXTENSION_STRING, string("héllo")),
            (EXTENSION_DOUBLE, struct.pack("<f", 2.5)),
            (EXTENSION_COLOR, struct.pack("<I", 0xFF112233)),
        ]
        if with_properties
        else []
    )
    node = types["Node"]
    return (
        header(table)
        + obj(types["Backboard"])
        + obj(types["Artboard"], (name, string("main")))
        + obj(
            node,
            (name, string("a")),
            (node_x, struct.pack("<f", 1.5)),
            (parent_id, varuint(0)),
            *on_node,
        )
        + obj(EXTENSION_TYPE, *on_extension)
        + obj(node, (name, string("b")), (parent_id, varuint(0)))
        + obj(node, (name, string("c")), (parent_id, varuint(3)))
    )


def cpp_name(variant):
    return "k" + "".join(word.capitalize() for word in variant.split("-"))


def cpp_array(array_name, data):
    lines = []
    for start in range(0, len(data), BYTES_PER_LINE):
        chunk = data[start : start + BYTES_PER_LINE]
        lines.append("    " + ", ".join(f"0x{byte:02x}" for byte in chunk))
    body = ",\n".join(lines)
    return f"static const uint8_t {array_name}[] = {{\n{body}\n}};"


def all_arrays():
    return "\n\n".join(cpp_array(cpp_name(v), build(v)) for v in VARIANTS) + "\n"


def stale_arrays(cpp_file):
    source = Path(cpp_file).read_text(encoding="utf-8") if Path(cpp_file).is_file() else ""
    return [v for v in VARIANTS if cpp_array(cpp_name(v), build(v)) not in source]


def build_parser():
    parser = argparse.ArgumentParser(
        description="Build .twno files that use the Tweenora extension key range (D8)."
    )
    parser.add_argument("variant", nargs="?", choices=VARIANTS)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--cpp", action="store_true", help="print the C++ byte arrays of every variant")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 when the C++ test does not embed the current bytes",
    )
    parser.add_argument("--cpp-file", type=Path, default=CPP_TEST)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.check:
        stale = stale_arrays(args.cpp_file)
        if stale:
            print(f"error: {args.cpp_file} is out of date for {', '.join(stale)}", file=sys.stderr)
            return 1
        return 0
    if args.cpp:
        sys.stdout.write(all_arrays())
        return 0
    if args.variant is None or args.output is None:
        parser.error("give a variant and -o, or use --cpp or --check")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(build(args.variant))
    return 0


if __name__ == "__main__":
    sys.exit(main())
