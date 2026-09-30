"""CHIZ Booth — local admin panel (FastAPI + Jinja2).

Runs on the Pi at port 8000; the seller reaches it from their phone via
the booth WiFi hotspot:  http://chiz.local:8000/admin
"""
from __future__ import annotations

import csv
import io
import secrets
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.booth import Booth
from core.config import DATA_DIR
from core.format import format_toman, jalali_date_time
from core.payment import PaymentStatus

PRODUCT_IMG_DIR = DATA_DIR / "img" / "products"
SESSION_COOKIE = "chiz_admin"
_MAX_IMG_BYTES = 5 * 1024 * 1024

app = FastAPI(title="CHIZ Booth Admin", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.filters["toman"] = lambda v: format_toman(v)
templates.env.filters["jalali"] = lambda v: jalali_date_time(v)

_state: dict = {"booth": None, "tokens": set()}


def get_booth() -> Booth:
    if _state["booth"] is None:
        _state["booth"] = Booth.open()
    return _state["booth"]


# ---------------------------------------------------------------- auth

def _check_pin(pin: str, booth: Booth) -> bool:
    return secrets.compare_digest(str(pin), str(booth.config.admin_pin))


def require_login(request: Request, booth: Booth = Depends(get_booth)):
    token = request.cookies.get(SESSION_COOKIE)
    if not token or token not in _state["tokens"]:
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})
    return booth


# ---------------------------------------------------------------- routes

@app.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse(url="/admin", status_code=303)


@app.get("/admin/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": ""})


@app.post("/admin/login")
def login(request: Request, pin: str = Form(""), booth: Booth = Depends(get_booth)):
    if not _check_pin(pin, booth):
        return templates.TemplateResponse(request, "login.html",
                                          {"error": "PIN اشتباه است"})
    token = secrets.token_urlsafe(24)
    _state["tokens"].add(token)
    resp = RedirectResponse(url="/admin", status_code=303)
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return resp


@app.post("/admin/logout")
def logout():
    return RedirectResponse(url="/admin/login", status_code=303)


@app.get("/admin", response_class=HTMLResponse)
def dashboard(request: Request, booth: Booth = Depends(require_login)):
    open_orders = booth.orders.list_open()
    today = booth.stats.today()
    low_stock = [p for p in booth.products.list_all() if p.stock <= 2]
    return templates.TemplateResponse(request, "dashboard.html", {
        "today": today, "open_orders": open_orders,
        "low_stock": low_stock, "products_count": len(booth.products.list_all()),
    })


@app.get("/admin/products", response_class=HTMLResponse)
def products_list(request: Request, booth: Booth = Depends(require_login)):
    return templates.TemplateResponse(request, "products.html", {
        "products": booth.products.list_all(),
    })


@app.post("/admin/products/create")
def products_create(
    name: str = Form(...), price_toman: int = Form(...), stock: int = Form(0),
    sort_order: int = Form(0), active: bool = Form(False),
    image: Optional[UploadFile] = File(None),
    booth: Booth = Depends(require_login),
):
    img_rel = _save_image(image) if image and image.filename else None
    booth.products.create(name, price_toman, stock=stock,
                          image_path=img_rel, sort_order=sort_order, active=active)
    return RedirectResponse(url="/admin/products", status_code=303)


@app.post("/admin/products/{pid}/update")
def products_update(
    pid: int, name: str = Form(...), price_toman: int = Form(...),
    stock: int = Form(...), sort_order: int = Form(0), active: bool = Form(False),
    image: Optional[UploadFile] = File(None),
    booth: Booth = Depends(require_login),
):
    p = booth.products.get(pid)
    if p is None:
        raise HTTPException(404)
    img_rel = _save_image(image) if image and image.filename else p.image_path
    if image and image.filename and p.image_path and p.image_path != img_rel:
        _delete_image(p.image_path)
    booth.products.update(pid, name=name, price_toman=price_toman, stock=stock,
                          image_path=img_rel, sort_order=sort_order, active=active)
    return RedirectResponse(url="/admin/products", status_code=303)


