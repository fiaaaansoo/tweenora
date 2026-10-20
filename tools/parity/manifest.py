import argparse
import hashlib
import json
import sys
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parent
TOOLS_DIR = PARITY_DIR.parent
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

import twnoinfo

DEFAULT_OUTPUT = PARITY_DIR / "manifest.json"
UNIT_ASSETS = "runtime/tests/unit_tests/assets"
WEB_SCRIPTING = "runtime/tests/web_scripting"
MANIFEST_VERSION = 1

FEATURE_TYPES = {
    "vector": {"Shape"},
    "image": {"ImageAsset"},
    "mesh": {"Mesh"},
    "text": {"Text"},
    "state_machine": {"StateMachine"},
    "layout": {"LayoutComponent"},
    "data_binding": {"ViewModel", "DataBind"},
    "scripting": {"ScriptAsset", "ScriptModuleAsset"},
    "audio": {"AudioAsset"},
    "nested_artboard": {"NestedArtboard"},
}


def collect_files(repo_root=REPO_ROOT):
    root = Path(repo_root)
    found = set()
    for base in (UNIT_ASSETS, WEB_SCRIPTING):
        for path in (root / base).rglob("*"):
            if path.suffix != ".riv" or not path.is_file():
                continue
            found.add(path.relative_to(root).as_posix())
    return sorted(found)


def group_of(rel):
    if rel.startswith(UNIT_ASSETS + "/"):
        inner = rel[len(UNIT_ASSETS) + 1 :]
        return "unit_tests_sub" if "/" in inner else "unit_tests_root"
    if rel.startswith(WEB_SCRIPTING + "/"):
        return "web_scripting"
    raise ValueError(f"location outside the parity scope : {rel}")


def features_of(type_names):
    names = set(type_names)
    features = {
        feature
        for feature, wanted in FEATURE_TYPES.items()
        if names & wanted
    }
    if any(name.startswith("Scripted") for name in names):
        features.add("scripting")
    return sorted(features)


def describe(root, rel, schema):
    data = (Path(root) / rel).read_bytes()
    entry = {
        "path": rel,
        "group": group_of(rel),
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "artboards": [],
        "state_machines": [],
        "features": [],
        "parse_error": None,
    }
    try:
        doc = twnoinfo.read_document(data, schema)
    except twnoinfo.TwnoError as error:
        entry["parse_error"] = str(error)
        return entry
    entry["artboards"] = [board["name"] for board in doc["artboards"]]
    entry["state_machines"] = [
        {"artboard": obj["artboard"], "name": obj["name"]}
        for obj in doc["objects"]
        if obj["typeName"] == "StateMachine"
    ]
    entry["features"] = features_of(obj["typeName"] for obj in doc["objects"])
    return entry


def build_manifest(repo_root=REPO_ROOT):
    schema = twnoinfo.load_schema()
    files = [describe(repo_root, rel, schema) for rel in collect_files(repo_root)]
    groups = {}
    for entry in files:
        groups[entry["group"]] = groups.get(entry["group"], 0) + 1
    return {
        "version": MANIFEST_VERSION,
        "count": len(files),
        "groups": dict(sorted(groups.items())),
        "files": files,
    }


def render(manifest):
    return json.dumps(manifest, indent=1, ensure_ascii=False, sort_keys=True) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Write or check the manifest of the 475 parity files."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if the file on disk differs from a regeneration",
    )
    args = parser.parse_args(argv)
    text = render(build_manifest())
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.is_file() else None
        if current != text:
            print(f"{args.output} is out of date", file=sys.stderr)
            return 1
        return 0
    args.output.write_bytes(text.encode("utf-8"))
    print(f"{args.output}: {json.loads(text)['count']} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
