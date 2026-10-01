"""CHIZ Booth — main kiosk application (Pygame-CE)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

from core.booth import Booth  # noqa: E402
from core.config import load_config  # noqa: E402
from core.fonts import FontPack  # noqa: E402
from core.orders import OrderError  # noqa: E402
from core.payment import provider_from_config  # noqa: E402
from hardware.input import KeyboardInput  # noqa: E402
from hardware.led import LEDStrip  # noqa: E402
from hardware.lock import DoorLock  # noqa: E402
from kiosk.pay_screen import DoorScreen, PayScreen  # noqa: E402
from kiosk.screens import AttractScreen, ConfirmScreen, GridScreen  # noqa: E402
from kiosk.sound import SoundEngine  # noqa: E402
from kiosk.theme import K, Theme, plate  # noqa: E402


class KioskApp:
    def __init__(self, config=None, headless: bool = False) -> None:
        self.cfg = config or load_config()
        self.headless = headless
        self.booth = Booth.open(self.cfg)
        # orders left pending by a crash / power cut still hold stock
        self.booth.orders.expire_stale(self.cfg.order_ttl_minutes)
        self.provider = provider_from_config(self.booth)

        if not headless:
            flags = pygame.FULLSCREEN | pygame.SCALED if self.cfg.fullscreen else 0
            self.screen = pygame.display.set_mode(
                (self.cfg.screen_w, self.cfg.screen_h), flags)
            pygame.display.set_caption("CHIZ Booth")
            pygame.display.set_icon(self._make_icon())
            if self.cfg.fullscreen:
                pygame.mouse.set_visible(False)
        else:
            self.screen = pygame.Surface((self.cfg.screen_w, self.cfg.screen_h))

        self.fonts = FontPack()
        self.theme = Theme(self.fonts, self.cfg.screen_w, self.cfg.screen_h)
        if self.cfg.scanlines and not headless:
            self.theme.build_scanlines(self.cfg.scanline_strength)

        self.sounds = SoundEngine(self.cfg)
        self.sounds.load()
        self.led = LEDStrip(self.cfg)
        self.lock = DoorLock(self.cfg)
        self.lock.lock()

        self.input = KeyboardInput(self.cfg)
        self.idle_ms = 0
        self.pending_total = 0
        self._screens = {
            "attract": AttractScreen(self),
            "grid": GridScreen(self),
        }
        self.current_name = "attract"
        self.current = self._screens["attract"]
        self.current.enter()
        self.running = True
        self.sounds.play("boot")

    # -- navigation used by screens -----------------------------------

    def _show(self, screen, name: str) -> None:
        self.current_name = name
        self.current = screen
        self.idle_ms = 0
        screen.enter()

    def go(self, name: str):
        screen = self._screens[name]
        if name == "grid":
            screen.reload_products()
        elif name == "attract":
            self._screens["grid"].reset()
            self.booth.orders.expire_stale(self.cfg.order_ttl_minutes)
        self._show(screen, name)
        return screen

    def open_confirm(self, product) -> None:
        self._show(ConfirmScreen(self, product), "confirm")

    def create_order(self, product, qty: int) -> bool:
        """Reserve stock and move to payment. False when it can't be sold."""
        try:
            owi = self.booth.orders.create(product.id, qty=qty,
                                           provider=self.provider.name)
        except OrderError:
            return False
        self.pending_total = owi.order.total_toman
        self._show(PayScreen(self, owi.order.id), "pay")
        return True

    def open_door(self, order_id: int, code: str) -> None:
        self._show(DoorScreen(self, order_id, code), "door")

    def _make_icon(self) -> pygame.Surface:
        s = pygame.Surface((32, 32))
        s.fill(K["alt"])
        plate(s, pygame.Rect(4, 6, 22, 18), K["hi"], shadow=3, outline=2)
        pygame.draw.circle(s, K["danger"], (16, 27), 4)
        return s

    # -- main loop ---------------------------------------------------

    def step(self, dt_ms: int, actions=()) -> None:
        """One frame: input → idle timeout → tick → LEDs → draw."""
        for act in actions:
            self.idle_ms = 0
            value = act.value if hasattr(act, "value") else str(act)
            self.current.handle(value)
        if getattr(self.current, "idle_timeout", False):
            self.idle_ms += dt_ms
            if self.idle_ms > self.cfg.attract_timeout_s * 1000:
                self.go("attract")
        self.current.tick(dt_ms)
        self.led.tick()
        self.current.draw(self.screen)
        if self.theme.scanlines is not None and not self.headless:
            self.screen.blit(self.theme.scanlines, (0, 0))

    def run(self) -> int:
        clock = pygame.time.Clock()
        while self.running:
            dt_ms = min(clock.tick(self.cfg.fps), 250)
            actions = self.input.pump()
            if self.input.quit_requested:
                break
            self.step(dt_ms, actions)
            pygame.display.flip()
        self.shutdown()
        return 0

    def shutdown(self) -> None:
        # never leave the showcase unlocked or a reservation dangling
        self.lock.cleanup()
        if isinstance(self.current, PayScreen) and not self.current.done:
            try:
                self.booth.orders.cancel(self.current.order_id, restock=True)
            except Exception:
                pass
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
