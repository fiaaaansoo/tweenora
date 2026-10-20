import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PARITY_DIR))

import pixeldiff
import render


OK_STATUSES = ("deterministic", "identical", "identical_pixels_only", "same_failure")


def render_safely(exe, src, out_dir, advance, extra_env=None, **options):
    try:
        return render.render_file(exe, src, out_dir, advance=advance, extra_env=extra_env, **options), None
    except render.RenderError as error:
        return None, {"message": str(error), "code": error.code}
    except subprocess.TimeoutExpired as error:
        return None, {"message": f"timeout after {error.timeout}s", "code": "timeout"}
    except Exception as error:
        return None, {"message": f"{type(error).__name__}: {error}", "code": "exception"}


def check_determinism(exe, files, work_dir, advance, **options):
    work_dir = Path(work_dir)
    records = []
    for index, src in enumerate(files):
        record = {"path": str(src), "status": None, "sha256": None, "detail": None}
        first, error = render_safely(exe, src, work_dir / "a" / str(index), advance, **options)
        second = None
        if error is None:
            second, error = render_safely(exe, src, work_dir / "b" / str(index), advance, **options)
        if error is not None:
            record["status"], record["detail"] = "error", error["message"]
        else:
            try:
                hash_a, hash_b = render.sha256_file(first), render.sha256_file(second)
                record["sha256"] = hash_a
                record["status"] = "deterministic" if hash_a == hash_b else "non_deterministic"
                if hash_a != hash_b:
                    record["detail"] = pixeldiff.compare_png(first, second).__dict__
            except Exception as failure:
                record["status"], record["detail"] = "error", f"{type(failure).__name__}: {failure}"
        records.append(record)
    return records


def compare_one(exe_a, exe_b, src, work_dir, advance, env_a=None, env_b=None, src_b=None, **options):
    work_dir = Path(work_dir)
    record = {"path": str(src), "status": None, "byte_identical": None, "detail": None}
    png_a, error_a = render_safely(exe_a, src, work_dir / "a", advance, env_a, **options)
    png_b, error_b = render_safely(exe_b, src_b or src, work_dir / "b", advance, env_b, **options)
    if error_a is not None or error_b is not None:
        record["detail"] = {"a": error_a, "b": error_b}
        if error_a is not None and error_b is not None:
            same = isinstance(error_a["code"], int) and error_a["code"] == error_b["code"]
            record["status"] = "same_failure" if same else "both_error"
        else:
            record["status"] = "error_a" if error_a is not None else "error_b"
        return record
    try:
        diff = pixeldiff.compare_png(png_a, png_b)
        record["byte_identical"] = render.sha256_file(png_a) == render.sha256_file(png_b)
        record["status"] = "identical" if diff.identical else "different"
        record["differing_pixels"] = diff.differing_pixels
        record["max_channel_diff"] = diff.max_channel_diff
    except Exception as failure:
        record["status"] = "compare_error"
        record["detail"] = f"{type(failure).__name__}: {failure}"
    if record["status"] == "identical" and not record["byte_identical"]:
        record["status"] = "identical_pixels_only"
    return record


def compare_builds(exe_a, exe_b, files, work_dir, advance, env_a=None, env_b=None, **options):
    return [
        compare_one(exe_a, exe_b, src, Path(work_dir) / str(index), advance, env_a, env_b, **options)
        for index, src in enumerate(files)
    ]


def summarize(records):
    return dict(Counter(record["status"] for record in records))


def load_manifest(path=PARITY_DIR / "manifest.json"):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Determinism and fork-versus-reference render checks.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("determinism", "compare"):
        p = sub.add_parser(name)
        p.add_argument("--repo", type=Path, required=True, help="repository root the manifest paths are relative to")
        p.add_argument("--files", nargs="+", required=True, help="manifest paths (relative to --repo)")
        p.add_argument("--work", type=Path, required=True)
        p.add_argument("--advance", type=int, default=0)
        p.add_argument("--json", type=Path)
    sub.choices["determinism"].add_argument("--exe", required=True)
    sub.choices["compare"].add_argument("--exe-fork", required=True)
    sub.choices["compare"].add_argument("--exe-ref", required=True)
    args = parser.parse_args(argv)
    files = [args.repo / rel for rel in args.files]
    if args.command == "determinism":
        records = check_determinism(args.exe, files, args.work, args.advance)
    else:
        records = compare_builds(args.exe_fork, args.exe_ref, files, args.work, args.advance)
    for record in records:
        record["path"] = Path(record["path"]).relative_to(args.repo).as_posix()
    summary = summarize(records)
    print(json.dumps(summary))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"summary": summary, "records": records}, indent=1) + "\n", encoding="utf-8")
    bad = [r for r in records if r["status"] not in OK_STATUSES]
    for record in bad:
        print(f"{record['status']}: {record['path']} {record['detail'] or ''}", file=sys.stderr)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
