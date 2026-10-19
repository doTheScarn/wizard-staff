"""Advance the pattern schedule and dispatch classified button slots."""

from .button import ButtonInterpreter
from .config import StaffConfig
from .effects import (BASE_PATTERNS, InteractiveRedShots, StackingDropEffect,
                      base_vectors, manual_vectors)
from .geometry import StaffGeometry
from .patterns import BASE_PATTERN_OPTIONS, PATTERN_OPTIONS
from .vectors import render

EFFECT_FADE_SECONDS = 0.5

SLOTS = {name: option.get("effect") for name, option in PATTERN_OPTIONS.items()}
EXTENDABLE_EFFECTS = frozenset(
    option["effect"] for option in PATTERN_OPTIONS.values()
    if option.get("extend_on_hold"))
EFFECT_OPTIONS = {
    option["effect"]: option for option in PATTERN_OPTIONS.values()
    if option.get("effect") is not None
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
        self.extension_candidate = None
        self.extension_held = False
        self.extension_stop_at = None
        self.interactive_shots = None
        self.effect_options = {}
        self.fade_started_at = None
        self.fade_frame = None
        self.last_effect_frame = None

    def select_base_pattern(self, number, now):
        """Select one base pattern until another selection replaces it."""
        if not 1 <= number <= len(BASE_PATTERNS):
            raise ValueError("base pattern number out of range")
        self.cancel_effect(reset_button=True)
        self.selected_base = BASE_PATTERNS[number - 1]
        self.selected_base_started_at = now

    def cancel_effect(self, reset_button=False):
        """Immediately interrupt an effect for an explicit new selection."""
        self.effect = None
        self.effect_started_at = None
        self.stack_effect = None
        self.interactive_shots = None
        self.extension_candidate = None
        self.extension_held = False
        self.extension_stop_at = None
        self.effect_options = {}
        self.fade_started_at = None
        self.fade_frame = None
        self.last_effect_frame = None
        if reset_button:
            self.button = ButtonInterpreter(self.config)

    def _begin_fade(self, now):
        self.fade_started_at = now
        self.fade_frame = self.last_effect_frame or [(0, 0, 0)] * self.geometry.total_leds
        self.extension_candidate = None
        self.extension_held = False

    def _fade_step(self, now):
        fraction = (max(0.0, 1 - (now - self.fade_started_at) / EFFECT_FADE_SECONDS)
                    if any(any(rgb) for rgb in self.fade_frame) else 0.0)
        frame = [tuple(round(channel * fraction) for channel in rgb)
                 for rgb in self.fade_frame]
        if fraction == 0:
            self.cancel_effect()
        return frame

    def trigger(self, slot, now):
        if (slot == "interactive_shot" and self.effect == "interactive_red_shots"
                and self.fade_started_at is None):
            self.interactive_shots.shoot(now - self.effect_started_at)
            return
        if slot == "interactive_exit" and self.effect == "interactive_red_shots":
            self.interactive_shots.clear()
            self._begin_fade(now)
            return
        if slot in ("interactive_exit_release",):
            return
        if (slot in ("hold_start", "quick_hold_start") and
                self.extension_candidate is not None and
                self.extension_candidate == self.effect):
            self.extension_held = True
            return
        if slot in ("hold_release", "quick_hold_release") and self.extension_held:
            self.extension_stop_at = max(0.0, now - self.effect_started_at)
            self.extension_held = False
            self.extension_candidate = None
            return
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
        self.fade_started_at = None
        self.fade_frame = None
        self.last_effect_frame = None
        pattern_name = slot[:-6] if slot.endswith("_start") else slot
        self.effect = (SLOTS.get(pattern_name) or
                       (slot if slot in SLOTS.values() else "unset"))
        self.effect_options = EFFECT_OPTIONS.get(self.effect, {})
        if self.effect == "interactive_red_shots":
            self.interactive_shots = InteractiveRedShots(
                self.geometry, self.config.max_brightness,
                self.effect_options.get("downward_acceleration", "off"),
                self.effect_options.get("allow_reversal", True))
        else:
            self.interactive_shots = None
        self.effect_started_at = now
        self.extension_candidate = None
        self.extension_held = False
        self.extension_stop_at = None
        self.stack_effect = (StackingDropEffect(
                                 self.geometry,
                                 max_brightness=self.config.max_brightness,
                                 downward_acceleration_level=self.effect_options.get(
                                     "downward_acceleration", "off"),
                                 allow_reversal=self.effect_options.get(
                                     "allow_reversal", True))
                             if self.effect == "stack_drop" else None)

    def _render(self, vectors):
        return render(vectors, self.geometry.total_leds,
                      orb_leds=self.geometry.orb_leds,
                      baseline_shaft_brightness=self.config.baseline_shaft_brightness,
                      baseline_orb_brightness=self.config.baseline_orb_brightness,
                      orb_gain=self.config.orb_gain,
                      gamma=(self.effect_options.get("gamma", self.config.gamma)
                             if self.effect is not None else self.config.gamma))

    def step(self, now, pressed=False):
        if self.started_at is None:
            self.started_at = now
        if (self.fade_started_at is None and pressed and not self.button.candidate and
                self.effect in EXTENDABLE_EFFECTS and
                self.extension_stop_at is None):
            self.extension_candidate = self.effect
        interactive = (self.effect == "interactive_red_shots" and
                       self.fade_started_at is None)
        for event in self.button.update(pressed, now, interactive=interactive):
            self.trigger(event, now)
        if not self.button.stable and not self.button.candidate and not self.extension_held:
            self.extension_candidate = None
        if self.fade_started_at is not None:
            return self._fade_step(now)
        if self.effect is not None:
            if self.interactive_shots is not None:
                vectors, finished = self.interactive_shots.vectors(
                    now - self.effect_started_at), False
            elif self.stack_effect is not None:
                vectors, finished = self.stack_effect.vectors(now - self.effect_started_at)
            else:
                vectors, finished = manual_vectors(self.effect, now - self.effect_started_at,
                                                   self.geometry, self.charge_time,
                                                   self.config.max_brightness,
                                                   continuation=(self.extension_candidate is not None or
                                                                 self.extension_held),
                                                   stop_at=self.extension_stop_at,
                                                   options=self.effect_options)
            if not finished:
                frame = self._render(vectors)
                self.last_effect_frame = frame
                return frame
            self._begin_fade(now)
            return self._fade_step(now)

        if self.selected_base is not None:
            pattern_name = self.selected_base
            pattern_time = now - self.selected_base_started_at
        else:
            elapsed = now - self.started_at
            pattern_index = int(elapsed // self.config.base_pattern_s) % len(BASE_PATTERNS)
            pattern_name = BASE_PATTERNS[pattern_index]
            pattern_time = elapsed % self.config.base_pattern_s
        vectors = base_vectors(pattern_name, pattern_time,
                               self.geometry, self.config.max_brightness,
                               BASE_PATTERN_OPTIONS.get(pattern_name))
        return self._render(vectors)

