"""Nonblocking base and triggered effects built from light vectors."""

import colorsys
import math
import random
from dataclasses import dataclass

from .vectors import LightVector, solid, trail


BASE_PATTERNS = ("green_spiral", "green_channels", "rainbow_sparks")
ORB_PULSE_HZ = 2.0
SPIRAL_LEDS_PER_SECOND = 24.0
CHANNEL_ROWS_PER_SECOND = 4.8
RAINBOW_CYCLE_SECONDS = 6.0
SPARK_CHANGES_PER_SECOND = 20


@dataclass(frozen=True)
class FallingBar:
    channel: int
    color: tuple[int, int, int]
    spawned_at: float
    bottom_at_rest: int
    will_stack: bool


def _bar(path, color, position, length, upward=False):
    offsets = range(length) if upward else range(0, -length, -1)
    return LightVector(tuple(path), tuple((offset, color) for offset in offsets),
                       position)


class StackingDropEffect:
    """Drop four-pixel channel bars, then unload one bar per channel at a time."""

    def __init__(self, geometry, fall_speed=100.0, drop_rate=8.0,
                 rise_speed=200.0, vector_length=4, max_stack_vectors=10,
                 rng=None, max_brightness=0.5):
        if min(fall_speed, drop_rate, rise_speed, vector_length,
               max_stack_vectors) <= 0:
            raise ValueError("stack effect speeds, length, and height must be positive")
        self.geometry = geometry
        self.fall_speed = fall_speed
        self.drop_rate = drop_rate
        self.rise_speed = rise_speed
        self.vector_length = vector_length
        self.max_stack_vectors = max_stack_vectors
        self.max_brightness = max_brightness
        self.rng = rng or random.Random()
        self.paths = geometry.channels
        self.stacks = [[] for _ in self.paths]  # Bottom to top, by color.
        self.falling = []
        self.drop_count = 0
        self.released_at = None
        self.unloading = [[] for _ in self.paths]  # Top to bottom: (top row, color).
        self.unload_index = [0 for _ in self.paths]
        self.unload_started_at = [0.0 for _ in self.paths]
        self.unload_flashed = [False for _ in self.paths]
        self.flash_until = 0.0

    def _advance_drops(self, elapsed):
        while self.drop_count / self.drop_rate <= elapsed:
            spawned_at = self.drop_count / self.drop_rate
            self._settle_drops(spawned_at)
            channel = self.drop_count % len(self.paths)
            path = self.paths[channel]
            reserved = len(self.stacks[channel]) + sum(
                drop.will_stack for drop in self.falling if drop.channel == channel)
            capacity = min(self.max_stack_vectors, len(path) // self.vector_length)
            level = min(reserved, max(0, capacity - 1))
            self.falling.append(FallingBar(
                channel, rainbow(self.rng.random()),
                spawned_at,
                len(path) - 1 - level * self.vector_length,
                reserved < capacity))
            self.drop_count += 1

        self._settle_drops(elapsed)

    def _settle_drops(self, elapsed):
        still_falling = []
        for drop in self.falling:
            landed_at = drop.spawned_at + (drop.bottom_at_rest + 1) / self.fall_speed
            if elapsed >= landed_at:
                if drop.will_stack:
                    self.stacks[drop.channel].append(drop.color)
            else:
                still_falling.append(drop)
        self.falling = still_falling

    def release(self, elapsed):
        if self.released_at is not None:
            return
        self._advance_drops(elapsed)
        self.released_at = elapsed
        self.falling.clear()
        for channel, path in enumerate(self.paths):
            self.unloading[channel] = [
                (len(path) - (level + 1) * self.vector_length, color)
                for level, color in reversed(list(enumerate(self.stacks[channel])))
            ]
            self.unload_started_at[channel] = elapsed

    def vectors(self, elapsed):
        if self.released_at is None:
            self._advance_drops(elapsed)
            vectors = [solid(self.geometry.orb, (0, 20, 90), 0.3)]
            for channel, path in enumerate(self.paths):
                for level, color in enumerate(self.stacks[channel]):
                    top = len(path) - (level + 1) * self.vector_length
                    vectors.append(solid(path[top:top + self.vector_length], color))
            for drop in self.falling:
                position = -1 + self.fall_speed * (elapsed - drop.spawned_at)
                vectors.append(_bar(self.paths[drop.channel], drop.color, position,
                                    self.vector_length))
            return vectors, False

        vectors = []
        for channel, path in enumerate(self.paths):
            queue = self.unloading[channel]
            while self.unload_index[channel] < len(queue):
                index = self.unload_index[channel]
                top, _ = queue[index]
                started = self.unload_started_at[channel]
                arrival = started + top / self.rise_speed
                end = started + (top + self.vector_length) / self.rise_speed
                if elapsed >= arrival and not self.unload_flashed[channel]:
                    self.flash_until = max(self.flash_until, arrival + 0.08)
                    self.unload_flashed[channel] = True
                if elapsed < end:
                    break
                self.unload_index[channel] += 1
                self.unload_started_at[channel] = end
                self.unload_flashed[channel] = False

            index = self.unload_index[channel]
            if index < len(queue):
                top, color = queue[index]
                position = top - self.rise_speed * (
                    elapsed - self.unload_started_at[channel])
                vectors.append(_bar(path, color, position, self.vector_length,
                                    upward=True))
            for top, color in queue[index + 1:]:
                vectors.append(solid(path[top:top + self.vector_length], color))

        finished = (all(index == len(queue) for index, queue in
                        zip(self.unload_index, self.unloading)) and
                    elapsed >= self.flash_until)
        if finished:
            return [], True
        orb_color = (255, 255, 255) if elapsed < self.flash_until else (140, 10, 10)
        vectors.insert(0, solid(
            self.geometry.orb, orb_color,
            1.0 if elapsed < self.flash_until else 0.35,
            brightness_override=(self.max_brightness if elapsed < self.flash_until
                                 else None)))
        return vectors, False


def rainbow(phase, scale=255):
    return tuple(round(channel * scale) for channel in
                 colorsys.hsv_to_rgb(phase % 1.0, 1.0, 1.0))


def _pulse(t):
    return 0.12 + 0.58 * (0.5 + 0.5 * math.cos(2 * math.pi * t * ORB_PULSE_HZ))


def base_vectors(name, t, geometry, max_brightness=0.5):
    vectors = []
    if name in ("green_spiral", "green_channels"):
        vectors.append(solid(geometry.orb, (0, 220, 20), _pulse(t)))
        if name == "green_spiral":
            count = len(geometry.stem)
            for index in range(3):
                position = (t * SPIRAL_LEDS_PER_SECOND + index * count / 3) % (count + 6) - 3
                depth = max(0.0, min(1.0, position / count))
                vectors.append(trail(geometry.stem, (40, 170, 100), position,
                                     length=5, brightness=0.8 * (1 - 0.75 * depth)))
        else:
            stride = max(1, geometry.leds_per_repeat // 4)
            selected = range(0, geometry.leds_per_repeat, stride)
            for index, channel_number in enumerate(list(selected)[:4]):
                path = geometry.channel(channel_number)
                position = (t * CHANNEL_ROWS_PER_SECOND + index * len(path) / 4) % (len(path) + 3) - 1
                depth = max(0.0, min(1.0, position / len(path)))
                vectors.append(trail(path, (55, 210, 95), position,
                                     length=3, brightness=0.85 * (1 - 0.65 * depth)))
        return vectors

    if name == "rainbow_sparks":
        vectors.append(solid(geometry.orb, rainbow(t / RAINBOW_CYCLE_SECONDS), 0.7))
        vectors.append(solid(geometry.stem, (2, 0, 8)))
        rng = random.Random(int(t * SPARK_CHANGES_PER_SECOND))
        for band in range(4):
            start = band * geometry.stem_leds // 4
            end = (band + 1) * geometry.stem_leds // 4
            if start >= end:
                continue
            local = rng.randrange(start, end)
            vectors.append(solid((geometry.stem[local],), rainbow(rng.random()),
                                 0.65, brightness_override=max_brightness))
        return vectors

    raise ValueError(f"Unknown base pattern: {name}")


def manual_vectors(name, elapsed, geometry, charge_time=0.0,
                   max_brightness=0.5):
    """Return (vectors, finished) for a finite triggered effect."""
    stem = geometry.stem
    if name == "descent_fill":
        if elapsed < 1.5:
            position = -1 + elapsed / 1.5 * (len(stem) + 2)
            return [trail(stem, (20, 200, 255), position, length=6)], False
        if elapsed < 3.0:
            fraction = (elapsed - 1.5) / 1.5
            lit = min(len(stem), math.ceil(fraction * len(stem)))
            return [solid(stem[-lit:], (160, 30, 230), 0.75)] if lit else [], False
        if elapsed < 4.0:
            color = rainbow(math.floor((elapsed - 3) * 9) / 9)
            return [solid(stem, (22, 4, 35)),
                    solid(geometry.orb, color, 0.85,
                          brightness_override=max_brightness)], False
        return [], True

    if name == "upward_spirals":
        cycle_s = 0.9
        if elapsed >= 3 * cycle_s:
            return [], True
        phase = (elapsed % cycle_s) / cycle_s
        vectors = []
        for index in range(3):
            offset = index * len(stem) / 5
            position = len(stem) + offset - phase * (len(stem) + 6)
            vectors.append(trail(stem, rainbow(index / 3 + elapsed / 5),
                                 position, length=5, direction=-1))
        if phase > 0.78:
            vectors.append(solid(geometry.orb, rainbow(elapsed / 3),
                                 (phase - 0.78) / 0.22,
                                 brightness_override=max_brightness))
        return vectors, False

    if name == "channel_wave":
        if elapsed >= 3.0:
            return [], True
        vectors = [solid(geometry.orb, (60, 0, 100), 0.35)]
        for number, path in enumerate(geometry.channels):
            phase = elapsed * 2.5 - number / geometry.leds_per_repeat
            brightness = 0.15 + 0.65 * (0.5 + 0.5 * math.cos(2 * math.pi * phase))
            vectors.append(solid(path, rainbow(number / geometry.leds_per_repeat),
                                 brightness))
        return vectors, False

    if name == "charge":
        speed = 0.6 + min(elapsed, 8.0) * 0.25
        vectors = [solid(geometry.orb, (15, 0, 80), min(0.8, 0.15 + elapsed * 0.07))]
        for index in range(7):
            position = (len(stem) - 1 - (elapsed * speed + index / 7) * len(stem)) % (len(stem) + 5)
            vectors.append(trail(stem, rainbow(index / 7 + elapsed * 0.1),
                                 position, length=4, direction=-1, brightness=0.7))
        return vectors, False

    if name == "release_burst":
        if elapsed >= 1.5:
            return [], True
        vectors = []
        for index in range(12):
            position = len(stem) - 1 - elapsed * (len(stem) / 0.75) + index * len(stem) / 18
            vectors.append(trail(stem, rainbow(index / 12 + elapsed * 0.3),
                                 position, length=7, direction=-1,
                                 brightness=min(1.0, 0.55 + charge_time * 0.07),
                                 brightness_override=max_brightness))
        if elapsed >= 0.55:
            vectors.append(solid(geometry.orb, rainbow(elapsed * 2),
                                 min(1.0, 0.6 + charge_time * 0.05),
                                 brightness_override=max_brightness))
        return vectors, False

    if name == "unset":
        if elapsed >= 0.45:
            return [], True
        return [solid(geometry.unset_indicator, (70, 0, 0), 0.35)], False

    raise ValueError(f"Unknown manual effect: {name}")

