# Wizard Staff project notes

This is a fixed NeoPixel staff. Physical LED index 0 is at the top of the orb.
The remaining LEDs run down the pole in a helix. There is no IMU or wheel frame.

- Keep orb and stem counts configurable.
- Map the stem from top to bottom. Vertical channels repeat every configured
  number of LEDs, over one or two physical turns.
- Build effects from independent light vectors and add their RGB contributions.
  Clip each channel to 255 before sending a frame to the LEDs.
- Keep pattern updates nonblocking. The button is debounced in software, and
  press sequences are classified from monotonic time.
- Use logical RGB values in patterns. The output adapter defaults to the
  red/green swap and RGB pixel order used by tire-pixel; both are configurable.
- Hardware imports belong in the output/input adapters so simulation and tests
  work on computers without Raspberry Pi packages.
- Use LF line endings for project text files; do not introduce CRLF.