@app.post("/admin/products/{pid}/stock")
def stock_delta(pid: int, delta: int = Form(...), booth: Booth = Depends(require_login)):
    booth.products.adjust_stock(pid, delta)
    return RedirectResponse(request.url.path if False else "/admin/products", status_code=303)


@app.post("/admin/products/{pid}/delete")
def products_delete(pid: int, booth: Booth = Depends(require_login)):
    p = booth.products.get(pid)
    if p:
        if p.image_path:
            _delete_image(p.image_path)
        booth.products.delete(pid)
    return RedirectResponse(url="/admin/products", status_code=303)


@app.get("/admin/orders", response_class=HTMLResponse)
def orders_list(request: Request, booth: Booth = Depends(require_login)):
    return templates.TemplateResponse(request, "orders.html", {
        "orders": booth.orders.list_recent(limit=50),
    })


@app.post("/admin/orders/{oid}/approve")
def order_approve(oid: int, booth: Booth = Depends(require_login)):
    try:
        booth.orders.mark_paid(oid, provider="manual", provider_ref="seller")
    except Exception:
        pass
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/admin/orders/{oid}/deliver")
def order_deliver(oid: int, booth: Booth = Depends(require_login)):
    try:
        booth.orders.mark_delivered(oid)
    except Exception:
        pass
    return RedirectResponse(url="/admin", status_code=303)


@app.get("/admin/reports", response_class=HTMLResponse)
def reports(request: Request, days: int = 14, booth: Booth = Depends(require_login)):
    return templates.TemplateResponse(request, "reports.html", {
        "days": days, "daily": booth.stats.daily(days),
        "top": booth.stats.top_products(days),
        "rows": booth.stats.rows_for_csv(days),
    })


@app.get("/admin/reports/export.csv")
def reports_csv(days: int = 30, booth: Booth = Depends(require_login)):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "code", "status", "total_toman", "provider",
                     "provider_ref", "created_at", "paid_at", "items"])
    for r in booth.stats.rows_for_csv(days):
        writer.writerow([r["id"], r["code"], r["status"], r["total_toman"],
                         r["provider"], r["provider_ref"], r["created_at"],
                         r["paid_at"], r["items"]])
    return PlainTextResponse(
        buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=chiz-sales.csv"})


@app.get("/admin/img/{rel_path:path}")
def product_image(rel_path: str):
    """Serve uploaded product images from the data dir."""
    p = (DATA_DIR / rel_path).resolve()
    if not str(p).startswith(str((DATA_DIR / "img" / "products").resolve())) \
            or not p.is_file():
        raise HTTPException(404)
    mt = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}.get(p.suffix, "application/octet-stream")
    from fastapi.responses import FileResponse
    return FileResponse(p, media_type=mt)


@app.get("/admin/api/open-orders")
def api_open_orders(booth: Booth = Depends(require_login)):
    """Polled by the dashboard for live seller view."""
    out = []
    for owi in booth.orders.list_open():
        out.append({
            "id": owi.order.id, "code": owi.order.code,
            "status": owi.order.status, "total": owi.order.total_toman,
            "items": [{"name": i.name, "qty": i.qty} for i in owi.items],
            "created_at": owi.order.created_at,
        })
    return JSONResponse({"orders": out})


# ---------------------------------------------------------------- images

def _save_image(upload: UploadFile) -> str | None:
    ct = (upload.content_type or "").lower()
    if not ct.startswith("image/"):
        return None
    data = upload.file.read(_MAX_IMG_BYTES + 1)
    if len(data) > _MAX_IMG_BYTES:
        return None
    ext = ".png" if "png" in ct else ".jpg" if "jpeg" in ct else ".webp" if "webp" in ct else ""
    if not ext:
        return None
    PRODUCT_IMG_DIR.mkdir(parents=True, exist_ok=True)
    rel = f"img/products/{uuid.uuid4().hex[:12]}{ext}"
    (DATA_DIR / rel).write_bytes(data)
    return rel


def _delete_image(rel: str) -> None:
    try:
        p = DATA_DIR / rel
        if p.is_file() and "img/products" in str(p):
            p.unlink()
    except OSError:
        pass
