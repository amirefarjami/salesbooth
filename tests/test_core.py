"""Tests for core: config, db schema, products, orders, stats, formatting."""
from __future__ import annotations

import pytest

from core.config import Config, load_config
from core.db import connect, init_schema
from core.products import ProductRepo
from core.orders import OrderRepo, OrderError, OutOfStock
from core.stats import Stats
from core.format import format_toman, to_jalali, jalali_date


@pytest.fixture()
def db(tmp_path):
    conn = connect(tmp_path / "test.db")
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture()
def catalog(db):
    repo = ProductRepo(db)
    repo.create("دستگاه دستی بلی", 150000, stock=5, sort_order=1)
    repo.create("پک انرژی", 120000, stock=3, sort_order=2)
    repo.create("مارچوبه سرد", 80000, stock=0, sort_order=3)
    return repo


# ---------- config ----------

def test_config_defaults():
    c = Config()
    assert c.screen_w == 480 and c.screen_h == 800
    assert c.payment_provider == "manual"


def test_config_env_override(monkeypatch):
    monkeypatch.setenv("CHIZ_ADMIN_PORT", "9001")
    monkeypatch.setenv("CHIZ_FULLSCREEN", "true")
    c = load_config()
    assert c.admin_port == 9001
    assert c.fullscreen is True


# ---------- products ----------

def test_product_crud(catalog):
    p = catalog.list_active()[0]
    catalog.update(p.id, price_toman=999)
    assert catalog.get(p.id).price_toman == 999
    catalog.set_stock(p.id, 10)
    assert catalog.get(p.id).stock == 10
    assert catalog.adjust_stock(p.id, -2) == 8
    assert catalog.adjust_stock(p.id, -100) == 0  # clamped


def test_inactive_hidden_from_kiosk(catalog):
    p = catalog.list_active()[0]
    catalog.update(p.id, active=False)
    assert all(x.id != p.id for x in catalog.list_active())
    assert any(x.id == p.id for x in catalog.list_all())


# ---------- orders ----------

def test_order_create_reserves_stock(db, catalog):
    orders = OrderRepo(db)
    p = catalog.list_active()[0]
    owi = orders.create(p.id, qty=2)
    assert owi.order.status == "pending"
    assert owi.order.total_toman == p.price_toman * 2
    assert catalog.get(p.id).stock == 3


def test_order_out_of_stock_rejected(db, catalog):
    orders = OrderRepo(db)
    empty = [p for p in catalog.list_active() if p.stock == 0][0]
    with pytest.raises(OutOfStock):
        orders.create(empty.id, qty=1)


def test_order_pay_deliver_flow(db, catalog):
    orders = OrderRepo(db)
    p = catalog.list_active()[0]
    owi = orders.create(p.id, qty=1)
    oid = owi.order.id
    orders.mark_paid(oid, provider="manual", provider_ref="seller")
    assert orders.get(oid).order.status == "paid"
    orders.mark_delivered(oid)
    assert orders.get(oid).order.status == "delivered"


def test_double_pay_is_idempotent(db, catalog):
    orders = OrderRepo(db)
    p = catalog.list_active()[0]
    owi = orders.create(p.id)
    orders.mark_paid(owi.order.id, provider="manual")
    orders.mark_paid(owi.order.id, provider="manual")  # no raise
    assert orders.get(owi.order.id).order.status == "paid"


def test_cancel_restocks(db, catalog):
    orders = OrderRepo(db)
    p = catalog.list_active()[0]
    before = catalog.get(p.id).stock
    owi = orders.create(p.id, qty=2)
    orders.cancel(owi.order.id)
    assert catalog.get(p.id).stock == before
    assert orders.get(owi.order.id).order.status == "canceled"


def test_order_codes_unique_among_open(db, catalog):
    orders = OrderRepo(db)
    p = catalog.list_active()[0]
    seen = set()
    for _ in range(5):
        owi = orders.create(p.id)
        assert owi.order.code not in seen
        seen.add(owi.order.code)


# ---------- stats ----------

def test_stats_today_and_top(db, catalog):
    orders = OrderRepo(db)
    p = catalog.list_active()[0]
    owi = orders.create(p.id, qty=2)
    orders.mark_paid(owi.order.id, provider="manual")
    s = Stats(db)
    assert s.today()["orders"] == 1
    assert s.today()["revenue"] == p.price_toman * 2
    tops = s.top_products()
    assert tops and tops[0].name == p.name and tops[0].qty == 2
    assert s.daily() and s.daily()[0].orders == 1


# ---------- formatting ----------

def test_format_toman():
    assert format_toman(1234567) == "1,234,567 تومان"


def test_jalali_conversion():
    jy, jm, jd = to_jalali(2026, 9, 30)
    assert jy == 1405 and jm == 7 and jd == 8
    assert jalali_date("2026-09-30 14:03:00") == "1405/07/08"
