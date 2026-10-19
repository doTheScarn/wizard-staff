from dataclasses import dataclass

from .config import StaffConfig


@dataclass(frozen=True)
class StaffGeometry:
    orb_leds: int
    stem_leds: int
    leds_per_repeat: int
    turns_per_repeat: int = 1

    @classmethod
    def from_config(cls, config: StaffConfig):
        return cls(config.orb_leds, config.stem_leds,
                   config.leds_per_repeat, config.turns_per_repeat)

    @property
    def total_leds(self):
        return self.orb_leds + self.stem_leds

    @property
    def orb(self):
        return tuple(range(self.orb_leds))

    @property
    def stem(self):
        return tuple(range(self.orb_leds, self.total_leds))

    def channel(self, number):
        if not 0 <= number < self.leds_per_repeat:
            raise ValueError("channel out of range")
        return tuple(self.orb_leds + i for i in
                     range(number, self.stem_leds, self.leds_per_repeat))

    @property
    def channels(self):
        return tuple(self.channel(i) for i in range(self.leds_per_repeat))

    def spiral_channel(self, phase):
        """A spring along the physical helix, activating literally every third LED."""
        if not 0 <= phase < 3:
            raise ValueError("spiral phase must be 0, 1, or 2")
        return self.stem[phase::3]

    @property
    def spiral_channels(self):
        return tuple(self.spiral_channel(phase) for phase in range(3))

    @property
    def unset_indicator(self):
        return self.stem[:4]

