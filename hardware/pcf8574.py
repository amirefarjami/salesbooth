"""CHIZ Booth — the 8 panel buttons through a PCF8574 I2C expander.

Wiring (docs/wiring.md): module VCC → Pi 3.3 V (pin 1, NOT 5 V: the module's
I2C pull-ups go to VCC), GND → pin 6, SDA → pin 3 (GPIO2), SCL → pin 5
(GPIO3). Each button: one leg to P0…P7, the other leg to GND. The chip's
inputs idle HIGH (weak pull-ups), a pressed button reads LOW.

The expander is polled every frame (an 8-bit read is ~0.3 ms at 100 kHz);
a press is accepted once the pin is LOW on two reads in a row (debounce)
and fires once per press. If the module is missing (laptop, wiring
fault) the reader stays silent and `ok` is False — the keyboard keeps
working either way.
"""
from __future__ import annotations

DEFAULT_PINS = {   # action → P-pin on the module
    "slot1": 0, "slot2": 1, "slot3": 2, "slot4": 3,
    "slot5": 4, "slot6": 5, "confirm": 6, "cancel": 7,
}


class PCF8574Buttons:
    def __init__(self, config) -> None:
        self.enabled = (getattr(config, "buttons_source", "keyboard") or "").lower() == "pcf8574"
        self.bus_no = int(getattr(config, "i2c_bus", 1))
        self.address = int(getattr(config, "pcf8574_address", 0x20))
        pins = dict(DEFAULT_PINS)
        pins.update({k: int(v) for k, v in (getattr(config, "pcf8574_pins", None) or {}).items()})
        self.pin_to_action = {p: a for a, p in pins.items() if 0 <= p <= 7}
        self.ok = False
        self.error = ""
        self._bus = None
        self._stable = 0xFF        # last debounced levels (1 = released)
        self._last_raw = 0xFF
        if self.enabled:
            self._open()

    def _open(self) -> None:
        try:
            from smbus2 import SMBus  # type: ignore

            self._bus = SMBus(self.bus_no)
            self._bus.write_byte(self.address, 0xFF)    # all pins = inputs (high)
            self._stable = self._last_raw = self._bus.read_byte(self.address)
            self.ok = True
        except Exception as e:  # missing library, I2C off, wrong address, no module
            self.error = f"PCF8574 @0x{self.address:02x} on i2c-{self.bus_no}: {e}"
            print("BUTTONS:", self.error)
            self._bus = None
            self.ok = False

    def read_raw(self) -> int | None:
        if self._bus is None:
            return None
        try:
            return self._bus.read_byte(self.address)
        except OSError:
            return None            # a glitch on the bus: skip this frame

    def poll(self) -> list[str]:
        """Action names pressed since the last call (debounced, edge-only)."""
        raw = self.read_raw()
        if raw is None:
            return []
        out = []
        settled = ~(raw ^ self._last_raw) & 0xFF        # same on two reads
        self._last_raw = raw
        new_stable = (self._stable & ~settled | raw & settled) & 0xFF
        pressed = self._stable & ~new_stable & 0xFF      # went 1 → 0
        self._stable = new_stable
        for pin in range(8):
            if pressed & (1 << pin) and pin in self.pin_to_action:
                out.append(self.pin_to_action[pin])
        return out

    def pressed_pins(self, raw: int | None = None) -> list[int]:
        """P-pins currently held down (factory test)."""
        raw = self.read_raw() if raw is None else raw
        if raw is None:
            return []
        return [p for p in range(8) if not raw & (1 << p)]

    def close(self) -> None:
        if self._bus is not None:
            try:
                self._bus.close()
            except Exception:
                pass
