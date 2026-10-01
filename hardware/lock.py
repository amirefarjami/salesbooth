"""CHIZ Booth — showcase door lock (12V solenoid behind the glass, via relay).

After a confirmed payment the kiosk unlocks the glass door for
`door_open_s` seconds, then locks it again. On the Pi the relay is driven
with gpiozero (works on Pi 3/4/5 through lgpio); anywhere else, or when
the library is missing, a simulator keeps the same API and just logs.
The door is always re-locked on shutdown so a crash never leaves it open.
"""
from __future__ import annotations


class DoorLock:
    def __init__(self, config) -> None:
        self.enabled = bool(getattr(config, "lock_enabled", True))
        self.pin = int(getattr(config, "lock_gpio", 17))
        self.active_high = bool(getattr(config, "lock_active_high", True))
        self.is_open = False
        self._dev = None
        if self.enabled:
            try:
                from gpiozero import OutputDevice  # type: ignore

                self._dev = OutputDevice(self.pin, active_high=self.active_high,
                                         initial_value=False)
            except Exception:
                self._dev = None  # simulator (laptop / no GPIO access)

    @property
    def simulated(self) -> bool:
        return self._dev is None

    def unlock(self) -> None:
        self.is_open = True
        if self._dev is not None:
            self._dev.on()
        elif self.enabled:
            print("LOCK: open")

    def lock(self) -> None:
        was_open = self.is_open
        self.is_open = False
        if self._dev is not None:
            self._dev.off()
        elif self.enabled and was_open:
            print("LOCK: closed")

    def cleanup(self) -> None:
        self.lock()
        if self._dev is not None:
            try:
                self._dev.close()
            except Exception:
                pass
