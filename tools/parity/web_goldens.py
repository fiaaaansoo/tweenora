import argparse
import json
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parent
REPO_ROOT = PARITY_DIR.parents[1]
sys.path.insert(0, str(PARITY_DIR))

import bench
import render
import render_compare

DEFAULT_SAMPLE = REPO_ROOT / "web" / "parity" / "sample.json"
DEFAULT_OUT = PARITY_DIR / ".work" / "web" / "golden"
DEFAULT_BACKEND = "angle_d3d"
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def load_sample(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = data.get("entries", [])
    if not entries:
        raise ValueError("empty sample")
    seen = set()
    for entry in entries:
        identifier = entry.get("id", "")
        if not ID_PATTERN.match(identifier):
            raise ValueError(f"bad id: {identifier!r}")
        if identifier in seen:
            raise ValueError(f"duplicate id: {identifier}")
        seen.add(identifier)
        advance = entry.get("advance")
        if not isinstance(advance, int) or isinstance(advance, bool) or advance < 0:
            raise ValueError(f"bad advance for {identifier}: {advance!r}")
    return entries


def render_entry(entry, repo, exe, out_dir, timeout, backend):
    record = {"id": entry["id"], "path": entry["path"], "advance": entry["advance"], "status": None}
    source = Path(repo) / entry["path"]
    if not source.is_file():
        record["status"], record["detail"] = "error", f"missing source {entry['path']}"
        return record
    scratch = Path(out_dir) / ".scratch" / entry["id"]
    png, error = bench.render_safely(
        exe,
        source,
        scratch,
        entry["advance"],
        artboard=entry.get("artboard"),
        state_machine=entry.get("stateMachine"),
        timeout=timeout,
        backend=backend,
    )
    if error is not None:
        record["status"], record["detail"] = "error", error["message"]
        return record
    target = Path(out_dir) / f"{entry['id']}.png"
    shutil.move(str(png), str(target))
    if not is_opaque(target):
        target.unlink()
        record["status"], record["detail"] = "error", f"{entry['id']}: the native image has transparent pixels (window clipped or covered)"
        return record
    record["status"] = "rendered"
    record["sha256"] = render.sha256_file(target)
    return record


def render_goldens(entries, repo, exe, out_dir, jobs=2, timeout=120, backend=DEFAULT_BACKEND):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.png"):
        stale.unlink()
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        index = list(pool.map(lambda e: render_entry(e, repo, exe, out_dir, timeout, backend), entries))
    shutil.rmtree(out_dir / ".scratch", ignore_errors=True)
    (out_dir / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
    return index


def is_opaque(path):
    import numpy
    from PIL import Image

    with Image.open(path) as image:
        return bool((numpy.asarray(image.convert("RGBA"))[:, :, 3] == 255).all())


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render the native goldens of the web parity sample.")
    parser.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--config", choices=("debug", "release"), default="release")
    parser.add_argument("--fork", type=Path)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--backend", default=DEFAULT_BACKEND)
    args = parser.parse_args(argv)
    try:
        entries = load_sample(args.sample)
    except (OSError, ValueError) as failure:
        print(f"sample: {failure}", file=sys.stderr)
        return 2
    exe = args.fork or render_compare.default_binaries(args.config)[0]
    index = render_goldens(entries, REPO_ROOT, exe, args.out, jobs=args.jobs, timeout=args.timeout, backend=args.backend)
    failed = [record for record in index if record["status"] != "rendered"]
    for record in failed:
        print(f"error: {record['id']}: {record.get('detail')}", file=sys.stderr)
    print(json.dumps({"rendered": len(index) - len(failed), "errors": len(failed)}))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
