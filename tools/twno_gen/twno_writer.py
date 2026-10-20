import math
import re
import struct
from pathlib import Path

from schema_index import FIELD_SIZE_CLASS, SchemaIndex

SIGNATURES = {"twno": b"TWNR", "riv": b"RIVE"}
SUFFIXES = {".twno": b"TWNR", ".riv": b"RIVE"}
MAJOR_VERSION = 7
DEFAULT_MINOR_VERSION = 4
EMPTY_ID = 0xFFFFFFFF
UINT32_MAX = 2**32 - 1
UINT64_MAX = 2**64 - 1
INT31_MAX = 2**31 - 1
INT32_MIN = -(2**31)
EXTENSION_KEYS = range(50000, 60000)
SIZE_CLASS_CODES = {"uint": 0, "string": 1, "double": 2, "color": 3}
TABLE_MODES = ("used", "minimal")
HEX_COLOR = re.compile(r"#([0-9a-fA-F]{6})")

COMPONENT = "component"
ANIMATION = "animation"
STATE = "state"
INPUT = "input"
STATE_MACHINE = "statemachine"
ARTBOARD = "artboard"

KIND_TYPES = {
    ANIMATION: "LinearAnimation",
    STATE: "LayerState",
    INPUT: "StateMachineInput",
    STATE_MACHINE: "StateMachine",
    ARTBOARD: "Artboard",
}
KIND_SCOPES = {
    COMPONENT: "artboard",
    ANIMATION: "artboard",
    STATE_MACHINE: "artboard",
    STATE: "layer",
    INPUT: "machine",
    ARTBOARD: "file",
}

BEFORE_SOURCE = True

ID_RULES = {
    5: (COMPONENT, "ContainerComponent", False),
    51: (COMPONENT, None, False),
    69: (COMPONENT, "KeyFrameInterpolator", False),
    92: (COMPONENT, "Node", False),
    95: (COMPONENT, "Bone", False),
    119: (COMPONENT, "Drawable", False),
    121: (COMPONENT, "DrawTarget", False),
    173: (COMPONENT, None, False),
    224: (COMPONENT, None, False),
    272: (COMPONENT, "TextStylePaint", False),
    350: (COMPONENT, "KeyFrameInterpolator", False),
    389: (COMPONENT, "Event", False),
    392: (COMPONENT, "Event", False),
    459: (COMPONENT, "Node", False),
    494: (COMPONENT, "LayoutComponentStyle", False),
    591: (COMPONENT, "KeyFrameInterpolator", False),
    149: (ANIMATION, None, False),
    165: (ANIMATION, None, BEFORE_SOURCE),
    151: (STATE, None, False),
    155: (INPUT, None, BEFORE_SOURCE),
    167: (INPUT, "StateMachineNumber", BEFORE_SOURCE),
    168: (INPUT, "StateMachineNumber", BEFORE_SOURCE),
    227: (INPUT, None, BEFORE_SOURCE),
    236: (STATE_MACHINE, None, False),
    197: (ARTBOARD, None, False),
    858: (ARTBOARD, None, False),
    876: (ARTBOARD, None, False),
}

INPUT_TYPE_FOR_SOURCE = {
    "TransitionBoolCondition": "StateMachineBool",
    "TransitionNumberCondition": "StateMachineNumber",
    "TransitionTriggerCondition": "StateMachineTrigger",
    "ListenerBoolChange": "StateMachineBool",
    "ListenerNumberChange": "StateMachineNumber",
    "ListenerTriggerChange": "StateMachineTrigger",
}


class WriteError(ValueError):
    pass


class RawId:
    def __init__(self, value):
        self.value = varuint_checked(value, UINT32_MAX, "RawId")


class _NoReference:
    def __repr__(self):
        return "NONE"


NONE = _NoReference()


