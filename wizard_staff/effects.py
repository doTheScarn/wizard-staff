"""Nonblocking base and triggered effects built from light vectors."""

import colorsys
import math
import random
from dataclasses import dataclass

from .vectors import LightVector, solid, trail


BASE_PATTERNS = ("green_spiral", "green_channels", "bounce_vectors")
ORB_PULSE_HZ = 2.0
SPIRAL_LEDS_PER_SECOND = 48.0
CHANNEL_ROWS_PER_SECOND = 9.6
RAINBOW_CYCLE_SECONDS = 6.0
SPARK_CHANGES_PER_SECOND = 20
ORB_ACCENT_SECONDS = 0.1
BOUNCE_LEDS_PER_SECOND = 120.0
CHANNEL_ROTATIONS_PER_SECOND = 4.0
CHANNEL_WAVE_ROWS_PER_SECOND = 56.0
CHANNEL_WAVE_PERIOD_ROWS = 24
CHANNEL_WAVE_DARK_ROWS = 6
BOUNCE_PREFLASH_SECONDS = 0.1
STACK_FLASH_SEQUENCE_SECONDS = 0.36
STACK_WHITE_HOLD_SECONDS = 0.4
STACK_FADE_SECONDS = 0.15
OPPOSED_PAIR_WRAPS = 30
OPPOSED_PAIR_INTERVAL_SECONDS = 0.5
OPPOSED_PAIR_LAUNCH_SECONDS = 3.0
DESCENT_FALL_SECONDS = 1.0
DESCENT_FILL_SECONDS = 1.5
DESCENT_HOLD_SECONDS = 1.0
DESCENT_TOTAL_SECONDS = (DESCENT_FALL_SECONDS + DESCENT_FILL_SECONDS +
                        DESCENT_HOLD_SECONDS)
CHANNEL_WAVE_TOTAL_SECONDS = 3.0
RELEASE_BURST_SECONDS = 1.5
UNSET_INDICATOR_SECONDS = 0.45


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
        self.unload_motion_end_at = None
        self.unload_finish_at = None

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
        self.unload_motion_end_at = elapsed
        for queue in self.unloading:
            next_start = elapsed
            for top, _ in queue:
                next_start += (top + self.vector_length) / self.rise_speed
                self.unload_motion_end_at = max(self.unload_motion_end_at,
                                                next_start)
        self.unload_finish_at = (self.unload_motion_end_at +
                                 STACK_FLASH_SEQUENCE_SECONDS +
                                 STACK_WHITE_HOLD_SECONDS + STACK_FADE_SECONDS)

    def vectors(self, elapsed):
        if self.released_at is None:
            self._advance_drops(elapsed)
            vectors = []
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
                end = started + (top + self.vector_length) / self.rise_speed
                if elapsed < end:
                    break
                self.unload_index[channel] += 1
                self.unload_started_at[channel] = end

            index = self.unload_index[channel]
            if index < len(queue):
                top, color = queue[index]
                position = top - self.rise_speed * (
                    elapsed - self.unload_started_at[channel])
                vectors.append(_bar(path, color, position, self.vector_length,
                                    upward=True))
            for top, color in queue[index + 1:]:
                vectors.append(solid(path[top:top + self.vector_length], color))

        finished = elapsed >= self.unload_finish_at
        if finished:
            return [], True
        if elapsed < self.unload_motion_end_at:
            duration = max(0.001, self.unload_motion_end_at - self.released_at)
            progress = max(0.0, min(1.0,
                                    (elapsed - self.released_at) / duration))
            orb_level = progress ** 3
        else:
            post = elapsed - self.unload_motion_end_at
            if post < STACK_FLASH_SEQUENCE_SECONDS:
                orb_level = (1.0 if any(start <= post < start + 0.06
                                        for start in (0.06, 0.18, 0.30)) else 0.0)
            elif post < STACK_FLASH_SEQUENCE_SECONDS + STACK_WHITE_HOLD_SECONDS:
                orb_level = 1.0
            else:
                fade_age = (post - STACK_FLASH_SEQUENCE_SECONDS -
                            STACK_WHITE_HOLD_SECONDS)
                orb_level = max(0.0, 1.0 - fade_age / STACK_FADE_SECONDS)
        if orb_level:
            vectors.insert(0, solid(self.geometry.orb, (255, 255, 255),
                                    orb_level, brightness_override=self.max_brightness))
        return vectors, False


def rainbow(phase, scale=255):
    return tuple(round(channel * scale) for channel in
                 colorsys.hsv_to_rgb(phase % 1.0, 1.0, 1.0))


