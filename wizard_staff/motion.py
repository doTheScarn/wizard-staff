"""Small kinematics helpers for effects that opt into downward acceleration."""

import math


ACCELERATION_LEVELS = {"low": 6.0, "med": 10.0, "high": 14.0}


def downward_acceleration(level, units_per_wrap=1.0):
    """Convert a named physical-wrap acceleration to path units/s²."""
    if level in (None, "off"):
        return 0.0
    try:
        return ACCELERATION_LEVELS[level] * units_per_wrap
    except KeyError as exc:
        raise ValueError(f"Unknown downward acceleration level: {level}") from exc


def position(start, velocity, acceleration, elapsed):
    return start + velocity * elapsed + 0.5 * acceleration * elapsed ** 2


def velocity_at(velocity, acceleration, elapsed):
    return velocity + acceleration * elapsed


def time_to_position(start, target, velocity, acceleration, direction=None):
    """First nonnegative crossing time, optionally requiring a travel direction."""
    distance = target - start
    if abs(acceleration) < 1e-12:
        roots = [] if abs(velocity) < 1e-12 else [distance / velocity]
    else:
        discriminant = velocity * velocity + 2 * acceleration * distance
        if discriminant < 0:
            return None
        root = math.sqrt(max(0.0, discriminant))
        roots = [(-velocity - root) / acceleration,
                 (-velocity + root) / acceleration]
    candidates = [t for t in roots if t >= 0 and
                  (direction is None or
                   (velocity_at(velocity, acceleration, t) * direction > 0))]
    return min(candidates) if candidates else None
