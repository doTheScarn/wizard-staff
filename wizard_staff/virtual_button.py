"""Timed raw button signals for exercising the normal button interpreter."""

from collections import deque


VIRTUAL_GESTURES = (
    ("a", "dit"),
    ("b", "dit_dit"),
    ("c", "dah"),
    ("d", "hold"),
    ("e", "dit_dah (opposed pairs)"),
    ("f", "dit_hold"),
    ("g", "dit_dit_dit (interactive red shots)"),
    ("h", "dah_dit (twisting ribbons)"),
    ("i", "dah_dah (gathering spell)"),
    ("j", "dit_dit_dah (American flag)"),
    ("s", "interactive red shot"),
    ("x", "simulate a long press to exit interactive shots"),
)
CYCLE_GESTURES = VIRTUAL_GESTURES[:-2]
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
        self.base_number = None
        self.base_after_key = None
        self.base_selection = None
        self.announcements = []
        self.interrupt_requested = False
        self.interactive_cycle_started_at = None
        self.interactive_cycle_exiting = False

    def enqueue(self, text):
        key = text.strip().lower()
        if key not in LABELS and key not in ("1", "2", "3", "4"):
            return False
        self.pending.append(key)
        return True

    def _intervals_for(self, key):
        config = self.config
        dit = config.quick_press_max_s - (
            config.quick_press_max_s - config.debounce_s) / 4
        gap = (config.debounce_s + config.multi_press_s) / 2
        dah = (config.quick_press_max_s + config.long_press_s) / 2
        hold_seconds = HOLD_EFFECT_SECONDS + (1.0 if key == "f" else 0.0)
        hold = config.long_press_s + hold_seconds + config.debounce_s
        # The classifier starts its hold timer only after the press debounce.
        # Keep the raw signal asserted long enough to cross that threshold.
        exit_hold = config.long_press_s + 2 * config.debounce_s + 0.02
        if key == "a":
            return ((0.0, dit),)
        if key == "b":
            return ((0.0, dit), (dit + gap, 2 * dit + gap))
        if key == "c":
            return ((0.0, dah),)
        if key == "d":
            return ((0.0, hold),)
        if key == "e":
            return ((0.0, dit), (dit + gap, dit + gap + dah))
        if key == "g":
            return tuple((index * (dit + gap),
                          index * (dit + gap) + dit) for index in range(3))
        if key == "h":
            return ((0.0, dah), (dah + gap, dah + gap + dit))
        if key == "i":
            return ((0.0, dah), (dah + gap, 2 * dah + gap))
        if key == "j":
            return ((0.0, dit), (dit + gap, 2 * dit + gap),
                    (2 * (dit + gap), 2 * (dit + gap) + dah))
        if key == "s":
            return ((0.0, dit),)
        if key == "x":
            return ((0.0, exit_hold),)
        return ((0.0, dit), (dit + gap, dit + gap + hold))

    def _start(self, key, now):
        self.current_key = key
        self.base_until = None
        self.base_number = None
        self.base_after_key = None
        self.effect_seen = False
        self.started_at = now
        self.intervals = self._intervals_for(key)
        if key in ("s", "x"):
            # Allow the classifier to observe the debounced release before the
            # next queued command starts; shots can still overlap in flight.
            self.script_end = (self.intervals[-1][1] +
                               self.config.debounce_s +
                               2 / self.config.frame_rate)
        else:
            self.script_end = (self.intervals[-1][1] + self.config.multi_press_s +
                               self.config.debounce_s + 0.25)
        self.announcements.append(f"Virtual {key}: {LABELS[key]}")

    def tick(self, now, effect_active=False, interactive=False):
        """Return the raw button state to pass to WizardStaff.step()."""
        self.announcements = []
        self.base_selection = None
        self.interrupt_requested = False
        if self.mode == "input" and self.pending and self.pending[0] in ("1", "2", "3", "4"):
            self.current_key = None
            self.base_selection = int(self.pending.popleft())
            self.interrupt_requested = True
            self.announcements.append(f"Base pattern {self.base_selection}")
            return False
        if (self.mode == "input" and self.current_key is not None and self.pending
                and effect_active and self.effect_seen
                and not (interactive and self.pending[0] in ("s", "x"))):
            # A new pattern can interrupt a simulated hold or an active effect.
            # Interactive shot commands retain their independent tap timing.
            self.current_key = None
        if (self.mode == "input" and self.current_key is not None and
                now - self.started_at >= self.script_end):
            self.current_key = None
        if (self.mode == "cycle" and
                (self.interactive_cycle_exiting or
                 self.interactive_cycle_started_at is not None) and
                not interactive and not effect_active):
            self.interactive_cycle_started_at = None
            self.interactive_cycle_exiting = False
            self.base_until = now + BASE_INTERVAL_SECONDS
            self.base_after_key = "g"
            self.base_number = 1
            self.base_selection = 1
            self.announcements.append("Base pattern 1 for 5 seconds")
        if self.current_key is not None and effect_active:
            self.effect_seen = True
        if (self.current_key is not None and
                self.effect_seen and now - self.started_at >= self.script_end and
                (not effect_active or
                 (interactive and self.current_key in ("g", "s")))):
            finished_key = self.current_key
            self.current_key = None
            if self.mode == "cycle" and interactive and finished_key == "g":
                self.interactive_cycle_started_at = now
                self.announcements.append("Interactive shots: three taps, then hold to exit")
            elif self.mode == "cycle":
                self.base_until = now + BASE_INTERVAL_SECONDS
                self.base_after_key = finished_key
                self.base_number = (1 if finished_key == "g" else
                                    (next(index for index, (key, _) in enumerate(CYCLE_GESTURES)
                                          if key == finished_key) % 4) + 1)
                self.base_selection = self.base_number
                self.announcements.append(
                    f"Base pattern {self.base_number} for 5 seconds")
        if (self.mode == "cycle" and interactive and
                self.interactive_cycle_started_at is not None):
            elapsed = now - self.interactive_cycle_started_at
            dit = self.config.quick_press_max_s - (
                self.config.quick_press_max_s - self.config.debounce_s) / 4
            intervals = ((0.25, 0.25 + dit), (1.15, 1.15 + dit),
                         (2.5, 2.5 + dit), (3.9, 3.9 +
                          self.config.long_press_s + 2 * self.config.debounce_s +
                          0.02))
            if elapsed >= intervals[-1][1]:
                self.interactive_cycle_started_at = None
                self.interactive_cycle_exiting = True
                return False
            else:
                return any(start <= elapsed < end for start, end in intervals)

        if (self.current_key is None and
                (self.mode == "input" or not effect_active or interactive) and
                self.interactive_cycle_started_at is None and
                not self.interactive_cycle_exiting):
            if self.mode == "cycle":
                if self.base_until is None or now >= self.base_until:
                    key = CYCLE_GESTURES[self.next_cycle_index][0]
                    self.next_cycle_index = ((self.next_cycle_index + 1) %
                                             len(CYCLE_GESTURES))
                    self._start(key, now)
            elif self.pending:
                key = self.pending.popleft()
                if key in ("1", "2", "3", "4"):
                    self.base_selection = int(key)
                    self.announcements.append(f"Base pattern {key}")
                else:
                    self.interrupt_requested = not (interactive and key in ("s", "x"))
                    self._start(key, now)

        if self.current_key is None:
            return False
        elapsed = now - self.started_at
        return any(start <= elapsed < end for start, end in self.intervals)
