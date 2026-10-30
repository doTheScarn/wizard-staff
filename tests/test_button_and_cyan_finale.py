"""Button routing and spatial/timing checks for the expanded descent effect."""

import unittest

from wizard_staff.config import StaffConfig
from wizard_staff.controller import WizardStaff
from wizard_staff.cycle_status import format_status, status_snapshot
from wizard_staff.effects import (
    BASE_PATTERNS, DESCENT_FALL_SECONDS,
    DESCENT_HOLD_SECONDS, DESCENT_ORB_FADE_SECONDS,
    descent_fill_duration, descent_fill_timing, descent_finale_timing,
    descent_finale_vectors, manual_vectors,
)
from wizard_staff.geometry import StaffGeometry
from wizard_staff.motion import downward_acceleration, time_to_position
from wizard_staff.patterns import PATTERN_OPTIONS
from wizard_staff.vectors import render
from wizard_staff.virtual_button import VirtualButtonPlayer


class ButtonAndFinaleTests(unittest.TestCase):
    def test_short_press_advances_scheduled_base_then_pins_and_wraps(self):
        staff = WizardStaff()
        staff.step(0)
        # The automatic schedule is showing base 3 before the first tap.
        for at, pressed in ((37, True), (37.04, True), (37.15, False),
                            (37.19, False), (37.60, False)):
            staff.step(at, pressed)
        self.assertIsNone(staff.effect)
        self.assertEqual(staff.selected_base, BASE_PATTERNS[3])
        staff.step(200)
        self.assertEqual(staff.selected_base, BASE_PATTERNS[3])
        staff.trigger("dit", 201)
        self.assertEqual(staff.selected_base, BASE_PATTERNS[0])
        staff.trigger("dit", 202)
        self.assertEqual(staff.selected_base, BASE_PATTERNS[1])
        staff.trigger("dit_dah_dit", 203)
        self.assertEqual(staff.effect, "descent_fill")
        staff.trigger("dit", 204)
        self.assertIsNone(staff.effect)
        self.assertEqual(staff.selected_base, BASE_PATTERNS[2])

    def test_descent_and_existing_multi_presses_do_not_advance_base(self):
        for key, effect in (("a", "descent_fill"), ("b", "upward_spirals"),
                            ("e", "opposed_pairs"), ("j", "american_flag")):
            with self.subTest(key=key):
                staff = WizardStaff()
                staff.select_base_pattern(3, 0)
                player = VirtualButtonPlayer(staff.config, "input")
                player.enqueue(key)
                for frame in range(150):
                    now = frame / 60
                    staff.step(now, player.tick(now, staff.effect is not None))
                self.assertEqual(staff.effect, effect)
                self.assertEqual(staff.selected_base, BASE_PATTERNS[2])

    def test_requested_patterns_continue_beyond_normal_end_and_finish_on_release(self):
        for slot, effect in (("dit_dit", "upward_spirals"),
                             ("dit_dah", "opposed_pairs"),
                             ("dit_dit_dah", "american_flag")):
            with self.subTest(effect=effect):
                staff = WizardStaff()
                staff.select_base_pattern(4, 0)
                staff.trigger(slot, 0)
                for at in (2, 2.04, 3, 7.9, 8.1, 10):
                    frame = staff.step(at, True)
                    self.assertEqual(staff.effect, effect)
                    self.assertIsNone(staff.fade_started_at)
                    self.assertTrue(any(any(rgb) for rgb in frame))
                player = VirtualButtonPlayer(staff.config, "input")
                self.assertIsNone(status_snapshot(staff, player, 10)[1])
                self.assertIn("holding: release to finish", format_status(staff, player, 10)[0])
                staff.step(10.1, False)
                staff.step(10.14, False)
                self.assertAlmostEqual(staff.extension_stop_at, 10.14)
                staff.step(12)
                staff.step(12.51)
                self.assertIsNone(staff.effect)
                self.assertEqual(staff.selected_base, BASE_PATTERNS[3])

    def test_fall_and_fill_follow_old_trajectories_in_two_thirds_the_time(self):
        geometry = StaffGeometry.from_config(StaffConfig())
        for level in ("off", "low", "high"):
            with self.subTest(level=level):
                options = {"downward_acceleration": level}
                acceleration = downward_acceleration(level, 4)
                old_fall = time_to_position(-1, 270, 271, acceleration, direction=1)
                old_fill = (time_to_position(268, -1, -268 / 1.5, acceleration, direction=-1)
                            if acceleration else 1.5)
                fall, fill = descent_fill_timing(geometry, options)
                self.assertAlmostEqual(fall, old_fall / 1.5)
                self.assertAlmostEqual(fill, old_fill / 1.5)
                age = fall / 2
                vectors, _ = manual_vectors("descent_fill", age, geometry, options=options)
                old_age = age * 1.5
                self.assertAlmostEqual(vectors[0].position,
                                       -1 + 271 * old_age + 0.5 * acceleration * old_age ** 2)
                vectors, _ = manual_vectors("descent_fill", fall + fill / 2,
                                             geometry, options=options)
                old_age = fill / 2 * 1.5
                self.assertAlmostEqual(vectors[-1].position,
                                       268 - 268 / 1.5 * old_age +
                                       0.5 * acceleration * old_age ** 2)

    @staticmethod
    def finale_frame(age, geometry):
        vectors, done = descent_finale_vectors(age, geometry, 0.5)
        return render(vectors, geometry.total_leds), done

    def test_six_linear_boundaries_and_five_color_spaces_replace_red(self):
        geometry = StaffGeometry(3, 240, 4)
        first, _ = self.finale_frame(DESCENT_FALL_SECONDS / 2, geometry)
        later, _ = self.finale_frame(DESCENT_FALL_SECONDS * 0.75, geometry)
        for frame, positions in ((first, (119, 99, 79, 59, 39, 19)),
                                 (later, (179, 149, 119, 89, 59, 29))):
            stem = frame[3:]
            self.assertEqual([i for i, rgb in enumerate(stem) if rgb == (255, 255, 255)],
                             sorted(positions))
            for high, low, expected in zip(positions, positions[1:],
                                          ((0, 255, 255), (0, 0, 0), (102, 0, 0),
                                           (0, 0, 0), (0, 255, 255))):
                self.assertEqual(stem[(high + low) // 2], expected)
            self.assertEqual(stem[positions[0] + 2], (102, 0, 0))
            self.assertEqual(stem[0], (0, 0, 0))

    def test_upward_train_overwrites_while_boundaries_keep_descending(self):
        geometry = StaffGeometry(3, 240, 4)
        timing = descent_finale_timing(geometry)
        # One quarter of the stem is overwritten upward, with boundaries
        # still present above the front. No white or red survives below it.
        frame, done = self.finale_frame(timing.fall + 0.25, geometry)
        self.assertFalse(done)
        self.assertTrue(any(rgb == (255, 255, 255) for rgb in frame[3:183]))
        self.assertTrue(all(rgb in ((0, 255, 255), (0, 0, 0)) for rgb in frame[183:]))
        self.assertTrue(any(rgb == (0, 255, 255) for rgb in frame[183:]))
        self.assertTrue(any(rgb == (0, 0, 0) for rgb in frame[183:]))

    def test_ten_two_row_cyan_bands_then_black_and_orb_fade(self):
        for geometry in (StaffGeometry(3, 240, 4), StaffGeometry(2, 269, 5, 2),
                         StaffGeometry(1, 1, 1)):
            with self.subTest(geometry=geometry):
                timing = descent_finale_timing(geometry)
                before, _ = self.finale_frame(timing.first_arrival - 0.0001, geometry)
                self.assertFalse(any(before[0]))
                cyan_rows = []
                for row in range(40):
                    age = (timing.first_arrival +
                           (row + 0.5) * geometry.leds_per_repeat / timing.rise_speed)
                    frame, _ = self.finale_frame(age, geometry)
                    cyan_rows.append(frame[geometry.orb_leds] == (0, 255, 255))
                self.assertEqual(cyan_rows, [True, True, False, False] * 10)
                starts = sum(on and (i == 0 or not cyan_rows[i - 1])
                             for i, on in enumerate(cyan_rows))
                self.assertEqual(starts, 10)
                last, _ = self.finale_frame(timing.last_clear, geometry)
                self.assertEqual(last[0], (0, 128, 128))
                self.assertFalse(any(any(rgb) for rgb in last[geometry.orb_leds:]))
                fading, _ = self.finale_frame(timing.last_clear + DESCENT_ORB_FADE_SECONDS / 2,
                                              geometry)
                self.assertEqual(fading[0], (0, 64, 64))
                black, done = self.finale_frame(timing.duration, geometry)
                self.assertTrue(done)
                self.assertFalse(any(any(rgb) for rgb in black))

    def test_full_effect_duration_includes_finale_and_returns_to_selected_base(self):
        staff = WizardStaff()
        staff.select_base_pattern(2, 0)
        staff.trigger("dit_dah_dit", 0)
        options = PATTERN_OPTIONS["dit_dah_dit"]
        fall, fill = descent_fill_timing(staff.geometry, options)
        start = fall + fill + DESCENT_HOLD_SECONDS
        timing = descent_finale_timing(staff.geometry)
        duration = descent_fill_duration(staff.geometry, options)
        self.assertAlmostEqual(duration, start + timing.duration)
        orb_time = start + timing.first_arrival + 0.01
        frame = staff.step(orb_time)
        self.assertGreater(frame[0][1], 0)
        self.assertEqual(frame[0][0], 0)
        for frame_number in range(int(orb_time * 60) + 1, round(duration * 60) + 40):
            staff.step(frame_number / 60)
        self.assertIsNone(staff.effect)
        self.assertEqual(staff.selected_base, BASE_PATTERNS[1])


if __name__ == "__main__":
    unittest.main()
