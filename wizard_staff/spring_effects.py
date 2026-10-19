"""Opposing sparse spirals with reproducible, independent random launches."""

import math
import random
from dataclasses import dataclass

from .motion import directional_acceleration, position, time_to_position
from .spell_effects import STACK_COLORS
from .vectors import trail, solid

SPRING_INTERVAL_SECONDS = 1.0
SPRING_SPEED_WRAPS = (12.0, 22.0)
SPRING_TAIL_WRAPS = 8


@dataclass(frozen=True)
class SpringLaunch:
    path: tuple
    color: tuple
    direction: int
    speed: float
    acceleration: float
    start: float
    lifetime: float
    length: int


def spring_launches(group, geometry):
    """Generate a fixed pair for a launch index, independent of frame rate."""
    rng = random.Random(41041 + group)
    paths = [path for path in geometry.spiral_channels if path]
    units = geometry.leds_per_repeat / (3 * geometry.turns_per_repeat)
    length = max(2, round(SPRING_TAIL_WRAPS * units))
    launches = []
    for direction in (1, -1):
        path = rng.choice(paths)
        color = rng.choice(STACK_COLORS)
        speed = rng.uniform(*SPRING_SPEED_WRAPS) * units
        level = rng.choice(("low", "med", "high"))
        acceleration = directional_acceleration(level, direction, units)
        start = -1.0 if direction > 0 else float(len(path))
        target = len(path) + length if direction > 0 else -length
        lifetime = time_to_position(start, target, direction * speed,
                                    acceleration, direction=direction)
        launches.append(SpringLaunch(path, color, direction, speed, acceleration,
                                     start, lifetime, length))
    return tuple(launches)


def spring_vectors(elapsed, geometry, max_brightness):
    units = geometry.leds_per_repeat / (3 * geometry.turns_per_repeat)
    max_path = max(len(path) for path in geometry.spiral_channels)
    length = max(2, round(SPRING_TAIL_WRAPS * units))
    # Keep only the bounded history that could still be visible at the slowest
    # launch speed and acceleration. No unbounded list of old particles grows.
    max_lifetime = time_to_position(-1, max_path + length,
                                    SPRING_SPEED_WRAPS[0] * units,
                                    directional_acceleration("low", 1, units), 1)
    newest = int(elapsed // SPRING_INTERVAL_SECONDS)
    oldest = max(0, newest - math.ceil(max_lifetime / SPRING_INTERVAL_SECONDS) - 1)
    vectors = [solid(geometry.orb, (120, 180, 255), 0.85,
                     brightness_override=max_brightness)]
    for group in range(oldest, newest + 1):
        age = elapsed - group * SPRING_INTERVAL_SECONDS
        for launch in spring_launches(group, geometry):
            if not 0 <= age < launch.lifetime:
                continue
            head = position(launch.start, launch.direction * launch.speed,
                            launch.acceleration, age)
            vectors.append(trail(launch.path, launch.color, head,
                                 length=launch.length, direction=launch.direction,
                                 brightness_override=0.5 * max_brightness, tail_power=2.0))
    return vectors
