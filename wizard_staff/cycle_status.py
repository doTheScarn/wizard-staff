"""In-place terminal status for the virtual button cycle."""

from .effects import (
    CHANNEL_WAVE_TOTAL_SECONDS,
    DESCENT_TOTAL_SECONDS,
    RELEASE_BURST_SECONDS, RELEASE_DELAY_SECONDS,
    UNSET_INDICATOR_SECONDS,
    descent_fill_duration,
    opposed_pair_effect_duration,
    release_burst_duration,
    upward_spiral_effect_duration,
)
from .spell_effects import SPELL_DURATIONS

PATTERN_ROWS = (
    ("a", "a", "Descent fill"),
    ("base_a", "1", "Green spiral"),
    ("b", "b", "Upward spirals"),
    ("base_b", "2", "Green channels"),
    ("c", "c", "Channel wave"),
    ("base_c", "3", "Bouncing vectors"),
    ("d", "d", "Charge / release burst"),
    ("base_d", "1", "Green spiral"),
    ("e", "e", "Opposed pairs"),
    ("base_e", "2", "Green channels"),
    ("f", "f", "Stacking drops / unload"),
    ("base_f", "3", "Bouncing vectors"),
    ("g", "g", "Interactive red shots"),
    ("base_g", "1", "Green spiral"),
    ("h", "h", "Twisting ribbons"),
    ("base_h", "2", "Green channels"),
    ("i", "i", "Gathering spell"),
    ("base_i", "3", "Bouncing vectors"),
)
PATTERN_NAMES = {key: name for key, _, name in PATTERN_ROWS}
EFFECT_LENGTHS = {
    "descent_fill": DESCENT_TOTAL_SECONDS,
    "channel_wave": CHANNEL_WAVE_TOTAL_SECONDS,
    "release_burst": RELEASE_BURST_SECONDS + RELEASE_DELAY_SECONDS,
    "unset": UNSET_INDICATOR_SECONDS,
    **SPELL_DURATIONS,
}
EFFECT_ROWS = {
    "descent_fill": "a",
    "upward_spirals": "b",
    "channel_wave": "c",
    "charge": "d",
    "release_burst": "d",
    "opposed_pairs": "e",
    "unset": "e",
    "stack_drop": "f",
    "stack_unload": "f",
    "interactive_red_shots": "g",
    "twisting_ribbons": "h",
    "gathering_spell": "i",
}


def _hold_release_at(player):
    if player.started_at is None or not player.intervals:
        return None
    return player.started_at + player.intervals[-1][1] + player.config.debounce_s


def _next_effect_at(player):
    if player.current_key is None:
        return None
    key = player.current_key
    if key in ("a", "b", "c", "e", "h", "i"):
        delay = player.config.debounce_s + player.config.multi_press_s
        return player.started_at + player.intervals[-1][1] + delay
    if key == "g":
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
            duration = upward_spiral_effect_duration(
                len(staff.geometry.stem), staff.geometry, staff.effect_options)
            remaining = staff.effect_started_at + duration - now
        elif effect == "opposed_pairs":
            remaining = (staff.effect_started_at +
                         opposed_pair_effect_duration(staff.geometry,
                                                      staff.effect_options) - now)
        elif effect == "interactive_red_shots":
            remaining = None
        elif effect == "descent_fill":
            remaining = (staff.effect_started_at +
                         descent_fill_duration(staff.geometry,
                                               staff.effect_options) - now)
        elif effect == "release_burst":
            remaining = (staff.effect_started_at +
                         release_burst_duration(staff.geometry,
                                                staff.effect_options) - now)
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
    return key, None if remaining is None else int(max(0.0, remaining) + 0.5)


def format_status(staff, player, now, report_text=None):
    key, seconds = status_snapshot(staff, player, now)
    entries = [(row_key, f"{code:<2}  {name}")
               for row_key, code, name in PATTERN_ROWS]
    width = max(len(entry) for _, entry in entries)
    lines = [f"Active pattern: {PATTERN_NAMES[key]}", "", "Cycle sequence:"]
    for row_key, entry in entries:
        if row_key == key:
            countdown = ("interactive: tap shoots, hold exits" if seconds is None
                         else f"{seconds:>2}s left")
            lines.append(f"> {entry:<{width}}  {countdown}")
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
