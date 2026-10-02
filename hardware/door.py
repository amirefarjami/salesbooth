"""CHIZ Booth — showcase door sensor (reed switch on a GPIO input).

The magnet closes the reed switch while the door is shut. With the pin's
pull-up, a shut door reads LOW and an open door reads HIGH (flip with
`door_open_when_high = false` for a normally-open wiring). Without GPIO
(laptop) a simulator keeps the same API; the kiosk toggles it with the
"d" key so the whole door flow can be tried on the simulator.
"""
from __future__ import annotations


class DoorSensor:
    def __init__(self, config) -> None:
        self.enabled = bool(getattr(config, "door_sensor_enabled", True))
        self.pin = int(getattr(config, "door_sensor_gpio", 27))
        self.open_when_high = bool(getattr(config, "door_open_when_high", True))
        self._dev = None
        self._sim_open = False
        if self.enabled:
            try:
                from gpiozero import DigitalInputDevice  # type: ignore

                self._dev = DigitalInputDevice(self.pin, pull_up=True, bounce_time=0.05)
            except Exception:
                self._dev = None

    @property
    def simulated(self) -> bool:
        return self._dev is None

    @property
    def is_open(self) -> bool:
        if self._dev is None:
            return self._sim_open
        high = bool(self._dev.value)
        return high if self.open_when_high else not high

    def toggle_sim(self) -> None:
        """Simulator only: flip the door state (the "d" key)."""
        if self._dev is None:
            self._sim_open = not self._sim_open
            print("DOOR:", "open" if self._sim_open else "closed")

    def set_sim(self, is_open: bool) -> None:
        if self._dev is None:
            self._sim_open = bool(is_open)

    def cleanup(self) -> None:
        if self._dev is not None:
            try:
                self._dev.close()
            except Exception:
                pass
