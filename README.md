# Wizard Staff

A fixed NeoPixel staff built from the light-vector idea in `tire-pixel`. The
first `orb_leds` logical pixels form the orb at the top. The next `stem_leds` pixels
follow the helix from top to bottom. Patterns add independent orb, spiral, and
vertical-channel vectors, plus sparse spring paths that activate every third stem LED. There is no IMU or motion compensation.

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
the sum of overlapping RGB contributions. Every orb contribution additionally
receives an independent linear `orb_gain = 1.5` multiplier, after gamma correction.
The orb can therefore exceed the shaft peak setting; only RGB 255 clips the sum.
Use `--orb-gain 1.0` to compare with the earlier orb intensity.

The `effects` branch uses gamma 2.2 for authored RGB values and brightness
envelopes. Each vector is corrected before its baseline/override multiplier and
before contributions are added. Those output multipliers and fractional-pixel
coverage remain linear; clipping still happens after addition. A full-strength
primary therefore keeps the same configured peak, while intermediate colors
and fades change. Dry-run frames and live frames use the same correction.
Pattern e uses gamma 1.0 to preserve its pre-branch appearance.
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

At startup, the base patterns cycle every 18 seconds. A single short press
advances from the currently displayed base to the next one, wraps after pattern
4, and keeps that selection until another manual selection. Effects return to
that selected base. The four bases are:

1. Near-white, two-wrap tails fall from the top at an initial 48 stem LEDs/s
   with low downward acceleration. The green orb pulses once per launch,
   peaking as the vector first enters the stem.
2. Lights fall along four vertical channels at 9.6 vertical LEDs/s. The green
   orb pulses twice per drop, with one peak aligned to each vector entering.
3. White vectors reflect above a green anchor with a pronounced impact pulse.
   They launch at 120 stem LEDs/s and low acceleration, 6 wraps/s^2. Falling
   vectors are one third dimmer; rising vectors progressively dim toward the top.
   Both white vectors now use half their previous output brightness and are
   one physical wrap shorter (one wrap long with the default geometry).
   Two flights overlap. A returning light remains absent for 200 ms before its
   replacement launches. The brighter orange orb gives a red cue 60 ms before
   each drop.
4. Spring streams use three literal every-third-LED paths. Every 1.0 s, one
   vector launches down from the top and another up from the bottom. Each
   independently chooses a path, a familiar palette color, an initial speed
   between 12 and 22 wraps/s, and low/medium/high acceleration toward its
   destination. Vectors run at half the former intensity with quadratic, eight-wrap fading
   tails. The orb is much brighter. Vectors can cross and overtake;
   overlapping RGB contributions add and clip only at 255.

Rainbow sparks remain available in code but are out of the cycle.

The button has software debounce and a 0.38-second multi-press window.
Gesture names use Morse-style notation: `dit` is a short press (up to
0.28 seconds), `dah` is a medium press (below 0.85 seconds), and `hold`
starts at 0.85 seconds. Underscores join presses, such as `dit_dah_dit`.
The a-j terminal effect shortcuts remain available; a now simulates the new
short-medium-short descent/fill gesture:

| Gesture | Slot | Effect |
| --- | --- | --- |
| `dit` | 1-4 select directly | Advance to the next base pattern and keep it selected |
| `dit_dah_dit` | a | Icy drop and red fill at 1.5 times their former speeds, then six white boundaries with cyan/dark/red/dark/cyan bands descend; ten two-row cyan bands with six dark rows between them overwrite upward; cyan orb fades after the last band clears |
| `dit_dit` | b | Growing groups of varied, two-wrap upward trails; quiet yellow orb flashes brighter blue on the first light arrival, with a 15 ms rise and 600 ms fade |
| `dah` | c | Channel wave with a six-row dark gap, rising at 56 rows per second and rotating one column per second under a subdued white orb |
| `hold` | d | Slower upward lights and a blue orb while held; release pauses for 200 ms with the orb blue before launching the burst; the orb stays blue until the first burst vector arrives, then bright purple with rapid white flashes |
| `dit_dah` | e | Original alternating blue and green pairs with linear 30-wrap fading tails launch from the center toward both ends twice per second; orb stays dark |
| `dit_hold` | f | Four-pixel bars cycle through all eight familiar saturated colors in shuffled order before repeating, and stack with the orb off; release unloads the bars under a slow-then-fast white orb ramp, then three flashes, a longer white hold, and a fade |
| `dit_dit_dit` | g | Interactive red shots spanning two solid red wraps: the leading wrap at configured maximum brightness, the trailing wrap at one third; dits shoot and a hold exits |
| `dah_dit` | h | Opposing amber/blue ribbons grow up the channels, twist, fade, and leave a quiet blue orb response; 5 seconds, or continue while held |
| `dah_dah` | i | Two tightly spaced triplets accelerate upward at high (14 wraps/s^2); the second starts as the first set of tails clears, without waiting for orb flashes; arrival and duration follow the actual motion |
| `dit_dit_dah` | j | Red orb and upper stem third, white middle third, blue lower third; strong traveling brightness ripples soften between gusts; 8 seconds, or continue while held |

