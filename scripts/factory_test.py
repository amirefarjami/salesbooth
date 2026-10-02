#!/usr/bin/env python3
"""CHIZ Booth — factory/field test mode.

Shows every button press on screen (with the mapped key), lights the
LED strip in the matching color, shows the door sensor (open/closed), and
on the red button lights its lamp, pulses the lock relay and switches the
booth lights to the warning look (MOSFET 1 dim, MOSFET 2 red) for 1 s — so
all wiring can be verified before the booth is assembled. Ctrl-Q quits (ESC is the cancel button, so it is shown, not quit).

Run on the Pi:   .venv/bin/python scripts/factory_test.py
Run on laptop:   SDL_VIDEODRIVER=dummy .venv/bin/python scripts/factory_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

from core.config import load_config  # noqa: E402
from core.fa import shape  # noqa: E402
from core.fonts import FontPack  # noqa: E402
from hardware.input import JOY_BASE, SLOT_ACTIONS, Action, build_action_map  # noqa: E402
from hardware.button_light import ButtonLight  # noqa: E402
from hardware.door import DoorSensor  # noqa: E402
from hardware.led import LEDStrip  # noqa: E402
from hardware.lights import BoothLights  # noqa: E402
from hardware.lock import DoorLock  # noqa: E402
from kiosk.theme import BTN_COLORS, PAL  # noqa: E402

LABELS = {
    Action.UP: "بالا", Action.DOWN: "پایین", Action.LEFT: "چپ",
    Action.RIGHT: "راست", Action.CONFIRM: "تأیید (قرمز)", Action.CANCEL: "انصراف",
    **{a: f"کالا {i}" for i, a in enumerate(SLOT_ACTIONS, start=1)},
    Action.DOOR_SIM: "در (شبیه‌ساز)",
}
LED_COLOR = {
    Action.UP: (255, 180, 40), Action.DOWN: (60, 220, 120),
    Action.LEFT: (70, 100, 255), Action.RIGHT: (160, 40, 40),
    Action.CONFIRM: (255, 40, 40), Action.CANCEL: (200, 200, 220),
    **{a: (8, 160, 170) for a in SLOT_ACTIONS},
    Action.DOOR_SIM: (255, 236, 200),
}


def main() -> int:
    pygame.init()
    cfg = load_config()
    screen = pygame.display.set_mode((cfg.screen_w, cfg.screen_h))
    pygame.display.set_caption("CHIZ factory test")
    fp = FontPack()             # Vazirmatn: the default font has no Persian
    fonts = fp.fa("md")
    fa_big = fp.fa("xl")
    action_map = build_action_map(cfg)
    pygame.joystick.init()
    pads = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
    from hardware.pcf8574 import PCF8574Buttons
    cfg.buttons_source = "pcf8574"           # always try the I2C module here
    panel = PCF8574Buttons(cfg)
    events: list = []
    shown_unmapped: set = set()
    leds = LEDStrip(cfg)
    door = DoorSensor(cfg)
    red = ButtonLight(cfg)
    lock = DoorLock(cfg)
    lights = BoothLights(cfg)
    red_until = 0

    pressed: list[tuple[str, str]] = []
    clock = pygame.time.Clock()
    running = True
    while running:
        for ev in pygame.event.get():
            code = name = None
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_q and ev.mod & pygame.KMOD_CTRL:
                    running = False
                    continue
                code, name = ev.key, pygame.key.name(ev.key)
            elif ev.type == pygame.JOYBUTTONDOWN:          # «Zero Delay» encoders
                code, name = JOY_BASE + ev.button, f"joy{ev.button}"
            elif ev.type == pygame.JOYDEVICEADDED:
                pads.append(pygame.joystick.Joystick(ev.device_index))
            if code is None:
                continue
            events.append((action_map.get(code), name))

        # PCF8574 I2C button module: debounced presses + which P-pin
        if panel.ok:
            for act_name in panel.poll():
                pin = next(p for p, a in panel.pin_to_action.items() if a == act_name)
                events.append((Action(act_name), f"P{pin}"))
            held = panel.pressed_pins()
            for pin in held:
                if pin not in panel.pin_to_action and pin not in shown_unmapped:
                    shown_unmapped.add(pin)
                    events.append((None, f"P{pin}"))
            shown_unmapped &= set(held)

        for act, name in events:
            if act is None:
                # unmapped: show what to put in booth.toml [booth.keymap]
                pressed.insert(0, ("نگاشت‌نشده", f'"{name}"'))
            else:
                if act == Action.DOOR_SIM:
                    door.toggle_sim()
                if act == Action.CONFIRM:      # red lamp + lock coil + warn lights, 1 s
                    red_until = pygame.time.get_ticks() + 1000
                    lock.unlock()
                pressed.insert(0, (LABELS.get(act, act.value), f'"{name}"'))
                leds._set_all(LED_COLOR.get(act, (255, 255, 255)))
            pressed = pressed[:8]
        events.clear()

        now = pygame.time.get_ticks()
        red.set("on" if now < red_until else "off")
        red.tick()
        lights.set("warn" if now < red_until else "door")     # MOSFET 1 dim + MOSFET 2 red
        lights.tick(clock.get_time())
        if now >= red_until and lock.is_open:
            lock.lock()

        screen.fill(PAL["bg_deep"])
        mod = (f"ماژول دکمه PCF8574: وصل (0x{panel.address:02x})" if panel.ok
               else "ماژول دکمه PCF8574: پیدا نشد (کیبورد کار می‌کند)")
        ms = fonts.render(shape(mod), True, PAL["green"] if panel.ok else PAL["gray"])
        screen.blit(ms, ms.get_rect(midtop=(cfg.screen_w // 2, 116)))
        state = fonts.render(shape("در ویترین: " + ("باز" if door.is_open else "بسته")),
                             True, PAL["amber"] if door.is_open else PAL["cream"])
        screen.blit(state, state.get_rect(midtop=(cfg.screen_w // 2, 80)))
        title = fa_big.render(shape("تست سیم‌کشی باجه"), True, PAL["amber"])
        screen.blit(title, title.get_rect(midtop=(cfg.screen_w // 2, 30)))
        y = 160
        for label, key in pressed:
            row = fonts.render(shape(f"{label}  {key}"), True, PAL["cream"])
            screen.blit(row, (60, y))
            y += 46
        hint = fonts.render("Ctrl+Q=quit", True, PAL["gray"])
        screen.blit(hint, (cfg.screen_w - 130, cfg.screen_h - 44))
        pygame.display.flip()
        clock.tick(30)
    leds.cleanup()
    red.cleanup()
    lights.cleanup()
    lock.cleanup()
    door.cleanup()
    panel.close()
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
