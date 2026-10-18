# Wizard Staff

A fixed NeoPixel staff built from the light-vector idea in `tire-pixel`. The
first `orb_leds` logical pixels form the orb at the top. The next `stem_leds` pixels
follow the helix from top to bottom. Patterns add independent orb, spiral, and
vertical-channel vectors. There is no IMU or motion compensation.

## Layout

The current defaults in `main.py` are 300 LEDs total: 31 in the orb and 269 on
the stem, with 4 LEDs per wrap. Logical indices 31, 35, 39, ... are one
vertical channel; 32, 36, 40, ... are the next. This accounts for 67 complete
four-LED wraps plus one stem LED. The rendering model numbers the orb first and
the stem from
top to bottom. `DATA_START = "bottom"` reverses each frame for a strand whose
physical LED 0 is at the bottom; the orb occupies physical LEDs 269–299. Set
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

The `effects` branch uses gamma 2.2 for authored RGB values and brightness
envelopes. Each vector is corrected before its baseline/override multiplier and
before contributions are added. Those output multipliers and fractional-pixel
coverage remain linear; clipping still happens after addition. A full-strength
primary therefore keeps the same configured peak, while intermediate colors
and fades change. Dry-run frames and live frames use the same correction.
Use `--gamma 1.0` for an uncorrected comparison, or try `--gamma 2.8` for a
stronger curve. `StaffConfig.gamma` accepts 1.0 through 3.5.

