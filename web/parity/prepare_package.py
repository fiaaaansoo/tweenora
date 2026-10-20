import argparse
import hashlib
import json
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
DEFAULT_TGZ = REPO_ROOT / "web" / "rive-wasm" / "js" / "build" / "pack" / "tweenora-webgl2-0.1.0.tgz"
DEFAULT_DEST = HERE / "pkg"
RUNTIME_FILES = ("rive.js", "rive.wasm", "rive_fallback.wasm")


def extract_package(tgz, dest):
    tgz = Path(tgz)
    if not tgz.is_file():
        raise FileNotFoundError(tgz)
    dest = Path(dest)
    digests = {}
    with tarfile.open(tgz, "r:gz") as archive:
        members = {Path(member.name).name: member for member in archive.getmembers() if member.isfile()}
        for name in RUNTIME_FILES:
            if name not in members:
                raise ValueError(f"{name} missing from {tgz}")
        dest.mkdir(parents=True, exist_ok=True)
        for name in RUNTIME_FILES:
            payload = archive.extractfile(members[name]).read()
            (dest / name).write_bytes(payload)
            digests[name] = hashlib.sha256(payload).hexdigest()
    return digests


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extract the runtime files of the web package for the parity pages.")
    parser.add_argument("--tgz", type=Path, default=DEFAULT_TGZ)
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    args = parser.parse_args(argv)
    try:
        digests = extract_package(args.tgz, args.dest)
    except (OSError, ValueError) as failure:
        print(f"prepare_package: {failure}", file=sys.stderr)
        return 1
    print(json.dumps(digests, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
