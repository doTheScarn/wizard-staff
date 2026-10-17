"""Raspberry Pi adapters; imported only in live mode."""


def encode_color(color, mapping):
    if mapping == "tire_pixel":
        red, green, blue = color
        return green, red, blue
    return color


class PiHardware:
    def __init__(self, config, total_leds, enable_button=True):
        import board
        import neopixel

        pin = getattr(board, config.led_pin)
        order = getattr(neopixel, config.pixel_order)
        self.strip = neopixel.NeoPixel(pin, total_leds, brightness=config.brightness,
                                      auto_write=False, pixel_order=order)
        self.gpio = None
        if enable_button:
            import RPi.GPIO as GPIO

            GPIO.setmode(GPIO.BCM)
            GPIO.setup(config.button_gpio, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self.gpio = GPIO
        self.button_gpio = config.button_gpio
        self.color_mapping = config.color_mapping
        self.data_start = config.data_start
        self.total_leds = total_leds

    def is_pressed(self):
        if self.gpio is None:
            return False
        return self.gpio.input(self.button_gpio) == self.gpio.LOW

    def show(self, frame):
        indices = (range(self.total_leds - 1, -1, -1) if self.data_start == "bottom"
                   else range(self.total_leds))
        for index, color in zip(indices, frame):
            self.strip[index] = encode_color(color, self.color_mapping)
        self.strip.show()

    def close(self):
        self.strip.fill((0, 0, 0))
        self.strip.show()
        if self.gpio is not None:
            self.gpio.cleanup(self.button_gpio)
        self.strip.deinit()

