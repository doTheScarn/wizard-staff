"""Raspberry Pi adapters; imported only in live mode."""


def encode_color(color, mapping):
    if mapping == "tire_pixel":
        red, green, blue = color
        return green, red, blue
    return color


class PiHardware:
    def __init__(self, config, total_leds):
        import board
        import neopixel
        from gpiozero import Button

        pin = getattr(board, config.led_pin)
        order = getattr(neopixel, config.pixel_order)
        self.strip = neopixel.NeoPixel(pin, total_leds, brightness=config.brightness,
                                      auto_write=False, pixel_order=order)
        self.button = Button(config.button_gpio, pull_up=True, bounce_time=None)
        self.color_mapping = config.color_mapping

    def is_pressed(self):
        return self.button.is_pressed

    def show(self, frame):
        for index, color in enumerate(frame):
            self.strip[index] = encode_color(color, self.color_mapping)
        self.strip.show()

    def close(self):
        self.strip.fill((0, 0, 0))
        self.strip.show()
        self.button.close()
        self.strip.deinit()

