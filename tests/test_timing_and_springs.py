"""Cross-effect timing, signed motion, and sparse spiral integration checks."""

import math
import unittest

from wizard_staff.config import StaffConfig
from wizard_staff.controller import WizardStaff
from wizard_staff.effects import (base_vectors, manual_vectors, StackingDropEffect,
                                  upward_spiral_timing)
from wizard_staff.geometry import StaffGeometry
from wizard_staff.motion import (directional_acceleration, pattern_acceleration,
                                 time_to_position)
from wizard_staff.patterns import BASE_PATTERN_OPTIONS
from wizard_staff.spell_effects import gathering_timing
from wizard_staff.spring_effects import spring_launches, spring_vectors
from wizard_staff.vectors import render, solid
from wizard_staff.virtual_button import VirtualButtonPlayer


class TimingAndSpringTests(unittest.TestCase):
    def setUp(self):
        self.config = StaffConfig()
        self.geometry = StaffGeometry.from_config(self.config)

    def test_orb_has_independent_linear_gain_and_only_rgb_clips(self):
        vectors = [solid((0, 1), (255, 80, 0), brightness_override=0.5)]
        frame = render(vectors, 2, orb_leds=1, orb_gain=1.5)
        self.assertEqual(frame, [(191, 60, 0), (128, 40, 0)])
        bright = render([solid((0,), (255, 0, 0))], 1,
                        orb_leds=1, orb_gain=1.5)
        self.assertEqual(bright, [(255, 0, 0)])

    def test_signed_acceleration(self):
        self.assertEqual(directional_acceleration("high", -1, 4), -56)
        self.assertEqual(directional_acceleration("med", 1, 4), 40)
        self.assertEqual(pattern_acceleration({"upward_acceleration": "low"}, 4), -24)
        with self.assertRaises(ValueError):
            pattern_acceleration({"upward_acceleration": "low",
                                  "downward_acceleration": "high"})

    def test_pulses_follow_visible_launches(self):
        for name, start, speed, tail, streams, pulses in (
                ("green_spiral", -3, 48, 8, 3, 1),
                ("green_channels", -1, 9.6, 3, 4, 2)):
            options = BASE_PATTERN_OPTIONS[name]
            units = 4 if name == "green_spiral" else 1
            acceleration = pattern_acceleration(options, units)
            paths = ([self.geometry.stem] if name == "green_spiral"
                     else self.geometry.channels)
            flight = time_to_position(start, max(map(len, paths)) + tail - 1,
                                      speed, acceleration, 1)
            first_visible = time_to_position(start, 0, speed, acceleration, 1)
            period = flight / streams / pulses
            for index in range(5):
                peak = base_vectors(name, first_visible + index * period,
                                    self.geometry, options=options)[0].brightness
                trough = base_vectors(name, first_visible + (index + 0.5) * period,
                                      self.geometry, options=options)[0].brightness
                self.assertAlmostEqual(peak, 0.9)
                self.assertAlmostEqual(trough, 0.25)

    def test_b_flash_uses_first_light_with_fast_attack_and_soft_decay(self):
        _, speed, _ = upward_spiral_timing(len(self.geometry.stem), self.geometry)
        arrival = len(self.geometry.stem) / speed
        def flashes(now):
            vectors, _ = manual_vectors("upward_spirals", now, self.geometry)
            return [v for v in vectors if v.path == self.geometry.orb][1:]
        self.assertEqual(flashes(arrival - 0.001), [])
        self.assertEqual(len(flashes(arrival)), 1)
        peak = flashes(arrival + 0.015)[0].brightness
        tail = flashes(arrival + 0.15)[0].brightness
        self.assertAlmostEqual(peak, 1.0)
        self.assertTrue(0 < tail < peak)

    def test_longer_f_hold_shows_overflow_without_extra_stacking(self):
        player = VirtualButtonPlayer(self.config, "input")
        self.assertAlmostEqual(player._intervals_for("f")[-1][1] -
                               player._intervals_for("d")[-1][1] -
                               player._intervals_for("f")[-1][0], 1.0)
        effect = StackingDropEffect(self.geometry)
        effect.vectors(6.0)
        self.assertEqual(sum(map(len, effect.stacks)), 40)
        self.assertTrue(any(not drop.will_stack for drop in effect.falling))
        effect.vectors(7.0)
        self.assertEqual(sum(map(len, effect.stacks)), 40)

    def test_g_strong_head_and_dim_tail(self):
        staff = WizardStaff(self.config)
        staff.trigger("dit_dit_dit", 0)
        staff.trigger("interactive_shot", 0)
        vector = staff.interactive_shots.vectors(0.1)[0]
        self.assertGreater(vector.samples[0][1][0], 3 * vector.samples[2][1][0])
        self.assertGreater(vector.samples[1][1][0], 3 * vector.samples[2][1][0])

    def test_gathering_clearance_and_arrival_at_different_geometries(self):
        for size in (1, 9, 269):
            for turns in (1, 2):
                geometry = StaffGeometry.from_config(StaffConfig(stem_leds=size,
                                                                  leds_per_repeat=min(4, size),
                                                                  turns_per_repeat=turns))
                timing = gathering_timing(geometry)
                self.assertLess(timing.acceleration, 0)
                self.assertAlmostEqual(timing.launches[3][0],
                                       max(t + clear for (t, _), clear in
                                           zip(timing.launches[:3], timing.clear_times)))
                for frame in range(math.ceil(timing.duration * 60) + 1):
                    vectors, _ = manual_vectors("gathering_spell", frame / 60, geometry)
                    image = render(vectors, geometry.total_leds)
                    self.assertTrue(all(0 <= c <= 255 for rgb in image for c in rgb))

    def test_sparse_paths_are_literal_every_third_and_cover_the_stem(self):
        for size in (1, 9, 269):
            geometry = StaffGeometry.from_config(StaffConfig(stem_leds=size, leds_per_repeat=min(4, size)))
            paths = geometry.spiral_channels
            self.assertEqual(len(paths), 3)
            self.assertEqual(sorted(led for path in paths for led in path),
                             list(geometry.stem))
            for path in paths:
                self.assertTrue(all(b - a == 3 for a, b in zip(path, path[1:])))

    def test_random_springs_have_signed_acceleration_and_no_queue(self):
        colors, speeds, accelerations = set(), set(), set()
        for group in range(20):
            pair = spring_launches(group, self.geometry)
            self.assertEqual(pair, spring_launches(group, self.geometry))
            self.assertEqual([launch.direction for launch in pair], [1, -1])
            for launch in pair:
                self.assertGreater(launch.direction * launch.acceleration, 0)
                colors.add(launch.color)
                speeds.add(launch.speed)
                accelerations.add(abs(launch.acceleration))
        self.assertGreater(len(colors), 4)
        self.assertGreater(len(speeds), 10)
        self.assertEqual(len(accelerations), 3)
        self.assertEqual(len(spring_vectors(1.3, self.geometry, 0.5)), 5)
        self.assertLess(len(spring_vectors(100000, self.geometry, 0.5)), 30)
        staff = WizardStaff(self.config)
        staff.select_base_pattern(4, 0)
        image = staff.step(1.3)
        self.assertTrue(any(any(rgb) for rgb in image[self.geometry.orb_leds:]))

    def test_sparse_spiral_overlap_adds_colors_and_clips_at_255(self):
        led = self.geometry.spiral_channel(0)[3]
        frame = render([solid((led,), (255, 0, 0), brightness_override=0.5),
                        solid((led,), (255, 0, 255), brightness_override=0.5),
                        solid((led,), (255, 0, 255), brightness_override=0.5)],
                       self.geometry.total_leds)
        self.assertEqual(frame[led], (255, 0, 255))


