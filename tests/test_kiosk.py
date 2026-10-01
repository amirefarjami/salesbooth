"""Headless kiosk flow: slot buttons, confirm, pay, door lock, timeouts."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

pygame = pytest.importorskip("pygame")

from core.config import Config  # noqa: E402
from core.payment import PaymentCheck, PaymentStatus  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    from kiosk.app import KioskApp

    pygame.init()
    cfg = Config()
    cfg.db_path = tmp_path / "k.db"
    cfg.sound = False
    cfg.led_enabled = False
    cfg.lock_enabled = False
    cfg.door_open_s = 6
    cfg.door_warn_s = 2
    a = KioskApp(cfg, headless=True)
    for i, (name, stock) in enumerate([("الف", 3), ("ب", 1), ("ج", 0),
                                        ("د", 2), ("ه", 5), ("و", 5), ("ز", 4)]):
        a.booth.products.create(name, 10_000 * (i + 1), stock=stock, sort_order=i)
    yield a
    a.shutdown()


def stock(app, name):
    return next(p.stock for p in app.booth.products.list_all() if p.name == name)


def test_every_screen_draws(app):
    app.step(16)
    app.step(16, ["slot1"])           # attract → grid, slot 1 selected
    assert app.current_name == "grid"
    assert app.current.selected == 0
    app.step(16)


def test_slot_select_then_red_buys(app):
    app.go("grid")
    app.step(16, ["slot2"])
    assert app.current.selected == 1
    app.step(16, ["confirm"])
    assert app.current_name == "confirm"
    app.step(16, ["confirm"])
    assert app.current_name == "pay"
    assert stock(app, "ب") == 0       # reserved


def test_double_press_same_slot_opens_confirm(app):
    app.go("grid")
    app.step(16, ["slot1"])
    app.step(16, ["slot1"])
    assert app.current_name == "confirm"


def test_sold_out_slot_is_not_selectable(app):
    app.go("grid")
    app.step(16, ["slot3"])           # «ج» has no stock
    assert app.current.selected is None


def test_empty_slot_ignored_and_paging(app):
    grid = app.go("grid")
    assert grid.pages == 2
    app.step(16, ["down"])            # nothing selected → selects first card
    for _ in range(3):
        app.step(16, ["down"])
    assert grid.page == 1 and grid.selected == 6
    app.step(16, ["slot2"])           # page 2 has a single card
    assert grid.selected == 6


def test_cancel_clears_selection_then_leaves(app):
    app.go("grid")
    app.step(16, ["slot1"])
    app.step(16, ["cancel"])
    assert app.current_name == "grid" and app.current.selected is None
    app.step(16, ["cancel"])
    assert app.current_name == "attract"


def test_cancel_payment_restocks(app):
    app.go("grid")
    app.step(16, ["slot1"])
    app.step(16, ["confirm"])
    app.step(16, ["confirm"])
    assert stock(app, "الف") == 2
    app.step(16, ["cancel"])
    assert app.current_name == "grid"
    assert stock(app, "الف") == 3


def test_payment_timeout_restocks_and_retry(app):
    app.cfg.payment_timeout_s = 1
    app.go("grid")
    app.step(16, ["slot1"]); app.step(16, ["confirm"]); app.step(16, ["confirm"])
    app.step(1500)
    pay = app.current
    assert pay.status == PaymentStatus.DECLINED
    assert stock(app, "الف") == 3
    app.step(16, ["confirm"])         # retry → new pending order
    assert app.current is not pay and app.current_name == "pay"
    assert stock(app, "الف") == 2


def test_idle_timeout_never_kicks_out_a_payer(app):
    app.cfg.attract_timeout_s = 1
    app.go("grid")
    app.step(16, ["slot1"]); app.step(16, ["confirm"]); app.step(16, ["confirm"])
    app.step(1500)
    assert app.current_name == "pay"


def test_idle_timeout_from_grid(app):
    app.cfg.attract_timeout_s = 1
    app.go("grid")
    app.step(1500)
    assert app.current_name == "attract"


def test_paid_opens_door_then_relocks(app, monkeypatch):
    app.go("grid")
    app.step(16, ["slot1"]); app.step(16, ["confirm"]); app.step(16, ["confirm"])
    pay = app.current
    monkeypatch.setattr(app.provider, "check",
                        lambda start: PaymentCheck(PaymentStatus.APPROVED, ref="t"))
    app.step(int(app.cfg.payment_poll_seconds * 1000) + 10)
    assert app.current_name == "door"
    assert app.lock.is_open
    order = app.booth.orders.get(pay.order_id).order
    assert order.status == "paid"
    app.step(4100)
    assert app.current.warning
    app.step(2000)
    assert app.current_name == "attract"
    assert not app.lock.is_open
    assert app.booth.orders.get(pay.order_id).order.status == "delivered"


def test_shutdown_cancels_pending_and_locks(app):
    app.go("grid")
    app.step(16, ["slot1"]); app.step(16, ["confirm"]); app.step(16, ["confirm"])
    app.lock.unlock()
    app.shutdown()
    assert not app.lock.is_open
    # the fixture's shutdown runs again on a closed app; reopen DB to check
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
    app.step(16)                      # poster slide draws
    app.step(16, ["slot4"])           # any button still starts shopping
    assert app.current_name == "grid" and app.current.selected == 3


def test_brand_font_never_renders_digits(app):
    """Sina Bold maps ۶→۱ and ۷→U; numbers must come from another face."""
    t = app.theme
    brand = t.fonts.brand("md")
    if brand is None:
        pytest.skip("SSINABD.TTF not installed")
    from core.fa import shape
    sina_h = brand.render(shape("پرداخت"), True, (0, 0, 0)).get_height()
    price = t.text("۶۰,۰۰۰", "md", face="display")
    assert price.get_height() != sina_h                # not rendered by Sina
    word = t.text("پرداخت", "md", face="display")
    assert word.get_height() == sina_h                 # words still use Sina
