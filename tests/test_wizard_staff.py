import unittest
import random

from main import (BASELINE_ORB_BRIGHTNESS, BASELINE_SHAFT_BRIGHTNESS,
                  LEDS_PER_WRAP, MAX_BRIGHTNESS, ORB_LEDS, STEM_LEDS, TOTAL_LEDS)
from wizard_staff.button import ButtonInterpreter
from wizard_staff.config import StaffConfig
from wizard_staff.controller import WizardStaff
from wizard_staff.effects import StackingDropEffect, base_vectors
from wizard_staff.geometry import StaffGeometry
from wizard_staff.hardware import PiHardware, encode_color
from wizard_staff.vectors import solid, render


class WizardStaffTests(unittest.TestCase):
    def test_default_physical_layout(self):
        config = StaffConfig()
        geometry = StaffGeometry.from_config(config)
        self.assertEqual(config.data_start, "bottom")
        self.assertEqual(config.frame_rate, 60.0)
        self.assertEqual((ORB_LEDS, STEM_LEDS, LEDS_PER_WRAP, TOTAL_LEDS),
                         (36, 264, 4, 300))
        self.assertEqual(geometry.total_leds, TOTAL_LEDS)
        self.assertEqual(geometry.channels[0][0], ORB_LEDS)
        self.assertEqual(len(geometry.channels[0]), 66)

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
        self.assertEqual(staff.step(3.05)[0], (108, 0, 0))

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

    def test_faster_base_pattern_timing(self):
        geometry = StaffGeometry.from_config(StaffConfig())
        spiral_start = base_vectors("green_spiral", 0.0, geometry)
        spiral_half = base_vectors("green_spiral", 0.5, geometry)
        self.assertAlmostEqual(spiral_half[1].position - spiral_start[1].position, 12.0)
        self.assertAlmostEqual(spiral_start[0].brightness, 0.7)
        self.assertAlmostEqual(base_vectors("green_spiral", 0.25, geometry)[0].brightness,
                               0.12)

        channels_start = base_vectors("green_channels", 0.0, geometry)
        channels_half = base_vectors("green_channels", 0.5, geometry)
        self.assertAlmostEqual(channels_half[1].position - channels_start[1].position, 2.4)

        sparks_start = base_vectors("rainbow_sparks", 0.0, geometry)[2:]
        sparks_before_change = base_vectors("rainbow_sparks", 0.049, geometry)[2:]
        sparks_after_change = base_vectors("rainbow_sparks", 0.05, geometry)[2:]
        self.assertEqual(sparks_start, sparks_before_change)
        self.assertNotEqual(sparks_start, sparks_after_change)

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
        self.assertEqual(sample(2.44, False), ["medium"])

        sample(3.00, True)
        sample(3.04, True)
        self.assertEqual(sample(3.90, True), ["hold_start"])
        sample(4.00, False)
        self.assertEqual(sample(4.04, False), ["hold_release"])

    def test_mixed_gesture_and_unset_indicator(self):
        button = ButtonInterpreter(StaffConfig())
        button.update(True, 0.0)
        button.update(True, 0.04)
        button.update(False, 0.10)
        button.update(False, 0.14)
        button.update(True, 0.25)
        button.update(True, 0.29)
        button.update(False, 0.65)
        self.assertEqual(button.update(False, 0.69), ["quick_medium"])

        staff = WizardStaff(StaffConfig(orb_leds=2, stem_leds=12,
                                        leds_per_repeat=4))
        staff.step(0.0)
        staff.trigger("quick_medium", 1.0)
        frame = staff.step(1.1)
        self.assertEqual(frame[:2], [(0, 0, 0)] * 2)
        self.assertEqual([i for i, pixel in enumerate(frame) if pixel != (0, 0, 0)],
                         [2, 3, 4, 5])
        staff.step(1.5)
        self.assertIsNone(staff.effect)

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
        self.assertGreater(frame[0][0], frame[0][2])  # Red orb on release.
        self.assertEqual(effect.unload_index, [0] * 4)
        vectors, _ = effect.vectors(7.14)
        frame = render(vectors, geometry.total_leds)
        self.assertEqual(frame[0][0], frame[0][1])  # White arrival flash.
        self.assertEqual(frame[0][1], frame[0][2])
        scaled = render(vectors, geometry.total_leds, orb_leds=geometry.orb_leds,
                        baseline_orb_brightness=0.2,
                        baseline_shaft_brightness=0.2)
        self.assertEqual(scaled[0], (128, 128, 128))
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


if __name__ == "__main__":
    unittest.main()

