#!/usr/bin/env python3
"""CHIZ Booth — factory/field test mode.

Shows every button press on screen (with the mapped key) and lights the
LED strip in the matching color, so wiring can be verified before the
booth is assembled. Ctrl-Q quits (ESC is the cancel button, so it is shown, not quit).

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
from hardware.input import SLOT_ACTIONS, Action, build_action_map  # noqa: E402
from hardware.led import LEDStrip  # noqa: E402
from kiosk.theme import BTN_COLORS, PAL  # noqa: E402

LABELS = {
    Action.UP: "بالا", Action.DOWN: "پایین", Action.LEFT: "چپ",
    Action.RIGHT: "راست", Action.CONFIRM: "تأیید (قرمز)", Action.CANCEL: "انصراف",
    **{a: f"کالا {i}" for i, a in enumerate(SLOT_ACTIONS, start=1)},
}
LED_COLOR = {
    Action.UP: (255, 180, 40), Action.DOWN: (60, 220, 120),
    Action.LEFT: (70, 100, 255), Action.RIGHT: (160, 40, 40),
    Action.CONFIRM: (255, 40, 40), Action.CANCEL: (200, 200, 220),
    **{a: (8, 160, 170) for a in SLOT_ACTIONS},
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
    leds = LEDStrip(cfg)

    pressed: list[tuple[str, str]] = []
    clock = pygame.time.Clock()
    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                act = action_map.get(ev.key)
                if ev.key == pygame.K_q and ev.mod & pygame.KMOD_CTRL:
                    running = False
                elif act is not None:
                    pressed.insert(0, (LABELS[act], f"key={ev.key}"))
                    leds._set_all(LED_COLOR[act])
                    pressed = pressed[:8]

        screen.fill(PAL["bg_deep"])
        title = fa_big.render(shape("تست سیم‌کشی باجه"), True, PAL["amber"])
        screen.blit(title, title.get_rect(midtop=(cfg.screen_w // 2, 30)))
        y = 120
        for label, key in pressed:
            row = fonts.render(shape(f"{label}  {key}"), True, PAL["cream"])
            screen.blit(row, (60, y))
            y += 46
        hint = fonts.render("Ctrl+Q=quit", True, PAL["gray"])
        screen.blit(hint, (cfg.screen_w - 130, cfg.screen_h - 44))
        pygame.display.flip()
        clock.tick(30)
    leds.cleanup()
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
