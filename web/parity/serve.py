import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT / "web" / "examples"))

import serve as examples_serve

DEFAULT_GOLDEN = REPO_ROOT / "tools" / "parity" / ".work" / "web" / "golden"


def parity_mounts(golden=DEFAULT_GOLDEN):
    return {
        "/pkg/": HERE / "pkg",
        "/src/runtime/tests/": REPO_ROOT / "runtime" / "tests",
        "/golden/": Path(golden),
        "/goldens/": Path(golden).parent,
        "/sm/": REPO_ROOT / "tools" / "parity" / ".work" / "sm_web",
        "/": HERE,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Serve the web parity page, the package and the native goldens on localhost.")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    server = examples_serve.make_server("127.0.0.1", args.port, parity_mounts(args.golden), verbose=args.verbose)
    print(f"http://127.0.0.1:{args.port}/render.html", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
