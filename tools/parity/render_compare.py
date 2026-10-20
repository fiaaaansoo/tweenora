import argparse
import hashlib
import json
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parent
TOOLS_DIR = PARITY_DIR.parent
REPO_ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(PARITY_DIR))
sys.path.insert(0, str(TOOLS_DIR))

import bench
import pixeldiff
import render
import twno_convert

CONFIGURATIONS = ("debug", "release")


def default_binaries(config="debug"):
    if config not in CONFIGURATIONS:
        raise ValueError(f"unknown configuration: {config!r}")
    fork = REPO_ROOT / "runtime" / "tests" / "out" / config / "goldens.exe"
    ref = PARITY_DIR / ".ref" / "rive-runtime" / "tests" / "out" / config / "goldens.exe"
    return fork, ref


DEFAULT_FORK, DEFAULT_REF = default_binaries()
DEFAULT_INSTANTS = (0, 15, 60)
DEFAULT_EXPLAINED = PARITY_DIR / "explained.json"


@dataclass(frozen=True)
class Job:
    rel: str
    group: str
    advance: int
    artboard: object

    @property
    def key(self):
        board = "default" if self.artboard is None else f"artboard:{self.artboard}"
        return f"{self.rel}@{self.advance}@{board}"


def plan_jobs(entries, instants):
    for instant in instants:
        if not isinstance(instant, int) or instant < 0:
            raise ValueError(f"instant must be a non-negative integer: {instant!r}")
    jobs = []
    for item in entries:
        artboards = [None]
        names = list(dict.fromkeys(item["artboards"]))
        if len(item["artboards"]) > 1:
            artboards += names
        for artboard in artboards:
            for instant in instants:
                jobs.append(Job(item["path"], item["group"], instant, artboard))
    keys = [job.key for job in jobs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate render keys in the plan")
    return jobs


def select_sample(entries, count):
    pool = sorted(entries, key=lambda e: (e["sha256"], e["path"]))
    chosen = []
    seen = set()
    features = sorted({f for e in pool for f in e["features"]})
    for feature in features:
        taken = 0
        for item in pool:
            if taken == 2:
                break
            if feature in item["features"] and item["path"] not in seen:
                chosen.append(item)
                seen.add(item["path"])
                taken += 1
    for item in pool:
        if len(chosen) >= count:
            break
        if item["path"] not in seen:
            chosen.append(item)
            seen.add(item["path"])
    return sorted(chosen[:count], key=lambda e: e["path"])


def run_job(job, repo, exe_fork, exe_ref, work_dir, fmt, env_fork, env_ref, timeout, backend):
    workspace = Path(work_dir) / hashlib.sha1(job.key.encode()).hexdigest()[:12]
    source = Path(repo) / job.rel
    base = {
        "key": job.key,
        "path": job.rel,
        "group": job.group,
        "advance": job.advance,
        "artboard": job.artboard,
    }
    try:
        if not source.is_file():
            raise FileNotFoundError(f"source not found: {source}")
        fork_source = source
        if fmt == "twno":
            fork_source = workspace / "src" / (source.stem + ".riv")
            fork_source.parent.mkdir(parents=True, exist_ok=True)
            fork_source.write_bytes(twno_convert.riv_to_twno(source.read_bytes()))
        record = bench.compare_one(
            exe_fork,
            exe_ref,
            fork_source,
            workspace,
            job.advance,
            env_fork,
            env_ref,
            src_b=source,
            artboard=job.artboard,
            timeout=timeout,
            backend=backend,
        )
    except Exception as failure:
        record = {"status": "setup_error", "detail": f"{type(failure).__name__}: {failure}"}
    record.update(base)
    record["format"] = fmt
    return record


NOISE_STATUS = "non_deterministic"


RETEST_REPEATS = 6


def repeat_is_stable(exe, src, workspace, tag, job, env, timeout, backend):
    pngs = []
    for index in range(RETEST_REPEATS):
        png, error = bench.render_safely(
            exe,
            src,
            workspace / tag / str(index + 1),
            job["advance"],
            env,
            artboard=job["artboard"],
            timeout=timeout,
            backend=backend,
        )
        if error is not None:
            return None
        pngs.append(png)
    try:
        return all(pixeldiff.compare_png(pngs[0], other).identical for other in pngs[1:])
    except Exception:
        return None


def retest_differences(
    records, repo, exe_fork, exe_ref, work_dir, fmt="riv", env_fork=None, env_ref=None, timeout=120, backend="gl"
):
    out = []
    for record in records:
        if record["status"] != "different":
            out.append(record)
            continue
        job = Job(record["path"], record["group"], record["advance"], record["artboard"])
        workspace = Path(work_dir) / hashlib.sha1(job.key.encode()).hexdigest()[:12]
        source = Path(repo) / job.rel
        fork_source = source
        if fmt == "twno":
            fork_source = workspace / "src" / (source.stem + ".riv")
            fork_source.parent.mkdir(parents=True, exist_ok=True)
            fork_source.write_bytes(twno_convert.riv_to_twno(source.read_bytes()))
        repeat = {
            "fork": repeat_is_stable(exe_fork, fork_source, workspace, "repeat_fork", record, env_fork, timeout, backend),
            "ref": repeat_is_stable(exe_ref, source, workspace, "repeat_ref", record, env_ref, timeout, backend),
        }
        record = dict(record, repeat=repeat)
        if False in repeat.values():
            record["status"] = NOISE_STATUS
        out.append(record)
    return out


def load_checkpoint(path, fmt, keys):
    path = Path(path)
    if not path.is_file():
        return {}
    reused = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if (
            isinstance(record, dict)
            and record.get("key") in keys
            and record.get("format") == fmt
            and record.get("status") != "setup_error"
        ):
            reused[record["key"]] = record
    return reused


def run_campaign(
    repo,
    entries,
    exe_fork,
    exe_ref,
    work_dir,
    instants=DEFAULT_INSTANTS,
    jobs=3,
    fmt="riv",
    env_fork=None,
    env_ref=None,
    timeout=120,
    backend="gl",
    progress=None,
    checkpoint=None,
):
    planned = plan_jobs(entries, list(instants))
    reused = load_checkpoint(checkpoint, fmt, {job.key for job in planned}) if checkpoint else {}
    pending = [job for job in planned if job.key not in reused]
    done = len(reused)
    lock = threading.Lock()
    sink = None
    if checkpoint:
        Path(checkpoint).parent.mkdir(parents=True, exist_ok=True)
        sink = open(checkpoint, "a", encoding="utf-8")

    def task(job):
        nonlocal done
        record = run_job(job, repo, exe_fork, exe_ref, work_dir, fmt, env_fork, env_ref, timeout, backend)
        with lock:
            if sink:
                sink.write(json.dumps(record, sort_keys=True) + chr(10))
                sink.flush()
            done += 1
        if progress:
            try:
                progress(done, len(planned))
            except Exception:
                pass
        return record

    try:
        with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
            fresh = dict(zip((job.key for job in pending), pool.map(task, pending)))
    finally:
        if sink:
            sink.close()
    return [reused[job.key] if job.key in reused else fresh[job.key] for job in planned]


def load_explained(path):
    path = Path(path)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_report(records, explained):
    summary = Counter(record["status"] for record in records)
    noise = [record["key"] for record in records if record["status"] == NOISE_STATUS]
    unexplained = []
    explained_keys = []
    for record in records:
        if record["status"] in bench.OK_STATUSES or record["status"] == NOISE_STATUS:
            continue
        note = explained.get(record["key"])
        if isinstance(note, dict) and note.get("status") == record["status"]:
            explained_keys.append(record["key"])
        else:
            unexplained.append(record["key"])
    out = dict(summary)
    out["total"] = len(records)
    out["noise"] = len(noise)
    out["explained"] = len(explained_keys)
    out["unexplained"] = len(unexplained)
    return {
        "summary": out,
        "explained": explained_keys,
        "noise": noise,
        "unexplained": unexplained,
        "exit_code": 1 if unexplained or not records else 0,
    }


def explanation(explained, record):
    note = explained.get(record["key"])
    if isinstance(note, dict) and note.get("status") == record["status"]:
        return note.get("reason", "")
    return ""


def render_markdown(report, records, seconds, explained=None):
    explained = explained or {}
    lines = ["# Render comparison report", ""]
    lines.append(f"Duration: {seconds:.0f} s. Renders compared: {report['summary']['total']}.")
    lines.append("")
    lines.append("| Status | Count |")
    lines.append("|---|---|")
    for status, count in sorted(report["summary"].items()):
        if status not in ("total", "explained", "unexplained", "noise"):
            lines.append(f"| {status} | {count} |")
    lines.append("")
    lines.append(
        f"Noise (non-deterministic from one render to the next): {report['summary']['noise']}. "
        f"Explained differences: {report['summary']['explained']}. "
        f"Unexplained differences: {report['summary']['unexplained']}."
    )
    bad = [r for r in records if r["status"] not in bench.OK_STATUSES]
    if bad:
        lines += ["", "## Differences and errors", "", "| Render | Status | Pixels | Max difference | Explanation |", "|---|---|---|---|---|"]
        for record in bad:
            lines.append(
                f"| {record['key']} | {record['status']} | {record.get('differing_pixels', '')} | "
                f"{record.get('max_channel_diff', '')} | {explanation(explained, record)} |"
            )
    return "\n".join(lines) + "\n"


def parse_instants(text):
    return [int(part) for part in text.split(",") if part.strip()]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render with the fork and the reference and compare pixel by pixel.")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--manifest", type=Path, default=PARITY_DIR / "manifest.json")
    parser.add_argument("--config", choices=CONFIGURATIONS, default="debug")
    parser.add_argument("--fork", type=Path)
    parser.add_argument("--ref", type=Path)
    parser.add_argument("--work", type=Path, default=PARITY_DIR / ".work" / "render_compare")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--sample", type=int)
    selection.add_argument("--files", nargs="+")
    parser.add_argument("--instants", default=",".join(str(i) for i in DEFAULT_INSTANTS))
    parser.add_argument("--format", choices=("riv", "twno"), default="riv")
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--explained", type=Path, default=DEFAULT_EXPLAINED)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--report-md", type=Path)
    parser.add_argument("--checkpoint", type=Path)
    args = parser.parse_args(argv)

    default_fork, default_ref = default_binaries(args.config)
    args.fork = args.fork or default_fork
    args.ref = args.ref or default_ref
    entries = bench.load_manifest(args.manifest)["files"]
    if args.sample is not None:
        entries = select_sample(entries, args.sample)
    elif args.files:
        wanted = set(args.files)
        entries = [e for e in entries if e["path"] in wanted]
        missing = wanted - {e["path"] for e in entries}
        if missing:
            print(f"not in the manifest: {sorted(missing)}", file=sys.stderr)
            return 2

    def progress(done, total):
        if done % 25 == 0 or done == total:
            print(f"{done}/{total}", file=sys.stderr, flush=True)

    started = time.time()
    records = run_campaign(
        args.repo,
        entries,
        str(args.fork),
        str(args.ref),
        args.work,
        instants=parse_instants(args.instants),
        jobs=args.jobs,
        fmt=args.format,
        timeout=args.timeout,
        progress=progress,
        checkpoint=args.checkpoint,
    )
    records = retest_differences(
        records, args.repo, str(args.fork), str(args.ref), args.work, fmt=args.format, timeout=args.timeout
    )
    seconds = time.time() - started
    explained = load_explained(args.explained)
    report = build_report(records, explained)
    print(json.dumps(report["summary"], sort_keys=True))
    for key in report["unexplained"]:
        print(f"unexplained: {key}", file=sys.stderr)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {"format": args.format, "seconds": seconds, "report": report, "records": records}
        args.report_json.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if args.report_md:
        args.report_md.parent.mkdir(parents=True, exist_ok=True)
        args.report_md.write_text(render_markdown(report, records, seconds, explained), encoding="utf-8")
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
