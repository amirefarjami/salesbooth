#!/usr/bin/env python3
"""Seed demo products (with generated pixel-art icons) and render the
kiosk screens to PNGs for the booth-monitor preview page."""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

OUT = ROOT / "data" / "preview"
IMG_DIR = ROOT / "data" / "img" / "products"

# ---------------------------------------------------------------- icons
from PIL import Image, ImageDraw  # noqa: E402

CREAM, AMBER, RED, GREEN, BLUE = (255, 240, 200), (255, 196, 60), (232, 48, 48), (60, 220, 120), (64, 96, 255)


def _bg(d, top=(36, 46, 105), bottom=(14, 18, 46)):
    for y in range(160):
        t = y / 159
        d.line([(0, y), (160, y)],
               fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))


def _star(d, cx, cy, r, fill):
    pts = []
    for i in range(10):
        rr = r if i % 2 == 0 else r * 0.45
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill)


def icon_tx(d):      # drone transmitter
    _bg(d)
    d.rounded_rectangle([28, 62, 132, 142], 10, fill=(52, 64, 140), outline=CREAM, width=3)
    d.ellipse([42, 92, 70, 120], fill=AMBER, outline=(120, 90, 20), width=2)
    d.ellipse([90, 92, 118, 120], fill=RED, outline=(120, 20, 20), width=2)
    d.line([(80, 26), (80, 62)], fill=CREAM, width=5)
    d.ellipse([73, 14, 87, 28], fill=RED)
    d.rectangle([46, 68, 114, 84], fill=(24, 30, 70))


def icon_battery(d):  # energy pack
    _bg(d, (30, 70, 60), (10, 26, 24))
    d.rounded_rectangle([48, 34, 112, 138], 8, fill=(40, 120, 80), outline=CREAM, width=3)
    d.rectangle([68, 22, 92, 34], fill=CREAM)
    d.polygon([(88, 52), (66, 92), (82, 92), (72, 122), (98, 80), (82, 80)], fill=AMBER)


def icon_roll(d):     # device roll / wheel
    _bg(d, (60, 40, 100), (20, 12, 40))
    d.ellipse([24, 24, 136, 136], fill=(70, 80, 160), outline=CREAM, width=4)
    d.ellipse([56, 56, 104, 104], fill=(20, 24, 56), outline=AMBER, width=3)
    d.ellipse([72, 72, 88, 88], fill=AMBER)
    for a in range(0, 360, 45):
        x = 80 + 44 * math.cos(math.radians(a))
        y = 80 + 44 * math.sin(math.radians(a))
        d.line([(80, 80), (x, y)], fill=(90, 100, 180), width=4)


def icon_box(d):      # combo pack
    _bg(d)
    d.polygon([(30, 62), (80, 42), (130, 62), (80, 82)], fill=(90, 104, 200))
    d.polygon([(30, 62), (80, 82), (80, 138), (30, 118)], fill=(52, 64, 140))
    d.polygon([(130, 62), (80, 82), (80, 138), (130, 118)], fill=(36, 44, 104))
    d.line([(80, 82), (80, 138)], fill=CREAM, width=2)
    _star(d, 80, 34, 14, AMBER)


def icon_set(d):      # full set
    _bg(d, (90, 60, 20), (30, 18, 8))
    d.rounded_rectangle([30, 66, 130, 136], 8, fill=(120, 84, 30), outline=CREAM, width=3)
    d.rectangle([30, 92, 130, 100], fill=(90, 62, 22))
    _star(d, 80, 52, 26, AMBER)


def icon_badge(d):    # small badge
    _bg(d)
    d.ellipse([30, 30, 130, 130], fill=(150, 40, 40), outline=CREAM, width=4)
    d.ellipse([44, 44, 116, 116], outline=AMBER, width=3)
    _star(d, 80, 80, 24, AMBER)
    d.rectangle([74, 18, 86, 32], fill=CREAM)


ICONS = {"tx": icon_tx, "battery": icon_battery, "roll": icon_roll,
         "box": icon_box, "set": icon_set, "badge": icon_badge}

DEMO = [
    ("دستگاه دستی بلی", 150_000, 5, "tx"),
    ("پک انرژی", 120_000, 8, "battery"),
    ("نورد دستگاه", 90_000, 6, "roll"),
    ("پک ترکیبی مالت", 200_000, 4, "box"),
    ("ست کامل چیز", 450_000, 2, "set"),
    ("پلاک کوچک چیز", 60_000, 10, "badge"),
]

