"""Timed raw button signals for exercising the normal button interpreter."""

from collections import deque


VIRTUAL_GESTURES = (
    ("a", "one quick press"),
    ("b", "two quick presses"),
    ("c", "medium press"),
    ("d", "long hold"),
    ("e", "quick press, then medium press (unset)"),
    ("f", "quick press, then long hold"),
)
KEY_ALIASES = {str(index): key for index, (key, _) in
               enumerate(VIRTUAL_GESTURES, start=1)}
LABELS = dict(VIRTUAL_GESTURES)
HOLD_EFFECT_SECONDS = 5.0
BASE_INTERVAL_SECONDS = 5.0


class VirtualButtonPlayer:
    """Play gestures as raw press/release intervals without blocking frames."""

    def __init__(self, config, mode):
        if mode not in ("cycle", "input"):
            raise ValueError("virtual button mode must be cycle or input")
        self.config = config
        self.mode = mode
        self.pending = deque()
        self.next_cycle_index = 0
        self.current_key = None
        self.started_at = None
        self.intervals = ()
        self.script_end = 0.0
        self.effect_seen = False
        self.base_until = None
        self.announcements = []

    def enqueue(self, text):
        key = text.strip().lower()
        key = KEY_ALIASES.get(key, key)
        if key not in LABELS:
            return False
        self.pending.append(key)
        return True

    def _intervals_for(self, key):
        config = self.config
        quick = config.quick_press_max_s - (
            config.quick_press_max_s - config.debounce_s) / 4
        gap = (config.debounce_s + config.multi_press_s) / 2
        medium = (config.quick_press_max_s + config.long_press_s) / 2
        hold = config.long_press_s + HOLD_EFFECT_SECONDS + config.debounce_s
        if key == "a":
            return ((0.0, quick),)
        if key == "b":
            return ((0.0, quick), (quick + gap, 2 * quick + gap))
        if key == "c":
            return ((0.0, medium),)
        if key == "d":
            return ((0.0, hold),)
        if key == "e":
            return ((0.0, quick), (quick + gap, quick + gap + medium))
        return ((0.0, quick), (quick + gap, quick + gap + hold))

    def _start(self, key, now):
        self.current_key = key
        self.effect_seen = False
        self.started_at = now
        self.intervals = self._intervals_for(key)
        self.script_end = (self.intervals[-1][1] + self.config.multi_press_s +
                           self.config.debounce_s + 0.25)
        self.announcements.append(f"Virtual {key}: {LABELS[key]}")

    def tick(self, now, effect_active=False):
        """Return the raw button state to pass to WizardStaff.step()."""
        self.announcements = []
        if self.current_key is not None and effect_active:
            self.effect_seen = True
        if (self.current_key is not None and
                self.effect_seen and now - self.started_at >= self.script_end and
                not effect_active):
            self.current_key = None
            if self.mode == "cycle":
                self.base_until = now + BASE_INTERVAL_SECONDS
                self.announcements.append("Base patterns for 5 seconds")

        if self.current_key is None and not effect_active:
            if self.mode == "cycle":
                if self.base_until is None or now >= self.base_until:
                    key = VIRTUAL_GESTURES[self.next_cycle_index][0]
                    self.next_cycle_index = ((self.next_cycle_index + 1) %
                                             len(VIRTUAL_GESTURES))
                    self._start(key, now)
            elif self.pending:
                self._start(self.pending.popleft(), now)

        if self.current_key is None:
            return False
        elapsed = now - self.started_at
        return any(start <= elapsed < end for start, end in self.intervals)
