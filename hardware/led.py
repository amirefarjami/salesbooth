"""CHIZ Booth — WS2812B LED strip controller (with simulator fallback)."""
from __future__ import annotations

import colorsys
import math
import time


class LEDStrip:
    """Uniform API for real rpi_ws281x strip and a terminal simulator.

    Effects used by the kiosk:
      idle()      slow breathing Malibu blue (attract mode)
      navigate()  tiny tick flicker
      success()   fast green/amber celebration
      paywait()   chasing amber dots while waiting for payment
      error()     red pulse
    """

    def __init__(self, config) -> None:
        self.count = int(getattr(config, "led_count", 8))
        self.pin = int(getattr(config, "led_gpio", 18))
        self.brightness = int(getattr(config, "led_brightness", 160))
        self.enabled = bool(getattr(config, "led_enabled", True))
        self._strip = None
        self._sim_state = [(0, 0, 0)] * self.count
        self._mode = ("idle", time.time())
        if self.enabled:
            self._try_init_driver()

    def _try_init_driver(self) -> None:
        try:
            from rpi_ws281x import PixelStrip, Color  # type: ignore

            strip = PixelStrip(self.count, self.pin, 800000, 10, False,
                               self.brightness, 0)
            strip.begin()
            self._strip = strip
        except Exception:
            self._strip = None  # simulator mode (laptop / driver missing)

    # --- low level ---

    def _set_all(self, rgb) -> None:
        if self._strip is not None:
            from rpi_ws281x import Color  # type: ignore

            for i in range(self.count):
                self._strip.setPixelColor(i, Color(*rgb))
            self._strip.show()
        else:
            self._sim_state = [rgb] * self.count

    def _set_one(self, i: int, rgb) -> None:
        if self._strip is not None:
            from rpi_ws281x import Color  # type: ignore

            self._strip.setPixelColor(i, Color(*rgb))
            self._strip.show()
        else:
            self._sim_state[i] = rgb

    def show_state(self) -> None:
        """Simulator: print a one-line state change (driver: no-op)."""
        if self._strip is None and self.enabled:
            print("LED:", " ".join(f"{r:02x}{g:02x}{b:02x}"
                                   for r, g, b in self._sim_state))

    # --- effects ---

    def idle(self) -> None:
        t = time.time()
        v = 0.5 - 0.5 * math.cos(t * 1.2)
        base = (24, 40, 140)
        rgb = tuple(int(c * (0.25 + 0.75 * v)) for c in base)
        self._set_all(rgb)

    def navigate(self) -> None:
        self._set_all((70, 90, 220))
        time.sleep(0.03)
        self.idle()

    def success(self, duration: float = 2.5) -> None:
        end = time.time() + duration
        while time.time() < end:
            t = time.time()
            v = 0.5 - 0.5 * math.cos(t * 6)
            rgb = (int(60 * v), int(220 * v), int(90 * v))
            self._set_all(rgb)
            time.sleep(0.04)
        self.idle()

    def paywait(self) -> None:
        t = time.time()
        pos = int(t * 6) % max(1, self.count)
        for i in range(self.count):
            v = 1.0 if i == pos else (0.35 if (i + 1) % self.count == pos else 0.08)
            self._set_one(i, (int(255 * v), int(180 * v), int(40 * v)))

    def error(self, duration: float = 1.2) -> None:
        end = time.time() + duration
        while time.time() < end:
            v = 0.5 - 0.5 * math.cos(time.time() * 8)
            self._set_all((int(200 * v), 20, 20))
            time.sleep(0.04)
        self.idle()

    def off(self) -> None:
        self._set_all((0, 0, 0))

    def cleanup(self) -> None:
        self.off()
