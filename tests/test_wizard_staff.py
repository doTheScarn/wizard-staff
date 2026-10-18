import unittest
import random
import sys
import io
import re
from types import SimpleNamespace
from unittest.mock import patch

from main import (BASELINE_ORB_BRIGHTNESS, BASELINE_SHAFT_BRIGHTNESS,
                  LEDS_PER_WRAP, MAX_BRIGHTNESS, ORB_LEDS, STEM_LEDS, TOTAL_LEDS)
from wizard_staff.button import ButtonInterpreter
from wizard_staff.config import StaffConfig
from wizard_staff.controller import WizardStaff
from wizard_staff.cycle_status import (CycleStatusDisplay, PATTERN_ROWS,
                                       format_status, status_snapshot)
from wizard_staff.effects import (BASE_PATTERNS, BOUNCE_LEDS_PER_SECOND,
                                  BOUNCE_FLASH_DELAY_SECONDS,
                                  StackingDropEffect, base_vectors,
                                  manual_vectors, opposed_pair_vectors,
                                  opposed_pair_clear_time)
from wizard_staff.geometry import StaffGeometry
from wizard_staff.hardware import PiHardware, encode_color
from wizard_staff.motion import downward_acceleration, time_to_position
from wizard_staff.vectors import solid, render
from wizard_staff.virtual_button import VirtualButtonPlayer


