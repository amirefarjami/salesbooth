"""Tests for the admin panel (auth + CRUD + reports)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from admin.app import app, get_booth, _state
from core.booth import Booth
from core.db import connect, init_schema


@pytest.fixture()
def client(tmp_path, monkeypatch):
    conn = connect(tmp_path / "admin_test.db", shared=True)
    init_schema(conn)
    booth = Booth.__new__(Booth)
    from core.config import Config
    cfg = Config()
    cfg.db_path = tmp_path / "admin_test.db"
    booth.config = cfg
    booth.conn = conn
    booth.products = __import__("core.products", fromlist=["ProductRepo"]).ProductRepo(conn)
    booth.orders = __import__("core.orders", fromlist=["OrderRepo"]).OrderRepo(conn)
    booth.stats = __import__("core.stats", fromlist=["Stats"]).Stats(conn)
    _state["booth"] = booth
    _state["tokens"] = set()
    with TestClient(app) as c:
        yield c
    conn.close()
    _state["booth"] = None


def _login(client, pin="1390"):
    r = client.post("/admin/login", data={"pin": pin}, follow_redirects=False)
    assert r.status_code == 303
    return r


def test_login_wrong_pin(client):
    r = client.post("/admin/login", data={"pin": "0000"})
    assert "اشتباه" in r.text


def test_dashboard_requires_login(client):
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/admin/login"


def test_product_crud_flow(client):
    _login(client)
    r = client.post("/admin/products/create", data={
        "name": "دستگاه بلی", "price_toman": 150000, "stock": 5,
        "sort_order": 1, "active": "on"}, follow_redirects=False)
    assert r.status_code == 303
    prods = client.get("/admin/products").text
    assert "دستگاه بلی" in prods

    pid = _state["booth"].products.list_all()[0].id
    r = client.post(f"/admin/products/{pid}/stock", data={"delta": "-2"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert _state["booth"].products.get(pid).stock == 3

    r = client.post(f"/admin/products/{pid}/delete", follow_redirects=False)
    assert r.status_code == 303
    assert _state["booth"].products.get(pid) is None


def test_manual_approval_flow(client):
    _login(client)
    booth = _state["booth"]
    p = booth.products.create("تست", 1000, stock=2)
    owi = booth.orders.create(p.id, qty=1)
    r = client.post(f"/admin/orders/{owi.order.id}/approve", follow_redirects=False)
    assert r.status_code == 303
    assert booth.orders.get(owi.order.id).order.status == "paid"
    client.post(f"/admin/orders/{owi.order.id}/deliver")
    assert booth.orders.get(owi.order.id).order.status == "delivered"


def test_open_orders_api(client):
    _login(client)
    booth = _state["booth"]
    p = booth.products.create("تست۲", 2000, stock=1)
    booth.orders.create(p.id)
    data = client.get("/admin/api/open-orders").json()
    assert len(data["orders"]) == 1
    assert data["orders"][0]["status"] == "pending"


def test_csv_export(client):
    _login(client)
    booth = _state["booth"]
    p = booth.products.create("تست۳", 3000, stock=1)
    owi = booth.orders.create(p.id)
    booth.orders.mark_paid(owi.order.id, provider="manual")
    r = client.get("/admin/reports/export.csv")
    assert r.status_code == 200
    assert "تست۳" in r.text


def test_logout_really_ends_session(client):
    _login(client)
    assert client.get("/admin", follow_redirects=False).status_code == 200
    client.post("/admin/logout", follow_redirects=False)
    r = client.get("/admin", follow_redirects=False)
    assert r.status_code == 303 and "/admin/login" in r.headers["location"]


def test_delete_sold_product_hides_it_instead(client):
    _login(client)
    booth = _state["booth"]
    pid = booth.products.create("فروخته‌شده", 1000, stock=3).id
    owi = booth.orders.create(pid)
    booth.orders.mark_paid(owi.order.id, provider="manual")
    r = client.post(f"/admin/products/{pid}/delete", follow_redirects=False)
    assert r.status_code == 303
    p = booth.products.get(pid)
    assert p is not None and not p.active and p.stock == 0   # history kept
    pid2 = booth.products.create("هرگز‌فروخته‌نشده", 1000, stock=1).id
    client.post(f"/admin/products/{pid2}/delete", follow_redirects=False)
    assert booth.products.get(pid2) is None


def test_csv_has_bom_for_excel(client):
    _login(client)
    r = client.get("/admin/reports/export.csv")
    assert r.content.startswith("﻿".encode("utf-8"))


def test_big_phone_photo_is_resized(client, tmp_path, monkeypatch):
    import io
    from PIL import Image
    import admin.app as admin_app
    monkeypatch.setattr(admin_app, "DATA_DIR", tmp_path)
    monkeypatch.setattr(admin_app, "PRODUCT_IMG_DIR", tmp_path / "img" / "products")
    _login(client)
    buf = io.BytesIO()
    Image.new("RGB", (3000, 4000), (200, 30, 30)).save(buf, "PNG")
    r = client.post("/admin/products/create",
                    data={"name": "عکس‌دار", "price_toman": "5000", "stock": "2",
                          "sort_order": "1", "active": "true"},
                    files={"image": ("photo.png", buf.getvalue(), "image/png")},
                    follow_redirects=False)
    assert r.status_code == 303
    p = next(p for p in _state["booth"].products.list_all() if p.name == "عکس‌دار")
    assert p.image_path and p.image_path.endswith(".jpg")
    with Image.open(tmp_path / p.image_path) as im:
        assert max(im.size) == 600


def test_products_page_shows_booth_button(client):
    _login(client)
    booth = _state["booth"]
    booth.products.create("اولی", 1000, stock=1, sort_order=1)
    booth.products.create("دومی", 1000, stock=1, sort_order=2)
    r = client.get("/admin/products")
    assert "دکمه‌ی ۱" in r.text and "دکمه‌ی ۲" in r.text


def test_real_connection_survives_thread_pool(tmp_path, monkeypatch):
    """Regression: one shared SQLite connection crashed on pool threads."""
    monkeypatch.setenv("CHIZ_DB_PATH", str(tmp_path / "real.db"))
    _state["booth"] = None
    _state["tokens"] = set()
    with TestClient(app) as c:
        assert c.post("/admin/login", data={"pin": "1390"},
                      follow_redirects=False).status_code == 303
        for _ in range(15):
            for path in ("/admin", "/admin/products", "/admin/orders",
                         "/admin/reports", "/admin/api/open-orders"):
                assert c.get(path).status_code == 200, path
