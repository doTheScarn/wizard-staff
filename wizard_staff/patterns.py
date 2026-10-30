"""Button sequences and optional per-pattern behavior."""


# Omitted downward_acceleration means "off". Supported levels are low (6),
# med (10), and high (14) physical wraps per second squared. Upward motion may
# reverse under gravity by default; set allow_reversal=False to stop and fade.
BASE_PATTERN_OPTIONS = {
    "green_spiral": {"downward_acceleration": "low"},
    "green_channels": {},
    "bounce_vectors": {"downward_acceleration": "low"},
    "spring_streams": {},
}


PATTERN_OPTIONS = {
    "dit": {"sequence": ("dit",), "action": "next_base"},
    "dah": {"sequence": ("dah",), "effect": "channel_wave",
               "extend_on_hold": True},
    "dit_dit": {"sequence": ("dit", "dit"),
                     "effect": "upward_spirals", "extend_on_hold": True},
    "dit_dah": {"sequence": ("dit", "dah"),
                     "effect": "opposed_pairs", "extend_on_hold": True, "gamma": 1.0},
    "dah_dit": {"sequence": ("dah", "dit"),
                     "effect": "twisting_ribbons", "extend_on_hold": True},
    "dah_dah": {"sequence": ("dah", "dah"),
                      "effect": "gathering_spell", "upward_acceleration": "high"},
    "dit_dit_dit": {"sequence": ("dit", "dit", "dit"),
                          "effect": "interactive_red_shots", "interactive": True},
    "dit_dit_dah": {"sequence": ("dit", "dit", "dah"),
                           "effect": "american_flag", "extend_on_hold": True},
    "dit_dah_dit": {"sequence": ("dit", "dah", "dit"),
                        "effect": "descent_fill", "downward_acceleration": "low"},
    "dit_dah_dah": {"sequence": ("dit", "dah", "dah"), "effect": None},
    "dah_dit_dit": {"sequence": ("dah", "dit", "dit"), "effect": None},
    "dah_dit_dah": {"sequence": ("dah", "dit", "dah"), "effect": None},
    "dah_dah_dit": {"sequence": ("dah", "dah", "dit"), "effect": None},
    "dah_dah_dah": {"sequence": ("dah", "dah", "dah"), "effect": None},
    "hold": {"sequence": ("hold",), "effect": "charge", "hold": True},
    "dit_hold": {"sequence": ("dit", "hold"), "effect": "stack_drop",
                   "hold": True},
}

PATTERNS_BY_SEQUENCE = {
    option["sequence"]: name for name, option in PATTERN_OPTIONS.items()
}
