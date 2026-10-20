import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HEADERS = REPO_ROOT / "runtime" / "include" / "rive" / "generated"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "schema" / "schema.json"
REGISTRY_NAME = "core_registry.hpp"
SCHEMA_VERSION = 1

WIRE_TYPES = {
    "Bool": "bool",
    "Bytes": "bytes",
    "Color": "color",
    "Double": "double",
    "Id": "id",
    "Int": "int",
    "String": "string",
    "Uint": "uint",
}
REGISTRY_SETTERS = {
    "setBool": "bool",
    "setCallback": "callback",
    "setColor": "color",
    "setDouble": "double",
    "setId": "id",
    "setInt": "int",
    "setString": "string",
    "setUint": "uint",
}

CLASS_RE = re.compile(r"^class (\w+)Base\b\s*(?::([^{;]*))?", re.M)
TYPE_KEY_RE = re.compile(r"static const uint16_t typeKey = (\d+);")
PROPERTY_KEY_RE = re.compile(r"static const uint16_t (\w+)PropertyKey = (\d+);")
CASE_RE = re.compile(r"case\s+(\w+)PropertyKey\s*:")
WIRE_TYPE_RE = re.compile(r"Core(\w+)Type::")
SIDECAR_RE = re.compile(r"struct \w+Sidecar\s*\{(.*?)\n\};", re.S)
SIDECAR_FIELD_RE = re.compile(r"^\s+[\w:<> ]+? (\w+) = ([^;]+);", re.M)
REGISTRY_FUNCTION_RE = re.compile(r"^    static [\w:<>*& ]+? (\w+)\(", re.M)
INSTANCE_RE = re.compile(r"return new (\w+)\(\);")
REGISTRY_CASE_RE = re.compile(r"case\s+(\w+)Base::\s*(\w+)PropertyKey\s*:")
FLOAT_RE = re.compile(r"-?\d+\.\d*f?|-?\d+f")
INT_RE = re.compile(r"-?(?:0|[1-9]\d*)u?|0[xX][0-9a-fA-F]+u?")
SHIFT_RE = re.compile(r"1u? << (\d+)")


class SchemaError(Exception):
    pass


def capitalize(name):
    return name[0].upper() + name[1:]


def lower_first(name):
    return name[0].lower() + name[1:]


def parse_literal(expr):
    if expr is None:
        return None
    if FLOAT_RE.fullmatch(expr):
        return float(expr.rstrip("f"))
    if INT_RE.fullmatch(expr):
        return int(expr.rstrip("uU"), 0)
    if expr in ("true", "false"):
        return expr == "true"
    if len(expr) >= 2 and expr[0] == expr[-1] == '"' and "\\" not in expr:
        return expr[1:-1]
    return None


def parse_mask(expr):
    shift = SHIFT_RE.fullmatch(expr)
    if shift:
        return 1 << int(shift.group(1))
    return int(expr.rstrip("uU"), 0)


def wire_types(text):
    found = {}
    cases = list(CASE_RE.finditer(text))
    for index, case in enumerate(cases):
        end = cases[index + 1].start() if index + 1 < len(cases) else len(text)
        block = text[case.end() : end]
        stop = block.find("return true;")
        if stop != -1:
            block = block[:stop]
        wire = WIRE_TYPE_RE.search(block)
        if wire:
            found[case.group(1)] = WIRE_TYPES[wire.group(1)]
    return found


def registry_field_types(path):
    text = Path(path).read_text(encoding="utf-8")
    functions = list(REGISTRY_FUNCTION_RE.finditer(text))
    declared = {}
    for index, function in enumerate(functions):
        if function.group(1) not in REGISTRY_SETTERS:
            continue
        end = (
            functions[index + 1].start()
            if index + 1 < len(functions)
            else len(text)
        )
        field_type = REGISTRY_SETTERS[function.group(1)]
        for case in REGISTRY_CASE_RE.finditer(text[function.end() : end]):
            declared.setdefault(case.groups(), set()).add(field_type)
    resolved = {}
    for key, field_types in declared.items():
        if len(field_types) > 1:
            field_types.discard("uint")
        if len(field_types) != 1:
            raise SchemaError(f"{key}: ambiguous registry types {sorted(field_types)}")
        resolved[key] = next(iter(field_types))
    return resolved


def sidecar_defaults_of(path, text):
    defaults = {}
    for sidecar in SIDECAR_RE.finditer(text):
        for field in SIDECAR_FIELD_RE.finditer(sidecar.group(1)):
            if field.group(1) in defaults:
                raise SchemaError(f"{path}: sidecar field {field.group(1)} declared twice")
            defaults[field.group(1)] = field.group(2)
    return defaults


def default_expression(text, name, sidecar_defaults):
    if name in sidecar_defaults:
        return sidecar_defaults[name]
    member = re.search(
        rf"\n\s+(?!return\b)[\w:<>]+(?: [\w:<>]+)* m_{capitalize(name)}(?: = ([^;]+))?;",
        text,
    )
    return member.group(1) if member else None


