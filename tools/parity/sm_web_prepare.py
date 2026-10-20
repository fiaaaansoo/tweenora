import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parent
REPO_ROOT = PARITY_DIR.parents[1]
sys.path.insert(0, str(PARITY_DIR))

import run_trace
import sm_actions
import sm_compare
import trace_compare

DEFAULT_OUT = PARITY_DIR / ".work" / "sm_web"


def safe_id(path):
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(path).stem)
    return f"{stem}-{hashlib.sha1(path.encode()).hexdigest()[:6]}"


def choose(records, others):
    with_stats = [r for r in records if "stats" in r]
    must = [r for r in with_stats if r["stats"]["events"] > 0 or r["stats"]["inputs"] > 0]
    rest = sorted(
        (r for r in with_stats if r not in must), key=lambda r: hashlib.sha256(r["id"].encode()).hexdigest()
    )
    return must + rest[:others]


def collect(entries, repo, exe, out_dir, timeout):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for item in entries:
        identifier = safe_id(item["path"])
        source = Path(repo) / item["path"]
        description, error = sm_compare.describe(exe, source, None, timeout)
        if error:
            continue
        actions = sm_actions.generate(description)
        script = out_dir / f"{identifier}.script.jsonl"
        script.write_text(sm_actions.script_text(actions), encoding="utf-8", newline="\n")
        text, error = run_trace.run_one(exe, source, script, None, None, None, timeout)
        if error:
            continue
        steps = trace_compare.parse_trace(text)["steps"]
        (out_dir / f"{identifier}.native.jsonl").write_text(text, encoding="utf-8", newline="\n")
        records.append(
            {
                "id": identifier,
                "path": item["path"],
                "artboard": description["artboard"],
                "stateMachine": description["stateMachine"],
                "stats": {
                    "changed_steps": sum(1 for step in steps if step["changed"]),
                    "events": sum(len(step["events"]) for step in steps),
                    "inputs": len(steps[-1]["inputs"]) if steps else 0,
                },
            }
        )
    return records


def prepare(entries, repo, exe, out_dir, others=20, timeout=60):
    records = collect(entries, repo, exe, out_dir, timeout)
    chosen = choose(records, others)
    keep = {r["id"] for r in chosen}
    out_dir = Path(out_dir)
    for record in records:
        if record["id"] not in keep:
            (out_dir / f"{record['id']}.script.jsonl").unlink(missing_ok=True)
            (out_dir / f"{record['id']}.native.jsonl").unlink(missing_ok=True)
    (out_dir / "index.json").write_text(json.dumps(chosen, indent=1, sort_keys=True), encoding="utf-8")
    return chosen


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write the scripts and the native traces used by the web state machine parity page.")
    parser.add_argument("--manifest", type=Path, default=PARITY_DIR / "manifest.json")
    parser.add_argument("--config", choices=("debug", "release"), default="release")
    parser.add_argument("--fork", type=Path)
    parser.add_argument("--others", type=int, default=20)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    fork = args.fork or run_trace.default_binaries(args.config)[0]
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    chosen = prepare(sm_compare.select_files(manifest["files"]), REPO_ROOT, fork, args.out, args.others)
    print(json.dumps({"files": len(chosen)}))
    return 0 if chosen else 1


if __name__ == "__main__":
    sys.exit(main())
