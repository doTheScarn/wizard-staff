"""Independent light vectors mapped to an orb, helix, or channel path."""

from dataclasses import dataclass
from math import floor
from functools import lru_cache
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


def palette_color(palette, fraction):
    """Interpolate an ordered head-to-tail palette in logical RGB."""
    point = max(0.0, min(1.0, fraction)) * (len(palette) - 1)
    index = min(floor(point), len(palette) - 1)
    blend = point - index
    following = palette[min(index + 1, len(palette) - 1)]
    return tuple(round(a + (b - a) * blend)
                 for a, b in zip(palette[index], following))


def palette_trail(path, palette, position, length=4, brightness=1.0,
                  direction=1, brightness_override=None):
    """A colored head, changing hue and fading toward the end of its tail."""
    samples = []
    for index in range(length):
        fraction = index / max(1, length - 1)
        color = palette_color(palette, fraction)
        fade = 1 - index / length
        samples.append((-direction * index,
                        tuple(round(channel * fade) for channel in color)))
    return LightVector(tuple(path), tuple(samples), position,
                       brightness=brightness,
                       brightness_override=brightness_override)


@lru_cache(maxsize=8)
def _gamma_table(gamma):
    return tuple(255 * (index / 255) ** gamma for index in range(256))


def _gamma_level(value, table, gamma):
    value = max(0.0, value)
    if value >= 255:
        return 255 * (value / 255) ** gamma
    lower = floor(value)
    fraction = value - lower
    return table[lower] + (table[lower + 1] - table[lower]) * fraction


def render(vectors, total_leds, orb_leds=None,
           baseline_shaft_brightness=1.0, baseline_orb_brightness=1.0,
           gamma=1.0):
    # Convert authored colors/envelopes to PWM intensity before adding light.
    # Region/override multipliers and fractional spatial coverage stay linear.
    table = _gamma_table(gamma) if gamma != 1.0 else None
    frame = [[0.0, 0.0, 0.0] for _ in range(total_leds)]
    for vector in vectors:
        count = len(vector.path)
        if count == 0:
            continue
        for offset, color in vector.samples:
            levels = tuple(channel * vector.brightness for channel in color)
            if table is not None:
                levels = tuple(_gamma_level(value, table, gamma) for value in levels)
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
                    frame[led][channel] += levels[channel] * scale * weight
    return [tuple(max(0, min(255, round(c))) for c in led) for led in frame]

