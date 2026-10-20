import os
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDENS_ENV = "TWNO_GOLDENS"
GOLDENS_RELATIVE = Path("runtime") / "tests" / "out" / "debug"
FRAME_SIZE = 1600


class RenderUnavailable(Exception):
    pass


def find_goldens():
    configured = os.environ.get(GOLDENS_ENV)
    candidates = [Path(configured)] if configured else []
    candidates += [REPO_ROOT / GOLDENS_RELATIVE / name for name in ("goldens.exe", "goldens")]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RenderUnavailable(f"goldens not built (set {GOLDENS_ENV} or build runtime/tests)")


def require_imaging():
    try:
        import numpy
        from PIL import Image
    except ImportError as error:
        raise RenderUnavailable(f"{error.name} is not installed") from None
    return numpy, Image


def load_pixels(path):
    numpy, Image = require_imaging()
    with Image.open(path) as image:
        return numpy.asarray(image.convert("RGBA"))


def render(path, advance=0, artboard=None, state_machine=None, timeout=120, extra_env=None):
    goldens = find_goldens()
    path = Path(path)
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        source = folder / (path.stem + ".riv")
        shutil.copyfile(path, source)
        out_dir = folder / "out"
        out_dir.mkdir()
        command = [str(goldens), "-b", "gl", "-d", "-s", str(source), "-o", str(out_dir)]
        if artboard is not None:
            command += ["-t", artboard]
        if state_machine is not None:
            command += ["-S", state_machine]
        env = {**os.environ, **(extra_env or {}), "RIVE_GOLDENS_ADVANCE": str(advance)}
        done = subprocess.run(command, env=env, capture_output=True, text=True, timeout=timeout)
        pngs = sorted(out_dir.glob("*.png"))
        if done.returncode != 0 or len(pngs) != 1:
            raise RuntimeError(
                f"goldens failed on {path} (code {done.returncode}): "
                f"{(done.stdout + done.stderr).strip()[-400:]}"
            )
        return load_pixels(pngs[0])


def hidden_rows(image):
    numpy, _ = require_imaging()
    drawn = numpy.where(image[:, :, 3].max(axis=1) > 0)[0]
    return int(drawn[0]) if len(drawn) else image.shape[0]


def artboard_to_frame(x, y, width, height):
    scale = FRAME_SIZE / max(width, height)
    return round(x * scale), round(y * scale)
