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
        import RPi.GPIO as GPIO

        pin = getattr(board, config.led_pin)
        order = getattr(neopixel, config.pixel_order)
        self.strip = neopixel.NeoPixel(pin, total_leds, brightness=config.brightness,
                                      auto_write=False, pixel_order=order)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(config.button_gpio, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        self.gpio = GPIO
        self.button_gpio = config.button_gpio
        self.color_mapping = config.color_mapping
        self.data_start = config.data_start
        self.total_leds = total_leds

    def is_pressed(self):
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
        self.gpio.cleanup(self.button_gpio)
        self.strip.deinit()

