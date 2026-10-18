"""Nonblocking base and triggered effects built from light vectors."""

import colorsys
import math
import random
from dataclasses import dataclass

from .vectors import LightVector, palette_color, palette_trail, solid, trail
from .motion import downward_acceleration, position as motion_position, time_to_position
from .spell_effects import (EMBER_PALETTE, MIST_PALETTE, RED_PALETTE,
                           SPELL_DURATIONS, spell_vectors)


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
BOUNCE_FLASH_SECONDS = 0.1
# Kept as an alias for callers that imported the former timing constant.
BOUNCE_FLASH_DELAY_SECONDS = BOUNCE_FLASH_SECONDS
BOUNCE_REST_SECONDS = 0.2
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


def _bar(path, color, position, length, upward=False, brightness=1.0):
    offsets = range(length) if upward else range(0, -length, -1)
    return LightVector(tuple(path), tuple((offset, color) for offset in offsets),
                       position, brightness=brightness)


class StackingDropEffect:
    """Drop four-pixel channel bars, then unload one bar per channel at a time."""

    def __init__(self, geometry, fall_speed=100.0, drop_rate=8.0,
                 rise_speed=200.0, vector_length=4, max_stack_vectors=10,
                 rng=None, max_brightness=0.5,
                 downward_acceleration_level="off", allow_reversal=True):
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
        self.acceleration = downward_acceleration(
            downward_acceleration_level, 1 / geometry.turns_per_repeat)
        self.allow_reversal = allow_reversal
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
            travel = ((drop.bottom_at_rest + 1) / self.fall_speed
                      if not self.acceleration else
                      time_to_position(-1, drop.bottom_at_rest,
                                       self.fall_speed, self.acceleration,
                                       direction=1))
            landed_at = drop.spawned_at + (travel or 0.0)
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
                next_start += self._unload_duration(top)
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
                age = elapsed - drop.spawned_at
                bar_position = (-1 + self.fall_speed * age
                                if not self.acceleration else
                                motion_position(-1, self.fall_speed,
                                                self.acceleration, age))
                vectors.append(_bar(self.paths[drop.channel], drop.color, bar_position,
                                    self.vector_length))
            return vectors, False

        vectors = []
        for channel, path in enumerate(self.paths):
            queue = self.unloading[channel]
            while self.unload_index[channel] < len(queue):
                index = self.unload_index[channel]
                top, _ = queue[index]
                started = self.unload_started_at[channel]
                end = started + self._unload_duration(top)
                if elapsed < end:
                    break
                self.unload_index[channel] += 1
                self.unload_started_at[channel] = end

            index = self.unload_index[channel]
            if index < len(queue):
                top, color = queue[index]
                age = elapsed - self.unload_started_at[channel]
                bar_position = (top - self.rise_speed * age
                                if not self.acceleration else
                                motion_position(top, -self.rise_speed,
                                                self.acceleration, age))
                fade = 1.0
                if self.acceleration and not self.allow_reversal and \
                        self._unload_duration(top) > self.rise_speed / self.acceleration:
                    fade = max(0.0, 1 - (age - self.rise_speed /
                                         self.acceleration) / STACK_FADE_SECONDS)
                vectors.append(_bar(path, color, bar_position, self.vector_length,
                                    upward=True, brightness=fade))
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

    def _unload_duration(self, top):
        if not self.acceleration:
            return (top + self.vector_length) / self.rise_speed
        arrival = time_to_position(top, -self.vector_length, -self.rise_speed,
                                   self.acceleration, direction=-1)
        if arrival is not None:
            return arrival
        if not self.allow_reversal:
            return self.rise_speed / self.acceleration + STACK_FADE_SECONDS
        clear = time_to_position(top, len(self.paths[0]) + self.vector_length,
                                 -self.rise_speed, self.acceleration,
                                 direction=1)
        return clear if clear is not None else 0.0


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


