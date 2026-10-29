"""CHIZ Booth - leave the lock and the lights OFF after the app exits.

gpiozero releases a pin on close() and the Pi then pulls it LOW, which turns an
active-LOW MOSFET/relay module ON. `pinctrl set <pin> op dh|dl` keeps the pin an
output at the OFF level even after this process is gone.
"""
from __future__ import annotations

import subprocess

# which pins to switch off on exit: (config pin name, config active_high name)
CHANNELS = (
    ("lock_gpio", "lock_active_high"),
    ("warn_light_gpio", "lights_active_high"),
    ("booth_light_gpio", "lights_active_high"),   # remove this line to leave the main light lit
)


def drive_off(config) -> None:
    for pin_name, ah_name in CHANNELS:
        pin = getattr(config, pin_name, None)
        if pin is None:
            continue
        off_level = "dl" if bool(getattr(config, ah_name, True)) else "dh"
        try:
            subprocess.run(["pinctrl", "set", str(int(pin)), "op", off_level],
                           check=False, timeout=3,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
