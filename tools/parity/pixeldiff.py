from dataclasses import dataclass
from pathlib import Path

import numpy
from PIL import Image


@dataclass(frozen=True)
class PixelDiff:
    same_size: bool
    width: int
    height: int
    differing_pixels: int
    max_channel_diff: int

    @property
    def identical(self):
        return self.same_size and self.differing_pixels == 0


def load_rgba(path):
    with Image.open(path) as image:
        return numpy.asarray(image.convert("RGBA"), dtype="int16")


def compare_png(path_a, path_b):
    a = load_rgba(Path(path_a))
    b = load_rgba(Path(path_b))
    if a.shape != b.shape:
        return PixelDiff(False, a.shape[1], a.shape[0], -1, -1)
    delta = numpy.abs(a - b)
    differing = numpy.any(delta != 0, axis=2)
    return PixelDiff(
        True,
        a.shape[1],
        a.shape[0],
        int(differing.sum()),
        int(delta.max()) if delta.size else 0,
    )