def _accelerated_falling_position(elapsed, path_length, speed, acceleration,
                                  offset=0.0, start_offset=1.0):
    """Repeat a downward launch with fixed launch speed and gravity."""
    start = -start_offset + offset
    flight = time_to_position(start, path_length + 2, speed, acceleration,
                              direction=1)
    if not flight:
        return start
    age = elapsed % flight
    return motion_position(start, speed, acceleration, age)


def opposed_pair_clear_time(geometry):
    """Time from one launch until both 30-wrap vectors clear the stem."""
    length = min(round(OPPOSED_PAIR_WRAPS * geometry.leds_per_repeat /
                       geometry.turns_per_repeat), len(geometry.stem))
    to_end = (len(geometry.stem) - 1) / 2
    half_gone_distance = to_end + length / 2
    final_speed = half_gone_distance / OPPOSED_PAIR_INTERVAL_SECONDS * 0.9
    return (OPPOSED_PAIR_INTERVAL_SECONDS +
            (to_end + length - half_gone_distance) / final_speed)


def _accelerated_pair_lifetime(stem_length, length, center, speed,
                               acceleration, allow_reversal):
    up_arrival = time_to_position(center, -length, -speed, acceleration,
                                  direction=-1)
    if allow_reversal:
        up_clear = time_to_position(center, stem_length + length, -speed,
                                    acceleration, direction=1)
    elif up_arrival is not None:
        up_clear = up_arrival + 0.2
    else:
        up_clear = speed / acceleration + 0.2
    down_clear = time_to_position(center, stem_length + length, speed,
                                  acceleration, direction=1)
    return max(up_clear or 0.0, down_clear or 0.0)


def opposed_pair_effect_duration(geometry, options=None):
    """Return the time from first launch until the final pair clears."""
    last_launch_at = OPPOSED_PAIR_LAUNCH_SECONDS - OPPOSED_PAIR_INTERVAL_SECONDS
    options = options or {}
    acceleration = downward_acceleration(
        options.get("downward_acceleration", "off"),
        geometry.leds_per_repeat / geometry.turns_per_repeat)
    if not acceleration:
        clear_time = opposed_pair_clear_time(geometry)
    else:
        stem = geometry.stem
        length = min(round(OPPOSED_PAIR_WRAPS * geometry.leds_per_repeat /
                           geometry.turns_per_repeat), len(stem))
        center = (len(stem) - 1) / 2
        half_gone = max(center, len(stem) - 1 - center) + length / 2
        speed = half_gone / OPPOSED_PAIR_INTERVAL_SECONDS * 1.1
        clear_time = _accelerated_pair_lifetime(
            len(stem), length, center, speed, acceleration,
            options.get("allow_reversal", True))
    return last_launch_at + clear_time


def upward_spiral_timing(stem_length, geometry=None, options=None):
    """Return (group interval, rise speed, group lifetime) for spiral bursts."""
    group_interval = 0.65
    rise_speed = (stem_length + 6) / 0.9
    group_lifetime = (stem_length * 1.2 + 6) / rise_speed + 0.12
    options = options or {}
    if options.get("downward_acceleration") not in (None, "off"):
        units_per_wrap = (geometry.leds_per_repeat / geometry.turns_per_repeat
                          if geometry is not None else 4.0)
        acceleration = downward_acceleration(
            options["downward_acceleration"], units_per_wrap)
        allow_reversal = options.get("allow_reversal", True)
        lifetimes = []
        for index in range(3):
            start = stem_length + index * stem_length / 10
            arrival = time_to_position(start, -1, -rise_speed,
                                       acceleration, direction=-1)
            if not allow_reversal:
                lifetime = (arrival + 0.12 if arrival is not None else
                            rise_speed / acceleration + 0.2)
            else:
                lifetime = (time_to_position(start, stem_length + 5,
                                              -rise_speed, acceleration,
                                              direction=1) or group_lifetime)
            lifetimes.append(lifetime)
        group_lifetime = max(lifetimes)
    return group_interval, rise_speed, group_lifetime


def upward_spiral_effect_duration(stem_length, geometry=None, options=None):
    """Return the duration of the default three upward spiral groups."""
    group_interval, _, group_lifetime = upward_spiral_timing(
        stem_length, geometry, options)
    return 2 * group_interval + group_lifetime


