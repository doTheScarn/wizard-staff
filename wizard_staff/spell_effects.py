"""Palette-based spells and color themes shared with the existing effects."""

import math

from .vectors import LightVector, palette_trail, solid


EMBER_PALETTE = ((255, 205, 80), (255, 45, 0), (100, 0, 8))
MIST_PALETTE = ((210, 245, 255), (15, 155, 255), (45, 8, 120))
RED_PALETTE = ((255, 32, 5), (255, 0, 0), (65, 0, 15))
SPELL_DURATIONS = {"twisting_ribbons": 5.0, "gathering_spell": 4.2}
GATHERING_LAUNCHES = ((0.3, 0.55), (0.8, 0.65), (1.95, 1.0))
GATHERING_TRAVEL_SECONDS = 1.3


def _smooth(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3 - 2 * value)


def twisting_ribbons(elapsed, geometry, max_brightness):
    """Grow two opposing ribbons, twist them, then let their light settle."""
    if elapsed >= SPELL_DURATIONS["twisting_ribbons"]:
        return [], True
    vectors = []
    growth = _smooth(elapsed / 1.4)
    fade = 1 - _smooth((elapsed - 3.8) / 0.7)
    channels = geometry.channels
    channel_count = len(channels)
    for channel, path in enumerate(channels):
        samples = []
        for row in range(len(path)):
            height = 1 - row / max(1, len(path) - 1)
            reveal = _smooth((growth * 1.12 - height) / 0.12)
            angle = 2 * math.pi * (channel * geometry.turns_per_repeat /
                                   channel_count -
                                   0.65 * elapsed + height * 1.8)
            # Broad angular lobes remain readable with four LEDs per wrap.
            warm = max(0.0, math.cos(angle))
            cool = max(0.0, math.cos(angle + math.pi))
            color = tuple(round((a * warm + b * cool) * reveal)
                          for a, b in zip((255, 100, 12), (15, 145, 255)))
            samples.append((row, color))
        vectors.append(LightVector(path, tuple(samples), brightness=fade,
                                   brightness_override=0.65 * max_brightness))
    # A quiet release after the stem fades gives the effect an ending.
    if 4.2 <= elapsed < 5.0:
        age = elapsed - 4.2
        level = math.sin(math.pi * age / 0.8) ** 2
        vectors.append(solid(geometry.orb, (30, 115, 255), 0.5 * level,
                             brightness_override=max_brightness))
    return vectors, False


def gathering_spell(elapsed, geometry, max_brightness):
    """Two smaller channel launches, a pause, then a stronger spiral arrival."""
    if elapsed >= SPELL_DURATIONS["gathering_spell"]:
        return [], True
    stem = geometry.stem
    vectors = []
    orb_level = 0.0
    units_per_wrap = geometry.leds_per_repeat / geometry.turns_per_repeat
    channels = geometry.channels
    opposite = len(channels) // (2 * geometry.turns_per_repeat)
    source_channels = sorted({0, opposite})
    for launch_number, (started, strength) in enumerate(GATHERING_LAUNCHES):
        age = elapsed - started
        if -0.16 <= age < 0:
            # A small gathering glow at the source precedes each launch.
            level = _smooth((age + 0.16) / 0.16) * strength
            for channel in source_channels:
                vectors.append(solid(channels[channel][-2:],
                                     (15, 100, 255), 0.4 * level))
        if 0 <= age < GATHERING_TRAVEL_SECONDS:
            progress = age / GATHERING_TRAVEL_SECONDS
            head = (len(stem) - 1) * (1 - progress)
            blend = _smooth((progress - 0.3) / 0.45)
            tail_wraps = 8 if launch_number == 2 else 4
            tail_length = max(1, round(tail_wraps * units_per_wrap))
            for channel in source_channels:
                vectors.append(palette_trail(
                    channels[channel], MIST_PALETTE,
                    (head - channel) / geometry.leds_per_repeat,
                    length=max(1, round(tail_length / geometry.leds_per_repeat)),
                    direction=-1, brightness=0.7 * strength * (1 - blend),
                    brightness_override=max_brightness))
            vectors.append(palette_trail(
                stem, MIST_PALETTE, head, length=tail_length, direction=-1,
                brightness=strength * blend,
                brightness_override=max_brightness))
        flash_age = age - GATHERING_TRAVEL_SECONDS
        if 0 <= flash_age < 0.6:
            orb_level = max(orb_level, strength * (1 - flash_age / 0.6) ** 2)
    if orb_level:
        vectors.append(solid(geometry.orb, (100, 205, 255), orb_level,
                             brightness_override=max_brightness))
    return vectors, False


def spell_vectors(name, elapsed, geometry, max_brightness):
    if name == "twisting_ribbons":
        return twisting_ribbons(elapsed, geometry, max_brightness)
    if name == "gathering_spell":
        return gathering_spell(elapsed, geometry, max_brightness)
    raise ValueError(f"Unknown spell: {name}")
