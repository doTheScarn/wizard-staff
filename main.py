"""Run Wizard Staff on a Raspberry Pi or preview it without hardware."""

import argparse
from queue import Empty, Queue
import sys
import threading
import time

from wizard_staff.config import StaffConfig
from wizard_staff.controller import WizardStaff
from wizard_staff.cycle_status import CycleStatusDisplay
from wizard_staff.virtual_button import VIRTUAL_GESTURES, VirtualButtonPlayer


TOTAL_LEDS = 300
ORB_LEDS = 31
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
    parser.add_argument("--frame-rate", type=float, default=60)
    parser.add_argument("--brightness", type=float, default=1.0,
                        help="Additional hardware output multiplier (default: 1.0).")
    parser.add_argument("--led-pin", default="D18")
    parser.add_argument("--data-start", choices=("top", "bottom"), default=DATA_START)
    parser.add_argument("--pixel-order", default="RGB")
    parser.add_argument("--color-mapping", choices=("tire_pixel", "standard"),
                        default="tire_pixel")
    parser.add_argument("--button-gpio", type=int, default=17)
    parser.add_argument("--virtual-button", choices=("cycle", "input"),
                        help="Simulate button gestures automatically or from terminal input; "
                             "overrides the GPIO button.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-fps", action="store_true",
                        help="Print measured frame rate and update time every 2 seconds.")
    parser.add_argument("--seconds", type=float, default=None,
                        help="Stop after this many seconds (useful for a preview).")
    parser.add_argument("--effect", choices=("quick", "double_quick", "medium",
                                              "hold_start", "quick_medium",
                                              "quick_hold_start"),
                        help="Start a slot immediately; useful with --dry-run.")
    args = parser.parse_args()
    if args.effect and args.virtual_button:
        parser.error("--effect and --virtual-button cannot be used together")
    return args


def preview(frame, orb_leds):
    orb = max(frame[:orb_leds], key=lambda pixel: sum(pixel))
    stem = frame[orb_leds:]
    glyphs = " .:-=+*#%@"
    line = "".join(glyphs[min(len(glyphs) - 1, sum(pixel) // 65)] for pixel in stem)
    return f"orb={orb} stem={line}"


def read_virtual_commands(commands):
    """Read terminal lines without blocking the LED update loop."""
    for line in sys.stdin:
        commands.put(line.strip())
    commands.put(None)


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
    virtual_button = (VirtualButtonPlayer(config, args.virtual_button)
                      if args.virtual_button else None)
    cycle_status = (CycleStatusDisplay(sys.stdout)
                    if args.virtual_button == "cycle" else None)
    commands = Queue() if args.virtual_button == "input" else None
    if commands is not None:
        mapping = ", ".join(f"{key}/{index}: {label}" for index, (key, label)
                            in enumerate(VIRTUAL_GESTURES, start=1))
        print(f"Virtual button commands: {mapping}. Type q to quit.", flush=True)
        threading.Thread(target=read_virtual_commands, args=(commands,),
                         daemon=True).start()
    hardware = None
    if not args.dry_run:
        from wizard_staff.hardware import PiHardware
        hardware = PiHardware(config, staff.geometry.total_leds,
                              enable_button=virtual_button is None)

    start = time.monotonic()
    if args.effect:
        staff.trigger(args.effect, start)
    next_frame = start
    next_preview = start
    report_start = start
    report_frames = 0
    report_work_s = 0.0
    report_max_work_s = 0.0
    report_text = "" if cycle_status is not None and args.report_fps else None
    quit_requested = False
    try:
        while (not quit_requested and
               (args.seconds is None or time.monotonic() - start < args.seconds)):
            now = time.monotonic()
            if commands is not None:
                while True:
                    try:
                        command = commands.get_nowait()
                    except Empty:
                        break
                    if command is None:
                        if args.seconds is None:
                            quit_requested = True
                        break
                    if command.lower() == "q":
                        quit_requested = True
                        break
                    if not virtual_button.enqueue(command):
                        print(f"Unknown virtual button: {command!r}", flush=True)
            if quit_requested:
                break
            work_started = time.perf_counter() if args.report_fps else None
            if virtual_button is not None:
                pressed = virtual_button.tick(now, staff.effect is not None)
                if cycle_status is None:
                    for announcement in virtual_button.announcements:
                        print(announcement, flush=True)
            else:
                pressed = hardware.is_pressed() if hardware else False
            frame = staff.step(now, pressed)
            if hardware:
                hardware.show(frame)
            elif cycle_status is None and now >= next_preview:
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
                    summary = (f"fps={report_frames / report_elapsed:.1f} "
                               f"update_avg_ms={report_work_s / report_frames * 1000:.2f} "
                               f"update_max_ms={report_max_work_s * 1000:.2f}")
                    if cycle_status is not None:
                        report_text = summary
                    else:
                        print(summary, flush=True)
                    report_start = finished_at
                    report_frames = 0
                    report_work_s = 0.0
                    report_max_work_s = 0.0
            if cycle_status is not None:
                cycle_status.update(staff, virtual_button, now, report_text)
            next_frame += 1 / config.frame_rate
            time.sleep(max(0, next_frame - time.monotonic()))
    except KeyboardInterrupt:
        pass
    finally:
        if hardware:
            hardware.close()


if __name__ == "__main__":
    main()

