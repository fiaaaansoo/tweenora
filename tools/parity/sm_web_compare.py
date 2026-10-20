import argparse
import json
import sys
from pathlib import Path

PARITY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PARITY_DIR))

import trace_compare

DEFAULT_DIR = PARITY_DIR / ".work" / "sm_web"
DEFAULT_EXPLAINED = PARITY_DIR / "sm_web_explained.json"
COMMON_FIELDS = ("inputs", "events")
FLOAT_TOLERANCE = 1e-6


def compare_dir(directory):
    directory = Path(directory)
    index = json.loads((directory / "index.json").read_text(encoding="utf-8"))
    records = []
    for item in index:
        record = {"id": item["id"], "path": item["path"], "status": None}
        web_path = directory / f"{item['id']}.web.jsonl"
        if not web_path.is_file():
            record["status"] = "missing_web"
            records.append(record)
            continue
        result = trace_compare.compare_traces(
            (directory / f"{item['id']}.native.jsonl").read_text(encoding="utf-8"),
            web_path.read_text(encoding="utf-8"),
            fields=COMMON_FIELDS,
            float_tolerance=FLOAT_TOLERANCE,
        )
        record["status"] = result["status"]
        for key in ("steps", "first", "side", "detail"):
            if key in result:
                record[key] = result[key]
        records.append(record)
    return records


def build_report(records, explained):
    summary = {"total": len(records), "explained": 0, "unexplained": 0}
    for record in records:
        summary[record["status"]] = summary.get(record["status"], 0) + 1
        if record["status"] == "identical":
            continue
        entry = explained.get(record["path"])
        if entry and entry.get("status") == record["status"]:
            summary["explained"] += 1
        else:
            summary["unexplained"] += 1
    return {"summary": summary, "exit_code": 1 if summary["unexplained"] or not records else 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare the native and web state machine traces of a prepared directory.")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--explained", type=Path, default=DEFAULT_EXPLAINED)
    parser.add_argument("--report-json", type=Path)
    args = parser.parse_args(argv)
    explained = json.loads(args.explained.read_text(encoding="utf-8")) if args.explained.is_file() else {}
    records = compare_dir(args.dir)
    report = build_report(records, explained)
    if args.report_json:
        args.report_json.write_text(json.dumps({**report, "records": records}, indent=1, sort_keys=True), encoding="utf-8")
    for record in records:
        if record["status"] != "identical":
            print(f"{record['status']}: {record['path']} {json.dumps(record.get('first'))[:300]}", file=sys.stderr)
    print(json.dumps(report["summary"], sort_keys=True))
    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
