"""Debounce a momentary button and classify short press sequences."""


class ButtonInterpreter:
    def __init__(self, config):
        self.config = config
        self.candidate = False
        self.stable = False
        self.changed_at = 0.0
        self.pressed_at = None
        self.hold_started = False
        self.hold_event = None
        self.tap_count = 0
        self.last_tap_at = None

    def update(self, raw_pressed, now):
        events = []
        if raw_pressed != self.candidate:
            self.candidate = raw_pressed
            self.changed_at = now
        if self.candidate != self.stable and now - self.changed_at >= self.config.debounce_s:
            self.stable = self.candidate
            if self.stable:
                if (self.tap_count and
                        self.changed_at - self.last_tap_at >= self.config.multi_press_s):
                    events.append({1: "quick", 2: "double_quick"}.get(self.tap_count,
                                                                      "unset"))
                    self.tap_count = 0
                self.pressed_at = now
                self.hold_started = False
                self.hold_event = None
            else:
                duration = now - self.pressed_at
                if self.hold_started or duration >= self.config.long_press_s:
                    if not self.hold_started:
                        self.hold_event = ("quick_hold" if self.tap_count == 1
                                           else "hold")
                        events.append(self.hold_event + "_start")
                    events.append(self.hold_event + "_release")
                    self.tap_count = 0
                elif duration > self.config.quick_press_max_s:
                    if self.tap_count == 1:
                        events.append("quick_medium")
                    else:
                        events.append("medium")
                    self.tap_count = 0
                else:
                    self.tap_count += 1
                    self.last_tap_at = now
                self.pressed_at = None

        if self.stable and not self.hold_started and self.pressed_at is not None:
            if now - self.pressed_at >= self.config.long_press_s:
                self.hold_started = True
                self.hold_event = "quick_hold" if self.tap_count == 1 else "hold"
                self.tap_count = 0
                events.append(self.hold_event + "_start")

        if not self.stable and not self.candidate and self.tap_count:
            if now - self.last_tap_at >= self.config.multi_press_s:
                events.append({1: "quick", 2: "double_quick"}.get(self.tap_count, "unset"))
                self.tap_count = 0
        return events

