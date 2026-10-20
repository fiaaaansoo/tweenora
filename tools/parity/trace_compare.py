import argparse
import json
import sys
from pathlib import Path

FORMAT_VERSION = 1
STEP_FIELDS = ("action", "needsAdvance", "changed", "inputs", "events")
POINTER_KINDS = ("down", "move", "up")
INPUT_OPS = ("bool", "number", "trigger")


class TraceError(ValueError):
    pass


def parse_trace(text):
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise TraceError("empty trace")
    records = []
    for number, line in enumerate(lines, 1):
        try:
            records.append(json.loads(line))
        except ValueError as failure:
            raise TraceError(f"line {number}: not JSON ({failure})") from failure
    header = records[0]
    if not isinstance(header, dict) or header.get("trace") != FORMAT_VERSION:
        raise TraceError(f"unsupported trace header: {header!r}")
    steps = []
    ended = None
    for record in records[1:]:
        if not isinstance(record, dict):
            raise TraceError(f"unexpected record: {record!r}")
        if record.get("end") is True:
            ended = record
            break
        if "step" not in record:
            raise TraceError(f"unexpected record: {record!r}")
        if record["step"] != len(steps):
            raise TraceError(f"step {record['step']} where {len(steps)} was expected")
        steps.append(record)
    if ended is not None and ended.get("steps") != len(steps):
        raise TraceError(f"end marker counts {ended.get('steps')} steps, found {len(steps)}")
    return {"header": header, "steps": steps, "complete": ended is not None}


def values_equal(a, b, tolerance):
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(values_equal(a[k], b[k], tolerance) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(values_equal(x, y, tolerance) for x, y in zip(a, b))
    if tolerance and isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(a - b) <= tolerance * max(1.0, abs(a), abs(b))
    return a == b


def compare_traces(a_text, b_text, fields=None, float_tolerance=None):
    if fields is not None:
        unknown = [field for field in fields if field not in STEP_FIELDS]
        if unknown:
            raise ValueError(f"unknown fields: {unknown}")
    compared = tuple(fields) if fields is not None else STEP_FIELDS
    parsed = {}
    for side, text in (("a", a_text), ("b", b_text)):
        try:
            parsed[side] = parse_trace(text)
        except TraceError as failure:
            return {"status": "invalid", "side": side, "detail": str(failure)}
    for side in ("a", "b"):
        if not parsed[side]["complete"]:
            return {"status": "truncated", "side": side, "steps": len(parsed[side]["steps"])}
    a, b = parsed["a"], parsed["b"]
    header_a, header_b = a["header"], b["header"]
    if fields is not None:
        header_a = {k: header_a.get(k) for k in ("trace", "artboard", "stateMachine")}
        header_b = {k: header_b.get(k) for k in ("trace", "artboard", "stateMachine")}
    if header_a != header_b:
        return {
            "status": "different",
            "first": {"step": None, "field": "header", "a": header_a, "b": header_b},
        }
    for index, (step_a, step_b) in enumerate(zip(a["steps"], b["steps"])):
        for field in compared:
            if not values_equal(step_a.get(field), step_b.get(field), float_tolerance):
                return {
                    "status": "different",
                    "first": {"step": index, "field": field, "a": step_a.get(field), "b": step_b.get(field)},
                }
    if len(a["steps"]) != len(b["steps"]):
        return {
            "status": "different",
            "first": {"step": min(len(a["steps"]), len(b["steps"])), "field": "steps", "a": len(a["steps"]), "b": len(b["steps"])},
        }
    return {"status": "identical", "steps": len(a["steps"])}


def parse_script(text):
    actions = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            action = json.loads(line)
        except ValueError as failure:
            raise TraceError(f"script line {number}: not JSON ({failure})") from failure
        op = action.get("op") if isinstance(action, dict) else None
        if op == "advance":
            dt = action.get("dt")
            if not isinstance(dt, (int, float)) or isinstance(dt, bool) or dt < 0:
                raise TraceError(f"script line {number}: bad dt {dt!r}")
        elif op in INPUT_OPS:
            if not isinstance(action.get("name"), str) or not action["name"]:
                raise TraceError(f"script line {number}: {op} needs a name")
            if op == "bool" and not isinstance(action.get("value"), bool):
                raise TraceError(f"script line {number}: bool needs a boolean value")
            if op == "number" and (not isinstance(action.get("value"), (int, float)) or isinstance(action["value"], bool)):
                raise TraceError(f"script line {number}: number needs a numeric value")
        elif op == "pointer":
            if action.get("kind") not in POINTER_KINDS:
                raise TraceError(f"script line {number}: bad pointer kind {action.get('kind')!r}")
            for axis in ("x", "y"):
                if not isinstance(action.get(axis), (int, float)) or isinstance(action[axis], bool):
                    raise TraceError(f"script line {number}: pointer needs {axis}")
        else:
            raise TraceError(f"script line {number}: unknown operation {op!r}")
        actions.append(action)
    return actions


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare two state machine traces.")
    parser.add_argument("fork", type=Path)
    parser.add_argument("official", type=Path)
    args = parser.parse_args(argv)
    result = compare_traces(
        args.fork.read_text(encoding="utf-8"), args.official.read_text(encoding="utf-8")
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "identical" else 1


if __name__ == "__main__":
    sys.exit(main())
