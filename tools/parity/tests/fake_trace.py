import json
import os
import sys


def main(argv):
    mode = os.environ.get("FAKE_TRACE_MODE", "stable")
    if mode == "fail":
        print("boom", file=sys.stderr)
        return 3
    if argv[2] == "--describe":
        print(
            json.dumps(
                {
                    "artboard": "A",
                    "stateMachine": "SM",
                    "width": 100.0,
                    "height": 100.0,
                    "inputs": [{"name": "go", "kind": "trigger"}, {"name": "on", "kind": "bool"}],
                }
            )
        )
        return 0
    script = [json.loads(line) for line in open(argv[2], encoding="utf-8") if line.strip()]
    print(json.dumps({"trace": 1, "file": os.path.basename(argv[1]), "artboard": "A", "stateMachine": "SM"}))
    for index, action in enumerate(script):
        events = [{"name": "Ping", "delay": 0.0}] if action.get("op") == "trigger" else []
        if mode == "drop_event":
            events = []
        if mode == "late_event" and events:
            events[0]["delay"] = 0.016
        print(
            json.dumps(
                {
                    "step": index,
                    "action": action,
                    "needsAdvance": True,
                    "changed": [],
                    "inputs": [],
                    "events": events,
                }
            )
        )
        if mode == "truncate" and index == 0:
            return 0
    print(json.dumps({"end": True, "steps": len(script)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
