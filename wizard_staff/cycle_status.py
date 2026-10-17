"""In-place terminal status for the virtual button cycle."""

from .effects import BASE_PATTERNS
from .virtual_button import BASE_INTERVAL_SECONDS


PATTERN_ROWS = (
    ("green_spiral", "B1", "Green spiral"),
    ("green_channels", "B2", "Green channels"),
    ("rainbow_sparks", "B3", "Rainbow sparks"),
    ("descent_fill", "a", "Descent fill"),
    ("upward_spirals", "b", "Upward spirals"),
    ("channel_wave", "c", "Channel wave"),
    ("charge", "d", "Charge hold"),
    ("release_burst", "d", "Release burst"),
    ("unset", "e", "Unset indicator"),
    ("stack_drop", "f", "Stacking drops"),
    ("stack_unload", "f", "Stack unload"),
)
PATTERN_NAMES = {key: name for key, _, name in PATTERN_ROWS}
EFFECT_LENGTHS = {
    "descent_fill": 4.0,
    "upward_spirals": 2.7,
    "channel_wave": 3.0,
    "release_burst": 1.5,
    "unset": 0.45,
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
    """Return (active pattern key, rounded seconds remaining)."""
    effect = staff.effect
    if effect is not None:
        if effect in ("charge", "stack_drop"):
            release_at = _hold_release_at(player)
            remaining = 0.0 if release_at is None else release_at - now
        elif effect == "stack_unload":
            remaining = (staff.effect_started_at +
                         staff.stack_effect.unload_finish_at - now)
        else:
            remaining = staff.effect_started_at + EFFECT_LENGTHS[effect] - now
        key = effect
    else:
        elapsed = max(0.0, now - staff.started_at)
        pattern_duration = staff.config.base_pattern_s
        key = BASE_PATTERNS[int(elapsed // pattern_duration) % len(BASE_PATTERNS)]
        remaining = pattern_duration - elapsed % pattern_duration
        if player.current_key is not None:
            if player.effect_seen:
                remaining = min(remaining, BASE_INTERVAL_SECONDS)
            else:
                remaining = min(remaining, _next_effect_at(player) - now)
        elif player.base_until is not None:
            remaining = min(remaining, player.base_until - now)
    return key, int(max(0.0, remaining) + 0.5)


def format_status(staff, player, now, report_text=None):
    key, seconds = status_snapshot(staff, player, now)
    entries = [(row_key, f"{code:<2}  {name}")
               for row_key, code, name in PATTERN_ROWS]
    width = max(len(entry) for _, entry in entries)
    lines = [f"Active pattern: {PATTERN_NAMES[key]}", "", "Rotating patterns:"]
    for row_key, entry in entries:
        if row_key == key:
            lines.append(f"> {entry:<{width}}  {seconds}s left")
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