def _pulse(t):
    return 0.44 + 0.24 * (0.5 + 0.5 * math.cos(2 * math.pi * t * ORB_PULSE_HZ))


def _launch_accent(t, speeds_and_offsets):
    """Peak a subtle white overlay halfway through each 0.1-second launch cue."""
    age = min(((t * speed + offset) % span) / speed
              for speed, offset, span in speeds_and_offsets)
    return max(0.0, 1.0 - abs(age - ORB_ACCENT_SECONDS / 2) /
               (ORB_ACCENT_SECONDS / 2))


def opposed_pair_clear_time(geometry):
    """Time from one launch until both 30-wrap vectors clear the stem."""
    length = min(round(OPPOSED_PAIR_WRAPS * geometry.leds_per_repeat /
                       geometry.turns_per_repeat), len(geometry.stem))
    to_end = (len(geometry.stem) - 1) / 2
    half_gone_distance = to_end + length / 2
    final_speed = half_gone_distance / OPPOSED_PAIR_INTERVAL_SECONDS * 0.9
    return (OPPOSED_PAIR_INTERVAL_SECONDS +
            (to_end + length - half_gone_distance) / final_speed)


def opposed_pair_effect_duration(geometry):
    """Return the time from first launch until the final pair clears."""
    last_launch_at = OPPOSED_PAIR_LAUNCH_SECONDS - OPPOSED_PAIR_INTERVAL_SECONDS
    return last_launch_at + opposed_pair_clear_time(geometry)


def upward_spiral_timing(stem_length):
    """Return (group interval, rise speed, group lifetime) for spiral bursts."""
    group_interval = 0.65
    rise_speed = (stem_length + 6) / 0.9
    group_lifetime = (stem_length * 1.2 + 6) / rise_speed + 0.12
    return group_interval, rise_speed, group_lifetime


def upward_spiral_effect_duration(stem_length):
    """Return the duration of the default three upward spiral groups."""
    group_interval, _, group_lifetime = upward_spiral_timing(stem_length)
    return 2 * group_interval + group_lifetime


