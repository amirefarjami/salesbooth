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
from core.payment import provider_for_method  # noqa: E402
from hardware.button_light import ButtonLight  # noqa: E402
from hardware.door import DoorSensor  # noqa: E402
from hardware.input import KeyboardInput  # noqa: E402
from hardware.led import LEDStrip  # noqa: E402
from hardware.lights import BoothLights  # noqa: E402
from hardware.lock import DoorLock  # noqa: E402
from kiosk.pay_screen import DoorScreen, PayScreen, SuccessScreen  # noqa: E402
from kiosk.screens import AttractScreen, CartScreen, GridScreen, MethodScreen  # noqa: E402
from kiosk.sound import SoundEngine  # noqa: E402
from kiosk.theme import K, Theme, plate  # noqa: E402


class KioskApp:
    def __init__(self, config=None, headless: bool = False) -> None:
        self.cfg = config or load_config()
        self.headless = headless
        self.booth = Booth.open(self.cfg)
        # orders left pending by a crash / power cut still hold stock
        self.booth.orders.expire_stale(self.cfg.order_ttl_minutes)
        self._providers: dict = {}

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
        self.door = DoorSensor(self.cfg)
        self.red = ButtonLight(self.cfg)
        self.lights = BoothLights(self.cfg)

        # the cart: {product_id: qty} + the order things were added in
        self.cart: dict[int, int] = {}
        self.cart_log: list[int] = []

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
            self.cart_clear()
            self._screens["grid"].reset()
            self.booth.orders.expire_stale(self.cfg.order_ttl_minutes)
        self._show(screen, name)
        return screen

    # -- cart -----------------------------------------------------------

    def cart_add(self, product_id: int) -> None:
        self.cart[product_id] = self.cart.get(product_id, 0) + 1
        self.cart_log.append(product_id)

    def cart_remove_last(self) -> int | None:
        if not self.cart_log:
            return None
        pid = self.cart_log.pop()
        self.cart[pid] -= 1
        if self.cart[pid] <= 0:
            del self.cart[pid]
        return pid

    def cart_clear(self) -> None:
        self.cart.clear()
        self.cart_log.clear()

    def cart_lines(self) -> list:
        """[(Product, qty)] in the order products were first added."""
        seen, out = set(), []
        for pid in self.cart_log:
            if pid in seen or pid not in self.cart:
                continue
            seen.add(pid)
            p = self.booth.products.get(pid)
            if p is not None:
                out.append((p, self.cart[pid]))
        return out

    def cart_count(self) -> int:
        return sum(self.cart.values())

    def cart_total(self) -> int:
        return sum(p.price_toman * q for p, q in self.cart_lines())

    # -- checkout ---------------------------------------------------------

    def open_cart(self) -> None:
        if not self.cart:
            self.go("grid")
            return
        self._show(CartScreen(self), "cart")

    def open_methods(self) -> None:
        if not self.cart:
            self.go("grid")
            return
        self._show(MethodScreen(self), "method")

    def provider_for(self, method: str):
        if method not in self._providers:
            self._providers[method] = provider_for_method(self.booth, method)
        return self._providers[method]

    def create_order(self, method: str) -> bool:
        """Reserve the whole cart and start paying. False if it can't be sold."""
        provider = self.provider_for(method)
        try:
            owi = self.booth.orders.create_cart(self.cart, provider=provider.name)
        except OrderError:
            return False
        self.pending_total = owi.order.total_toman
        self._show(PayScreen(self, owi.order.id, provider, method), "pay")
        return True

    def open_success(self, order_id: int, code: str) -> None:
        self.cart_clear()                      # paid: the cart is now an order
        self._show(SuccessScreen(self, order_id, code), "success")

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
            value = act.value if hasattr(act, "value") else str(act)
            if value == "door_sim":            # laptop: the "d" key is the door
                self.door.toggle_sim()
                continue
            self.idle_ms = 0
            self.current.handle(value)
        if getattr(self.current, "idle_timeout", False):
            self.idle_ms += dt_ms
            if self.idle_ms > self.cfg.attract_timeout_s * 1000:
                self.go("attract")
        self.current.tick(dt_ms)
        self.led.tick()
        self.lights.set(self.current.lights_mode())
        self.lights.tick(dt_ms)
        # the red button lamp joins the attract «insert coin» call
        self.red.set("fast" if self.lights.calling else self.current.red_light())
        self.red.tick()
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
        self.door.cleanup()
        self.red.cleanup()
        self.lights.cleanup()
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