JUNK = {"تست", "تست۲", "تست۳", "QR تست"}


def seed(booth) -> list:
    # retire old test junk (soft-delete keeps order history intact)
    for name in JUNK:
        for p in booth.products.list_all():
            if p.name == name and p.active:
                booth.products.update(p.id, active=False, stock=0)
    for i, (name, price, stock, key) in enumerate(DEMO, start=1):
        img_rel = f"img/products/demo_{key}.png"
        existing = next((p for p in booth.products.list_all() if p.name == name), None)
        if existing is None:
            booth.products.create(name, price, stock=stock, image_path=img_rel,
                                  sort_order=i)
        else:
            booth.products.update(existing.id, price_toman=price, stock=stock,
                                  image_path=img_rel, sort_order=i, active=True)
    return booth.products.list_active()


def make_icons() -> None:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    for key, fn in ICONS.items():
        img = Image.new("RGB", (160, 160))
        fn(ImageDraw.Draw(img))
        img.save(IMG_DIR / f"demo_{key}.png")


# ---------------------------------------------------------------- renders
def render(booth, products: list) -> None:
    import pygame
    from core.config import load_config
    from core.payment import PaymentStart
    from kiosk.app import KioskApp
    from kiosk.pay_screen import DoorScreen, PayScreen, _qr_surface

    pygame.init()
    cfg = load_config()
    cfg.sound = False
    cfg.led_enabled = False
    cfg.lock_enabled = False
    app = KioskApp(cfg, headless=True)
    OUT.mkdir(parents=True, exist_ok=True)

    def snap(name: str, ms: int = 16) -> None:
        app.step(ms)
        pygame.image.save(app.screen, str(OUT / f"{name}.png"))
        print("rendered", name)

    # 1 — attract: brand slide + the two poster slides
    snap("1-attract", 1500)
    for i, name in ((1, "1b-attract-poster-1"), (3, "1c-attract-poster-2")):
        app.current.slide, app.current.slide_ms = i, 0
        snap(name)
    app.current.slide = 0

    # 2 — grid, nothing picked yet
    app.go("grid")
    snap("2-grid")

    # 3 — grid, slot 2 pressed (left column, top)
    app.step(16, ["slot2"])
    snap("3-grid-selected", 400)

    # 4 — confirm
    app.open_confirm(products[1])
    snap("4-confirm")

    # 5 — payment with QR (zarinpal)
    p0 = products[0]
    owi = booth.orders.create(p0.id, provider="zarinpal")
    pay = PayScreen(app, owi.order.id)
    pay.start = PaymentStart(ok=True, provider="zarinpal", order_id=owi.order.id,
                             amount=owi.order.total_toman,
                             qr_payload="https://sandbox.zarinpal.com/pg/StartPay/DEMO1234",
                             authority="DEMO1234")
    pay.qr = _qr_surface(pay.start.qr_payload, 236)
    pay.t_ms = 40_000
    app.current = pay
    pay.draw(app.screen)
    pygame.image.save(app.screen, str(OUT / "5-pay-qr.png"))
    print("rendered 5-pay-qr")
    booth.orders.cancel(owi.order.id)

    # 6 — waiting for the seller (manual)
    owi2 = booth.orders.create(p0.id, provider="manual")
    app.pending_total = owi2.order.total_toman
    pay2 = PayScreen(app, owi2.order.id)
    app.current = pay2
    snap("6-pay-wait", 900)

    # 7 — declined
    owi3 = booth.orders.create(p0.id, provider="manual")
    pay3 = PayScreen(app, owi3.order.id)
    pay3._fail("زمان پرداخت تمام شد")
    app.current = pay3
    snap("7-pay-failed")

    # 8 — paid → showcase door open, countdown
    booth.orders.mark_paid(owi2.order.id, provider="manual", provider_ref="seller")
    door = DoorScreen(app, owi2.order.id, owi2.order.code)
    app.current = door
    snap("8-door-open", 6_000)

    # 9 — last seconds: red + alarm
    snap("9-door-closing", 11_000)

    app.shutdown()


def main() -> int:
    make_icons()
    from core.booth import Booth
    booth = Booth.open()
    try:
        products = seed(booth)
        render(booth, products)
    finally:
        booth.close()
    print("done →", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