def descent_fill_timing(geometry, options=None):
    options = options or {}
    stem_length = len(geometry.stem)
    acceleration = downward_acceleration(
        options.get("downward_acceleration", "off"),
        geometry.leds_per_repeat / geometry.turns_per_repeat)
    if not acceleration:
        return DESCENT_FALL_SECONDS, DESCENT_FILL_SECONDS
    fall_speed = (stem_length + 2) / DESCENT_FALL_SECONDS
    fall_time = time_to_position(-1, stem_length + 1, fall_speed,
                                 acceleration, direction=1)
    fill_speed = -(stem_length - 1) / DESCENT_FILL_SECONDS
    fill_time = time_to_position(stem_length - 1, -1, fill_speed,
                                 acceleration, direction=-1)
    if fill_time is None:
        if options.get("allow_reversal", True):
            fill_time = (time_to_position(stem_length - 1, stem_length + 5,
                                          fill_speed, acceleration,
                                          direction=1) or
                         abs(fill_speed) / acceleration + 0.2)
        else:
            fill_time = abs(fill_speed) / acceleration + 0.2
    return fall_time or DESCENT_FALL_SECONDS, fill_time


def descent_fill_duration(geometry, options=None):
    fall_time, fill_time = descent_fill_timing(geometry, options)
    return fall_time + fill_time + DESCENT_HOLD_SECONDS


def release_burst_duration(geometry, options=None):
    options = options or {}
    acceleration = downward_acceleration(
        options.get("downward_acceleration", "off"),
        geometry.leds_per_repeat / geometry.turns_per_repeat)
    if not acceleration:
        return RELEASE_BURST_SECONDS
    stem_length = len(geometry.stem)
    speed = stem_length / 0.75
    arrival = time_to_position(stem_length - 1, -1, -speed,
                               acceleration, direction=-1)
    if arrival is not None:
        return max(RELEASE_BURST_SECONDS, arrival + 0.75)
    if options.get("allow_reversal", True):
        clear = time_to_position(stem_length - 1, stem_length + 6,
                                 -speed, acceleration, direction=1)
        return max(RELEASE_BURST_SECONDS, (clear or 0.0) + 0.75)
    return max(RELEASE_BURST_SECONDS,
               speed / acceleration + 0.2 + 0.75)


def opposed_pair_vectors(elapsed, geometry, peak_brightness=1.0,
                         launch_until=None, options=None):
    """Launch blue and green pairs from the center toward opposite ends."""
    stem = geometry.stem
    length = min(round(OPPOSED_PAIR_WRAPS * geometry.leds_per_repeat /
                       geometry.turns_per_repeat), len(stem))
    center = (len(stem) - 1) / 2
    to_end = max(center, len(stem) - 1 - center)
    half_gone_distance = to_end + length / 2
    average_speed = half_gone_distance / OPPOSED_PAIR_INTERVAL_SECONDS
    initial_speed = average_speed * 1.1
    interval = OPPOSED_PAIR_INTERVAL_SECONDS
    options = options or {}
    acceleration = downward_acceleration(
        options.get("downward_acceleration", "off"),
        geometry.leds_per_repeat / geometry.turns_per_repeat)
    if acceleration:
        return _accelerated_opposed_pairs(
            elapsed, geometry, peak_brightness, launch_until, length, center,
            interval, initial_speed, acceleration,
            options.get("allow_reversal", True))
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


