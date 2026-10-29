"""CHIZ Booth - showcase door lock (12V solenoid behind the glass).

Idle: no current, bolt out = locked. unlock() energizes the coil. The coil
is cut again as soon as the door sensor reports the door open, or after
`door_wait_s` seconds if the door is never opened, so the bolt springs out
and latches when the door is closed. Without GPIO a simulator logs instead.
"""
from __future__ import annotations

import threading
import time

_SENSOR = None      # set by hardware.door.DoorSensor


class DoorLock:
    def __init__(self, config) -> None:
        self.enabled = bool(getattr(config, "lock_enabled", True))
        self.pin = int(getattr(config, "lock_gpio", 17))
        self.active_high = bool(getattr(config, "lock_active_high", True))
        self.wait_s = float(getattr(config, "door_wait_s", 15))
        self.is_open = False
        self._gen = 0
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

    def _coil(self, on: bool) -> None:
        if self._dev is not None:
            if on:
                self._dev.on()
            else:
                self._dev.off()
        elif self.enabled:
            print("LOCK: coil", "ON" if on else "OFF")

    def unlock(self) -> None:
        self.is_open = True
        self._gen += 1
        self._coil(True)
        threading.Thread(target=self._watch, args=(self._gen,), daemon=True).start()

    def _watch(self, gen: int) -> None:
        t0 = time.monotonic()
        while gen == self._gen:
            s = _SENSOR
            if s is not None and getattr(s, "enabled", False) and s.is_open:
                break                                   # door opened: cut current now
            if time.monotonic() - t0 >= self.wait_s:
                break                                   # never opened: lock again
            time.sleep(0.02)
        if gen == self._gen:
            self._coil(False)

    def lock(self) -> None:
        self._gen += 1
        self.is_open = False
        self._coil(False)

    def cleanup(self) -> None:
        self.lock()
        if self._dev is not None:
            try:
                self._dev.close()
            except Exception:
                pass
