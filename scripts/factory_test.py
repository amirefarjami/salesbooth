#!/usr/bin/env python3
"""CHIZ Booth — factory/field test mode.

Shows every button press on screen (with the mapped key) and lights the
LED strip in the matching color, so wiring can be verified before the
booth is assembled. ESC/Ctrl-Q quits.

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
from hardware.input import Action, build_action_map  # noqa: E402
from hardware.led import LEDStrip  # noqa: E402
from kiosk.theme import BTN_COLORS, PAL  # noqa: E402

LABELS = {
    Action.UP: "بالا", Action.DOWN: "پایین", Action.LEFT: "چپ",
    Action.RIGHT: "راست", Action.CONFIRM: "تأیید (قرمز)", Action.CANCEL: "لغو",
}
LED_COLOR = {
    Action.UP: (255, 180, 40), Action.DOWN: (60, 220, 120),
    Action.LEFT: (70, 100, 255), Action.RIGHT: (160, 40, 40),
    Action.CONFIRM: (255, 40, 40), Action.CANCEL: (200, 200, 220),
}


def main() -> int:
    pygame.init()
    cfg = load_config()
    screen = pygame.display.set_mode((cfg.screen_w, cfg.screen_h))
    pygame.display.set_caption("CHIZ factory test")
    fonts = pygame.font.SysFont(None, 34)
    fa_big = pygame.font.Font(None, 48)
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
                if act is not None:
                    pressed.insert(0, (LABELS[act], f"key={ev.key}"))
                    leds._set_all(LED_COLOR[act])
                    pressed = pressed[:8]
                elif ev.key == pygame.K_q and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    running = False
                elif ev.key == pygame.K_ESCAPE:
                    running = False

        screen.fill(PAL["bg_deep"])
        title = fa_big.render(shape("تست سیم‌کشی باجه"), True, PAL["amber"])
        screen.blit(title, title.get_rect(midtop=(cfg.screen_w // 2, 30)))
        y = 120
        for label, key in pressed:
            row = fonts.render(f"{label}  {key}", True, PAL["cream"])
            screen.blit(row, (60, y))
            y += 46
        hint = fonts.render("ESC=quit", True, PAL["gray"])
        screen.blit(hint, (cfg.screen_w - 130, cfg.screen_h - 44))
        pygame.display.flip()
        clock.tick(30)
    leds.cleanup()
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
