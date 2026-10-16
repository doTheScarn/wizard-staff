"""Independent light vectors mapped to an orb, helix, or channel path."""

from dataclasses import dataclass
from math import floor
from typing import Optional


RGB = tuple[int, int, int]


@dataclass(frozen=True)
class LightVector:
    path: tuple[int, ...]
    samples: tuple[tuple[float, RGB], ...]
    position: float = 0.0
    brightness: float = 1.0
    wrap: bool = False
    brightness_override: Optional[float] = None


def solid(path, color, brightness=1.0, brightness_override=None):
    return LightVector(tuple(path), tuple((i, color) for i in range(len(path))),
                       brightness=brightness, brightness_override=brightness_override)


def trail(path, color, position, length=4, brightness=1.0, direction=1,
          wrap=False, brightness_override=None):
    samples = tuple((-direction * i, tuple(round(c * (1 - i / length))
                                      for c in color)) for i in range(length))
    return LightVector(tuple(path), samples, position, brightness, wrap,
                       brightness_override)


def render(vectors, total_leds, orb_leds=None,
           baseline_shaft_brightness=1.0, baseline_orb_brightness=1.0):
    frame = [[0.0, 0.0, 0.0] for _ in range(total_leds)]
    for vector in vectors:
        count = len(vector.path)
        if count == 0:
            continue
        for offset, color in vector.samples:
            point = vector.position + offset
            lower = floor(point)
            fraction = point - lower
            for path_index, weight in ((lower, 1 - fraction), (lower + 1, fraction)):
                if weight == 0:
                    continue
                if vector.wrap:
                    path_index %= count
                elif not 0 <= path_index < count:
                    continue
                led = vector.path[path_index]
                scale = vector.brightness_override
                if scale is None:
                    scale = (baseline_orb_brightness if orb_leds is not None and
                             led < orb_leds else baseline_shaft_brightness)
                for channel in range(3):
                    frame[led][channel] += (color[channel] * vector.brightness *
                                            scale * weight)
    return [tuple(max(0, min(255, round(c))) for c in led) for led in frame]

