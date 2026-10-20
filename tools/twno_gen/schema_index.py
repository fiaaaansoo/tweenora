import functools
import json
from pathlib import Path

DEFAULT_SCHEMA = Path(__file__).resolve().parents[2] / "docs" / "schema" / "schema.json"

NO_SLOT_FAMILIES = ("ScrollPhysics",)
SLOT_FAMILIES = ("KeyFrameInterpolator", "UserInput")
SCRIPT_INPUT_PREFIX = "ScriptInput"
ARTBOARD = "Artboard"
COMPONENT = "Component"

FIELD_SIZE_CLASS = {
    "uint": "uint",
    "int": "uint",
    "bool": "uint",
    "id": "uint",
    "string": "string",
    "bytes": "string",
    "double": "double",
    "color": "color",
}


class SchemaIndex:
    def __init__(self, raw):
        self.types = {entry["name"]: entry for entry in raw["types"]}
        self.properties = {entry["key"]: entry for entry in raw["properties"]}
        self.mixins = {entry["name"]: entry for entry in raw["mixins"]}
        self._ancestry = {name: self._chain(name) for name in self.types}
        self._names = {name: self._property_names(name) for name in self.types}

    @classmethod
    def load(cls, path=DEFAULT_SCHEMA):
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    @functools.cache
    def default(cls):
        return cls.load()

    def _chain(self, name):
        chain = []
        while name is not None:
            chain.append(name)
            name = self.types[name]["parent"]
        return tuple(chain)

    def _property_names(self, type_name):
        names = {}
        for ancestor in self._ancestry[type_name]:
            entry = self.types[ancestor]
            keys = list(entry["properties"])
            for mixin in entry["mixins"]:
                keys.extend(self.mixins[mixin]["properties"])
            for key in keys:
                names.setdefault(self.properties[key]["name"], key)
        return names

    def ancestry(self, type_name):
        return self._ancestry[type_name]

    def descends(self, type_name, ancestor):
        return ancestor in self._ancestry[type_name]

    def is_property_name(self, name):
        return any(name in names or name + "Id" in names for names in self._names.values())

    def property_key(self, type_name, property_name):
        return self._names[type_name].get(property_name)

    def property(self, key):
        return self.properties[key]

    def takes_slot(self, type_name, parent_is_artboard):
        if type_name == ARTBOARD:
            return False
        family = self._ancestry[type_name]
        if any(name in family for name in NO_SLOT_FAMILIES):
            return False
        if COMPONENT in family:
            if any(name.startswith(SCRIPT_INPUT_PREFIX) for name in family):
                return not parent_is_artboard
            return True
        return any(name in family for name in SLOT_FAMILIES)
