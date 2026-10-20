import hashlib
import os
import subprocess
from pathlib import Path


class RenderError(RuntimeError):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def build_command(exe, src, out_dir, artboard=None, state_machine=None, backend="gl"):
    prefix = [str(part) for part in exe] if isinstance(exe, (list, tuple)) else [str(exe)]
    cmd = prefix + ["-b", backend, "-d", "-s", str(src), "-o", str(out_dir)]
    if artboard is not None:
        cmd += ["-t", artboard]
    if state_machine is not None:
        cmd += ["-S", state_machine]
    return cmd


def build_env(base, advance):
    if advance < 0:
        raise ValueError("advance must be >= 0")
    env = dict(base)
    env["RIVE_GOLDENS_ADVANCE"] = str(advance)
    return env


def output_png(out_dir, src):
    return Path(out_dir) / (Path(src).stem + ".png")


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render_file(
    exe,
    src,
    out_dir,
    advance=0,
    artboard=None,
    state_machine=None,
    backend="gl",
    timeout=120,
    extra_env=None,
):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    png = output_png(out_dir, src)
    if png.exists():
        png.unlink()
    completed = subprocess.run(
        build_command(exe, src, out_dir, artboard, state_machine, backend),
        env=build_env({**os.environ, **(extra_env or {})}, advance),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0 or not png.is_file():
        raise RenderError(
            f"goldens failed on {src} (code {completed.returncode}): "
            f"{(completed.stdout + completed.stderr).strip()[-500:]}",
            completed.returncode,
        )
    return png
