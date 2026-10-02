"""Headless kiosk flow: product buttons → cart → method → pay → success →
door hand-over driven by the door sensor; red-button light; timeouts."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

pygame = pytest.importorskip("pygame")

from core.config import Config  # noqa: E402
from core.payment import PaymentCheck, PaymentStatus  # noqa: E402

NAMES = [("الف", 3), ("ب", 1), ("ج", 0), ("د", 2), ("ه", 5), ("و", 5), ("ز", 4)]


@pytest.fixture()
def app(tmp_path):
    from kiosk.app import KioskApp

    pygame.init()
    cfg = Config()
    cfg.db_path = tmp_path / "k.db"
    cfg.sound = False
    cfg.led_enabled = False
    cfg.lock_enabled = False
    cfg.red_light_enabled = False
    cfg.door_open_s = 6
    cfg.door_warn_s = 2
    cfg.door_wait_s = 10
    a = KioskApp(cfg, headless=True)
    for i, (name, stock) in enumerate(NAMES):
        a.booth.products.create(name, 10_000 * (i + 1), stock=stock, sort_order=i)
    yield a
    a.shutdown()


def stock(app, name):
    return next(p.stock for p in app.booth.products.list_all() if p.name == name)


def pid(app, name):
    return next(p.id for p in app.booth.products.list_all() if p.name == name)


def to_pay(app, method_slot="slot2", products=("slot1",)):
    app.go("grid")
    for s in products:
        app.step(16, [s])
    app.step(16, ["confirm"])          # → cart
    app.step(16, ["confirm"])          # → method
    app.step(16, [method_slot])        # 1 = QR, 2 = card reader
    app.step(16, ["confirm"])          # → pay
    return app.current


def approve(app, pay, monkeypatch):
    monkeypatch.setattr(pay.provider, "check",
                        lambda start: PaymentCheck(PaymentStatus.APPROVED, ref="t"))
    app.step(int(app.cfg.payment_poll_seconds * 1000) + 10)


# --- layout -----------------------------------------------------------------

def test_slot_numbers_left_column_odd(app):
    grid = app.go("grid")
    left = [c.slot for c in grid.cards if c.side == "left"]
    right = [c.slot for c in grid.cards if c.side == "right"]
    assert left == [1, 3, 5] and right == [2, 4, 6]
    by_slot = {c.slot: c.rect for c in grid.cards}
    assert by_slot[1].x < by_slot[2].x and by_slot[1].y == by_slot[2].y
    assert by_slot[1].y < by_slot[3].y < by_slot[5].y


def test_only_six_products_one_per_button(app):
    grid = app.go("grid")
    assert len(grid.cards) == 6        # the 7th product has no button


# --- cart -------------------------------------------------------------------

def test_product_button_adds_to_cart_and_shows_details(app):
    grid = app.go("grid")
    app.step(16, ["slot1"])
    app.step(16, ["slot1"])
    app.step(16, ["slot4"])
    assert app.cart == {pid(app, "الف"): 2, pid(app, "د"): 1}
    assert grid.focus == 3             # details of the last pressed product
    assert app.cart_total() == 2 * 10_000 + 40_000
    app.step(16)                       # draws with badges and the detail strip


def test_cannot_add_more_than_stock(app):
    app.go("grid")
    for _ in range(3):
        app.step(16, ["slot2"])        # «ب» has 1
    app.step(16, ["slot3"])            # «ج» is sold out
    assert app.cart == {pid(app, "ب"): 1}


def test_cancel_removes_last_added_then_leaves(app):
    app.go("grid")
    app.step(16, ["slot1"])
    app.step(16, ["slot4"])
    app.step(16, ["cancel"])
    assert app.cart == {pid(app, "الف"): 1}
    app.step(16, ["cancel"])
    assert app.cart == {} and app.current_name == "grid"
    app.step(16, ["cancel"])
    assert app.current_name == "attract"


def test_red_does_nothing_with_empty_cart(app):
    app.go("grid")
    app.step(16, ["confirm"])
    assert app.current_name == "grid"


def test_attract_product_button_adds_directly(app):
    app.step(16, ["slot1"])
    assert app.current_name == "grid" and app.cart == {pid(app, "الف"): 1}


# --- checkout ---------------------------------------------------------------

def test_method_needs_a_choice_and_cancel_goes_back(app):
    app.go("grid")
    app.step(16, ["slot1"])
    app.step(16, ["confirm"])
    app.step(16, ["confirm"])
    assert app.current_name == "method"
    app.step(16, ["confirm"])          # nothing chosen yet
    assert app.current_name == "method"
    app.step(16, ["slot5"])            # not a method button
    assert app.current.choice is None
    app.step(16, ["cancel"])
    assert app.current_name == "cart"
    app.step(16, ["cancel"])
    assert app.current_name == "grid" and app.cart  # cart kept


def test_card_payment_reserves_whole_cart(app):
    pay = to_pay(app, "slot2", ("slot1", "slot1", "slot4"))
    assert app.current_name == "pay" and pay.provider.name == "card"
    assert stock(app, "الف") == 1 and stock(app, "د") == 1
    order = app.booth.orders.get(pay.order_id)
    assert {(i.name, i.qty) for i in order.items} == {("الف", 2), ("د", 1)}
    assert order.order.provider == "card"


def test_qr_method_uses_zarinpal(app, monkeypatch):
    from core import zarinpal
    from core.payment import PaymentStart

    monkeypatch.setattr(zarinpal.ZarinpalProvider, "start",
                        lambda self, oid, amt, d: PaymentStart(
                            ok=True, provider="zarinpal", order_id=oid, amount=amt,
                            authority="A", qr_payload="https://x/A"))
    monkeypatch.setattr(zarinpal.ZarinpalProvider, "check",   # never hit the network
                        lambda self, start: PaymentCheck(PaymentStatus.PENDING))
    pay = to_pay(app, "slot1")
    assert pay.provider.name == "zarinpal"
    for _ in range(50):                # start() runs in a worker thread
        app.step(20)
        if pay.start is not None:
            break
    assert pay.start is not None and pay.start.ok


def test_cancel_payment_restocks_and_keeps_cart(app):
    to_pay(app)
    assert stock(app, "الف") == 2
    app.step(16, ["cancel"])
    assert app.current_name == "method"
    assert stock(app, "الف") == 3 and app.cart


def test_payment_timeout_restocks_and_retry(app):
    app.cfg.payment_timeout_s = 1
    pay = to_pay(app)
    app.step(1500)
    assert pay.status == PaymentStatus.DECLINED
    assert stock(app, "الف") == 3
    assert app.red.mode == "blink"     # red = try again
    app.step(16, ["confirm"])
    assert app.current is not pay and app.current_name == "pay"
    assert stock(app, "الف") == 2


def test_idle_timeout_never_kicks_out_a_payer(app):
    app.cfg.attract_timeout_s = 1
    to_pay(app)
    app.step(1500)
    assert app.current_name == "pay"


def test_idle_timeout_from_grid_clears_cart(app):
    app.cfg.attract_timeout_s = 1
    app.go("grid")
    app.step(16, ["slot1"])
    app.step(1500)
    assert app.current_name == "attract" and app.cart == {}


# --- after payment: success → door ------------------------------------------

def test_success_then_door_sensor_flow(app, monkeypatch):
    pay = to_pay(app)
    approve(app, pay, monkeypatch)
    assert app.current_name == "success" and app.cart == {}
    assert app.booth.orders.get(pay.order_id).order.status == "paid"
    app.step(3300)
    door = app.current
    assert app.current_name == "door" and door.state == "wait"
    assert app.lock.is_open            # coil on: the operator can open it

    app.door.set_sim(True)             # operator opens the showcase
    app.step(16)
    assert door.state == "open" and not app.lock.is_open   # latch armed
    app.step(4100)
    assert door.warning                # last 2 s: red + alarm
    app.step(2000)
    assert door.state == "overtime"    # still open after the countdown

    app.door.set_sim(False)            # door shut
    app.step(16)
    assert door.state == "done"
    assert app.booth.orders.get(pay.order_id).order.status == "delivered"
    app.step(3000)
    assert app.current_name == "attract"


def test_door_closed_early_finishes(app, monkeypatch):
    pay = to_pay(app)
    approve(app, pay, monkeypatch)
    app.step(3300)
    app.door.set_sim(True)
    app.step(1000)
    app.door.set_sim(False)
    app.step(16)
    assert app.current.state == "done"


def test_door_never_opened_relocks(app, monkeypatch):
    pay = to_pay(app)
    approve(app, pay, monkeypatch)
    app.step(3300)
    door = app.current
    app.step(10_100)
    assert door.state == "done" and not door.delivered
    assert not app.lock.is_open
    assert app.booth.orders.get(pay.order_id).order.status == "paid"


def test_without_sensor_countdown_starts_at_unlock(app, monkeypatch):
    app.door.enabled = False
    pay = to_pay(app)
    approve(app, pay, monkeypatch)
    app.step(3300)
    assert app.current.state == "open"
    app.step(6100)
    assert app.current.state == "done"


def test_door_sim_key_toggles_sensor(app):
    assert not app.door.is_open
    app.step(16, ["door_sim"])
    assert app.door.is_open


# --- red button light -------------------------------------------------------

def test_red_light_follows_what_red_does(app):
    app.step(16)
    assert app.red.mode == "blink"     # attract: press red
    app.go("grid")
    app.step(16)
    assert app.red.mode == "off"       # empty cart: red does nothing
    app.step(16, ["slot1"])
    assert app.red.mode == "blink"
    app.step(16, ["confirm"])
    app.step(16, ["confirm"])
    app.step(16)
    assert app.red.mode == "off"       # method screen, nothing chosen
    app.step(16, ["slot2"])
    assert app.red.mode == "blink"
    app.step(16, ["confirm"])
    assert app.red.mode == "off"       # waiting for the payment


# --- misc -------------------------------------------------------------------

def test_shutdown_cancels_pending_and_locks(app):
    to_pay(app)
    app.lock.unlock()
    app.shutdown()
    assert not app.lock.is_open
    from core.booth import Booth
    b = Booth.open(app.cfg)
    try:
        assert next(p.stock for p in b.products.list_all() if p.name == "الف") == 3
    finally:
        b.close()


def test_attract_cycles_brand_and_posters(app):
    a = app.current
    assert a.SLIDES[a.slide][0] == "brand"
    app.step(9_100)
    assert a.SLIDES[a.slide][0].startswith("poster")
    app.step(16)


def test_brand_font_never_renders_digits(app):
    """Sina Bold maps ۶→۱ and ۷→U; numbers must come from another face."""
    t = app.theme
    brand = t.fonts.brand("md")
    if brand is None:
        pytest.skip("SSINABD.TTF not installed")
    from core.fa import shape
    sina_h = brand.render(shape("پرداخت"), True, (0, 0, 0)).get_height()
    assert t.text("۶۰,۰۰۰", "md", face="display").get_height() != sina_h
    assert t.text("پرداخت", "md", face="display").get_height() == sina_h
