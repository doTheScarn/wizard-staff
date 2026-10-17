"""Advance the pattern schedule and dispatch classified button slots."""

from .button import ButtonInterpreter
from .config import StaffConfig
from .effects import BASE_PATTERNS, StackingDropEffect, base_vectors, manual_vectors
from .geometry import StaffGeometry
from .vectors import render


SLOTS = {
    "quick": "descent_fill",
    "double_quick": "upward_spirals",
    "medium": "channel_wave",
    "hold_start": "charge",
    "quick_hold_start": "stack_drop",
    "quick_medium": None,
}


class WizardStaff:
    def __init__(self, config=None):
        self.config = config or StaffConfig()
        self.geometry = StaffGeometry.from_config(self.config)
        self.button = ButtonInterpreter(self.config)
        self.started_at = None
        self.effect = None
        self.effect_started_at = None
        self.charge_time = 0.0
        self.stack_effect = None
        self.selected_base = None
        self.selected_base_started_at = None

    def select_base_pattern(self, number, now):
        """Select one base pattern until another selection replaces it."""
        if not 1 <= number <= len(BASE_PATTERNS):
            raise ValueError("base pattern number out of range")
        self.selected_base = BASE_PATTERNS[number - 1]
        self.selected_base_started_at = now

    def trigger(self, slot, now):
        if slot == "quick_hold_release":
            if self.effect == "stack_drop":
                self.stack_effect.release(now - self.effect_started_at)
                self.effect = "stack_unload"
            return
        if slot == "hold_release":
            if self.effect == "charge":
                self.charge_time = max(0.0, now - self.effect_started_at)
                self.effect = "release_burst"
                self.effect_started_at = now
            return
        self.effect = SLOTS.get(slot) or "unset"
        self.effect_started_at = now
        self.stack_effect = (StackingDropEffect(
                                 self.geometry,
                                 max_brightness=self.config.max_brightness)
                             if self.effect == "stack_drop" else None)

    def _render(self, vectors):
        return render(vectors, self.geometry.total_leds,
                      orb_leds=self.geometry.orb_leds,
                      baseline_shaft_brightness=self.config.baseline_shaft_brightness,
                      baseline_orb_brightness=self.config.baseline_orb_brightness)

    def step(self, now, pressed=False):
        if self.started_at is None:
            self.started_at = now
        for event in self.button.update(pressed, now):
            self.trigger(event, now)
        if self.effect is not None:
            if self.stack_effect is not None:
                vectors, finished = self.stack_effect.vectors(now - self.effect_started_at)
            else:
                vectors, finished = manual_vectors(self.effect, now - self.effect_started_at,
                                                   self.geometry, self.charge_time,
                                                   self.config.max_brightness)
            if not finished:
                return self._render(vectors)
            self.effect = None
            self.stack_effect = None

        if self.selected_base is not None:
            pattern_name = self.selected_base
            pattern_time = now - self.selected_base_started_at
        else:
            elapsed = now - self.started_at
            pattern_index = int(elapsed // self.config.base_pattern_s) % len(BASE_PATTERNS)
            pattern_name = BASE_PATTERNS[pattern_index]
            pattern_time = elapsed % self.config.base_pattern_s
        vectors = base_vectors(pattern_name, pattern_time,
                               self.geometry, self.config.max_brightness)
        return self._render(vectors)