5050 describes the 5 mm package, not an exact LED model or measured response.
Adafruit's [5050 NeoPixel description](https://www.adafruit.com/product/1379)
includes WS2812B and SK6812 variants. Its
[gamma guide](https://learn.adafruit.com/led-tricks-gamma-correction?view=all)
uses an empirically chosen 2.8 and discusses loss of dim steps with 8-bit PWM.
Our 2.2 starting point is a gentler estimate for this staff's dim tails, not a
calibration of its particular LEDs. The existing RGB order and red/green output
swap are independent of gamma correction.

Measure the completed wrap before setting these values. The code does not need
the total stem count to divide evenly by `leds_per_repeat`; the final partial
turn is handled automatically.

## Patterns and button slots

Without virtual-button selection, the base patterns cycle every 18 seconds:

1. A gently pulsing green orb with a brief white accent at each launch, and
   near-white, two-wrap palette tails that each enter from above the top and fall
   along the helix at 48 stem LEDs per second with low downward acceleration.
2. The same orb and launch accent with lights falling along vertical channels
   at 9.6 vertical LEDs per second.
3. A subdued orange orb and a green anchor that brightens at impact. White,
   eight-LED vectors start falling at 120 stem LEDs per second and reflect
   just above the anchor. Downward acceleration is high (6 physical wraps/s²);
   the vector reflects with the same speed and gravity slows it as it rises.
   Two vectors overlap and cross near the middle. Rising vectors gradually
   dim throughout their climb and disappear at the top. Each returning vector
   has been absent for 200 ms when its replacement launches, while the other
   vector continues. Each launch has a red orb cue 100 ms later; the green
   anchor has a brighter steady glow and a pronounced reflection pulse.
   Rainbow sparks remain available in code but are out of the cycle.

The button has software debounce and a 0.38-second multi-press window:

| Gesture | Slot | Effect |
| --- | --- | --- |
| One quick press | a | Icy blue/violet tail descends, then leads a steady, dim red fill back up; orb flashes |
| Two quick presses | b | Growing groups of varied, two-wrap upward trails; quiet yellow orb flashes blue on group arrivals |
| Medium press | c | Channel wave with a six-row dark gap, rising at 56 rows per second and rotating one column per second under a subdued white orb |
| Long press and hold | d | Slower upward lights and a blue orb while held; release keeps the orb blue until the first burst vector arrives, then bright purple with rapid white flashes |
| Quick press then medium press | e | Alternating blue and green pairs with bright leading edges and dim 30-wrap tails launch from the center toward both ends twice per second; orb stays dark |
| Quick press then long hold | f | Four-pixel bars cycle through all eight familiar saturated colors in shuffled order before repeating, and stack with the orb off; release unloads the bars under a slow-then-fast white orb ramp, then three flashes, a longer white hold, and a fade |
| Three quick presses | g | Interactive red shots with a warm head and red-to-crimson fading tail; short presses shoot and a long hold exits |
| Medium then quick press | h | Opposing amber/blue ribbons grow up the channels, twist, fade, and leave a quiet blue orb response; 5 seconds |
| Two medium presses | i | Two quick small/small/strong triplets, with launch spacing reduced by 2.5�; trails merge into a spiral and the orb responds on arrival; about 3.8 seconds |

The button interpreter defines the following short/medium sequences. Unassigned
sequences show the brief red unset indicator:

| Sequence | Assignment |
| --- | --- |
| One short | Descent fill |
| One medium | Channel wave |
| Two shorts | Upward spirals |
| Short, then medium | Opposed pairs |
| Medium, then short | Twisting ribbons |
| Two mediums | Gathering spell |
| Short, short, short | Interactive red shots |
| Short, short, medium | Unassigned |
| Short, medium, short | Unassigned |
| Short, medium, medium | Unassigned |
| Medium, short, short | Unassigned |
| Medium, short, medium | Unassigned |
| Medium, medium, short | Unassigned |
| Medium, medium, medium | Unassigned |

Button timings are in `wizard_staff/config.py`; slot assignments and optional
pattern flags are in `wizard_staff/patterns.py`. New spell choreography and
shared ember/mist/red palettes are in `wizard_staff/spell_effects.py`.
Patterns b, c, and e can be extended by pressing and holding while they run.
Releasing stops new launches and lets active vectors clear. Pattern e normally
launches for three seconds.
One- and two-press short/medium patterns are recognized after the multi-press
window closes; three-press patterns are recognized on the third release. A hold
starts its effect as soon as the long-press threshold is crossed. In interactive
red-shot mode the staff goes dark; each short press launches a red vector up the
helix with an eight-wrap fading tail. When it reaches the orb after 0.4 seconds,
the orb flashes red and fades over 0.2 seconds. Shots can overlap. Hold the
button for the normal 0.85-second threshold to exit; the staff immediately
returns to its selected or scheduled base pattern.
The quick-then-hold slot drops eight bars per second (two per second in each of
the default four channels) at 100 vertical pixels per second. Each channel
stacks up to ten bars, or 40 vertical pixels. Extra drops disappear when they
reach the full stack. On release, in-flight drops clear and the stacks unload
at 200 vertical pixels per second. The orb is off while dropping and ramps to
bright white as the last bars rise. After unloading, it flashes three times,
stays white for 0.4 seconds, and fades out over 150 ms. These
three speeds, the bar length, and the stack limit are parameters of
`StackingDropEffect`.

## Run

On a development computer, no Pi packages are needed:

```bash
python main.py --dry-run --seconds 10
python main.py --dry-run --seconds 5 --effect quick
python main.py --dry-run --virtual-button cycle
python main.py --dry-run --virtual-button input
python main.py --dry-run --effect gathering_spell --seconds 5
python -m unittest discover -s tests -v
```

`--virtual-button` replaces GPIO button input while keeping the normal gesture
classifier. In `input` mode, type `1`, `2`, or `3` followed by Enter to select
a base pattern, `a` through `i` to simulate a gesture, `s` to launch an
interactive shot, or `x` to simulate a long press and exit interactive mode.
The input mode prints the complete pattern list and command options at startup.
Type `q` to quit.
Commands entered while a finite effect is running are queued; `s` and `x` can
also be entered while interactive mode is active.
Hold gestures stay active for about five seconds before release. A selected
base pattern resumes after a triggered effect.
In `cycle` mode, the route includes `g` for interactive red shots after the
existing `a` through `f` gestures and their base-pattern gaps. It demonstrates
three shots at irregular intervals, then holds to exit and continues through
`h` (twisting ribbons) and `i` (gathering spell), with their base-pattern gaps.
Each base step lasts five seconds after its triggered effect finishes. The
terminal display shows the route in order, highlights its active row, and
updates a countdown in a fixed column. Interactive mode displays its tap/hold
instructions instead of a countdown. Cycle mode uses this display in place of
the dry-run LED preview. Either mode can drive the real LEDs without a wired
button by omitting `--dry-run`.

The optional `downward_acceleration` value in `wizard_staff/patterns.py` is
`low`, `med`, or `high`, meaning 2, 4, or 6 physical wraps/s². Omitting it (or
setting it to `off`) preserves the original motion. Low acceleration is
used by the green spiral and bouncing base patterns. Pattern a (descent fill)
uses steady motion so its leading ring and red fill stay aligned. The red
boundary is derived from the ring position even if acceleration is enabled.
Pattern e retains its original motion
and two-pair-per-second launch cadence; the remaining mappings omit acceleration. Bouncing vectors overlap and cross near the middle,
with a 100 ms red orb cue beginning 100 ms after each launch. Rising vectors
dim progressively, and replacements launch 200 ms after the older return ends. The optional `allow_reversal` mapping field
defaults to true for upward motion; vectors that fully leave the staff are
retired rather than returning from beyond its ends.

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

The normal loop targets 60 frames per second. To see its measured rate and
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

If the live loop reports about 60 FPS and update time stays under 16.7 ms, its
configured frame rate is the limiting factor. If it stays below 60 FPS, compare
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