def bitmask_of(text, name):
    mask = re.search(rf"static const uint32_t {name}Bitmask = ([^;]+);", text)
    if not mask:
        return None
    storage = re.search(rf"\(m_(\w+) & {name}Bitmask\)", text)
    return {
        "storage": lower_first(storage.group(1)) if storage else None,
        "mask": parse_mask(mask.group(1)),
    }


def bit_field_of(text, name):
    offset = re.search(rf"static const uint32_t {name}BitOffset = (\d+);", text)
    mask = re.search(rf"static const uint32_t {name}FieldMask = ([^;]+);", text)
    if not (offset and mask):
        return None
    colour_storage = re.search(
        rf"uint32_t {name}\(\) const\s*\{{\s*return \(static_cast<uint32_t>\((\w+)\(\)\)",
        text,
    )
    member_storage = re.search(rf"\(m_(\w+) & {name}FieldMask\)", text)
    if colour_storage:
        storage = colour_storage.group(1)
    elif member_storage:
        storage = lower_first(member_storage.group(1))
    else:
        storage = None
    return {
        "storage": storage,
        "offset": int(offset.group(1)),
        "mask": parse_mask(mask.group(1)),
    }


def registry_instantiable_types(path):
    return set(INSTANCE_RE.findall(Path(path).read_text(encoding="utf-8")))


def parse_header(path, repo_root, registry):
    text = path.read_text(encoding="utf-8")
    declaration = CLASS_RE.search(text)
    if not declaration:
        raise SchemaError(f"{path}: no class declaration")
    name = declaration.group(1)
    bases = [
        base.replace("public", "").strip()
        for base in (declaration.group(2) or "").split(",")
        if base.strip()
    ]
    if bases and bases[0].endswith("Base"):
        raise SchemaError(f"{path}: first base {bases[0]} is a mixin")
    parent = bases[0] if bases and bases[0] != "Core" else None
    mixins = [base[: -len("Base")] for base in bases[1:] if base.endswith("Base")]
    type_key = TYPE_KEY_RE.search(text)
    wire = wire_types(text)
    sidecar_defaults = sidecar_defaults_of(path, text)
    properties = []
    for match in PROPERTY_KEY_RE.finditer(text):
        prop_name, key = match.group(1), int(match.group(2))
        expression = default_expression(text, prop_name, sidecar_defaults)
        field_type = wire.get(prop_name) or registry.get((name, prop_name))
        if field_type is None:
            raise SchemaError(f"{path}: cannot type property {prop_name} ({key})")
        properties.append(
            {
                "key": key,
                "name": prop_name,
                "owner": name,
                "fieldType": field_type,
                "serialized": prop_name in wire,
                "default": parse_literal(expression),
                "defaultExpr": expression,
                "bitmask": bitmask_of(text, prop_name),
                "bitField": bit_field_of(text, prop_name),
            }
        )
    try:
        header = path.relative_to(repo_root).as_posix()
    except ValueError:
        header = path.as_posix()
    entry = {
        "name": name,
        "key": int(type_key.group(1)) if type_key else None,
        "parent": parent,
        "mixins": mixins,
        "header": header,
        "properties": [prop["key"] for prop in properties],
    }
    return entry, properties


def extract_schema(headers_dir, repo_root=REPO_ROOT):
    headers_dir = Path(headers_dir)
    if not headers_dir.is_dir():
        raise SchemaError(f"headers directory not found: {headers_dir}")
    registry_path = headers_dir / REGISTRY_NAME
    if not registry_path.is_file():
        raise SchemaError(f"registry not found: {registry_path}")
    registry = registry_field_types(registry_path)
    instantiable = registry_instantiable_types(registry_path)
    types, mixins, properties = [], [], []
    for path in sorted(headers_dir.rglob("*_base.hpp")):
        entry, entry_properties = parse_header(path, Path(repo_root), registry)
        properties.extend(entry_properties)
        if entry["key"] is not None:
            entry["abstract"] = entry["name"] not in instantiable
        if entry["key"] is None:
            mixins.append({k: v for k, v in entry.items() if k not in ("key", "parent", "mixins")})
        else:
            types.append(entry)
    types.sort(key=lambda entry: entry["key"])
    mixins.sort(key=lambda entry: entry["name"])
    properties.sort(key=lambda entry: entry["key"])
    return {
        "schemaVersion": SCHEMA_VERSION,
        "types": types,
        "mixins": mixins,
        "properties": properties,
    }


def render(schema):
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def build_parser():
    parser = argparse.ArgumentParser(
        description="Extract the Tweenora object schema from the generated runtime headers."
    )
    parser.add_argument("--headers", type=Path, default=DEFAULT_HEADERS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare the output file with a fresh extraction instead of writing it",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        text = render(extract_schema(args.headers))
    except SchemaError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.is_file() else None
        if current != text:
            print(f"error: {args.output} is out of date", file=sys.stderr)
            return 1
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
