"""In-place terminal status for the virtual button cycle."""

PATTERN_ROWS = (
    ("a", "a", "Descent fill"),
    ("base_a", "1", "Green spiral"),
    ("b", "b", "Upward spirals"),
    ("base_b", "2", "Green channels"),
    ("c", "c", "Channel wave"),
    ("base_c", "3", "Bouncing vectors"),
    ("d", "d", "Charge / release burst"),
    ("base_d", "1", "Green spiral"),
    ("e", "e", "Unset indicator"),
    ("base_e", "2", "Green channels"),
    ("f", "f", "Stacking drops / unload"),
    ("base_f", "3", "Bouncing vectors"),
)
PATTERN_NAMES = {key: name for key, _, name in PATTERN_ROWS}
EFFECT_LENGTHS = {
    "descent_fill": 3.5,
    "channel_wave": 3.0,
    "release_burst": 1.5,
    "unset": 0.45,
}
EFFECT_ROWS = {
    "descent_fill": "a",
    "upward_spirals": "b",
    "channel_wave": "c",
    "charge": "d",
    "release_burst": "d",
    "unset": "e",
    "stack_drop": "f",
    "stack_unload": "f",
}


def _hold_release_at(player):
    if player.started_at is None or not player.intervals:
        return None
    return player.started_at + player.intervals[-1][1] + player.config.debounce_s


def _next_effect_at(player):
    if player.current_key is None:
        return None
    key = player.current_key
    if key in ("a", "b"):
        delay = player.config.debounce_s + player.config.multi_press_s
        return player.started_at + player.intervals[-1][1] + delay
    if key in ("c", "e"):
        return player.started_at + player.intervals[-1][1] + player.config.debounce_s
    start = player.intervals[-1][0]
    return player.started_at + start + player.config.debounce_s + player.config.long_press_s


def status_snapshot(staff, player, now):
    """Return (active route row, rounded seconds remaining)."""
    effect = staff.effect
    if effect is not None:
        if effect in ("charge", "stack_drop"):
            release_at = _hold_release_at(player)
            remaining = 0.0 if release_at is None else release_at - now
        elif effect == "stack_unload":
            remaining = (staff.effect_started_at +
                         staff.stack_effect.unload_finish_at - now)
        elif effect == "upward_spirals":
            stem = len(staff.geometry.stem)
            rise_speed = (stem + 6) / 0.9
            duration = 1.3 + (stem * 1.2 + 6) / rise_speed + 0.12
            remaining = staff.effect_started_at + duration - now
        else:
            remaining = staff.effect_started_at + EFFECT_LENGTHS[effect] - now
        key = EFFECT_ROWS[effect]
    else:
        if player.base_until is not None and now < player.base_until:
            key = f"base_{player.base_after_key}"
            remaining = player.base_until - now
        elif player.current_key is not None:
            key = player.current_key
            remaining = max(0.0, _next_effect_at(player) - now)
        else:
            key = "a"
            remaining = 0.0
    return key, int(max(0.0, remaining) + 0.5)


def format_status(staff, player, now, report_text=None):
    key, seconds = status_snapshot(staff, player, now)
    entries = [(row_key, f"{code:<2}  {name}")
               for row_key, code, name in PATTERN_ROWS]
    width = max(len(entry) for _, entry in entries)
    lines = [f"Active pattern: {PATTERN_NAMES[key]}", "", "Cycle sequence:"]
    for row_key, entry in entries:
        if row_key == key:
            lines.append(f"> {entry:<{width}}  {seconds:>2}s left")
        else:
            lines.append(f"  {entry}")
    if report_text is not None:
        lines.extend(("", report_text))
    return "\n".join(lines), (key, seconds, report_text)


class CycleStatusDisplay:
    def __init__(self, stream):
        self.stream = stream
        self.terminal = stream.isatty()
        self.line_count = 0
        self.last_state = None

    def update(self, staff, player, now, report_text=None):
        block, state = format_status(staff, player, now, report_text)
        if state == self.last_state:
            return
        self.last_state = state
        lines = block.split("\n")
        if self.terminal:
            if self.line_count:
                self.stream.write(f"\x1b[{self.line_count}F")
            count = max(self.line_count, len(lines))
            for index in range(count):
                self.stream.write("\x1b[2K" + (lines[index] if index < len(lines) else "") +
                                  "\n")
            self.line_count = count
        else:
            self.stream.write(block + "\n")
        self.stream.flush()
