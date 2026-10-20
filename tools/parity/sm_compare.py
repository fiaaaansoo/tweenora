import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parent
REPO_ROOT = PARITY_DIR.parents[1]
sys.path.insert(0, str(PARITY_DIR))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import run_trace
import sm_actions
import trace_compare
import twno_convert

OK_STATUSES = ("identical", "same_failure")
DEFAULT_EXPLAINED = PARITY_DIR / "sm_explained.json"


def select_files(entries, sample=None):
    selected = [e for e in entries if e.get("state_machines") and not e.get("parse_error")]
    if sample is not None:
        selected = sorted(selected, key=lambda e: hashlib.sha256(e["path"].encode()).hexdigest())[:sample]
    return selected


def describe(exe, src, env, timeout):
    text, error = run_trace.run_one(exe, src, "--describe", None, None, env, timeout)
    if error:
        return None, error
    try:
        return json.loads(text), None
    except ValueError as failure:
        return None, f"bad description: {failure}"


def compare_file(entry, repo, exe_fork, exe_ref, work_dir, fmt="riv", env_fork=None, env_ref=None, timeout=60):
    record = {"path": entry["path"], "format": fmt, "status": None}
    source = Path(repo) / entry["path"]
    if not source.is_file():
        record["status"], record["detail"] = "error", "missing source"
        return record
    workspace = Path(work_dir) / hashlib.sha1((fmt + entry["path"]).encode()).hexdigest()[:12]
    workspace.mkdir(parents=True, exist_ok=True)
    fork_source = source
    if fmt == "twno":
        fork_source = workspace / "src" / (source.stem + ".riv")
        fork_source.parent.mkdir(parents=True, exist_ok=True)
        fork_source.write_bytes(twno_convert.riv_to_twno(source.read_bytes()))
    desc_fork, error_fork = describe(exe_fork, fork_source, env_fork, timeout)
    desc_ref, error_ref = describe(exe_ref, source, env_ref, timeout)
    if error_fork and error_ref:
        record["status"], record["detail"] = "same_failure", {"a": error_fork, "b": error_ref}
        return record
    if error_fork or error_ref:
        record["status"], record["detail"] = "error", {"a": error_fork, "b": error_ref}
        return record
    if desc_fork != desc_ref:
        record["status"], record["detail"] = "different", {"describe": [desc_fork, desc_ref]}
        record["first"] = {"step": None, "field": "describe"}
        return record
    actions = sm_actions.generate(desc_ref)
    if actions is None:
        record["status"], record["detail"] = "error", "no script"
        return record
    script = workspace / "script.jsonl"
    script.write_text(sm_actions.script_text(actions), encoding="utf-8", newline="\n")
    result = run_trace.run_pair(
        exe_fork, exe_ref, fork_source, script, env_fork=env_fork, env_ref=env_ref, timeout=timeout, src_b=source
    )
    record["status"] = result["status"]
    if "trace_a" in result:
        steps = trace_compare.parse_trace(result["trace_a"])["steps"]
        record["stats"] = {
            "changed_steps": sum(1 for step in steps if step["changed"]),
            "events": sum(len(step["events"]) for step in steps),
            "inputs": len(steps[-1]["inputs"]) if steps else 0,
        }
    for key in ("steps", "first", "side", "detail"):
        if key in result:
            record[key] = result[key]
    return record


def load_explained(path):
    path = Path(path)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(records, explained):
    summary = {"total": len(records), "explained": 0, "unexplained": 0}
    for record in records:
        summary[record["status"]] = summary.get(record["status"], 0) + 1
        if record["status"] in OK_STATUSES:
            continue
        entry = explained.get(record["path"])
        if entry and entry.get("status") == record["status"]:
            summary["explained"] += 1
        else:
            summary["unexplained"] += 1
    exit_code = 1 if summary["unexplained"] or not records else 0
    return {"summary": summary, "exit_code": exit_code}


def run_campaign(entries, repo, exe_fork, exe_ref, work_dir, fmt, jobs, timeout):
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        return list(pool.map(lambda e: compare_file(e, repo, exe_fork, exe_ref, work_dir, fmt, timeout=timeout), entries))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare generated state machine traces on the manifest files.")
    parser.add_argument("--manifest", type=Path, default=PARITY_DIR / "manifest.json")
    parser.add_argument("--config", choices=("debug", "release"), default="release")
    parser.add_argument("--fork", type=Path)
    parser.add_argument("--ref", type=Path)
    parser.add_argument("--format", choices=("riv", "twno"), default="riv")
    parser.add_argument("--sample", type=int)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--explained", type=Path, default=DEFAULT_EXPLAINED)
    parser.add_argument("--work", type=Path, default=PARITY_DIR / ".work" / "sm_compare")
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args(argv)
    default_fork, default_ref = run_trace.default_binaries(args.config)
    fork, ref = args.fork or default_fork, args.ref or default_ref
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    entries = select_files(manifest["files"], args.sample)
    records = run_campaign(entries, REPO_ROOT, fork, ref, args.work, args.format, args.jobs, args.timeout)
    report = build_report(records, load_explained(args.explained))
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps({**report, "records": records}, indent=1, sort_keys=True), encoding="utf-8")
    for record in records:
        if record["status"] not in OK_STATUSES:
            print(f"{record['status']}: {record['path']} {json.dumps(record.get('first') or record.get('detail'))[:300]}", file=sys.stderr)
    print(json.dumps(report["summary"], sort_keys=True))
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
