"""PCF8574 I2C button module: debounce, edge detection, missing module."""
from __future__ import annotations

from core.config import Config
from hardware.pcf8574 import PCF8574Buttons


class FakeBus:
    def __init__(self):
        self.level = 0xFF          # all released
        self.written = []

    def write_byte(self, addr, val):
        self.written.append((addr, val))

    def read_byte(self, addr):
        return self.level

    def close(self):
        pass


def make(level=0xFF):
    cfg = Config()
    cfg.buttons_source = "keyboard"          # don't touch real I2C in __init__
    b = PCF8574Buttons(cfg)
    b._bus = FakeBus()
    b._bus.level = level
    b._stable = b._last_raw = level
    b.ok = True
    return b


def press(b, pin):
    b._bus.level &= ~(1 << pin) & 0xFF


def release(b, pin):
    b._bus.level |= 1 << pin


def test_press_fires_once_after_two_reads():
    b = make()
    press(b, 0)
    assert b.poll() == []                    # first low read: not yet stable
    assert b.poll() == ["slot1"]             # confirmed
    assert b.poll() == []                    # held: no repeat
    release(b, 0)
    b.poll(); b.poll()
    press(b, 0)
    b.poll()
    assert b.poll() == ["slot1"]             # next press fires again


def test_bounce_is_ignored():
    b = make()
    press(b, 6)
    b.poll()
    release(b, 6)                            # contact bounced back up
    assert b.poll() == []
    assert b.poll() == []


def test_default_pin_map_and_custom():
    b = make()
    press(b, 6); press(b, 7)
    b.poll()
    assert sorted(b.poll()) == ["cancel", "confirm"]
    cfg = Config()
    cfg.pcf8574_pins = {"confirm": 0}
    c = PCF8574Buttons(cfg)
    assert c.pin_to_action[0] == "confirm"


def test_missing_module_is_silent():
    cfg = Config()
    cfg.buttons_source = "pcf8574"
    cfg.i2c_bus = 99                         # no such bus here
    b = PCF8574Buttons(cfg)
    assert not b.ok and b.error
    assert b.poll() == []


def test_pressed_pins_for_factory_test():
    b = make()
    press(b, 2); press(b, 5)
    assert b.pressed_pins() == [2, 5]


def test_hex_address_from_env(monkeypatch):
    from core.config import load_config
    monkeypatch.setenv("CHIZ_PCF8574_ADDRESS", "0x27")
    assert load_config().pcf8574_address == 0x27