def opposed_pair_vectors(elapsed, geometry, peak_brightness=1.0,
                         launch_until=None):
    """Launch blue and green pairs from the center toward opposite ends."""
    stem = geometry.stem
    length = min(round(OPPOSED_PAIR_WRAPS * geometry.leds_per_repeat /
                       geometry.turns_per_repeat), len(stem))
    center = (len(stem) - 1) / 2
    to_end = max(center, len(stem) - 1 - center)
    half_gone_distance = to_end + length / 2
    interval = OPPOSED_PAIR_INTERVAL_SECONDS
    average_speed = half_gone_distance / interval
    initial_speed = average_speed * 1.1
    final_speed = average_speed * 0.9
    deceleration = (initial_speed - final_speed) / interval
    fully_gone_at = interval + (to_end + length - half_gone_distance) / final_speed
    newest = int(elapsed // interval)
    if launch_until is not None:
        newest = min(newest, math.ceil(launch_until / interval) - 1)
    oldest = max(0, int((elapsed - fully_gone_at) // interval))
    vectors = []
    for pair in range(oldest, newest + 1):
        age = elapsed - pair * interval
        if age < 0 or age >= fully_gone_at:
            continue
        if age <= interval:
            distance = initial_speed * age - 0.5 * deceleration * age * age
        else:
            distance = half_gone_distance + final_speed * (age - interval)
        color = (0, 0, 255) if pair % 2 == 0 else (0, 255, 0)
        tail_length = min(length, int(distance) + 1)
        for direction in (-1, 1):
            samples = tuple(
                (-direction * offset,
                 tuple(round(channel * (1 - offset / max(1, length - 1)))
                       for channel in color))
                for offset in range(tail_length))
            vectors.append(LightVector(stem, samples,
                                       center + direction * distance,
                                       brightness_override=peak_brightness))
    return vectors


def base_vectors(name, t, geometry, max_brightness=0.5):
    vectors = []
    if name in ("green_spiral", "green_channels"):
        vectors.append(solid(geometry.orb, (0, 220, 20), _pulse(t)))
        if name == "green_spiral":
            count = len(geometry.stem)
            launches = []
            for index in range(3):
                offset = index * count / 3
                span = count + 6
                position = (t * SPIRAL_LEDS_PER_SECOND + offset) % span - 3
                launches.append((SPIRAL_LEDS_PER_SECOND, offset, span))
                depth = max(0.0, min(1.0, position / count))
                vectors.append(trail(geometry.stem, (40, 170, 100), position,
                                     length=5, brightness=0.8 * (1 - 0.75 * depth)))
        else:
            stride = max(1, geometry.leds_per_repeat // 4)
            selected = range(0, geometry.leds_per_repeat, stride)
            launches = []
            for index, channel_number in enumerate(list(selected)[:4]):
                path = geometry.channel(channel_number)
                offset = index * len(path) / 4
                span = len(path) + 3
                position = (t * CHANNEL_ROWS_PER_SECOND + offset) % span - 1
                launches.append((CHANNEL_ROWS_PER_SECOND, offset, span))
                depth = max(0.0, min(1.0, position / len(path)))
                vectors.append(trail(path, (55, 210, 95), position,
                                     length=3, brightness=0.85 * (1 - 0.65 * depth)))
        accent = _launch_accent(t, launches)
        if accent:
            vectors.append(solid(geometry.orb, (255, 255, 255), 0.25 * accent))
        return vectors

    if name == "bounce_vectors":
        stem = geometry.stem
        length = min(2 * geometry.leds_per_repeat, max(1, len(stem) // 2))
        bottom = max(0, len(stem) - 2 * length)
        travel_s = max(2 * BOUNCE_PREFLASH_SECONDS,
                       bottom / BOUNCE_LEDS_PER_SECOND)
        vectors.append(solid(stem[-length:], (0, 20, 255), 0.9))
        phase = t % travel_s
        orb_color = (190, 28, 0) if phase < BOUNCE_PREFLASH_SECONDS else (255, 100, 0)
        orb_level = 0.55 if phase < BOUNCE_PREFLASH_SECONDS else 0.9
        vectors.append(solid(geometry.orb, orb_color, orb_level,
                             brightness_override=max_brightness))
        if t >= BOUNCE_PREFLASH_SECONDS:
            current_launch = int((t - BOUNCE_PREFLASH_SECONDS) // travel_s)
            for launch in range(max(0, current_launch - 1), current_launch + 1):
                age = t - BOUNCE_PREFLASH_SECONDS - launch * travel_s
                if not 0 <= age < 2 * travel_s:
                    continue
                position = min(bottom, min(age, 2 * travel_s - age) *
                               BOUNCE_LEDS_PER_SECOND)
                fall_scale = 0.4 * max_brightness
                if age <= travel_s or bottom == 0:
                    scale = fall_scale
                else:
                    top_scale = min(0.05, fall_scale)
                    scale = top_scale + (fall_scale - top_scale) * position / bottom
                vectors.append(LightVector(
                    stem, tuple((offset, (255, 255, 255)) for offset in range(length)),
                    position, brightness_override=scale))
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
                   max_brightness=0.5, continuation=False, stop_at=None):
    """Return (vectors, finished) for a finite triggered effect."""
    stem = geometry.stem
    if name == "descent_fill":
        fall_s = DESCENT_FALL_SECONDS
        fill_s = DESCENT_FILL_SECONDS
        if elapsed < fall_s:
            position = -1 + elapsed / fall_s * (len(stem) + 2)
            return [trail(stem, (20, 200, 255), position, length=6)], False
        if elapsed < fall_s + fill_s:
            fraction = (elapsed - fall_s) / fill_s
            lit = min(len(stem), math.ceil(fraction * len(stem)))
            head = len(stem) - 1 - fraction * (len(stem) - 1)
            vectors = [solid(stem[-lit:], (255, 0, 0), 0.4)] if lit else []
            vectors.append(trail(stem, (20, 200, 255), head,
                                 length=6, direction=-1))
            return vectors, False
        if elapsed < DESCENT_TOTAL_SECONDS:
            color = rainbow(math.floor((elapsed - fall_s - fill_s) * 9) / 9)
            return [solid(stem, (255, 0, 0), 0.4),
                    solid(geometry.orb, color, 0.85,
                          brightness_override=max_brightness)], False
        return [], True

    if name == "upward_spirals":
        group_interval, rise_speed, group_lifetime = upward_spiral_timing(len(stem))
        last_group = int(elapsed // group_interval)
        if stop_at is not None:
            last_group = min(last_group, math.ceil(stop_at / group_interval) - 1)
        elif not continuation:
            last_group = min(last_group, 2)
        if (last_group < 0 or
                ((stop_at is not None or not continuation) and
                 elapsed >= last_group * group_interval + group_lifetime)):
            return [], True
        vectors = [solid(geometry.orb, (170, 125, 10), 0.85)]
        first_group = max(0, int((elapsed - group_lifetime) // group_interval))
        for group in range(first_group, last_group + 1):
            started = group * group_interval
            if elapsed < started:
                continue
            for index in range(3):
                offset = index * len(stem) / 10
                position = len(stem) + offset - rise_speed * (elapsed - started)
                vectors.append(trail(stem, rainbow(index / 3 + group / 5),
                                     position, length=5, direction=-1))
            arrival = started + (len(stem) * 1.2 + 6) / rise_speed
            flash_age = elapsed - arrival
            if 0 <= flash_age < 0.12:
                vectors.append(solid(geometry.orb, (30, 90, 255),
                                     0.35 * math.sin(math.pi * flash_age / 0.12)))
        return vectors, False

    if name == "channel_wave":
        channels = geometry.channels
        clear_s = max(len(path) for path in channels) / CHANNEL_WAVE_ROWS_PER_SECOND
        if stop_at is not None and elapsed >= stop_at + clear_s:
            return [], True
        if (stop_at is None and not continuation and
                elapsed >= CHANNEL_WAVE_TOTAL_SECONDS):
            return [], True
        vectors = [solid(geometry.orb, (255, 255, 255), 0.8,
                         brightness_override=max_brightness)]
        rotation = int(elapsed * CHANNEL_ROTATIONS_PER_SECOND) % len(channels)
        for source in range(len(channels)):
            path = channels[(source + rotation) % len(channels)]
            pulse = 0.15 + 0.65 * (0.5 + 0.5 * math.cos(
                2 * math.pi * (elapsed * 2.5 - source / len(channels))))
            color = rainbow(source / len(channels))
            samples = []
            last_active_row = (len(path) - 1 -
                               CHANNEL_WAVE_ROWS_PER_SECOND * (elapsed - stop_at)
                               if stop_at is not None else len(path) - 1)
            for row in range(len(path)):
                if row > last_active_row:
                    continue
                phase = (row + elapsed * CHANNEL_WAVE_ROWS_PER_SECOND) % CHANNEL_WAVE_PERIOD_ROWS
                if phase < CHANNEL_WAVE_DARK_ROWS:
                    continue
                ramp = 1.0 - (phase - CHANNEL_WAVE_DARK_ROWS) / (
                    CHANNEL_WAVE_PERIOD_ROWS - CHANNEL_WAVE_DARK_ROWS)
                samples.append((row, tuple(round(c * ramp) for c in color)))
            vectors.append(LightVector(path, tuple(samples),
                                       brightness=0.5 * pulse))
        return vectors, False

    if name == "opposed_pairs":
        launch_until = (stop_at if stop_at is not None else
                        None if continuation else OPPOSED_PAIR_LAUNCH_SECONDS)
        vectors = opposed_pair_vectors(elapsed, geometry, max_brightness,
                                       launch_until=launch_until)
        return vectors, (launch_until is not None and not vectors and
                         elapsed >= launch_until)

    if name == "charge":
        speed = 0.3 + min(elapsed, 8.0) * 0.125
        vectors = [solid(geometry.orb, (10, 80, 255),
                         min(0.9, 0.35 + elapsed * 0.07))]
        for index in range(7):
            position = (len(stem) - 1 - (elapsed * speed + index / 7) * len(stem)) % (len(stem) + 5)
            vectors.append(trail(stem, rainbow(index / 7 + elapsed * 0.1),
                                 position, length=4, direction=-1, brightness=0.7))
        return vectors, False

    if name == "release_burst":
        if elapsed >= RELEASE_BURST_SECONDS:
            return [], True
        arrival = (len(stem) - 1) * 0.75 / len(stem)
        blue_level = min(0.9, 0.35 + charge_time * 0.07)
        if elapsed < arrival:
            vectors = [solid(geometry.orb, (10, 80, 255), blue_level)]
        else:
            vectors = [solid(geometry.orb, (170, 0, 220), 1.0,
                             brightness_override=max_brightness)]
            flash_age = (elapsed - arrival) % 0.12
            white_pulse = max(0.0, 1.0 - abs(flash_age - 0.03) / 0.03)
            if white_pulse:
                vectors.append(solid(geometry.orb, (255, 255, 255),
                                     0.45 * white_pulse,
                                     brightness_override=max_brightness))
        for index in range(12):
            position = len(stem) - 1 - elapsed * (len(stem) / 0.75) + index * len(stem) / 18
            vectors.append(trail(stem, rainbow(index / 12 + elapsed * 0.3),
                                 position, length=7, direction=-1,
                                 brightness=min(1.0, 0.55 + charge_time * 0.07),
                                 brightness_override=max_brightness))
        return vectors, False

    if name == "unset":
        if elapsed >= UNSET_INDICATOR_SECONDS:
            return [], True
        return [solid(geometry.unset_indicator, (70, 0, 0), 0.35)], False

    raise ValueError(f"Unknown manual effect: {name}")

