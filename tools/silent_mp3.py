import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = (
    REPO_ROOT / "runtime" / "tests" / "unit_tests" / "assets" / "audio" / "silence.mp3"
)
SAMPLE_RATE = 44100
SAMPLES_PER_FRAME = 1152
FRAME_HEADER = bytes([0xFF, 0xFB, 0x90, 0xC0])
FRAME_SIZE = 144 * 128000 // SAMPLE_RATE
DEFAULT_FRAMES = 38


def build(frames):
    if frames < 1:
        raise ValueError("frames must be positive")
    frame = FRAME_HEADER + bytes(FRAME_SIZE - len(FRAME_HEADER))
    return frame * frames


def duration_seconds(frames):
    return frames * SAMPLES_PER_FRAME / SAMPLE_RATE


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Write an MPEG-1 Layer III file made of silent frames."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frames", type=int, default=DEFAULT_FRAMES)
    args = parser.parse_args(argv)
    data = build(args.frames)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(f"{args.output}: {len(data)} bytes, {duration_seconds(args.frames):.3f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
