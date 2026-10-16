from dataclasses import dataclass


@dataclass(frozen=True)
class StaffConfig:
    orb_leds: int = 36
    stem_leds: int = 264
    leds_per_repeat: int = 4
    turns_per_repeat: int = 1
    frame_rate: float = 30.0
    brightness: float = 1.0
    baseline_shaft_brightness: float = 0.2
    baseline_orb_brightness: float = 0.2
    max_brightness: float = 0.5
    led_pin: str = "D18"
    data_start: str = "bottom"
    pixel_order: str = "RGB"
    color_mapping: str = "tire_pixel"
    button_gpio: int = 17
    debounce_s: float = 0.035
    multi_press_s: float = 0.38
    quick_press_max_s: float = 0.28
    long_press_s: float = 0.85
    base_pattern_s: float = 18.0

    def __post_init__(self):
        if self.orb_leds < 1 or self.stem_leds < 1:
            raise ValueError("orb_leds and stem_leds must be positive")
        if not 1 <= self.leds_per_repeat <= self.stem_leds:
            raise ValueError("leds_per_repeat must be between 1 and stem_leds")
        if self.turns_per_repeat not in (1, 2):
            raise ValueError("turns_per_repeat must be 1 or 2")
        if self.frame_rate <= 0 or not 0 < self.brightness <= 1:
            raise ValueError("frame_rate and hardware brightness must be positive")
        if not all(0 <= value <= 1 for value in
                   (self.baseline_shaft_brightness, self.baseline_orb_brightness,
                    self.max_brightness)):
            raise ValueError("pattern brightness values must be between 0 and 1")
        if not 0 < self.debounce_s < self.quick_press_max_s < self.long_press_s:
            raise ValueError("press thresholds must increase")
        if self.multi_press_s <= self.debounce_s or self.base_pattern_s <= 0:
            raise ValueError("invalid press window or base pattern duration")
        if self.color_mapping not in ("tire_pixel", "standard"):
            raise ValueError("color_mapping must be tire_pixel or standard")
        if self.data_start not in ("top", "bottom"):
            raise ValueError("data_start must be top or bottom")

