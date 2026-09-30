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
