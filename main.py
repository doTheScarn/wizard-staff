"""Run Wizard Staff on a Raspberry Pi or preview it without hardware."""

import argparse
import time

from wizard_staff.config import StaffConfig
from wizard_staff.controller import WizardStaff


TOTAL_LEDS = 300
ORB_LEDS = 36
LEDS_PER_WRAP = 4
STEM_LEDS = TOTAL_LEDS - ORB_LEDS
BASELINE_SHAFT_BRIGHTNESS = 0.2
BASELINE_ORB_BRIGHTNESS = 0.2
MAX_BRIGHTNESS = 0.5
DATA_START = "bottom"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orb-leds", type=int, default=ORB_LEDS)
    parser.add_argument("--stem-leds", type=int, default=STEM_LEDS)
    parser.add_argument("--leds-per-repeat", type=int, default=LEDS_PER_WRAP)
    parser.add_argument("--turns-per-repeat", type=int, choices=(1, 2), default=1)
    parser.add_argument("--frame-rate", type=float, default=30)
    parser.add_argument("--brightness", type=float, default=1.0,
                        help="Additional hardware output multiplier (default: 1.0).")
    parser.add_argument("--led-pin", default="D18")
    parser.add_argument("--data-start", choices=("top", "bottom"), default=DATA_START)
    parser.add_argument("--pixel-order", default="RGB")
    parser.add_argument("--color-mapping", choices=("tire_pixel", "standard"),
                        default="tire_pixel")
    parser.add_argument("--button-gpio", type=int, default=17)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-fps", action="store_true",
                        help="Print measured frame rate and update time every 2 seconds.")
    parser.add_argument("--seconds", type=float, default=None,
                        help="Stop after this many seconds (useful for a preview).")
    parser.add_argument("--effect", choices=("quick", "double_quick", "medium",
                                              "hold_start", "quick_medium",
                                              "quick_hold_start"),
                        help="Start a slot immediately; useful with --dry-run.")
    return parser.parse_args()


def preview(frame, orb_leds):
    orb = max(frame[:orb_leds], key=lambda pixel: sum(pixel))
    stem = frame[orb_leds:]
    glyphs = " .:-=+*#%@"
    line = "".join(glyphs[min(len(glyphs) - 1, sum(pixel) // 65)] for pixel in stem)
    return f"orb={orb} stem={line}"


def main():
    args = parse_args()
    config = StaffConfig(orb_leds=args.orb_leds, stem_leds=args.stem_leds,
                         leds_per_repeat=args.leds_per_repeat,
                         turns_per_repeat=args.turns_per_repeat,
                         frame_rate=args.frame_rate, brightness=args.brightness,
                         baseline_shaft_brightness=BASELINE_SHAFT_BRIGHTNESS,
                         baseline_orb_brightness=BASELINE_ORB_BRIGHTNESS,
                         max_brightness=MAX_BRIGHTNESS,
                         led_pin=args.led_pin, data_start=args.data_start,
                         pixel_order=args.pixel_order,
                         color_mapping=args.color_mapping, button_gpio=args.button_gpio)
    staff = WizardStaff(config)
    hardware = None
    if not args.dry_run:
        from wizard_staff.hardware import PiHardware
        hardware = PiHardware(config, staff.geometry.total_leds)

    start = time.monotonic()
    if args.effect:
        staff.trigger(args.effect, start)
    next_frame = start
    next_preview = start
    report_start = start
    report_frames = 0
    report_work_s = 0.0
    report_max_work_s = 0.0
    try:
        while args.seconds is None or time.monotonic() - start < args.seconds:
            now = time.monotonic()
            work_started = time.perf_counter() if args.report_fps else None
            frame = staff.step(now, hardware.is_pressed() if hardware else False)
            if hardware:
                hardware.show(frame)
            elif now >= next_preview:
                print(preview(frame, config.orb_leds))
                next_preview = now + 0.25
            if args.report_fps:
                finished_at = time.monotonic()
                work_s = time.perf_counter() - work_started
                report_frames += 1
                report_work_s += work_s
                report_max_work_s = max(report_max_work_s, work_s)
                report_elapsed = finished_at - report_start
                if report_elapsed >= 2.0:
                    print(f"fps={report_frames / report_elapsed:.1f} "
                          f"update_avg_ms={report_work_s / report_frames * 1000:.2f} "
                          f"update_max_ms={report_max_work_s * 1000:.2f}", flush=True)
                    report_start = finished_at
                    report_frames = 0
                    report_work_s = 0.0
                    report_max_work_s = 0.0
            next_frame += 1 / config.frame_rate
            time.sleep(max(0, next_frame - time.monotonic()))
    except KeyboardInterrupt:
        pass
    finally:
        if hardware:
            hardware.close()


if __name__ == "__main__":
    main()

