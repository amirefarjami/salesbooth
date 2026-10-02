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
    cfg.door_extra_per_item_s = 5
    cfg.lights_enabled = True          # simulated MOSFETs (no GPIO here)
    cfg.door_warn_s = 2
    cfg.door_wait_s = 10
    cfg.pos_sim_approve_s = 0          # simulated reader never answers by itself
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


def settle(app, pay, ms=8000, real=False):
    """Step until the payment leaves the pay screen (card/QR run threaded).
    real=True also lets wall-clock time pass (the simulated reader uses it)."""
    import time
    for _ in range(ms // 50):
        app.step(50)
        if app.current is not pay:
            return
        if real:
            time.sleep(0.02)


def approve(app, pay, monkeypatch):
    monkeypatch.setattr(pay.provider, "check",
                        lambda start: PaymentCheck(PaymentStatus.APPROVED, ref="t"))
    settle(app, pay)


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


def test_only_red_leaves_attract(app):
    for key in ("slot1", "slot4", "cancel"):
        app.step(16, [key])
        assert app.current_name == "attract"
    app.step(16, ["confirm"])
    assert app.current_name == "grid" and app.cart == {}


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
    for _ in range(40):                # the reader starts on a worker thread
        app.step(50)
        if pay.status == PaymentStatus.DECLINED:
            break
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

def test_card_reader_approves_automatically(app):
    app.cfg.pos_sim_approve_s = 0.3    # the simulated buyer swipes after 0.3 s
    app._providers.clear()
    app.cfg.payment_poll_seconds = 0.1
    pay = to_pay(app, "slot2")
    for _ in range(100):               # begin() runs on the worker thread
        if pay.start is not None:
            break
        app.step(10)
    assert pay.provider.driver.amount_rial == 10_000 * 10   # amount went to the reader
    settle(app, pay, real=True)
    assert app.current_name == "success"
    assert app.booth.orders.get(pay.order_id).order.status == "paid"
    assert app.booth.orders.get(pay.order_id).order.provider == "card"


def test_cancel_aborts_sale_on_the_reader(app):
    pay = to_pay(app, "slot2")
    for _ in range(20):
        app.step(20)
    app.step(16, ["cancel"])
    assert pay.provider.driver.poll().status == "declined"   # sale aborted


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


# --- door timer, ring direction, warning lights ----------------------------

def _open_door(app, monkeypatch, products):
    pay = to_pay(app, "slot2", products)
    approve(app, pay, monkeypatch)
    app.step(3300)
    app.door.set_sim(True)
    app.step(16)
    return app.current


def test_door_timer_base_for_one_item(app, monkeypatch):
    door = _open_door(app, monkeypatch, ("slot1",))
    assert door.open_ms == 6_000                       # base only


def test_door_timer_adds_per_extra_item(app, monkeypatch):
    door = _open_door(app, monkeypatch, ("slot1", "slot1", "slot4"))   # 3 items
    assert door.open_ms == (6 + 5 * 2) * 1000


def test_default_door_timer_is_20s_plus_5_per_item():
    cfg = Config()
    assert cfg.door_open_s == 20 and cfg.door_extra_per_item_s == 5
    assert cfg.door_warn_s == 5


def test_last_seconds_dim_booth_and_light_red(app, monkeypatch):
    door = _open_door(app, monkeypatch, ("slot1",))
    app.step(500)
    assert app.lights.mode == "door" and app.lights.main == 1.0
    app.step(4000)                                      # 1.5 s left of 6 s
    assert door.warning and app.lights.mode == "warn"
    app.step(600)                                       # fade done
    assert app.lights.main == pytest.approx(app.cfg.booth_light_dim)
    assert app.lights.red == 1.0
    app.step(2000)                                      # overtime: still warning
    assert door.state == "overtime" and app.lights.mode == "warn"
    app.door.set_sim(False)
    app.step(16)
    app.step(600)
    assert door.state == "done"                          # «thanks» still lit fully
    assert app.lights.mode == "door" and app.lights.main == 1.0 and app.lights.red == 0.0


def test_ring_empties_from_the_left_counter_clockwise():
    from kiosk.theme import K, ring_progress
    surf = pygame.Surface((200, 200))
    surf.fill((0, 0, 0))
    ring_progress(surf, (100, 100), 80, 20, 0.75, (255, 0, 0))
    # ring band at radius 70: 10:30 (top-left) vs 1:30 (top-right)
    top_left, top_right = surf.get_at((50, 50))[:3], surf.get_at((150, 50))[:3]
    bottom = surf.get_at((100, 170))[:3]
    assert top_right == (255, 0, 0) and bottom == (255, 0, 0)   # still full
    assert top_left == K["paper_2"]     # emptied from 12 o'clock to the left (CCW)


# --- light scenes and effects (two MOSFETs) --------------------------------

def _levels(lights, mode, seconds, step_ms=20):
    """Run a scene alone; returns [(t, main, red)]."""
    lights.set(mode)
    out = []
    for i in range(int(seconds * 1000 / step_ms)):
        lights.tick(step_ms)
        out.append(((i + 1) * step_ms / 1000, lights.main, lights.red))
    return out


def _rises(samples, idx, thr=0.5):
    out, prev = [], samples[0][idx]
    for row in samples[1:]:
        if prev < thr <= row[idx]:
            out.append(row[0])
        prev = row[idx]
    return out


def _max_per_second(times):
    return max((sum(1 for u in times if t <= u < t + 1) for t in times), default=0)


def test_attract_breathes_60_to_100(app):
    lv = _levels(app.lights, "attract", 8)[25:]          # after the cross-fade
    mains = [m for _, m, _ in lv]
    assert min(mains) == pytest.approx(0.6, abs=0.02)
    assert max(mains) == pytest.approx(1.0, abs=0.02)


def test_attract_insert_coin_call_and_lamp(app):
    app.step(16)
    app.step(21_900)                                    # just before the call at 22 s
    assert app.lights.red == 0.0 and not app.lights.calling
    app.step(150)
    assert app.lights.calling and app.red.mode == "fast"
    rises = []
    prev = app.lights.red
    for _ in range(60):
        app.step(20)
        if prev < 0.5 <= app.lights.red:
            rises.append(app.lights.scene_t)
        prev = app.lights.red
    assert len(rises) == 1                              # the second of the two pulses
    app.step(2000)
    assert not app.lights.calling and app.red.mode == "blink"


def test_poweron_ramps_from_low(app):
    app.step(16)
    app.step(16, ["confirm"])
    assert app.lights.effect == "poweron" and app.lights.main < 0.5
    app.step(600)
    assert app.lights.effect is None
    assert app.lights.main == pytest.approx(app.cfg.booth_light_level, abs=0.02)


def test_product_blip_goes_brighter(app):
    app.go("grid")
    app.step(700)
    base = app.lights.main
    app.step(16, ["slot1"])
    assert app.lights.main > base + 0.08               # the blip
    app.step(300)
    assert app.lights.main == pytest.approx(base, abs=0.01)


def test_paywait_pulses_calmly(app):
    to_pay(app)
    mains = []
    for _ in range(150):
        app.step(20)
        mains.append(app.lights.main)
    assert app.lights.mode == "paywait"
    assert 0.55 < min(mains[25:]) < max(mains[25:]) <= 0.86


def test_celebrate_follows_fanfare_and_ends_full(app):
    from hardware.lights import FANFARE_NOTES
    lv = _levels(app.lights, "celebrate", 2.0, step_ms=5)
    peaks = [t for (t, m, _), (_, pm, _) in zip(lv[1:], lv) if m > pm + 0.05]
    for note in FANFARE_NOTES[1:]:                       # a pulse on every note
        assert any(abs(p - note) < 0.012 for p in peaks), note
    assert min(m for _, m, _ in lv) >= 0.69             # soft: never dark
    assert lv[-1][1:] == (1.0, 0.0)                     # full on the final chord


def test_fail_two_slow_red_pulses(app):
    app.lights.set("shop")
    for _ in range(40):
        app.lights.tick(20)
    app.lights.trigger("fail")
    samples = []
    for i in range(90):
        app.lights.tick(20)
        samples.append(((i + 1) * 0.02, app.lights.main, app.lights.red))
    assert len(_rises(samples, 2)) + 1 == 2              # on at t=0, again at 0.7 s
    assert min(m for _, m, _ in samples[:25]) <= 0.4      # main dips
    assert samples[-1][1] == pytest.approx(0.85, abs=0.01)


@pytest.mark.parametrize("mode", ["attract", "celebrate", "paywait", "warn", "door", "shop"])
def test_no_full_flashing_faster_than_3_per_second(app, mode):
    lv = _levels(app.lights, mode, 30 if mode == "attract" else 3, step_ms=5)
    assert _max_per_second(_rises(lv, 2)) <= 3            # red channel
    assert _max_per_second(_rises([(t, m, r) for t, m, r in lv], 1, thr=0.3)) <= 3
