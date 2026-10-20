import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parent
REPO_ROOT = PARITY_DIR.parents[1]
sys.path.insert(0, str(PARITY_DIR))

import trace_compare

SM_TRACE_DIR = PARITY_DIR / "sm_trace"
DEFAULT_CASES = SM_TRACE_DIR / "cases.json"


def default_binaries(config="release"):
    return (
        SM_TRACE_DIR / "out" / "fork" / f"sm_trace_{config}.exe",
        SM_TRACE_DIR / "out" / "ref" / f"sm_trace_{config}.exe",
    )


def run_one(exe, src, script, artboard, machine, env, timeout):
    prefix = [str(part) for part in exe] if isinstance(exe, (list, tuple)) else [str(exe)]
    command = prefix + [str(src), str(script)]
    if artboard or machine:
        command += [artboard or "", machine or ""]
    try:
        completed = subprocess.run(
            command,
            env={**os.environ, **(env or {})},
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, f"timeout after {timeout}s"
    if completed.returncode != 0:
        return None, f"exit code {completed.returncode}: {completed.stderr.strip()[-300:]}"
    return completed.stdout, None


def run_pair(exe_a, exe_b, src, script, artboard=None, machine=None, env_fork=None, env_ref=None, timeout=60, src_b=None):
    trace_compare.parse_script(Path(script).read_text(encoding="utf-8"))
    text_a, error_a = run_one(exe_a, src, script, artboard, machine, env_fork, timeout)
    text_b, error_b = run_one(exe_b, src_b or src, script, artboard, machine, env_ref, timeout)
    if error_a or error_b:
        side = "both" if error_a and error_b else ("a" if error_a else "b")
        return {"status": "error", "side": side, "detail": {"a": error_a, "b": error_b}}
    result = trace_compare.compare_traces(text_a, text_b)
    result["trace_a"] = text_a
    result["trace_b"] = text_b
    return result


def load_cases(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = data.get("cases", [])
    if not cases:
        raise ValueError("no case")
    return cases


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare the state machine traces of the fork and the official runtime.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--config", choices=("debug", "release"), default="release")
    parser.add_argument("--fork", type=Path)
    parser.add_argument("--ref", type=Path)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--keep", type=Path)
    args = parser.parse_args(argv)
    default_fork, default_ref = default_binaries(args.config)
    fork, ref = args.fork or default_fork, args.ref or default_ref
    try:
        cases = load_cases(args.cases)
    except (OSError, ValueError) as failure:
        print(f"cases: {failure}", file=sys.stderr)
        return 2
    results = []
    for case in cases:
        src = REPO_ROOT / case["path"]
        script = SM_TRACE_DIR / "scripts" / case["script"]
        result = run_pair(fork, ref, src, script, case.get("artboard"), case.get("stateMachine"), timeout=args.timeout)
        record = {"id": case["id"], "path": case["path"], "status": result["status"]}
        for key in ("steps", "first", "side", "detail"):
            if key in result:
                record[key] = result[key]
        if args.keep and "trace_a" in result:
            args.keep.mkdir(parents=True, exist_ok=True)
            (args.keep / f"{case['id']}.fork.jsonl").write_text(result["trace_a"], encoding="utf-8")
            (args.keep / f"{case['id']}.ref.jsonl").write_text(result["trace_b"], encoding="utf-8")
        results.append(record)
    summary = {}
    for record in results:
        summary[record["status"]] = summary.get(record["status"], 0) + 1
    print(json.dumps({"summary": summary, "results": results}, indent=1, sort_keys=True))
    return 0 if set(summary) == {"identical"} else 1


if __name__ == "__main__":
    sys.exit(main())