def is_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def varuint_checked(value, limit, what):
    if not is_integer(value):
        raise WriteError(f"{what}: expected an integer, got {value!r}")
    if not 0 <= value <= limit:
        raise WriteError(f"{what}: {value} is outside 0..{limit}")
    return value


def varuint(value):
    value = varuint_checked(value, UINT64_MAX, "varuint")
    out = bytearray()
    while True:
        low = value & 0x7F
        value >>= 7
        if value:
            out.append(low | 0x80)
        else:
            out.append(low)
            return bytes(out)


def signed_varint(value):
    if not is_integer(value):
        raise WriteError(f"int: expected an integer, got {value!r}")
    if not INT32_MIN <= value <= INT31_MAX:
        raise WriteError(f"int: {value} is outside {INT32_MIN}..{INT31_MAX}")
    return varuint((value << 1) ^ (value >> 31))


def float32(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WriteError(f"double: expected a number, got {value!r}")
    try:
        number = float(value)
    except OverflowError:
        raise WriteError(f"double: {value!r} does not fit in a float32") from None
    if not math.isfinite(number):
        raise WriteError(f"double: {value!r} is not finite")
    try:
        return struct.pack("<f", number)
    except OverflowError:
        raise WriteError(f"double: {value!r} does not fit in a float32") from None


def color_word(value):
    return varuint_checked(value, UINT32_MAX, "color").to_bytes(4, "little")


def argb(alpha, red, green, blue):
    for channel in (alpha, red, green, blue):
        varuint_checked(channel, 255, "color channel")
    return (alpha << 24) | (red << 16) | (green << 8) | blue


def rgb(value, alpha=255):
    if isinstance(value, str):
        match = HEX_COLOR.fullmatch(value)
        if match is None:
            raise WriteError(f"color: {value!r} is not #RRGGBB")
        value = int(match.group(1), 16)
    varuint_checked(value, 0xFFFFFF, "rgb")
    varuint_checked(alpha, 255, "alpha")
    return (alpha << 24) | value


def string_value(value):
    if not isinstance(value, str):
        raise WriteError(f"string: expected str, got {value!r}")
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        raise WriteError("string: not encodable as UTF-8") from None
    return varuint(len(encoded)) + encoded


def bytes_value(value):
    if not isinstance(value, (bytes, bytearray)):
        raise WriteError(f"bytes: expected bytes, got {value!r}")
    return varuint(len(value)) + bytes(value)


def bool_value(value):
    if not isinstance(value, bool):
        raise WriteError(f"bool: expected bool, got {value!r}")
    return b"\x01" if value else b"\x00"


def uint_value(value):
    return varuint(varuint_checked(value, UINT32_MAX, "uint"))


ENCODERS = {
    "uint": uint_value,
    "int": signed_varint,
    "bool": bool_value,
    "double": float32,
    "string": string_value,
    "bytes": bytes_value,
    "color": color_word,
}


class Obj:
    def __init__(self, type_name, **props):
        index = SchemaIndex.default()
        entry = index.types.get(type_name)
        if entry is None:
            raise WriteError(f"unknown type {type_name!r}")
        if entry["abstract"]:
            raise WriteError(f"abstract type {type_name!r} cannot be instantiated")
        self.type_name = type_name
        self.type_key = entry["key"]
        self.props = props
        self.document = None
        self.entries = None
        self.artboard = None
        self.slot = None
        self.index = None
        self.context = None
        self.order = None
        self.indices = {}

    @property
    def name(self):
        return self.props.get("name")

    def __repr__(self):
        label = f" {self.name!r}" if self.name is not None else ""
        return f"<Obj {self.type_name}{label}>"


class Document:
    def __init__(self, minor=DEFAULT_MINOR_VERSION, file_id=0, table="used"):
        self.minor = varuint_checked(minor, INT31_MAX, "minor version")
        self.file_id = varuint_checked(file_id, UINT64_MAX, "file id")
        if table not in TABLE_MODES:
            raise WriteError(f"table must be one of {TABLE_MODES}, got {table!r}")
        self.table = table
        self.index = SchemaIndex.default()
        self.objects = []
        self.extension_by_key = {}
        self.extension_by_name = {}

    def declare_property(self, key, size_class, name):
        if not is_integer(key) or key not in EXTENSION_KEYS:
            raise WriteError(f"extension property key {key!r} is outside 50000..59999")
        if size_class not in SIZE_CLASS_CODES:
            raise WriteError(f"unknown size class {size_class!r}")
        if not isinstance(name, str) or not name:
            raise WriteError("extension property needs a name")
        if key in self.extension_by_key:
            raise WriteError(f"extension property key {key} is already declared")
        if name in self.extension_by_name or self.index.is_property_name(name):
            raise WriteError(f"extension property name {name!r} is already in use")
        self.extension_by_key[key] = (size_class, name)
        self.extension_by_name[name] = key

    def add(self, obj, **props):
        if isinstance(obj, str):
            obj = Obj(obj, **props)
        elif props:
            raise WriteError("properties go in Obj(...) when an Obj is passed")
        if obj.document is not None:
            raise WriteError(f"{obj!r} is already in a document")
        obj.entries = self._compile(obj)
        obj.document = self
        self.objects.append(obj)
        return obj

    def _resolve_name(self, obj, name):
        key = self.index.property_key(obj.type_name, name)
        if key is None:
            key = self.index.property_key(obj.type_name, name + "Id")
        if key is not None:
            return key, self.index.property(key)
        extension = self.extension_by_name.get(name)
        if extension is not None:
            size_class, _ = self.extension_by_key[extension]
            return extension, {"key": extension, "name": name, "fieldType": size_class, "serialized": True,
                               "bitmask": None, "bitField": None, "default": None}
        raise WriteError(f"{obj.type_name}: no property {name!r}")

    def _compile(self, obj):
        entries = {}
        folds = []
        for name, value in obj.props.items():
            key, prop = self._resolve_name(obj, name)
            where = f"{obj.type_name}.{prop['name']}"
            field_type = prop["fieldType"]
            if field_type == "callback":
                raise WriteError(f"{where}: callbacks are never written (not serialized)")
            if prop["bitmask"] or prop["bitField"]:
                folds.append((where, prop, value))
                continue
            if not prop["serialized"]:
                raise WriteError(f"{where}: runtime-only property, not serialized")
            if key in entries:
                raise WriteError(f"{where}: given twice")
            if field_type == "id":
                reference = self._check_reference(where, key, value)
                entries[key] = ("id", reference, reference)
            else:
                entries[key] = (field_type, self._encode(where, field_type, value), value)
        for where, prop, value in folds:
            self._fold(obj, entries, where, prop, value)
        return entries

    def _encode(self, where, field_type, value):
        try:
            return ENCODERS[field_type](value)
        except WriteError as error:
            raise WriteError(f"{where}: {error}") from None

    def _check_reference(self, where, key, value):
        if value is NONE or isinstance(value, RawId):
            return value
        if isinstance(value, (Obj, str)):
            if key not in ID_RULES:
                raise WriteError(f"{where}: no reference kind known for this property, use RawId or NONE")
            return value
        raise WriteError(f"{where}: expected an object, a name, NONE or RawId, got {value!r}")

    def _fold(self, obj, entries, where, prop, value):
        spec = prop["bitmask"] or prop["bitField"]
        storage_key = self.index.property_key(obj.type_name, spec["storage"])
        storage = self.index.property(storage_key)
        field_type = storage["fieldType"]
        if field_type not in ("uint", "color"):
            raise WriteError(f"{where}: storage {spec['storage']} is not an integer")
        base = entries[storage_key][2] if storage_key in entries else storage["default"] or 0
        mask = spec["mask"]
        if prop["bitmask"]:
            if not isinstance(value, bool):
                raise WriteError(f"{where}: expected bool, got {value!r}")
            result = base | mask if value else base & ~mask
        else:
            limit = mask >> spec["offset"]
            varuint_checked(value, limit, where)
            result = (base & ~mask) | (value << spec["offset"])
        entries[storage_key] = (field_type, ENCODERS[field_type](result), result)

    def _artboard_groups(self):
        groups = []
        for obj in self.objects:
            if obj.type_name == "Artboard":
                groups.append([obj])
            elif groups:
                groups[-1].append(obj)
        return groups

    def _layout(self):
        index = self.index
        groups = self._artboard_groups()
        artboards = 0
        state = None
        seen_backboard = False
        for position, obj in enumerate(self.objects):
            obj.artboard = obj.slot = obj.index = None
            obj.order = position
            obj.indices = {}
            obj.context = None
        for obj in self.objects:
            family = index.ancestry(obj.type_name)
            if obj.type_name == "Backboard":
                seen_backboard = True
            if obj.type_name == "Artboard":
                if not seen_backboard:
                    raise WriteError("an Artboard needs a Backboard before it")
                state = {"artboard": artboards, "slots": 1, "animations": 0, "machines": 0,
                         "layer": None, "layers": 0, "states": 0, "machine": None, "inputs": 0}
                obj.artboard = artboards
                obj.slot = 0
                obj.indices[COMPONENT] = 0
                obj.indices[ARTBOARD] = obj.index = artboards
                artboards += 1
                obj.context = dict(state)
                continue
            if state is None:
                continue
            obj.artboard = state["artboard"]
            if obj.type_name == "StateMachine":
                state["machine"] = state["machines"]
                obj.indices[STATE_MACHINE] = obj.index = state["machines"]
                state["machines"] += 1
                state["inputs"] = 0
                state["layer"] = None
            if obj.type_name == "LinearAnimation":
                obj.indices[ANIMATION] = obj.index = state["animations"]
                state["animations"] += 1
            if obj.type_name == "StateMachineLayer":
                if state["machine"] is None:
                    raise WriteError(f"{obj!r} comes before any state machine")
                state["layer"] = state["layers"]
                state["layers"] += 1
                state["states"] = 0
            obj.context = dict(state)
            if "LayerState" in family:
                if state["layer"] is None:
                    raise WriteError(f"{obj!r} comes before any state machine layer")
                obj.indices[STATE] = obj.index = state["states"]
                state["states"] += 1
            if "StateMachineInput" in family:
                if state["machine"] is None:
                    raise WriteError(f"{obj!r} comes before any state machine")
                obj.indices[INPUT] = obj.index = state["inputs"]
                state["inputs"] += 1
            if index.takes_slot(obj.type_name, self._parent_is_artboard(obj, groups[state["artboard"]])):
                obj.slot = state["slots"]
                obj.indices[COMPONENT] = state["slots"]
                state["slots"] += 1

    def _parent_is_artboard(self, obj, group):
        key = self.index.property_key(obj.type_name, "parentId")
        entry = obj.entries.get(key) if key is not None else None
        if entry is None:
            return True
        value = entry[2]
        if isinstance(value, Obj):
            return value.type_name == "Artboard"
        if isinstance(value, RawId):
            return value.value == 0
        if isinstance(value, str):
            named = [o for o in group if o.name == value and o is not obj]
            return len(named) == 1 and named[0].type_name == "Artboard"
        return False

    def _expected_type(self, key, source):
        kind, expected, _ = ID_RULES[key]
        if kind == INPUT:
            for name in self.index.ancestry(source.type_name):
                if name in INPUT_TYPE_FOR_SOURCE:
                    return INPUT_TYPE_FOR_SOURCE[name]
        return expected

    def _target_matches(self, kind, expected, target):
        if kind != COMPONENT and not self.index.descends(target.type_name, KIND_TYPES[kind]):
            return False
        return expected is None or self.index.descends(target.type_name, expected)

    def _scope_token(self, kind, obj):
        scope = KIND_SCOPES[kind]
        if scope == "file":
            return 0
        if obj.context is None or obj.context[scope] is None:
            return None
        token = obj.context[scope]
        return token if scope == "artboard" else (obj.context["artboard"], token)

    def _resolve_reference(self, source, where, key, value):
        kind, _, before_source = ID_RULES[key]
        expected = self._expected_type(key, source)
        scope = KIND_SCOPES[kind]
        source_token = self._scope_token(kind, source)
        if scope != "file" and source_token is None:
            raise WriteError(f"{where}: {source!r} is outside any {scope} that could hold the target")
        if isinstance(value, Obj):
            if value.document is not self:
                raise WriteError(f"{where}: {value!r} is not in this document")
            target = value
        else:
            found = [
                o for o in self.objects
                if o.name == value and kind in o.indices and self._target_matches(kind, expected, o)
                and self._scope_token(kind, o) == source_token
            ]
            if not found:
                raise WriteError(f"{where}: no {kind} named {value!r}")
            if len(found) > 1:
                raise WriteError(f"{where}: name {value!r} is ambiguous")
            target = found[0]
        if not self._target_matches(kind, expected, target):
            wanted = expected or KIND_TYPES.get(kind, "an object")
            raise WriteError(f"{where}: {target!r} is not a {wanted}")
        if kind not in target.indices:
            raise WriteError(f"{where}: {target!r} has no {kind} number")
        if scope != "file" and self._scope_token(kind, target) != source_token:
            raise WriteError(f"{where}: {target!r} belongs to another {scope}")
        if before_source and target.order >= source.order:
            raise WriteError(f"{where}: {target!r} must be written before {source!r}")
        return target.indices[kind]

    def _encode_object(self, obj):
        out = bytearray(varuint(obj.type_key))
        for key in sorted(obj.entries):
            field_type, payload, _ = obj.entries[key]
            out += varuint(key)
            if field_type != "id":
                out += payload
                continue
            where = f"{obj.type_name}.{self.index.property(key)['name']}"
            if payload is NONE:
                out += varuint(EMPTY_ID)
            elif isinstance(payload, RawId):
                out += varuint(payload.value)
            else:
                out += varuint(self._resolve_reference(obj, where, key, payload))
        out += b"\x00"
        return bytes(out)

    def _table(self):
        classes = {}
        for obj in self.objects:
            for key, (field_type, _, _) in obj.entries.items():
                if key in self.extension_by_key:
                    classes[key] = self.extension_by_key[key][0]
                elif self.table == "used":
                    classes[key] = FIELD_SIZE_CLASS[field_type]
        for key, (size_class, _) in self.extension_by_key.items():
            classes[key] = size_class
        keys = sorted(classes)
        out = bytearray()
        for key in keys:
            out += varuint(key)
        out += b"\x00"
        for start in range(0, len(keys), 4):
            word = 0
            for offset, key in enumerate(keys[start:start + 4]):
                word |= SIZE_CLASS_CODES[classes[key]] << (2 * offset)
            out += struct.pack("<I", word)
        return bytes(out)

    def to_bytes(self, signature=b"TWNR"):
        if isinstance(signature, str):
            signature = SIGNATURES.get(signature.lower())
        if signature not in SIGNATURES.values():
            raise WriteError("signature must be TWNR or RIVE")
        self._layout()
        body = b"".join(self._encode_object(obj) for obj in self.objects)
        header = signature + varuint(MAJOR_VERSION) + varuint(self.minor) + varuint(self.file_id)
        return header + self._table() + body

    def write(self, path):
        path = Path(path)
        signature = SUFFIXES.get(path.suffix.lower())
        if signature is None:
            raise WriteError(f"{path}: extension must be .twno or .riv")
        data = self.to_bytes(signature)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return data
