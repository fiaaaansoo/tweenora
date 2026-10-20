import argparse
import sys
from pathlib import Path

GEN_DIR = Path(__file__).resolve().parent
REPO_ROOT = GEN_DIR.parents[1]
DEFAULT_OUT = REPO_ROOT / "docs" / "examples"
sys.path.insert(0, str(GEN_DIR))

from scenes import bouncing_ball, button, spinning_square, tinted_shape

SCENES = (bouncing_ball, spinning_square, button, tinted_shape)


def render_all():
    return {scene.NAME + ".riv": scene.build().to_bytes(b"RIVE") for scene in SCENES}


def build(out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    produced = render_all()
    for name, data in produced.items():
        (out_dir / name).write_bytes(data)
    return produced


def check(out_dir):
    stale = []
    for name, data in render_all().items():
        path = Path(out_dir) / name
        if not path.is_file() or path.read_bytes() != data:
            stale.append(name)
    return stale


def main(argv=None):
    parser = argparse.ArgumentParser(description="Write the generated Tweenora example files.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--check", action="store_true", help="exit 1 if a file differs from its regeneration")
    args = parser.parse_args(argv)
    if args.check:
        stale = check(args.out)
        for name in stale:
            print(f"stale: {name}", file=sys.stderr)
        return 1 if stale else 0
    for name, data in build(args.out).items():
        print(f"{name}: {len(data)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