def _accelerated_opposed_pairs(elapsed, geometry, peak_brightness,
                                launch_until, length, center, interval,
                                speed, acceleration, allow_reversal):
    stem = geometry.stem
    up_arrival = time_to_position(center, -length, -speed, acceleration,
                                  direction=-1)
    lifetime = _accelerated_pair_lifetime(
        len(stem), length, center, speed, acceleration, allow_reversal)
    newest = int(elapsed // interval)
    if launch_until is not None:
        newest = min(newest, math.ceil(launch_until / interval) - 1)
    oldest = max(0, int((elapsed - lifetime) // interval))
    vectors = []
    for pair in range(oldest, newest + 1):
        age = elapsed - pair * interval
        if age < 0 or age >= lifetime:
            continue
        color = (0, 0, 255) if pair % 2 == 0 else (0, 255, 0)
        for direction in (-1, 1):
            vector_position = center + direction * speed * age + 0.5 * acceleration * age ** 2
            velocity = direction * speed + acceleration * age
            if direction < 0 and not allow_reversal and up_arrival is None:
                apex = speed / acceleration
                fade = max(0.0, 1 - (age - apex) / 0.2)
            else:
                fade = 1.0
            tail_length = min(length, int(abs(vector_position - center)) + 1)
            tail_direction = -1 if velocity < 0 else 1
            samples = tuple(
                (-tail_direction * offset,
                 tuple(round(channel * (1 - offset / max(1, length - 1)))
                       for channel in color))
                for offset in range(tail_length))
            vectors.append(LightVector(stem, samples, vector_position,
                                       brightness=fade,
                                       brightness_override=peak_brightness))
    return vectors


def base_vectors(name, t, geometry, max_brightness=0.5, options=None):
    options = options or {}
    vectors = []
    if name in ("green_spiral", "green_channels"):
        acceleration = downward_acceleration(
            options.get("downward_acceleration", "off"),
            (geometry.leds_per_repeat / geometry.turns_per_repeat
             if name == "green_spiral" else 1 / geometry.turns_per_repeat))
        vectors.append(solid(geometry.orb, (0, 220, 20), _pulse(t)))
        if name == "green_spiral":
            count = len(geometry.stem)
            launches = []
            start = -3.0
            if acceleration:
                flight_s = time_to_position(
                    start, count + 2, SPIRAL_LEDS_PER_SECOND, acceleration,
                    direction=1)
            else:
                flight_s = (count + 5) / SPIRAL_LEDS_PER_SECOND
            flight_s = flight_s or (count + 5) / SPIRAL_LEDS_PER_SECOND
            for index in range(3):
                launch_at = index * flight_s / 3
                age = t - launch_at
                if age < 0:
                    position = start
                else:
                    age %= flight_s
                    position = motion_position(
                        start, SPIRAL_LEDS_PER_SECOND, acceleration, age)
                launches.append((SPIRAL_LEDS_PER_SECOND,
                                 -launch_at * SPIRAL_LEDS_PER_SECOND,
                                 flight_s * SPIRAL_LEDS_PER_SECOND))
                depth = max(0.0, min(1.0, position / count))
                vectors.append(palette_trail(
                    geometry.stem, ((125, 255, 130), (0, 150, 65), (0, 25, 70)),
                    position, length=5, brightness=0.8 * (1 - 0.75 * depth)))
        else:
            stride = max(1, geometry.leds_per_repeat // 4)
            selected = range(0, geometry.leds_per_repeat, stride)
            launches = []
            for index, channel_number in enumerate(list(selected)[:4]):
                path = geometry.channel(channel_number)
                offset = index * len(path) / 4
                span = len(path) + 3
                position = ((t * CHANNEL_ROWS_PER_SECOND + offset) % span - 1
                            if not acceleration else
                            _accelerated_falling_position(
                                t, len(path), CHANNEL_ROWS_PER_SECOND,
                                acceleration, offset=offset))
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
        accel_level = options.get("downward_acceleration", "off")
        acceleration = downward_acceleration(
            accel_level, geometry.leds_per_repeat / geometry.turns_per_repeat)
        fall_s = (time_to_position(0, bottom, BOUNCE_LEDS_PER_SECOND,
                                   acceleration, direction=1)
                  if acceleration else bottom / BOUNCE_LEDS_PER_SECOND)
        fall_s = max(0.0, fall_s or 0.0)
        travel_s = max(2 * BOUNCE_FLASH_SECONDS, fall_s)
        impact_speed = BOUNCE_LEDS_PER_SECOND + acceleration * fall_s
        rise_s = (time_to_position(bottom, 0, -impact_speed, acceleration,
                                   direction=-1)
                  if acceleration and bottom else travel_s)
        allow_reversal = options.get("allow_reversal", True)
        if acceleration and bottom and rise_s is None:
            if allow_reversal:
                rise_s = time_to_position(bottom, bottom, -impact_speed,
                                          acceleration, direction=1)
            else:
                rise_s = impact_speed / acceleration + 0.2
        flight_s = fall_s + (rise_s or 0.0) if acceleration else 2 * travel_s
        cycle_s = flight_s + BOUNCE_REST_SECONDS
        impact_age = (t - fall_s) % cycle_s
        impact = (max(0.0, 1 - impact_age / 0.22) ** 2
                  if t >= fall_s and bottom else 0.0)
        anchor_color = palette_color(((0, 180, 20), (145, 255, 90)), impact)
        vectors.append(solid(stem[-length:], anchor_color,
                             0.28 + 0.62 * impact))
        current_launch = int(t // cycle_s)
        phase = t - current_launch * cycle_s
        flash_active = (current_launch > 0 and
                        phase < BOUNCE_FLASH_SECONDS)
        orb_color = (190, 28, 0) if flash_active else (255, 100, 0)
        orb_level = 0.55 if flash_active else 0.25
        vectors.append(solid(geometry.orb, orb_color, orb_level,
                             brightness_override=max_brightness))
        oldest_launch = max(0, int((t - flight_s) // cycle_s))
        for launch in range(oldest_launch, current_launch + 1):
            age = t - launch * cycle_s
            if not 0 <= age < flight_s:
                continue
            if acceleration and fall_s > 0:
                if age <= fall_s:
                    vector_position = motion_position(0, BOUNCE_LEDS_PER_SECOND,
                                                      acceleration, age)
                else:
                    vector_position = motion_position(bottom, -impact_speed,
                                                      acceleration, age - fall_s)
                vector_position = max(0.0, min(float(bottom), vector_position))
            else:
                vector_position = min(bottom, min(age, 2 * travel_s - age) *
                                      BOUNCE_LEDS_PER_SECOND)
            fall_scale = 0.4 * max_brightness
            fade = 1.0
            if (acceleration and not allow_reversal and bottom and
                    rise_s is not None and
                    time_to_position(bottom, 0, -impact_speed,
                                     acceleration, direction=-1) is None and
                    age > fall_s + impact_speed / acceleration):
                fade = max(0.0, 1 - (age - fall_s -
                                     impact_speed / acceleration) / 0.2)
            if age <= travel_s or bottom == 0:
                scale = fall_scale
            else:
                top_scale = 0.0
                progress = vector_position / bottom
                scale = top_scale + (fall_scale - top_scale) * progress ** 3
            vectors.append(LightVector(
                stem, tuple((offset, (255, 255, 255)) for offset in range(length)),
                vector_position, brightness=fade,
                brightness_override=scale))
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


class InteractiveRedShots:
    """Persistent tap-triggered upward red shots with a fading orb arrival."""

    TRAVEL_SECONDS = 0.4
    TAIL_WRAPS = 8
    FLASH_SECONDS = 0.2

    def __init__(self, geometry, max_brightness=0.5,
                 downward_acceleration_level="off", allow_reversal=True):
        self.geometry = geometry
        self.max_brightness = max_brightness
        self.acceleration = downward_acceleration(
            downward_acceleration_level,
            geometry.leds_per_repeat / geometry.turns_per_repeat)
        self.allow_reversal = allow_reversal
        self.launched_at = []
        self.tail_length = max(1, round(
            self.TAIL_WRAPS * geometry.leds_per_repeat /
            geometry.turns_per_repeat))
        self.speed = (len(geometry.stem) + 1) / self.TRAVEL_SECONDS
        self.arrival = (time_to_position(len(geometry.stem) - 1, -1,
                                         -self.speed, self.acceleration,
                                         direction=-1)
                        if self.acceleration else self.TRAVEL_SECONDS)
        if self.arrival is not None:
            self.shot_lifetime = self.arrival + self.FLASH_SECONDS
        elif not self.allow_reversal:
            self.shot_lifetime = self.speed / self.acceleration + self.FLASH_SECONDS
        else:
            self.shot_lifetime = time_to_position(
                len(geometry.stem) - 1, len(geometry.stem) + 1,
                -self.speed, self.acceleration, direction=1) or 10.0

    def shoot(self, elapsed):
        self.launched_at.append(elapsed)

    def clear(self):
        self.launched_at.clear()

    def vectors(self, elapsed):
        stem = self.geometry.stem
        self.launched_at = [started for started in self.launched_at
                            if elapsed - started < self.shot_lifetime]
        vectors = []
        orb_level = 0.0
        for started in self.launched_at:
            age = elapsed - started
            if 0 <= age < self.shot_lifetime and (self.arrival is not None or
                                                  self.allow_reversal or
                                                  age < self.speed / self.acceleration):
                head = motion_position(len(stem) - 1, -self.speed,
                                       self.acceleration, age)
                velocity = -self.speed + self.acceleration * age
                direction = -1 if velocity < 0 else 1
                fade = 1.0
                if self.arrival is None and not self.allow_reversal:
                    fade = max(0.0, 1 - (age - self.speed /
                                         self.acceleration) / self.FLASH_SECONDS)
                vectors.append(palette_trail(
                    stem, RED_PALETTE, head, length=self.tail_length,
                    direction=direction, brightness=fade,
                    brightness_override=self.max_brightness))
            flash_age = age - self.arrival if self.arrival is not None else -1
            if 0 <= flash_age < self.FLASH_SECONDS:
                orb_level = max(orb_level, 1 - flash_age / self.FLASH_SECONDS)
        if orb_level:
            vectors.append(solid(self.geometry.orb, (255, 0, 0), orb_level,
                                 brightness_override=self.max_brightness))
        return vectors


def manual_vectors(name, elapsed, geometry, charge_time=0.0,
                   max_brightness=0.5, continuation=False, stop_at=None,
                   options=None):
    """Return (vectors, finished) for a finite triggered effect."""
    options = options or {}
    stem = geometry.stem
    if name in SPELL_DURATIONS:
        return spell_vectors(name, elapsed, geometry, max_brightness)
    if name == "descent_fill":
        fall_s, fill_s = descent_fill_timing(geometry, options)
        acceleration = downward_acceleration(
            options.get("downward_acceleration", "off"),
            geometry.leds_per_repeat / geometry.turns_per_repeat)
        allow_reversal = options.get("allow_reversal", True)
        if elapsed < fall_s:
            head = (-1 + elapsed / fall_s * (len(stem) + 2)
                    if not acceleration else
                    motion_position(-1, (len(stem) + 2) / fall_s,
                                    acceleration, elapsed))
            return [palette_trail(stem, MIST_PALETTE, head, length=6)], False
        if elapsed < fall_s + fill_s:
            fraction = (elapsed - fall_s) / fill_s
            lit = min(len(stem), math.ceil(fraction * len(stem)))
            head = (len(stem) - 1 - fraction * (len(stem) - 1)
                    if not acceleration else
                    motion_position(len(stem) - 1,
                                    -(len(stem) - 1) / fill_s,
                                    acceleration, elapsed - fall_s))
            fill_age = elapsed - fall_s
            fill_speed = -(len(stem) - 1) / fill_s
            fill_arrival = (time_to_position(len(stem) - 1, -1, fill_speed,
                                             acceleration, direction=-1)
                            if acceleration else fill_s)
            fade = 1.0
            fill_direction = -1 if fill_speed + acceleration * fill_age < 0 else 1
            if acceleration and not allow_reversal and fill_arrival is None:
                fade = max(0.0, 1 - (fill_age - abs(fill_speed) /
                                     acceleration) / 0.2)
            vectors = [solid(stem[-lit:], (255, 0, 0), 0.4)] if lit else []
            vectors.append(palette_trail(stem, MIST_PALETTE, head,
                                         length=6, direction=fill_direction,
                                         brightness=fade))
            return vectors, False
        if elapsed < fall_s + fill_s + DESCENT_HOLD_SECONDS:
            color = rainbow(math.floor((elapsed - fall_s - fill_s) * 9) / 9)
            return [solid(stem, (255, 0, 0), 0.4),
                    solid(geometry.orb, color, 0.85,
                          brightness_override=max_brightness)], False
        return [], True

    if name == "upward_spirals":
        group_interval, rise_speed, group_lifetime = upward_spiral_timing(
            len(stem), geometry, options)
        acceleration = downward_acceleration(
            options.get("downward_acceleration", "off"),
            geometry.leds_per_repeat / geometry.turns_per_repeat)
        allow_reversal = options.get("allow_reversal", True)
        arrivals = []
        for index in range(3):
            start = len(stem) + index * len(stem) / 10
            arrival = (time_to_position(start, -1, -rise_speed, acceleration,
                                        direction=-1) if acceleration else
                       (start + 1) / rise_speed)
            arrivals.append(arrival)
        last_group = int(elapsed // group_interval)
        if stop_at is not None:
            last_group = min(last_group, math.ceil(stop_at / group_interval) - 1)
        elif not continuation:
            last_group = min(last_group, 2)
        if (last_group < 0 or
                ((stop_at is not None or not continuation) and
                 elapsed >= last_group * group_interval + group_lifetime)):
            return [], True
        vectors = [solid(geometry.orb, (170, 125, 10), 0.18)]
        first_group = max(0, int((elapsed - group_lifetime) // group_interval))
        for group in range(first_group, last_group + 1):
            started = group * group_interval
            if elapsed < started:
                continue
            for index in range(3):
                offset = index * len(stem) / 10
                age = elapsed - started
                initial_position = len(stem) + offset
                moving_position = motion_position(initial_position, -rise_speed,
                                                  acceleration, age)
                speed = -rise_speed + acceleration * age
                direction = -1 if speed < 0 else 1
                fade = 1.0
                if acceleration and not allow_reversal and speed >= 0 and arrivals[index] is None:
                    fade = max(0.0, 1 - (age - rise_speed / acceleration) / 0.2)
                palette = (MIST_PALETTE if index % 2 == 0 else EMBER_PALETTE)
                strength = (0.55, 0.65, 1.0)[group % 3]
                vectors.append(palette_trail(
                    stem, palette, moving_position, length=5,
                    direction=direction, brightness=fade * strength))
            arrival = (started + arrivals[-1] if acceleration else
                       started + (len(stem) * 1.2 + 6) / rise_speed)
            flash_age = elapsed - arrival if arrival is not None else -1
            if 0 <= flash_age < 0.12:
                vectors.append(solid(geometry.orb, (30, 90, 255),
                                     0.8 * math.sin(math.pi * flash_age / 0.12),
                                     brightness_override=max_brightness))
        return vectors, False

    if name == "channel_wave":
        channels = geometry.channels
        acceleration = downward_acceleration(
            options.get("downward_acceleration", "off"),
            1 / geometry.turns_per_repeat)
        max_rows = max(len(path) for path in channels)
        clear_s = (time_to_position(0, max_rows, CHANNEL_WAVE_ROWS_PER_SECOND,
                                    acceleration, direction=1) if acceleration
                   else max_rows / CHANNEL_WAVE_ROWS_PER_SECOND)
        if stop_at is not None and elapsed >= stop_at + clear_s:
            return [], True
        if (stop_at is None and not continuation and
                elapsed >= CHANNEL_WAVE_TOTAL_SECONDS):
            return [], True
        vectors = [solid(geometry.orb, (255, 255, 255), 0.16,
                         brightness_override=max_brightness)]
        rotation = int(elapsed * CHANNEL_ROTATIONS_PER_SECOND) % len(channels)
        for source in range(len(channels)):
            path = channels[(source + rotation) % len(channels)]
            pulse = 0.15 + 0.65 * (0.5 + 0.5 * math.cos(
                2 * math.pi * (elapsed * 2.5 - source / len(channels))))
            color = rainbow(source / len(channels))
            samples = []
            last_active_row = (len(path) - 1 -
                               (CHANNEL_WAVE_ROWS_PER_SECOND * (elapsed - stop_at) +
                                0.5 * acceleration * (elapsed - stop_at) ** 2)
                               if stop_at is not None else len(path) - 1)
            for row in range(len(path)):
                if row > last_active_row:
                    continue
                phase = (row + elapsed * CHANNEL_WAVE_ROWS_PER_SECOND +
                         0.5 * acceleration * elapsed ** 2) % CHANNEL_WAVE_PERIOD_ROWS
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
                                       launch_until=launch_until, options=options)
        return vectors, (launch_until is not None and not vectors and
                         elapsed >= launch_until)

    if name == "charge":
        acceleration = downward_acceleration(
            options.get("downward_acceleration", "off"),
            geometry.leds_per_repeat / geometry.turns_per_repeat)
        speed = (0.3 if acceleration else
                 0.3 + min(elapsed, 8.0) * 0.125)
        allow_reversal = options.get("allow_reversal", True)
        vectors = [solid(geometry.orb, (10, 80, 255),
                         min(0.9, 0.35 + elapsed * 0.07))]
        for index in range(7):
            if acceleration:
                start = len(stem) - 1 - index * len(stem) / 7
                moving_position = motion_position(
                    start, -speed * len(stem), acceleration, elapsed)
                arrival = time_to_position(start, -1, -speed * len(stem),
                                           acceleration, direction=-1)
                fade = (max(0.0, 1 - (elapsed - speed * len(stem) /
                                      acceleration) / 0.2)
                        if not allow_reversal and arrival is None else 1.0)
            else:
                moving_position = (len(stem) - 1 -
                                   (elapsed * speed + index / 7) * len(stem)) % (len(stem) + 5)
                fade = 1.0
            vectors.append(trail(stem, rainbow(index / 7 + elapsed * 0.1),
                                 moving_position, length=4,
                                 direction=(-1 if not acceleration or
                                            -speed * len(stem) + acceleration * elapsed < 0
                                            else 1), brightness=0.7 * fade))
        return vectors, False

    if name == "release_burst":
        acceleration = downward_acceleration(
            options.get("downward_acceleration", "off"),
            geometry.leds_per_repeat / geometry.turns_per_repeat)
        travel = (time_to_position(len(stem) - 1, -1,
                                   -len(stem) / 0.75, acceleration,
                                   direction=-1) if acceleration else 0.75)
        allow_reversal = options.get("allow_reversal", True)
        active_time = release_burst_duration(geometry, options)
        if elapsed >= (active_time if acceleration else RELEASE_BURST_SECONDS):
            return [], True
        arrival = (travel if acceleration else
                   (len(stem) - 1) * 0.75 / len(stem))
        blue_level = min(0.9, 0.35 + charge_time * 0.07)
        if arrival is None or elapsed < arrival:
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
            if acceleration:
                start = len(stem) - 1 + index * len(stem) / 18
                moving_position = motion_position(start, -len(stem) / 0.75,
                                                  acceleration, elapsed)
                direction = (-1 if -len(stem) / 0.75 +
                             acceleration * elapsed < 0 else 1)
                arrival_at_head = time_to_position(start, -1,
                                                   -len(stem) / 0.75,
                                                   acceleration, direction=-1)
                fade = (max(0.0, 1 - (elapsed - len(stem) / 0.75 /
                                      acceleration) / 0.2)
                        if not allow_reversal and arrival_at_head is None else 1.0)
            else:
                moving_position = (len(stem) - 1 -
                                   elapsed * (len(stem) / 0.75) +
                                   index * len(stem) / 18)
                direction = -1
                fade = 1.0
            vectors.append(trail(stem, rainbow(index / 12 + elapsed * 0.3),
                                 moving_position, length=7, direction=direction,
                                 brightness=(min(1.0, 0.55 + charge_time * 0.07) *
                                             fade),
                                 brightness_override=max_brightness))
        return vectors, False

    if name == "unset":
        if elapsed >= UNSET_INDICATOR_SECONDS:
            return [], True
        return [solid(geometry.unset_indicator, (255, 0, 0), 0.35)], False

    raise ValueError(f"Unknown manual effect: {name}")