class HandoffAndInputTests(unittest.TestCase):
    @staticmethod
    def input_step(staff, player, now):
        pressed = player.tick(now, staff.effect is not None,
                              staff.effect == "interactive_red_shots" and
                              staff.fade_started_at is None)
        if player.base_selection is not None:
            staff.select_base_pattern(player.base_selection, now)
        elif player.interrupt_requested:
            staff.cancel_effect(reset_button=True)
        return staff.step(now, pressed)

    def test_effect_fades_all_channels_for_half_second_then_returns_to_base(self):
        from wizard_staff.effects import descent_fill_duration
        from wizard_staff.patterns import PATTERN_OPTIONS
        staff = WizardStaff(StaffConfig())
        staff.trigger("dit", 0)
        end = descent_fill_duration(staff.geometry, PATTERN_OPTIONS["dit"])
        previous = staff.step(end - 0.01)
        first = staff.step(end + 0.01)
        self.assertEqual(first, previous)
        self.assertIsNotNone(staff.fade_started_at)
        half = staff.step(end + 0.26)
        self.assertTrue(all(abs(actual - expected * 0.5) <= 1
                            for rgb, source in zip(half, first)
                            for actual, expected in zip(rgb, source)))
        black = staff.step(end + 0.52)
        self.assertFalse(any(any(rgb) for rgb in black))
        self.assertIsNone(staff.effect)
        self.assertTrue(any(any(rgb) for rgb in staff.step(end + 0.54)))

    def test_new_input_interrupts_simulated_hold_after_normal_classification(self):
        staff = WizardStaff(StaffConfig())
        player = VirtualButtonPlayer(staff.config, "input")
        player.enqueue("f")
        for frame in range(100):
            self.input_step(staff, player, frame / 60)
        self.assertEqual(staff.effect, "stack_drop")
        player.enqueue("a")
        self.input_step(staff, player, 1.7)
        self.assertTrue(player.interrupt_requested)
        self.assertIsNone(staff.effect)
        # The ordinary multi-press window is preserved, rather than bypassed.
        for frame in range(103, 130):
            self.input_step(staff, player, frame / 60)
        self.assertIsNone(staff.effect)
        for frame in range(130, 150):
            self.input_step(staff, player, frame / 60)
        self.assertEqual(staff.effect, "descent_fill")

    def test_numbered_input_interrupts_fade_immediately(self):
        staff = WizardStaff(StaffConfig())
        player = VirtualButtonPlayer(staff.config, "input")
        staff.trigger("dah", 0)
        staff.step(2.9)
        staff.step(3.1)
        self.assertIsNotNone(staff.fade_started_at)
        player.enqueue("4")
        self.input_step(staff, player, 3.11)
        self.assertIsNone(staff.effect)
        self.assertIsNone(staff.fade_started_at)
        self.assertEqual(staff.selected_base, "spring_streams")

    def test_already_black_effect_does_not_flash_old_frame_back_on(self):
        staff = WizardStaff(StaffConfig())
        staff.trigger("dit_dit_dah", 0)
        staff.step(7.99)
        frame = staff.step(8.01)
        self.assertFalse(any(any(rgb) for rgb in frame))
        self.assertIsNone(staff.effect)

    def test_spring_launch_rate_tail_and_peak(self):
        geometry = StaffGeometry.from_config(StaffConfig())
        before = spring_vectors(0.99, geometry, 0.5)
        after = spring_vectors(1.01, geometry, 0.5)
        self.assertEqual(len(before), 3)
        self.assertEqual(len(after), 5)
        for vector in after[1:]:
            self.assertEqual(vector.brightness_override, 0.25)
            peak = sum(vector.samples[0][1])
            middle = sum(vector.samples[len(vector.samples) // 2][1])
            self.assertLess(middle, peak * 0.3)
        self.assertGreater(after[0].brightness, 0.8)
        self.assertEqual(after[0].brightness_override, 0.5)

    def test_b_slower_flash_preserves_group_launch_schedule(self):
        geometry = StaffGeometry.from_config(StaffConfig())
        _, speed, _ = upward_spiral_timing(len(geometry.stem), geometry)
        arrival = len(geometry.stem) / speed
        vectors, _ = manual_vectors("upward_spirals", arrival + 0.4, geometry)
        flashes = [v for v in vectors if v.path == geometry.orb][1:]
        self.assertTrue(flashes)
        self.assertGreater(flashes[0].brightness, 0)
        self.assertGreater(flashes[0].brightness_override, 0.5)
        before, _ = manual_vectors("upward_spirals", 0.65 - 0.001, geometry)
        after, _ = manual_vectors("upward_spirals", 0.65, geometry)
        self.assertEqual(len([v for v in before if v.path == geometry.stem]), 3)
        self.assertEqual(len([v for v in after if v.path == geometry.stem]), 6)
