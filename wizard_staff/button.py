"""Debounce a momentary button and classify short press sequences."""


PATTERN_OPTIONS = {
    "quick": {"sequence": ("short",)},
    "medium": {"sequence": ("medium",)},
    "double_quick": {"sequence": ("short", "short")},
    "quick_medium": {"sequence": ("short", "medium")},
    "medium_quick": {"sequence": ("medium", "short")},
    "double_medium": {"sequence": ("medium", "medium")},
    "short_short_short": {"sequence": ("short", "short", "short")},
    "short_short_medium": {"sequence": ("short", "short", "medium")},
    "short_medium_short": {"sequence": ("short", "medium", "short")},
    "short_medium_medium": {"sequence": ("short", "medium", "medium")},
    "medium_short_short": {"sequence": ("medium", "short", "short")},
    "medium_short_medium": {"sequence": ("medium", "short", "medium")},
    "medium_medium_short": {"sequence": ("medium", "medium", "short")},
    "medium_medium_medium": {"sequence": ("medium", "medium", "medium")},
    "hold": {"sequence": ("long",), "hold": True},
    "quick_hold": {"sequence": ("short", "long"), "hold": True},
}
PATTERNS_BY_SEQUENCE = {
    option["sequence"]: name for name, option in PATTERN_OPTIONS.items()
}


class ButtonInterpreter:
    def __init__(self, config):
        self.config = config
        self.candidate = False
        self.stable = False
        self.changed_at = 0.0
        self.pressed_at = None
        self.hold_started = False
        self.hold_event = None
        self.pending_presses = []
        self.last_press_at = None

    def _resolve_pending(self):
        event = PATTERNS_BY_SEQUENCE.get(tuple(self.pending_presses), "unset")
        self.pending_presses.clear()
        self.last_press_at = None
        return event

    def update(self, raw_pressed, now):
        events = []
        if raw_pressed != self.candidate:
            self.candidate = raw_pressed
            self.changed_at = now
        if self.candidate != self.stable and now - self.changed_at >= self.config.debounce_s:
            self.stable = self.candidate
            if self.stable:
                if (self.pending_presses and
                        self.changed_at - self.last_press_at >= self.config.multi_press_s):
                    events.append(self._resolve_pending())
                self.pressed_at = now
                self.hold_started = False
                self.hold_event = None
            else:
                duration = now - self.pressed_at
                if self.hold_started or duration >= self.config.long_press_s:
                    if not self.hold_started:
                        self.hold_event = ("quick_hold" if self.pending_presses == ["short"]
                                           else "hold")
                        self.pending_presses.clear()
                        self.last_press_at = None
                        events.append(self.hold_event + "_start")
                    events.append(self.hold_event + "_release")
                else:
                    press_type = ("short" if duration <= self.config.quick_press_max_s
                                  else "medium")
                    self.pending_presses.append(press_type)
                    self.last_press_at = now
                    if len(self.pending_presses) == 3:
                        events.append(self._resolve_pending())
                self.pressed_at = None

        if self.stable and not self.hold_started and self.pressed_at is not None:
            if now - self.pressed_at >= self.config.long_press_s:
                self.hold_started = True
                self.hold_event = ("quick_hold" if self.pending_presses == ["short"]
                                   else "hold")
                self.pending_presses.clear()
                self.last_press_at = None
                events.append(self.hold_event + "_start")

        if (not self.stable and not self.candidate and self.pending_presses and
                now - self.last_press_at >= self.config.multi_press_s):
            events.append(self._resolve_pending())
        return events
