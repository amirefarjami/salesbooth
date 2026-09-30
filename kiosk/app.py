"""CHIZ Booth — main kiosk application (Pygame-CE)."""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

from core.config import load_config  # noqa: E402
from core.fa import shape  # noqa: E402
from core.payment import provider_from_config  # noqa: E402
from core.booth import Booth  # noqa: E402
from core.fonts import FontPack  # noqa: E402
from hardware.input import KeyboardInput  # noqa: E402
from hardware.led import LEDStrip  # noqa: E402
from kiosk.pay_screen import PayScreen  # noqa: E402
from kiosk.screens import AttractScreen, ConfirmScreen, GridScreen  # noqa: E402
from kiosk.sound import SoundEngine  # noqa: E402
from kiosk.theme import PAL, Theme  # noqa: E402


class KioskApp:
    def __init__(self, config=None, headless: bool = False) -> None:
        self.cfg = config or load_config()
        self.headless = headless
        self.booth = Booth.open(self.cfg)
        self.provider = provider_from_config(self.booth)

        if not headless:
            flags = pygame.FULLSCREEN | pygame.SCALED if self.cfg.fullscreen else 0
            self.screen = pygame.display.set_mode(
                (self.cfg.screen_w, self.cfg.screen_h), flags)
            pygame.display.set_caption("CHIZ Booth")
            pygame.display.set_icon(self._make_icon())
        else:
            self.screen = pygame.Surface((self.cfg.screen_w, self.cfg.screen_h))

        self.fonts = FontPack()
        self.theme = Theme(self.fonts, self.cfg.screen_w, self.cfg.screen_h)
        if self.cfg.scanlines and not headless:
            self.theme.build_scanlines(self.cfg.scanline_strength)

        self.sounds = SoundEngine(self.cfg)
        self.sounds.load()
        self.led = LEDStrip(self.cfg)

        self.input = KeyboardInput(self.cfg)
        self.stars = [(random.randint(0, self.cfg.screen_w),
                       random.randint(0, self.cfg.screen_h),
                       random.uniform(0.3, 1.0)) for _ in range(60)]
        self.idle_ms = 0
        self.celebrate_until = 0
        self.pending_total = 0
        self._screens = {
            "attract": AttractScreen(self),
            "grid": GridScreen(self),
        }
        self.current_name = "attract"
        self.current = self._screens["attract"]
        self.running = True
        self.sounds.play("boot")

    # -- helpers used by screens ------------------------------------

    def go(self, name: str) -> None:
        if name == "grid" and isinstance(self._screens.get("grid"), GridScreen):
            self._screens["grid"].reload_products()
        self.current_name = name
        self.current = self._screens[name]
        self.idle_ms = 0

    def open_confirm(self, product) -> None:
        self.current = ConfirmScreen(self, product)

    def create_order(self, product, qty: int) -> None:
        try:
            owi = self.booth.orders.create(product.id, qty=qty,
                                           provider=self.provider.name)
        except Exception:
            self.sounds.play("error")
            return
        self.pending_total = owi.order.total_toman
        self.current = PayScreen(self, owi.order.id)

    def _make_icon(self) -> pygame.Surface:
        s = pygame.Surface((32, 32))
        s.fill(PAL["panel"])
        pygame.draw.rect(s, PAL["amber"], (6, 8, 20, 16), 3)
        pygame.draw.rect(s, PAL["red"], (12, 26, 8, 4))
        return s

    # -- main loop ---------------------------------------------------

    def run(self) -> int:
        clock = pygame.time.Clock()
        while self.running:
            dt_ms = clock.tick(self.cfg.fps)
            actions = self.input.pump()
            for act in actions:
                self.idle_ms = 0
                if self.current_name in ("attract", "grid") and hasattr(self.current, "handle"):
                    self.current.handle(act.value)
                elif isinstance(self.current, (ConfirmScreen, PayScreen)):
                    self.current.handle(act.value)
            if self.input.quit_requested:
                break

            # attract timeout
            if self.current_name in ("grid",) or isinstance(self.current, (ConfirmScreen, PayScreen)):
                self.idle_ms += dt_ms
                if self.idle_ms > self.cfg.attract_timeout_s * 1000:
                    self.go("attract")

            # tick active screen
            if isinstance(self.current, PayScreen):
                self.current.tick(dt_ms)
            elif hasattr(self.current, "tick"):
                self.current.tick(dt_ms)

            # LED idle effect on attract
            if self.current_name == "attract" and not isinstance(self.current, PayScreen):
                self.led.idle()

            self.current.draw(self.screen)
            if self.theme.scanlines is not None and not self.headless:
                self.screen.blit(self.theme.scanlines, (0, 0))
            pygame.display.flip()

            # paid celebration → grid refresh
            if isinstance(self.current, PayScreen) and self.current.done \
                    and self.current.status.value == "approved":
                pygame.time.wait(3500)
                self.go("grid")
        self.shutdown()
        return 0

    def shutdown(self) -> None:
        self.led.cleanup()
        self.sounds.shutdown()
        self.booth.close()
        pygame.quit()


def main() -> int:
    pygame.init()
    cfg = load_config()
    if "--fullscreen" in sys.argv:
        cfg.fullscreen = True
    app = KioskApp(cfg)
    try:
        return app.run()
    except KeyboardInterrupt:
        app.shutdown()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
