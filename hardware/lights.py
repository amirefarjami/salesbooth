"""CHIZ Booth — booth lighting on two MOSFET channels.

MOSFET 1 (`booth_light_gpio`) drives the booth's main light (PWM-dimmable).
MOSFET 2 (`warn_light_gpio`) drives the red warning lights.

    normal   main light full, red off
    warn     last seconds before the showcase re-locks (and any overtime):
             main light dims to `booth_light_dim`, red lights come on

Changes fade over ~0.4 s. gpiozero PWMOutputDevice works on Pi 3/4/5
(lgpio); without GPIO a simulator keeps the same API (prints changes).
"""
from __future__ import annotations


class BoothLights:
    FADE_PER_S = 2.5          # full swing in 0.4 s

    def __init__(self, config) -> None:
        self.enabled = bool(getattr(config, "lights_enabled", True))
        self.dim = float(getattr(config, "booth_light_dim", 0.15))
        self.mode = "normal"
        self.main = 1.0       # current output levels 0..1
        self.red = 0.0
        self._main_dev = self._red_dev = None
        if self.enabled:
            try:
                from gpiozero import PWMOutputDevice  # type: ignore

                self._main_dev = PWMOutputDevice(int(getattr(config, "booth_light_gpio", 12)),
                                                 initial_value=1.0, frequency=500)
                self._red_dev = PWMOutputDevice(int(getattr(config, "warn_light_gpio", 13)),
                                                initial_value=0.0, frequency=500)
            except Exception:
                self._main_dev = self._red_dev = None

    @property
    def simulated(self) -> bool:
        return self._main_dev is None

    def set(self, mode: str) -> None:
        mode = mode if mode in ("normal", "warn") else "normal"
        if mode != self.mode:
            self.mode = mode
            if self.enabled and self.simulated:
                print("LIGHTS:", "main dimmed + red ON" if mode == "warn" else "main full, red off")

    def tick(self, dt_ms: int) -> None:
        if not self.enabled:
            return
        want_main, want_red = (self.dim, 1.0) if self.mode == "warn" else (1.0, 0.0)
        step = self.FADE_PER_S * dt_ms / 1000.0
        self.main = _approach(self.main, want_main, step)
        self.red = _approach(self.red, want_red, step)
        if self._main_dev is not None:
            self._main_dev.value = self.main
            self._red_dev.value = self.red

    def cleanup(self) -> None:
        if self._main_dev is not None:
            try:
                self._main_dev.value = 1.0     # leave the booth lit, red off
                self._red_dev.value = 0.0
                self._main_dev.close()
                self._red_dev.close()
            except Exception:
                pass


def _approach(cur: float, target: float, step: float) -> float:
    if cur < target:
        return min(target, cur + step)
    return max(target, cur - step)