The button interpreter defines the following dit/dah sequences. Unassigned
sequences show the brief red unset indicator:

| Sequence | Assignment |
| --- | --- |
| `dit` | Next base pattern (manual selection) |
| `dah` | Channel wave |
| `dit_dit` | Upward spirals |
| `dit_dah` | Opposed pairs |
| `dah_dit` | Twisting ribbons |
| `dah_dah` | Gathering spell |
| `dit_dit_dit` | Interactive red shots |
| `dit_dit_dah` | American flag |
| `dit_dah_dit` | Descent fill and cyan finale |
| `dit_dah_dah` | Unassigned |
| `dah_dit_dit` | Unassigned |
| `dah_dit_dah` | Unassigned |
| `dah_dah_dit` | Unassigned |
| `dah_dah_dah` | Unassigned |
| `hold` | Charge / release burst |
| `dit_hold` | Stacking drops / unload |

All triggered patterns use a half-second fade-to-black handoff before returning
to a base pattern. The handoff fades the last displayed frame, including the
orb, without restarting launches. Effects that have already faded completely
stay black rather than reviving an old frame. A new explicit input command or
base selection interrupts the handoff; base patterns do not fade automatically.

Button timings are in `wizard_staff/config.py`; slot assignments and optional
pattern flags are in `wizard_staff/patterns.py`. New spell choreography and
shared ember/mist/red palettes are in `wizard_staff/spell_effects.py`.
Patterns b (`dit_dit`), c (`dah`), e (`dit_dah`), h (`dah_dit`,
twisting ribbons), and j (`dit_dit_dah`, American flag) can be extended by
pressing and holding while they run.
Releasing stops new launches and lets active vectors clear; the flag fades over
half a second from release. Twisting ribbons keep rotating while held, then
fade their stem and play the quiet blue orb ending over 1.2 seconds from release.
Pattern e normally launches for three seconds.