class WizardStaffTests(unittest.TestCase):
    def test_default_physical_layout(self):
        config = StaffConfig()
        geometry = StaffGeometry.from_config(config)
        self.assertEqual(config.data_start, "bottom")
        self.assertEqual(config.frame_rate, 60.0)
        self.assertEqual((ORB_LEDS, STEM_LEDS, LEDS_PER_WRAP, TOTAL_LEDS),
                         (31, 269, 4, 300))
        self.assertEqual(geometry.total_leds, TOTAL_LEDS)
        self.assertEqual(geometry.channels[0][0], ORB_LEDS)
        self.assertEqual(len(geometry.channels[0]), 68)

    def test_geometry_reserves_orb_and_aligns_channels(self):
        geometry = StaffGeometry.from_config(StaffConfig(orb_leds=3, stem_leds=10,
                                                         leds_per_repeat=4))
        self.assertEqual(geometry.orb, (0, 1, 2))
        self.assertEqual(geometry.stem, tuple(range(3, 13)))
        self.assertEqual(geometry.channel(0), (3, 7, 11))
        self.assertEqual(geometry.channel(1), (4, 8, 12))
        self.assertEqual(geometry.unset_indicator, (3, 4, 5, 6))

    def test_additive_vectors_clip_each_color(self):
        frame = render([solid((1,), (220, 10, 0)),
                        solid((1,), (80, 5, 255))], 3)
        self.assertEqual(frame, [(0, 0, 0), (255, 15, 255), (0, 0, 0)])

    def test_region_baselines_and_flash_override(self):
        config = StaffConfig()
        self.assertEqual((BASELINE_SHAFT_BRIGHTNESS, BASELINE_ORB_BRIGHTNESS,
                          MAX_BRIGHTNESS, config.brightness), (0.2, 0.2, 0.5, 1.0))
        vectors = [solid((0, 1), (255, 0, 0)),
                   solid((0,), (255, 0, 0), brightness_override=MAX_BRIGHTNESS)]
        frame = render(vectors, 2, orb_leds=1,
                       baseline_orb_brightness=BASELINE_ORB_BRIGHTNESS,
                       baseline_shaft_brightness=BASELINE_SHAFT_BRIGHTNESS)
        self.assertEqual(frame, [(178, 0, 0), (51, 0, 0)])

        staff = WizardStaff(StaffConfig(orb_leds=1, stem_leds=8))
        staff.trigger("quick", 0.0)
        self.assertEqual(max(staff.step(3.05)[0]), 108)

    def test_tire_pixel_color_mapping_matches_existing_strip(self):
        self.assertEqual(encode_color((255, 0, 0), "tire_pixel"), (0, 255, 0))
        self.assertEqual(encode_color((0, 255, 0), "tire_pixel"), (255, 0, 0))
        self.assertEqual(encode_color((0, 0, 255), "tire_pixel"), (0, 0, 255))
        self.assertEqual(encode_color((255, 0, 0), "standard"), (255, 0, 0))

    def test_output_order_keeps_logical_orb_at_top(self):
        class FakeStrip:
            def __init__(self):
                self.pixels = [(0, 0, 0)] * 5
                self.shows = 0

            def __setitem__(self, index, color):
                self.pixels[index] = color

            def show(self):
                self.shows += 1

        frame = [(10, 0, 0), (20, 0, 0), (30, 0, 0),
                 (40, 0, 0), (50, 0, 0)]
        for data_start, expected in (("bottom", list(reversed(frame))),
                                     ("top", frame)):
            hardware = PiHardware.__new__(PiHardware)
            hardware.strip = FakeStrip()
            hardware.total_leds = len(frame)
            hardware.data_start = data_start
            hardware.color_mapping = "standard"
            hardware.show(frame)
            self.assertEqual(hardware.strip.pixels, expected)
            self.assertEqual(hardware.strip.shows, 1)

        with self.assertRaises(ValueError):
            StaffConfig(data_start="side")

    def test_virtual_live_output_does_not_initialize_gpio(self):
        class FakeStrip:
            def __init__(self, *args, **kwargs):
                pass

            def fill(self, color):
                pass

            def show(self):
                pass

            def deinit(self):
                pass

        modules = {"board": SimpleNamespace(D18=18),
                   "neopixel": SimpleNamespace(RGB="RGB", NeoPixel=FakeStrip)}
        with patch.dict(sys.modules, modules):
            hardware = PiHardware(StaffConfig(), 5, enable_button=False)
            self.assertIsNone(hardware.gpio)
            self.assertFalse(hardware.is_pressed())
            hardware.close()

    def test_faster_base_pattern_timing(self):
        geometry = StaffGeometry.from_config(StaffConfig())
        spiral_start = base_vectors("green_spiral", 0.0, geometry)
        spiral_half = base_vectors("green_spiral", 0.5, geometry)
        self.assertAlmostEqual(spiral_half[1].position - spiral_start[1].position, 24.0)
        self.assertAlmostEqual(spiral_start[0].brightness, 0.68)
        self.assertAlmostEqual(base_vectors("green_spiral", 0.25, geometry)[0].brightness,
                               0.44)

        channels_start = base_vectors("green_channels", 0.0, geometry)
        channels_half = base_vectors("green_channels", 0.5, geometry)
        self.assertAlmostEqual(channels_half[1].position - channels_start[1].position, 4.8)
        self.assertGreater(len(base_vectors("green_spiral", 0.05, geometry)),
                           len(spiral_start))  # Brief white launch accent.

        sparks_start = base_vectors("rainbow_sparks", 0.0, geometry)[2:]
        sparks_before_change = base_vectors("rainbow_sparks", 0.049, geometry)[2:]
        sparks_after_change = base_vectors("rainbow_sparks", 0.05, geometry)[2:]
        self.assertEqual(sparks_start, sparks_before_change)
        self.assertNotEqual(sparks_start, sparks_after_change)

    def test_bouncing_base_starts_at_top_and_crosses_at_middle(self):
        geometry = StaffGeometry.from_config(StaffConfig())
        self.assertEqual(BASE_PATTERNS[-1], "bounce_vectors")
        one_way = (len(geometry.stem) - 16) / BOUNCE_LEDS_PER_SECOND
        at_start = base_vectors("bounce_vectors", 0.0, geometry)
        self.assertEqual(len(at_start), 3)  # The drop starts before the red cue.
        self.assertEqual(at_start[1].samples[0][1], (255, 100, 0))
        self.assertEqual(at_start[0].path, geometry.stem[-8:])
        launched = base_vectors("bounce_vectors", BOUNCE_FLASH_DELAY_SECONDS, geometry)
        self.assertEqual(launched[1].samples[0][1], (190, 28, 0))
        self.assertEqual(launched[-1].position,
                         BOUNCE_LEDS_PER_SECOND * BOUNCE_FLASH_DELAY_SECONDS)
        self.assertEqual(len(launched[-1].samples), 8)
        self.assertAlmostEqual(launched[-1].brightness_override, 0.2)
        bounce = base_vectors("bounce_vectors", one_way, geometry)
        self.assertEqual(bounce[-2].position, len(geometry.stem) - 16)
        self.assertLess(bounce[-2].position + 7,
                        len(geometry.stem) - 8)
        crossing = base_vectors("bounce_vectors",
                                1.5 * one_way,
                                geometry)
        self.assertEqual(len(crossing), 4)
        self.assertAlmostEqual(crossing[2].position, crossing[3].position)
        self.assertAlmostEqual(crossing[2].position,
                               (len(geometry.stem) - 16) / 2)
        self.assertEqual(crossing[1].samples[0][1], (255, 100, 0))
        self.assertLess(crossing[2].brightness_override,
                        crossing[3].brightness_override)
        near_top = base_vectors("bounce_vectors",
                                2 * one_way - 0.001,
                                geometry)
        self.assertLess(near_top[2].brightness_override, 0.01)

    def test_base_acceleration_is_enabled_for_selected_patterns(self):
        from wizard_staff.patterns import BASE_PATTERN_OPTIONS

        self.assertEqual(BASE_PATTERN_OPTIONS["green_spiral"][
            "downward_acceleration"], "med")
        self.assertEqual(BASE_PATTERN_OPTIONS["bounce_vectors"][
            "downward_acceleration"], "high")
        self.assertNotIn("downward_acceleration",
                         BASE_PATTERN_OPTIONS["green_channels"])

    def test_downward_acceleration_levels_use_physical_wraps(self):
        geometry = StaffGeometry.from_config(StaffConfig(leds_per_repeat=4,
                                                         turns_per_repeat=2))
        self.assertEqual(downward_acceleration("low", 2), 4)
        self.assertEqual(downward_acceleration("med", 2), 8)
        self.assertEqual(downward_acceleration("high", 2), 12)
        self.assertEqual(downward_acceleration(None), 0)
        self.assertAlmostEqual(time_to_position(0, 10, 4, 2, direction=1),
                               -2 + 14 ** 0.5)
        off = base_vectors("bounce_vectors", 0.5, geometry)
        accelerated = base_vectors("bounce_vectors", 0.5, geometry,
                                   options={"downward_acceleration": "med"})
        self.assertGreater(accelerated[-1].position, off[-1].position)

    def test_triggered_moving_effects_accept_acceleration_options(self):
        config = StaffConfig(orb_leds=2, stem_leds=40)
        geometry = StaffGeometry.from_config(config)
        options = {"downward_acceleration": "high"}
        for name in ("descent_fill", "upward_spirals", "channel_wave",
                     "opposed_pairs", "charge", "release_burst"):
            vectors, finished = manual_vectors(name, 0.5, geometry,
                                               options=options)
            self.assertTrue(vectors)
            self.assertFalse(finished)
        stack = StackingDropEffect(
            geometry, rng=random.Random(1),
            downward_acceleration_level="high")
        self.assertTrue(stack.vectors(0.5)[0])
        stack.release(0.5)
        self.assertFalse(stack.vectors(1.0)[1])

    def test_interactive_red_shots_overlap_flash_and_exit(self):
        geometry = StaffGeometry.from_config(StaffConfig(orb_leds=2,
                                                         stem_leds=40))
        staff = WizardStaff(StaffConfig(orb_leds=2, stem_leds=40))
        staff.step(0.0)
        staff.trigger("short_short_short", 0.1)
        dark = staff.step(0.1)
        self.assertEqual(dark, [(0, 0, 0)] * geometry.total_leds)
        self.assertEqual(status_snapshot(staff, VirtualButtonPlayer(
            staff.config, "input"), 0.1), ("g", None))

        shots = staff.interactive_shots
        shots.shoot(0.0)
        shots.shoot(0.2)
        before_arrival = shots.vectors(0.39)
        self.assertEqual(sum(vector.path == geometry.orb for vector in before_arrival), 0)
        self.assertEqual(sum(vector.path == geometry.stem for vector in before_arrival), 2)
        arrival = shots.vectors(0.4)
        self.assertEqual(sum(vector.path == geometry.orb for vector in arrival), 1)
        staff.trigger("interactive_exit", 0.41)
        self.assertIsNone(staff.effect)
        self.assertIsNone(staff.interactive_shots)

    def test_interactive_button_tap_fires_and_hold_exits_without_ghost_event(self):
        staff = WizardStaff(StaffConfig(orb_leds=2, stem_leds=40))
        staff.step(0.0)
        staff.trigger("short_short_short", 0.1)
        for now, pressed in ((0.2, True), (0.24, True),
                             (0.3, False), (0.34, False)):
            staff.step(now, pressed)
        self.assertEqual(len(staff.interactive_shots.launched_at), 1)

        staff.step(0.5, True)
        staff.step(0.54, True)
        staff.step(1.40, True)
        self.assertIsNone(staff.effect)
        staff.step(1.45, False)
        staff.step(1.49, False)
        self.assertIsNone(staff.effect)

    def test_a_fill_retains_brightness_and_reverses_falling_head(self):
        geometry = StaffGeometry.from_config(StaffConfig())
        falling, _ = manual_vectors("descent_fill", 0.5, geometry)
        filling, _ = manual_vectors("descent_fill", 1.3, geometry)
        full, _ = manual_vectors("descent_fill", 2.6, geometry)
        self.assertEqual(filling[0].brightness, full[0].brightness)
        self.assertEqual(filling[0].samples[0][1], (255, 0, 0))
        self.assertEqual(filling[0].brightness, 0.4)
        self.assertLess(filling[0].brightness, falling[0].brightness)
        self.assertEqual([color for _, color in filling[1].samples],
                         [color for _, color in falling[0].samples])
        self.assertGreater(filling[1].position,
                           manual_vectors("descent_fill", 1.4, geometry)[0][1].position)

    def test_b_groups_overlap_and_orb_flashes_only_on_arrival(self):
        geometry = StaffGeometry.from_config(StaffConfig())
        early, _ = manual_vectors("upward_spirals", 0.70, geometry)
        self.assertEqual(len(early), 7)  # Yellow orb and two groups of three.
        self.assertAlmostEqual(early[2].position - early[1].position,
                               len(geometry.stem) / 10)
        before, _ = manual_vectors("upward_spirals", 1.0, geometry)
        arrival, _ = manual_vectors("upward_spirals", 1.12, geometry)
        self.assertEqual(sum(vector.path == geometry.orb for vector in before), 1)
        self.assertEqual(sum(vector.path == geometry.orb for vector in arrival), 2)
        self.assertEqual(early[0].brightness, 0.85)

    def test_c_dark_spacer_rotates_one_column_per_step(self):
        geometry = StaffGeometry.from_config(StaffConfig())
        first, _ = manual_vectors("channel_wave", 0.0, geometry)
        halfway, _ = manual_vectors("channel_wave", 0.125, geometry)
        rotated, _ = manual_vectors("channel_wave", 0.25, geometry)
        self.assertEqual(first[0].samples[0][1], (255, 255, 255))
        self.assertEqual(first[0].brightness_override, 0.5)
        self.assertEqual(first[1].path, geometry.channel(0))
        self.assertEqual(halfway[1].path, geometry.channel(0))
        self.assertEqual(rotated[1].path, geometry.channel(1))
        self.assertTrue(all(row not in dict(first[1].samples) for row in range(6)))
        self.assertIn(6, dict(first[1].samples))
        self.assertTrue(all(row not in dict(rotated[1].samples)
                            for row in range(10, 16)))
        self.assertLessEqual(first[1].brightness, 0.4)

    def test_d_charge_is_slower_with_blue_orb(self):
        geometry = StaffGeometry.from_config(StaffConfig())
        first, _ = manual_vectors("charge", 0.0, geometry)
        later, _ = manual_vectors("charge", 1.0, geometry)
        self.assertGreater(first[0].samples[0][1][2],
                           first[0].samples[0][1][0])
        self.assertNotEqual(first[1].position, later[1].position)
        self.assertLess(abs(later[1].position - first[1].position),
                        len(geometry.stem))
        held, _ = manual_vectors("charge", 5.0, geometry)
        released, _ = manual_vectors("release_burst", 0.0, geometry,
                                     charge_time=5.0)
        self.assertEqual(released[0].samples, held[0].samples)
        self.assertEqual(released[0].brightness, held[0].brightness)
        before_arrival, _ = manual_vectors("release_burst", 0.7, geometry,
                                           charge_time=5.0)
        arrival_time = (len(geometry.stem) - 1) * 0.75 / len(geometry.stem)
        at_arrival, _ = manual_vectors("release_burst", arrival_time + 0.03,
                                       geometry, charge_time=5.0)
        self.assertEqual(before_arrival[0].samples, held[0].samples)
        self.assertEqual(at_arrival[0].samples[0][1], (170, 0, 220))
        self.assertEqual(at_arrival[1].samples[0][1], (255, 255, 255))

    def test_button_debounce_single_double_medium_and_hold(self):
        config = StaffConfig()
        button = ButtonInterpreter(config)

        def sample(time_s, pressed):
            return button.update(pressed, time_s)

        self.assertEqual(sample(0.00, True), [])
        self.assertEqual(sample(0.02, False), [])  # bounce
        self.assertEqual(sample(0.10, True), [])
        sample(0.14, True)
        sample(0.24, False)
        self.assertEqual(sample(0.28, False), [])
        self.assertEqual(sample(0.67, False), ["quick"])

        sample(1.00, True)
        sample(1.04, True)
        sample(1.10, False)
        sample(1.14, False)
        sample(1.24, True)
        sample(1.28, True)
        sample(1.35, False)
        sample(1.39, False)
        self.assertEqual(sample(1.78, False), ["double_quick"])

        sample(2.00, True)
        sample(2.04, True)
        sample(2.40, False)
        self.assertEqual(sample(2.44, False), [])
        self.assertEqual(sample(2.83, False), ["medium"])

        sample(3.00, True)
        sample(3.04, True)
        self.assertEqual(sample(3.90, True), ["hold_start"])
        sample(4.00, False)
        self.assertEqual(sample(4.04, False), ["hold_release"])

    def test_mixed_gesture_triggers_opposed_pairs(self):
        button = ButtonInterpreter(StaffConfig())
        button.update(True, 0.0)
        button.update(True, 0.04)
        button.update(False, 0.10)
        button.update(False, 0.14)
        button.update(True, 0.25)
        button.update(True, 0.29)
        button.update(False, 0.65)
        self.assertEqual(button.update(False, 0.69), [])
        self.assertEqual(button.update(False, 1.08), ["quick_medium"])

        staff = WizardStaff(StaffConfig(orb_leds=2, stem_leds=12,
                                        leds_per_repeat=4))
        staff.step(0.0)
        staff.trigger("quick_medium", 1.0)
        frame = staff.step(1.1)
        self.assertEqual(frame[:2], [(0, 0, 0)] * 2)
        self.assertEqual(staff.effect, "opposed_pairs")
        self.assertTrue(any(pixel != (0, 0, 0) for pixel in frame[2:]))
        staff.step(4.5)
        self.assertIsNone(staff.effect)

    def test_opposed_pairs_launch_and_clear(self):
        geometry = StaffGeometry.from_config(StaffConfig())
        initial = opposed_pair_vectors(0.0, geometry, MAX_BRIGHTNESS)
        self.assertEqual(len(initial), 2)
        self.assertEqual(initial[0].position, initial[1].position)
        self.assertEqual(len(initial[0].samples), 1)
        self.assertEqual(initial[0].brightness_override, MAX_BRIGHTNESS)
        self.assertEqual(initial[0].samples[0][1], (0, 0, 255))
        first = opposed_pair_vectors(0.49, geometry, MAX_BRIGHTNESS)
        self.assertEqual(len(first), 2)
        self.assertEqual(len(first[0].samples), 120)
        self.assertLess(first[0].position, 0)
        self.assertGreater(first[1].position, len(geometry.stem) - 1)
        second = opposed_pair_vectors(0.5, geometry, MAX_BRIGHTNESS)
        self.assertEqual(len(second), 4)
        self.assertEqual(second[2].samples[0][1], (0, 255, 0))
        self.assertLess(second[0].samples[-1][1][2],
                        second[0].samples[0][1][2])
        self.assertLess(opposed_pair_clear_time(geometry), 0.8)
        active, finished = manual_vectors("opposed_pairs", 3.05, geometry)
        self.assertTrue(active)
        self.assertFalse(finished)
        cleared, finished = manual_vectors("opposed_pairs", 3.5, geometry)
        self.assertEqual(cleared, [])
        self.assertTrue(finished)

    def test_hold_extends_b_c_and_e_then_clears(self):
        for slot, effect in (("double_quick", "upward_spirals"),
                             ("medium", "channel_wave"),
                             ("quick_medium", "opposed_pairs")):
            with self.subTest(effect=effect):
                staff = WizardStaff(StaffConfig())
                staff.step(0.0)
                staff.trigger(slot, 0.0)
                staff.step(2.0, True)
                staff.step(2.04, True)
                staff.step(3.0, True)
                self.assertEqual(staff.effect, effect)
                staff.step(4.5, True)
                self.assertEqual(staff.effect, effect)
                staff.step(5.1, False)
                staff.step(5.14, False)
                self.assertEqual(staff.effect, effect)
                self.assertAlmostEqual(staff.extension_stop_at, 5.14)
                staff.step(6.5, False)
                self.assertIsNone(staff.effect)

    def test_release_stops_new_pairs_and_wave_clears_upward(self):
        geometry = StaffGeometry.from_config(StaffConfig())
        pairs, _ = manual_vectors("opposed_pairs", 4.0, geometry,
                                  continuation=True, stop_at=3.1)
        self.assertEqual(len(pairs), 0)  # Last launch was at 3.0.
        wave_at_release, _ = manual_vectors("channel_wave", 3.1, geometry,
                                             continuation=True, stop_at=3.1)
        wave_later, _ = manual_vectors("channel_wave", 3.6, geometry,
                                       continuation=True, stop_at=3.1)
        self.assertGreater(sum(len(v.samples) for v in wave_at_release[1:]),
                           sum(len(v.samples) for v in wave_later[1:]))
        self.assertTrue(manual_vectors("channel_wave", 4.5, geometry,
                                       continuation=True, stop_at=3.1)[1])
        self.assertTrue(manual_vectors("descent_fill", 4.0, geometry,
                                       continuation=True)[1])

    def test_quick_then_hold_is_distinct_from_plain_hold(self):
        button = ButtonInterpreter(StaffConfig())
        button.update(True, 0.00)
        button.update(True, 0.04)
        button.update(False, 0.10)
        button.update(False, 0.14)
        button.update(True, 0.25)
        button.update(True, 0.29)
        self.assertEqual(button.update(True, 1.15), ["quick_hold_start"])
        button.update(False, 1.20)
        self.assertEqual(button.update(False, 1.24), ["quick_hold_release"])

        late = ButtonInterpreter(StaffConfig())
        late.update(True, 0.00)
        late.update(True, 0.04)
        late.update(False, 0.10)
        late.update(False, 0.14)
        late.update(True, 0.55)
        self.assertEqual(late.update(True, 0.59), ["quick"])
        self.assertEqual(late.update(True, 1.45), ["hold_start"])

    def test_quick_hold_drops_stack_and_unload(self):
        geometry = StaffGeometry.from_config(StaffConfig())
        effect = StackingDropEffect(geometry, rng=random.Random(1))
        vectors, finished = effect.vectors(0.1)
        self.assertFalse(finished)
        self.assertEqual(effect.drop_count, 1)
        frame = render(vectors, geometry.total_leds)
        self.assertNotEqual(frame[geometry.channel(0)[9]], (0, 0, 0))
        self.assertEqual(frame[geometry.channel(0)[10]], (0, 0, 0))

        effect.vectors(0.5)
        self.assertEqual(effect.drop_count, 5)
        effect.vectors(7.0)
        self.assertEqual([len(stack) for stack in effect.stacks], [10] * 4)
        self.assertEqual(effect.unloading, [[], [], [], []])
        effect.release(7.0)
        self.assertEqual(effect.falling, [])
        self.assertEqual([len(queue) for queue in effect.unloading], [10] * 4)
        vectors, finished = effect.vectors(7.0)
        self.assertFalse(finished)
        frame = render(vectors, geometry.total_leds)
        self.assertEqual(frame[0], (0, 0, 0))  # Orb ramps from off.
        self.assertEqual(effect.unload_index, [0] * 4)
        vectors, _ = effect.vectors(7.16)
        frame = render(vectors, geometry.total_leds)
        self.assertEqual(frame[0], (0, 0, 0))  # Cubic ramp begins slowly.
        duration = effect.unload_motion_end_at - effect.released_at
        ramp_levels = []
        for fraction in (0.25, 0.5, 0.75):
            ramp = effect.vectors(effect.released_at + fraction * duration)[0]
            ramp_levels.append(render(ramp, geometry.total_leds)[0][0])
        self.assertLess(ramp_levels[1] - ramp_levels[0],
                        ramp_levels[2] - ramp_levels[1])
        frame = render(effect.vectors(effect.released_at + 0.5 * duration)[0],
                       geometry.total_leds)
        self.assertEqual(frame[0][0], frame[0][1])
        self.assertEqual(frame[0][1], frame[0][2])
        vectors, _ = effect.vectors(effect.unload_motion_end_at - 0.01)
        scaled = render(vectors, geometry.total_leds, orb_leds=geometry.orb_leds,
                        baseline_orb_brightness=0.2,
                        baseline_shaft_brightness=0.2)
        self.assertGreaterEqual(scaled[0][0], 120)
        self.assertEqual(render(effect.vectors(effect.unload_motion_end_at + 0.02)[0],
                                geometry.total_leds)[0], (0, 0, 0))
        self.assertEqual(render(effect.vectors(effect.unload_motion_end_at + 0.08)[0],
                                geometry.total_leds)[0], (128, 128, 128))
        self.assertEqual(render(effect.vectors(effect.unload_motion_end_at + 0.40)[0],
                                geometry.total_leds)[0], (128, 128, 128))
        self.assertEqual(render(effect.vectors(effect.unload_motion_end_at + 0.75)[0],
                                geometry.total_leds)[0], (128, 128, 128))
        fade_frame = render(effect.vectors(effect.unload_motion_end_at + 0.83)[0],
                            geometry.total_leds)
        self.assertGreater(fade_frame[0][0], 0)
        self.assertLess(fade_frame[0][0], 128)
        for dark, flash in ((0.02, 0.08), (0.14, 0.20), (0.26, 0.32)):
            dark_frame = render(effect.vectors(effect.unload_motion_end_at + dark)[0],
                                geometry.total_leds)
            flash_frame = render(effect.vectors(effect.unload_motion_end_at + flash)[0],
                                 geometry.total_leds)
            self.assertEqual(dark_frame[0], (0, 0, 0))
            self.assertEqual(flash_frame[0], (128, 128, 128))
        self.assertTrue(effect.vectors(12.0)[1])

    def test_uneven_stacks_unload_in_parallel(self):
        geometry = StaffGeometry.from_config(StaffConfig(stem_leds=50))
        effect = StackingDropEffect(geometry, rng=random.Random(2))
        effect.vectors(0.6)
        effect.release(0.6)
        heights = [len(queue) for queue in effect.unloading]
        self.assertGreater(max(heights), min(heights))
        effect.vectors(0.68)
        self.assertTrue(any(index > 0 for index in effect.unload_index))
        self.assertTrue(effect.vectors(2.0)[1])

    def test_quick_hold_controller_returns_to_base(self):
        staff = WizardStaff(StaffConfig())
        for now, pressed in ((0.00, True), (0.04, True),
                             (0.10, False), (0.14, False),
                             (0.25, True), (0.29, True), (1.15, True)):
            staff.step(now, pressed)
        self.assertEqual(staff.effect, "stack_drop")
        staff.step(3.0, True)
        staff.step(3.10, False)
        staff.step(3.14, False)
        self.assertEqual(staff.effect, "stack_unload")
        staff.step(7.0)
        self.assertIsNone(staff.effect)

    def test_virtual_interactive_shots_overlap_and_x_exits(self):
        config = StaffConfig(orb_leds=2, stem_leds=40)
        staff = WizardStaff(config)
        player = VirtualButtonPlayer(config, "input")
        staff.step(0.0)
        staff.trigger("short_short_short", 0.1)
        player.enqueue("s")
        player.enqueue("s")
        started = []
        frame_count = int(2.0 * config.frame_rate)
        for frame_number in range(frame_count):
            now = 0.1 + frame_number / config.frame_rate
            pressed = player.tick(now, staff.effect is not None,
                                  staff.effect == "interactive_red_shots")
            staff.step(now, pressed)
            if len(staff.interactive_shots.launched_at) > len(started):
                started.extend(staff.interactive_shots.launched_at[len(started):])
        self.assertEqual(len(started), 2)
        self.assertLess(started[1] - started[0], 0.4)

        player.enqueue("x")
        exited = False
        for frame_number in range(int(1.5 * config.frame_rate)):
            now = 2.1 + frame_number / config.frame_rate
            pressed = player.tick(now, staff.effect is not None,
                                  staff.effect == "interactive_red_shots")
            staff.step(now, pressed)
            if staff.effect is None:
                exited = True
                break
        self.assertTrue(exited)

    def test_manual_effect_returns_to_base_and_hold_releases(self):
        staff = WizardStaff(StaffConfig(orb_leds=2, stem_leds=16,
                                        leds_per_repeat=4))
        staff.step(0.0)
        staff.trigger("quick", 1.0)
        self.assertEqual(staff.effect, "descent_fill")
        self.assertEqual(staff.step(1.3)[:2], [(0, 0, 0)] * 2)
        staff.step(5.1)
        self.assertIsNone(staff.effect)
        staff.trigger("hold_start", 6.0)
        staff.step(7.5)
        staff.trigger("hold_release", 7.6)
        self.assertEqual(staff.effect, "release_burst")
        self.assertAlmostEqual(staff.charge_time, 1.6)
        staff.step(9.2)
        self.assertIsNone(staff.effect)

    def test_virtual_button_cycle_runs_every_gesture_with_base_gaps(self):
        config = StaffConfig(orb_leds=2, stem_leds=40)
        staff = WizardStaff(config)
        player = VirtualButtonPlayer(config, "cycle")
        starts = []
        base_gaps = []
        selected_bases = []
        base_rows = []
        effects = []
        previous_key = None
        previous_effect = None
        for frame_number in range(100 * 60):
            now = frame_number / 60
            pressed = player.tick(now, staff.effect is not None,
                                  staff.effect == "interactive_red_shots")
            if player.current_key != previous_key and player.current_key is not None:
                starts.append((player.current_key, now))
            previous_key = player.current_key
            if player.base_selection is not None:
                selected_bases.append(player.base_selection)
                staff.select_base_pattern(player.base_selection, now)
            if any("for 5 seconds" in text for text in player.announcements):
                base_gaps.append((now, player.base_until))
            staff.step(now, pressed)
            if any("for 5 seconds" in text for text in player.announcements):
                base_rows.append(status_snapshot(staff, player, now)[0])
            if staff.effect != previous_effect and staff.effect is not None:
                effects.append((staff.effect, now))
            previous_effect = staff.effect

        self.assertEqual([key for key, _ in starts[:7]], list("abcdefg"))
        self.assertEqual(selected_bases[:7], [1, 2, 3, 1, 2, 3, 1])
        self.assertEqual(base_rows[:7],
                         ["base_a", "base_b", "base_c", "base_d",
                          "base_e", "base_f", "base_g"])
        self.assertEqual([effect for effect, _ in effects[:8]],
                         ["descent_fill", "upward_spirals", "channel_wave",
                          "charge", "release_burst", "opposed_pairs", "stack_drop",
                          "stack_unload"])
        for index, (base_start, base_end) in enumerate(base_gaps[:6]):
            self.assertAlmostEqual(base_end - base_start, 5.0)
            self.assertGreaterEqual(starts[index + 1][1], base_end)
        charge_start = next(now for effect, now in effects if effect == "charge")
        charge_release = next(now for effect, now in effects if effect == "release_burst")
        self.assertAlmostEqual(charge_release - charge_start, 5.0, delta=0.1)
        stack_start = next(now for effect, now in effects if effect == "stack_drop")
        stack_release = next(now for effect, now in effects if effect == "stack_unload")
        self.assertAlmostEqual(stack_release - stack_start, 5.0, delta=0.1)

    def test_virtual_button_input_selects_numbered_base_pattern(self):
        config = StaffConfig(orb_leds=2, stem_leds=40)
        staff = WizardStaff(config)
        player = VirtualButtonPlayer(config, "input")
        self.assertFalse(player.tick(0.0))
        self.assertIsNone(player.current_key)
        self.assertTrue(player.enqueue("a"))
        self.assertTrue(player.enqueue("2"))
        self.assertTrue(player.enqueue("d"))
        self.assertFalse(player.enqueue("4"))
        self.assertFalse(player.enqueue("z"))
        starts = []
        base_selections = []
        previous_key = None
        for frame_number in range(15 * 60):
            now = frame_number / 60
            pressed = player.tick(now, staff.effect is not None)
            if player.current_key != previous_key and player.current_key is not None:
                starts.append(player.current_key)
            previous_key = player.current_key
            if player.base_selection is not None:
                base_selections.append(player.base_selection)
                staff.select_base_pattern(player.base_selection, now)
            staff.step(now, pressed)
        self.assertEqual(starts, ["a", "d"])
        self.assertEqual(base_selections, [2])
        self.assertEqual(staff.selected_base, "green_channels")
        self.assertIsNone(player.current_key)
        self.assertFalse(player.tick(16.0, staff.effect is not None))

    def test_virtual_cycle_waits_for_effect_before_base_gap(self):
        player = VirtualButtonPlayer(StaffConfig(), "cycle")
        player.tick(0.0, False)
        player.tick(2.0, False)
        self.assertEqual(player.current_key, "a")
        self.assertIsNone(player.base_until)
        player.tick(2.1, True)
        player.tick(2.2, False)
        player.tick(3.0, False)
        self.assertEqual(player.base_until, 7.2)

    def test_cycle_status_lists_all_patterns_with_aligned_countdown(self):
        config = StaffConfig()
        staff = WizardStaff(config)
        player = VirtualButtonPlayer(config, "cycle")
        staff.step(0.0)
        player.tick(0.0, False)
        base_block, _ = format_status(staff, player, 0.0)
        staff.trigger("quick", 1.0)
        effect_block, _ = format_status(staff, player, 1.0)
        for block in (base_block, effect_block):
            lines = block.splitlines()
            self.assertEqual(lines[1], "")
            self.assertEqual(len(lines), 3 + len(PATTERN_ROWS))
            self.assertEqual(sum("s left" in line for line in lines), 1)
            for _, _, name in PATTERN_ROWS:
                self.assertIn(name, block)
        self.assertEqual([code for _, code, _ in PATTERN_ROWS],
                         ["a", "1", "b", "2", "c", "3",
                          "d", "1", "e", "2", "f", "3", "g", "1"])
        self.assertEqual(sum(code == "f" for _, code, _ in PATTERN_ROWS), 1)
        base_countdown = next(line.index("s left") for line in base_block.splitlines()
                              if "s left" in line)
        effect_countdown = next(line.index("s left") for line in effect_block.splitlines()
                                if "s left" in line)
        self.assertEqual(base_countdown, effect_countdown)

        staff.effect = None
        player.current_key = None
        player.base_after_key = "a"
        player.base_until = 20.0
        long_block, _ = format_status(staff, player, 17.0)
        countdown_starts = [re.search(r"\d+s left", line).start()
                            for block in (base_block, long_block)
                            for line in block.splitlines() if "s left" in line]
        self.assertEqual(countdown_starts[0], countdown_starts[1])

        self.assertEqual(status_snapshot(staff, player, 17.0), ("base_a", 3))
        self.assertEqual(status_snapshot(staff, player, 18.0), ("base_a", 2))

    def test_cycle_status_rewrites_terminal_only_when_second_changes(self):
        class Terminal(io.StringIO):
            def isatty(self):
                return True

        config = StaffConfig()
        staff = WizardStaff(config)
        staff.step(0.0)
        staff.trigger("quick", 0.0)
        player = VirtualButtonPlayer(config, "cycle")
        terminal = Terminal()
        display = CycleStatusDisplay(terminal)
        display.update(staff, player, 0.1)
        first = terminal.getvalue()
        display.update(staff, player, 0.2)
        self.assertEqual(terminal.getvalue(), first)
        display.update(staff, player, 1.7)
        self.assertIn(f"\x1b[{3 + len(PATTERN_ROWS)}F", terminal.getvalue())
        self.assertIn("\x1b[2K", terminal.getvalue())

    def test_cycle_status_counts_down_stack_unload(self):
        config = StaffConfig()
        staff = WizardStaff(config)
        staff.step(0.0)
        staff.trigger("quick_hold_start", 1.0)
        staff.step(3.0)
        staff.trigger("quick_hold_release", 3.0)
        player = VirtualButtonPlayer(config, "cycle")
        key, seconds = status_snapshot(staff, player, 3.0)
        self.assertEqual(key, "f")
        self.assertGreater(seconds, 0)
        self.assertEqual(status_snapshot(staff, player,
                         staff.effect_started_at + staff.stack_effect.unload_finish_at)[1],
                         0)


if __name__ == "__main__":
    unittest.main()

