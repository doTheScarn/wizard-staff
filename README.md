# Wizard Staff

A fixed NeoPixel staff built from the light-vector idea in `tire-pixel`. The
first `orb_leds` logical pixels form the orb at the top. The next `stem_leds` pixels
follow the helix from top to bottom. Patterns add independent orb, spiral, and
vertical-channel vectors. There is no IMU or motion compensation.

## Layout

The current defaults in `main.py` are 300 LEDs total: 36 in the orb and 264 on
the stem, with 4 LEDs per wrap. Logical indices 36, 40, 44, ... are one
vertical channel; 37, 41, 45, ... are the next. This accounts for 66 complete
four-LED wraps. The rendering model numbers the orb first and the stem from
top to bottom. `DATA_START = "bottom"` reverses each frame for a strand whose
physical LED 0 is at the bottom; the orb occupies physical LEDs 264–299. Set
`--data-start top` for a strand whose data input is at the orb.
`turns_per_repeat=1` means those four positions occur in each full turn. If
the physical wrap repeats only every two turns, set `turns_per_repeat=2` and
count the LEDs across *both* turns in `leds_per_repeat`.

Each vector specifies a path through logical LED indices, color samples along
that path, and a moving position. The renderer sums every vector and clips RGB
to 255. A channel path can contain nonadjacent physical indices, so a vertical
line is one vector even though its LEDs are separated along the string.

`main.py` sets `BASELINE_SHAFT_BRIGHTNESS = 0.2` and
`BASELINE_ORB_BRIGHTNESS = 0.2` for ordinary vectors. Effects can override the
baseline per vector; bright sparks, bursts, and orb flashes use
`MAX_BRIGHTNESS = 0.5`. This is a peak setting for those vectors, not a cap on
the sum of overlapping RGB contributions.

Measure the completed wrap before setting these values. The code does not need
the total stem count to divide evenly by `leds_per_repeat`; the final partial
turn is handled automatically.

## Patterns and button slots

The base patterns cycle automatically every 18 seconds:

1. Green orb pulsing once per second, with fading lights following the helix
   downward.
2. The same orb with lights moving downward along vertical channels.
3. Slowly changing rainbow orb, dim stem, and four distributed sparks that
   change several times per second.

The button has software debounce and a 0.38-second multi-press window:

| Gesture | Slot | Effect |
| --- | --- | --- |
| One quick press | 1 | Orb dark; light descends; color fills bottom to top; orb flashes |
| Two quick presses | 2 | Repeated fast upward spirals, flashing the orb at each arrival |
| Medium press | 3 | Colored vertical-channel wave |
| Long press and hold | 4 | Faster, more frequent upward lights while held; release burst |
| Quick press then medium press | 5 | Unset; top four stem pixels glow dim red briefly |
| Quick press then long hold | 6 | Colored four-pixel bars drop down successive vertical channels and stack; release sends one bar per channel upward at a time, with white orb flashes |

Timings and slot assignments are in `wizard_staff/config.py` and
`wizard_staff/controller.py`. Unset slots use the same red indicator.
Quick presses are recognized after the multi-press window closes. A hold
starts its effect as soon as the long-press threshold is crossed.
The quick-then-hold slot drops eight bars per second (two per second in each of
the default four channels) at 100 vertical pixels per second. Each channel
stacks up to ten bars, or 40 vertical pixels. Extra drops disappear when they
reach the full stack. On release, in-flight drops clear and the stacks unload
at 200 vertical pixels per second. The orb glows faint blue while dropping,
red while unloading, and flashes white as bars reach the top. These three
speeds, the bar length, and the stack limit are parameters of
`StackingDropEffect`.

## Run

On a development computer, no Pi packages are needed:

```bash
python main.py --dry-run --seconds 10
python main.py --dry-run --seconds 5 --effect quick
python -m unittest discover -s tests -v
```

On the Raspberry Pi, connect the strip data line
to the configured NeoPixel pin (default `D18`), and wire a normally-open
button from BCM GPIO 17 to ground. The code enables the internal pull-up.
The LED counts above are set in `main.py`, so no count arguments are required.
You can still override `--orb-leds`, `--stem-leds`, `--leds-per-repeat`,
`--turns-per-repeat`, `--led-pin`, `--data-start`, `--button-gpio`, `--pixel-order`, and
`--color-mapping` for another build.

```bash
sudo /home/pi/miniforge3/envs/tire/bin/python main.py
```

The normal loop targets 30 frames per second. To see its measured rate and
average/worst update time every two seconds, run:

```bash
sudo /home/pi/miniforge3/envs/tire/bin/python main.py --report-fps --seconds 10
```

To measure the strip without the frame-rate delay or pattern renderer, flash
the two physical ends with this benchmark. It reports one phase that changes
only those two pixels, then one that rewrites all 300 pixel values as the normal
output adapter does. Both phases transmit the full strand on every `show()`.

```bash
sudo /home/pi/miniforge3/envs/tire/bin/python benchmark_led_refresh.py
```

If the live loop reports about 30 FPS and update time stays under 33 ms, its
configured frame rate is the limiting factor. If it stays below 30 FPS, compare
its update time with the benchmark phases to identify the cost of writing the
frame and generating the patterns.

This uses the existing `tire` Conda environment even under `sudo`. The button
adapter uses its installed `RPi.GPIO` package; `board` comes from its installed
Adafruit Blinka package. For a new environment, install `requirements.txt`.

The defaults match `tire-pixel`: data pin `D18`, NeoPixel `RGB` order, and its
physical red/green channel swap. Patterns use logical RGB; the output
adapter sends red as `(0, 255, 0)`, green as `(255, 0, 0)`, and blue unchanged.
For a strip with standard color wiring, choose `--color-mapping standard` and
the appropriate `--pixel-order`.
Use a suitable external LED power supply with a shared ground. `--brightness`
is an additional NeoPixel output multiplier, defaulting to 1.0 so the pattern
baseline and flash settings are applied as written.