The descent/fill finale starts after the red fill and orb flashes. Six white
lights descend from the top at constant speeds in the ratio 6:5:4:3:2:1.
From the fastest to the slowest boundary, the spaces are cyan, dark, red, dark,
cyan. The leading boundary replaces the old red as it travels down. As soon as
it reaches the bottom, a finite train rises from the bottom, overwriting the
still-descending bands: ten cyan bands, each two vertical rows wide, separated
by six dark rows (triple the previous gap). A row spans `leds_per_repeat` stem
LEDs, including with two physical turns per repeat. Behind the final band the
stem stays dark. The orb
turns cyan on the first band arrival, stays cyan until the tenth clears the top,
then fades to black over 0.6 seconds. Timings and band count are in
`wizard_staff/effects.py`.
One- and two-press dit/dah patterns are recognized after the multi-press
window closes; three-press patterns are recognized on the third release. A hold
starts its effect as soon as the long-press threshold is crossed. In interactive
red-shot mode the staff goes dark; each dit launches two solid red wraps up the
helix. The leading wrap uses configured maximum brightness, and the trailing
wrap uses one third of that output, independent of gamma. Shots travel 30%
faster than before, reaching the orb after about 0.308 seconds without acceleration;
the orb flashes red and fades over 0.2 seconds. Shots can overlap. Hold the
button for the normal 0.85-second threshold to exit; the staff immediately
returns to its selected or scheduled base pattern.
The `dit_hold` slot drops eight bars per second (two per second in each of
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
python main.py --dry-run --seconds 10 --effect dit_dah_dit
python main.py --dry-run --virtual-button cycle
python main.py --dry-run --virtual-button input
python main.py --dry-run --effect gathering_spell --seconds 5
python -m unittest discover -s tests -v
```

`--virtual-button` replaces GPIO button input while keeping the normal gesture
classifier. In `input` mode, type `1`, `2`, `3`, or `4` followed by Enter to select
a base pattern, `a` through `j` to simulate a gesture, `s` to launch an
interactive shot, or `x` to simulate a long press and exit interactive mode.
The input mode prints the complete pattern list and command options at startup.
Type `q` to quit.
Input mode starts new gesture commands without waiting for an active effect to
finish, and can interrupt a simulated hold. A numbered base selection switches
immediately. Gesture commands still pass through the normal press durations,
debounce, and multi-press window. Base patterns, including 4, do not wait for
vectors to clear. `s` and `x` retain their interactive shot/exit behavior.
Hold gestures stay active for about five seconds before release; f holds for
six seconds to demonstrate drops continuing after the stacks fill. A selected
base pattern resumes after a triggered effect.
In `cycle` mode, the route includes `g` for interactive red shots after the
existing `a` through `f` gestures and their base-pattern gaps. It demonstrates
three shots at irregular intervals, then holds to exit and continues through
`h` (twisting ribbons), `i` (gathering spell), and `j` (American flag),
with their base-pattern gaps. Base gaps cycle through 1-4; g resumes base 1.
Each base step lasts five seconds after its triggered effect finishes. The
terminal display shows the route in order, highlights its active row, and
updates a countdown in a fixed column. Interactive mode displays its tap/hold
instructions instead of a countdown. Cycle mode uses this display in place of
the dry-run LED preview. Either mode can drive the real LEDs without a wired
button by omitting `--dry-run`.

The optional `downward_acceleration` value in `wizard_staff/patterns.py` is
`low`, `med`, or `high`, meaning 6, 10, or 14 physical wraps/s^2. Omitted or
`off` means no acceleration. Pattern a previously had acceleration disabled
because its ring and red fill used separate trajectories. The red boundary now
comes from the ring position, so a uses low acceleration while staying aligned.
Bases 1 and 3 also use low acceleration. Pattern i uses `upward_acceleration` set
to `high`; the shared motion helper represents upward acceleration as negative.
The new spring base independently chooses low, medium, or high acceleration
with the same sign as each vector's travel. Pattern e retains its original
motion and two-pair-per-second launch cadence. Other mappings omit acceleration.
The optional `allow_reversal` defaults to true for existing gravity effects.

`StaffGeometry.spiral_channel(0..2)` returns the three sparse spring paths;
`wizard_staff/spring_effects.py` generates their independent, reproducible
launches and only evaluates a bounded history of potentially visible vectors.

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


The American flag pattern is also available directly with `--effect american_flag`.
Its stem is divided into three nearly equal LED bands; the orb stays red.

## Start automatically on Raspberry Pi boot

Use a systemd service to start without logging in and restart after a crash.
The definition is tracked in [deploy/wizard-staff.service](deploy/wizard-staff.service).
It assumes the repository is `/home/pi/wizard-staff` and uses the existing
`tire` environment's Python. Stop any manually running staff script before
starting the service.

From the repository directory on the Pi, install the definition:

```bash
sudo install -m 0644 deploy/wizard-staff.service /etc/systemd/system/wizard-staff.service
```

If your paths differ, edit the installed file before starting it:

```bash
sudo nano /etc/systemd/system/wizard-staff.service
```

Set `WorkingDirectory` to the output of `pwd` from your repository. Update both
the Python executable and `main.py` paths in `ExecStart` as needed. To log frame
timing diagnostics, append `--report-fps` to that command.

The service runs as root, matching the existing hardware launch command. It
uses the environment's Python directly, so Conda activation is unnecessary.
`SIGINT` lets the script run its normal cleanup and clear the LEDs when stopped.
The service uses the physical button; omit interactive terminal options.
`Nice=-5` and `CPUWeight=200` give it higher CPU priority during contention;
they do not guarantee frame timing or prevent pauses in the LED driver.

Apply the definition, enable boot startup, and start or restart the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable wizard-staff.service
sudo systemctl restart wizard-staff.service
sudo systemctl status wizard-staff.service
```

After updating only Python code, restart the service. If the repository's
service definition changes, repeat the install step, reapply any custom paths,
then run `daemon-reload` and restart. Existing overrides made with
`systemctl edit` still take precedence; inspect the effective definition with
`sudo systemctl cat wizard-staff.service`.

View logs or restart after updating the code:

```bash
sudo journalctl -u wizard-staff.service -b -f
sudo systemctl restart wizard-staff.service
```

To stop the staff now and disable automatic startup on future boots:

```bash
sudo systemctl disable --now wizard-staff.service
```

To stop it temporarily while keeping automatic startup enabled:

```bash
sudo systemctl stop wizard-staff.service
```

To enable it again and start it immediately:

```bash
sudo systemctl enable --now wizard-staff.service
```

See the [systemd service documentation](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)
and [systemctl documentation](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html).
