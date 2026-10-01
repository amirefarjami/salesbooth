"""CHIZ Booth — WS2812B LED strip controller (with simulator fallback).

Effects are frame-driven: screens pick a mode with `set_mode()` (or the
named helpers below) and the main loop calls `tick()` once per frame, so
an effect never blocks the UI. The palette follows the «کمیک قورمه» kit:
saffron for idle/attention, turquoise while waiting, pomegranate for
errors and the closing-door warning.
"""
from __future__ import annotations

import math
import time

SAFFRON = (255, 184, 0)
TURQUOISE = (8, 160, 170)
POMEGRANATE = (220, 20, 50)
GREEN = (30, 210, 90)
WARM = (255, 236, 200)


class LEDStrip:
    """Uniform API for a real rpi_ws281x strip and a silent simulator.

    Modes:
      idle      slow saffron breathing (attract / menu)
      paywait   turquoise chaser while waiting for payment
      success   fast green celebration
      door      steady warm light while the showcase door is open
      warn      dimmed light + blinking red (last seconds before re-lock)
      error     red pulse, falls back to idle after ~1 s
    """

    def __init__(self, config) -> None:
        self.count = int(getattr(config, "led_count", 8))
        self.pin = int(getattr(config, "led_gpio", 18))
        self.brightness = int(getattr(config, "led_brightness", 160))
        self.enabled = bool(getattr(config, "led_enabled", True))
        self._strip = None
        self._sim_state = [(0, 0, 0)] * self.count
        self.mode = "idle"
        self._mode_t0 = time.time()
        self._last_frame: list | None = None
        if self.enabled:
            self._try_init_driver()

    def _try_init_driver(self) -> None:
        try:
            from rpi_ws281x import PixelStrip  # type: ignore

            strip = PixelStrip(self.count, self.pin, 800000, 10, False,
                               self.brightness, 0)
            strip.begin()
            self._strip = strip
        except Exception:
            self._strip = None  # simulator mode (laptop / driver missing / no root)

    @property
    def simulated(self) -> bool:
        return self._strip is None

    # --- low level ---

    def _show(self, frame: list) -> None:
        if frame == self._last_frame:
            return
        self._last_frame = frame
        if self._strip is not None:
            from rpi_ws281x import Color  # type: ignore

            for i, rgb in enumerate(frame):
                self._strip.setPixelColor(i, Color(*rgb))
            self._strip.show()
        else:
            self._sim_state = list(frame)

    def _set_all(self, rgb) -> None:
        self._show([tuple(rgb)] * self.count)

    # --- modes ---

    def set_mode(self, mode: str) -> None:
        if mode != self.mode:
            self.mode = mode
            self._mode_t0 = time.time()

    def idle(self) -> None:
        self.set_mode("idle")

    def paywait(self) -> None:
        self.set_mode("paywait")

    def success(self) -> None:
        self.set_mode("success")

    def door(self) -> None:
        self.set_mode("door")

    def warn(self) -> None:
        self.set_mode("warn")

    def error(self) -> None:
        self.set_mode("error")

    def tick(self) -> None:
        """Render one frame of the current mode (call every UI frame)."""
        if not self.enabled:
            return
        now = time.time()
        age = now - self._mode_t0
        n = max(1, self.count)
        if self.mode == "error" and age > 1.2:
            self.set_mode("idle")
        if self.mode == "success" and age > 3.0:
            self.set_mode("door")

        if self.mode == "paywait":
            pos = int(now * 8) % n
            frame = []
            for i in range(n):
                v = 1.0 if i == pos else (0.35 if (i + 1) % n == pos else 0.06)
                frame.append(_scale(TURQUOISE, v))
            self._show(frame)
            return
        if self.mode == "success":
            v = 0.5 - 0.5 * math.cos(now * 9)
            self._set_all(_scale(GREEN, 0.3 + 0.7 * v))
        elif self.mode == "door":
            self._set_all(WARM)
        elif self.mode == "warn":
            on = int(now * 4) % 2 == 0
            self._set_all(POMEGRANATE if on else _scale(WARM, 0.12))
        elif self.mode == "error":
            v = 0.5 - 0.5 * math.cos(now * 10)
            self._set_all(_scale(POMEGRANATE, 0.25 + 0.75 * v))
        else:  # idle
            v = 0.5 - 0.5 * math.cos(now * 1.2)
            self._set_all(_scale(SAFFRON, 0.2 + 0.6 * v))

    def off(self) -> None:
        self._set_all((0, 0, 0))

    def cleanup(self) -> None:
        self.off()


def _scale(rgb, v: float) -> tuple:
    return tuple(int(c * v) for c in rgb)
