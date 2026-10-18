"""Button sequences and optional per-pattern behavior."""


# Omitted downward_acceleration means "off". Supported levels are low (2),
# med (4), and high (6) physical wraps per second squared. Upward motion may
# reverse under gravity by default; set allow_reversal=False to stop and fade.
BASE_PATTERN_OPTIONS = {
    "green_spiral": {"downward_acceleration": "med"},
    "green_channels": {},
    "bounce_vectors": {"downward_acceleration": "high"},
}


PATTERN_OPTIONS = {
    "quick": {"sequence": ("short",), "effect": "descent_fill"},
    "medium": {"sequence": ("medium",), "effect": "channel_wave",
               "extend_on_hold": True},
    "double_quick": {"sequence": ("short", "short"),
                     "effect": "upward_spirals", "extend_on_hold": True},
    "quick_medium": {"sequence": ("short", "medium"),
                     "effect": "opposed_pairs", "extend_on_hold": True},
    "medium_quick": {"sequence": ("medium", "short"),
                     "effect": "twisting_ribbons"},
    "double_medium": {"sequence": ("medium", "medium"),
                      "effect": "gathering_spell"},
    "short_short_short": {"sequence": ("short", "short", "short"),
                          "effect": "interactive_red_shots", "interactive": True},
    "short_short_medium": {"sequence": ("short", "short", "medium"), "effect": None},
    "short_medium_short": {"sequence": ("short", "medium", "short"), "effect": None},
    "short_medium_medium": {"sequence": ("short", "medium", "medium"), "effect": None},
    "medium_short_short": {"sequence": ("medium", "short", "short"), "effect": None},
    "medium_short_medium": {"sequence": ("medium", "short", "medium"), "effect": None},
    "medium_medium_short": {"sequence": ("medium", "medium", "short"), "effect": None},
    "medium_medium_medium": {"sequence": ("medium", "medium", "medium"), "effect": None},
    "hold": {"sequence": ("long",), "effect": "charge", "hold": True},
    "quick_hold": {"sequence": ("short", "long"), "effect": "stack_drop",
                   "hold": True},
}

PATTERNS_BY_SEQUENCE = {
    option["sequence"]: name for name, option in PATTERN_OPTIONS.items()
}
