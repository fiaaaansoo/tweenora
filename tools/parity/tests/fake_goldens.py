import os
import sys
import time
from pathlib import Path

from PIL import Image


def main(argv):
    src = Path(argv[argv.index("-s") + 1])
    out = Path(argv[argv.index("-o") + 1])
    mode = os.environ.get("FAKE_MODE", "stable")
    advance = int(os.environ.get("RIVE_GOLDENS_ADVANCE", "0"))
    if mode == "nopng":
        return 0
    if mode == "corrupt":
        out.mkdir(parents=True, exist_ok=True)
        (out / (src.stem + ".png")).write_bytes(b"not a png")
        return 0
    if mode == "fail":
        print("boom", file=sys.stderr)
        return 3
    payload = src.read_bytes()
    required = os.environ.get("FAKE_REQUIRE_SIG")
    if required and payload[:4] != required.encode():
        print("bad signature", file=sys.stderr)
        return 4
    seed = sum(payload[4:]) + advance
    if "-t" in argv:
        seed += len(argv[argv.index("-t") + 1])
    if mode == "clock":
        seed += time.perf_counter_ns() % 251
    if mode == "shift":
        seed += 1
    if mode == "flaky":
        counter = Path(os.environ["FAKE_TICK_FILE"] + "." + src.stem + "." + str(advance) + ("." + argv[argv.index("-t") + 1] if "-t" in argv else ""))
        count = int(counter.read_text()) + 1 if counter.exists() else 1
        counter.write_text(str(count))
        if count % 4 == 1:
            seed += 5
    if mode == "tick":
        counter = Path(os.environ["FAKE_TICK_FILE"] + "." + src.stem + "." + str(advance) + ("." + argv[argv.index("-t") + 1] if "-t" in argv else ""))
        count = int(counter.read_text()) + 1 if counter.exists() else 1
        counter.write_text(str(count))
        seed += count * 3
    image = Image.new("RGBA", (8, 8), (seed % 256, (seed // 256) % 256, 7, int(os.environ.get("FAKE_ALPHA", "255"))))
    out.mkdir(parents=True, exist_ok=True)
    image.save(out / (src.stem + ".png"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
