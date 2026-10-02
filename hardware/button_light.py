"""CHIZ Booth — the lamp inside the red confirm button.

It is the only lit button on the panel, so it says "red does something
now": steady on when red is the next step, blinking when it is the call to
action (attract screen, the pay ticket), off when red does nothing (e.g.
while waiting for the payment). Driven through a transistor/relay with
gpiozero; a simulator keeps the same API on the laptop.
"""
from __future__ import annotations

import time


class ButtonLight:
    def __init__(self, config) -> None:
        self.enabled = bool(getattr(config, "red_light_enabled", True))
        self.pin = int(getattr(config, "red_light_gpio", 22))
        self.mode = "off"
        self._dev = None
        self._lit = False
        if self.enabled:
            try:
                from gpiozero import OutputDevice  # type: ignore

                self._dev = OutputDevice(self.pin, initial_value=False)
            except Exception:
                self._dev = None

    @property
    def lit(self) -> bool:
        return self._lit

    def set(self, mode: str) -> None:
        """'off' | 'on' | 'blink' | 'fast' (the «insert coin» call)."""
        self.mode = mode if mode in ("off", "on", "blink", "fast") else "off"

    def tick(self) -> None:
        if self.mode == "blink":
            want = int(time.time() * 2.5) % 2 == 0
        elif self.mode == "fast":                  # small lamp: 3 blinks/s
            want = int(time.time() * 6) % 2 == 0
        else:
            want = self.mode == "on"
        if want != self._lit:
            self._lit = want
            if self._dev is not None:
                self._dev.on() if want else self._dev.off()

    def cleanup(self) -> None:
        self.mode = "off"
        self._lit = False
        if self._dev is not None:
            try:
                self._dev.off()
                self._dev.close()
            except Exception:
                pass
