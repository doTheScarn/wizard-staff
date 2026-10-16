"""Flash the physical ends of a NeoPixel strand and measure update speed."""

import argparse
import time


OFF = (0, 0, 0)
WHITE = (255, 255, 255)


def measure(strip, led_count, seconds, rewrite_all):
    """Return (frames sent, elapsed seconds) without a frame-rate delay."""
    frames = 0
    started = time.monotonic()
    while time.monotonic() - started < seconds:
        color = WHITE if frames % 2 == 0 else OFF
        if rewrite_all:
            for index in range(led_count):
                strip[index] = color if index in (0, led_count - 1) else OFF
        else:
            strip[0] = color
            strip[led_count - 1] = color
        strip.show()
        frames += 1
    return frames, time.monotonic() - started


def report(label, frames, elapsed):
    print(f"{label}: {frames} frames in {elapsed:.2f} s; "
          f"{frames / elapsed:.1f} frames/s; "
          f"{1000 * elapsed / frames:.2f} ms/frame; "
          f"{frames / (2 * elapsed):.1f} on/off cycles/s", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--leds", type=int, default=300)
    parser.add_argument("--seconds", type=float, default=5.0,
                        help="Seconds per test phase (default: 5).")
    parser.add_argument("--led-pin", default="D18")
    parser.add_argument("--brightness", type=float, default=0.1)
    args = parser.parse_args()
    if args.leds < 2 or args.seconds <= 0 or not 0 < args.brightness <= 1:
        parser.error("use at least 2 LEDs, positive seconds, and brightness in (0, 1]")

    import board
    import neopixel

    strip = neopixel.NeoPixel(getattr(board, args.led_pin), args.leds,
                             brightness=args.brightness, auto_write=False,
                             pixel_order=neopixel.RGB)
    try:
        strip.fill(OFF)
        strip.show()
        print(f"Flashing physical LEDs 0 and {args.leds - 1}; no frame delay.",
              flush=True)
        for label, rewrite_all in (("End LEDs only", False),
                                   ("Rewrite all LEDs", True)):
            frames, elapsed = measure(strip, args.leds, args.seconds, rewrite_all)
            report(label, frames, elapsed)
    finally:
        strip.fill(OFF)
        strip.show()
        strip.deinit()


if __name__ == "__main__":
    main()
