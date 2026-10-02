"""CHIZ Booth — order lifecycle: create, pay, deliver, expire + events log."""
from __future__ import annotations

import json
import random
import sqlite3
from dataclasses import dataclass

from core.models import Order, OrderItem


@dataclass
class OrderWithItems:
    order: Order
    items: list[OrderItem]


class OrderError(Exception):
    pass


class OutOfStock(OrderError):
    pass


class OrderRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ---------- creation ----------

    def create(self, product_id: int, qty: int = 1,
               provider: str = "manual") -> OrderWithItems:
        """Create a pending order, reserving stock atomically."""
        if qty < 1:
            raise OrderError("qty must be >= 1")
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            row = self.conn.execute(
                "SELECT * FROM products WHERE id=?", (product_id,)
            ).fetchone()
            if row is None or not row["active"]:
                raise OrderError("product not found")
            if row["stock"] < qty:
                raise OutOfStock(row["name"])
            self.conn.execute(
                "UPDATE products SET stock=stock-? WHERE id=?", (qty, product_id)
            )
            total = row["price_toman"] * qty
            code = self._next_code()
            cur = self.conn.execute(
                "INSERT INTO orders(code, status, total_toman, provider) "
                "VALUES(?, 'pending', ?, ?)",
                (code, total, provider),
            )
            order_id = cur.lastrowid
            self.conn.execute(
                "INSERT INTO order_items(order_id, product_id, name, unit_price, qty) "
                "VALUES(?,?,?,?,?)",
                (order_id, product_id, row["name"], row["price_toman"], qty),
            )
            self._log("order_created", order_id, f"{row['name']} x{qty}")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get(order_id)  # type: ignore[arg-type]

    def create_cart(self, items: dict[int, int],
                    provider: str = "manual") -> OrderWithItems:
        """One pending order for a whole cart {product_id: qty}, reserving
        every line's stock atomically (all or nothing)."""
        lines = [(int(pid), int(q)) for pid, q in items.items() if int(q) > 0]
        if not lines:
            raise OrderError("cart is empty")
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            rows = []
            for pid, qty in lines:
                row = self.conn.execute(
                    "SELECT * FROM products WHERE id=?", (pid,)).fetchone()
                if row is None or not row["active"]:
                    raise OrderError("product not found")
                if row["stock"] < qty:
                    raise OutOfStock(row["name"])
                rows.append((row, qty))
            total = sum(r["price_toman"] * q for r, q in rows)
            code = self._next_code()
            cur = self.conn.execute(
                "INSERT INTO orders(code, status, total_toman, provider) "
                "VALUES(?, 'pending', ?, ?)", (code, total, provider))
            order_id = cur.lastrowid
            for row, qty in rows:
                self.conn.execute(
                    "UPDATE products SET stock=stock-? WHERE id=?", (qty, row["id"]))
                self.conn.execute(
                    "INSERT INTO order_items(order_id, product_id, name, unit_price, qty) "
                    "VALUES(?,?,?,?,?)",
                    (order_id, row["id"], row["name"], row["price_toman"], qty))
            self._log("order_created", order_id,
                      ", ".join(f"{r['name']} x{q}" for r, q in rows))
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return self.get(order_id)  # type: ignore[arg-type]

    def _next_code(self) -> str:
        """Short numeric pickup code unique among open orders."""
        for _ in range(50):
            code = str(random.randint(1, 9999))
            row = self.conn.execute(
                "SELECT 1 FROM orders WHERE code=? AND status IN ('pending','paid')",
                (code,),
            ).fetchone()
            if row is None:
                return code
        # extremely unlikely: fall back to timestamp-based code
        import time
        return str(int(time.time()) % 100000)

    # ---------- queries ----------

    def get(self, order_id: int) -> OrderWithItems | None:
        row = self.conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if row is None:
            return None
        return self._with_items(row)

    def get_by_code(self, code: str) -> OrderWithItems | None:
        row = self.conn.execute(
            "SELECT * FROM orders WHERE code=? ORDER BY id DESC LIMIT 1", (str(code),)
        ).fetchone()
        if row is None:
            return None
        return self._with_items(row)

    def _with_items(self, row: sqlite3.Row) -> OrderWithItems:
        items_rows = self.conn.execute(
            "SELECT * FROM order_items WHERE order_id=?", (row["id"],)
        ).fetchall()
        items = [
            OrderItem(
                product_id=r["product_id"], name=r["name"],
                unit_price=r["unit_price"], qty=r["qty"],
            )
            for r in items_rows
        ]
        order = Order(
            id=row["id"], code=row["code"], status=row["status"],
            total_toman=row["total_toman"], provider=row["provider"],
            provider_ref=row["provider_ref"], items=items,
            created_at=row["created_at"], paid_at=row["paid_at"],
        )
        return OrderWithItems(order=order, items=items)

    def list_recent(self, limit: int = 20, status: str | None = None) -> list[OrderWithItems]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM orders WHERE status=? ORDER BY id DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._with_items(r) for r in rows]

    def list_open(self) -> list[OrderWithItems]:
        rows = self.conn.execute(
            "SELECT * FROM orders WHERE status IN ('pending','paid') ORDER BY id ASC"
        ).fetchall()
        return [self._with_items(r) for r in rows]

    # ---------- lifecycle ----------

    def mark_paid(self, order_id: int, provider: str,
                  provider_ref: str | None = None, meta: dict | None = None) -> OrderWithItems:
        row = self.conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if row is None:
            raise OrderError("order not found")
        if row["status"] == "paid":
            return self.get(order_id)  # idempotent
        if row["status"] != "pending":
            raise OrderError(f"cannot pay order in status {row['status']}")
        self.conn.execute(
            "UPDATE orders SET status='paid', provider=?, provider_ref=?, "
            "paid_at=datetime('now','localtime'), meta=? WHERE id=?",
            (provider, provider_ref,
             json.dumps(meta, ensure_ascii=False) if meta else None, order_id),
        )
        self._log("payment_approved", order_id, f"provider={provider} ref={provider_ref}")
        self.conn.commit()
        return self.get(order_id)  # type: ignore[arg-type]

    def mark_delivered(self, order_id: int) -> None:
        row = self.conn.execute("SELECT status FROM orders WHERE id=?", (order_id,)).fetchone()
        if row is None:
            raise OrderError("order not found")
        if row["status"] == "paid":
            self.conn.execute(
                "UPDATE orders SET status='delivered', "
                "delivered_at=datetime('now','localtime') WHERE id=?",
                (order_id,),
            )
            self._log("order_delivered", order_id)
            self.conn.commit()

    def cancel(self, order_id: int, restock: bool = True) -> None:
        """Cancel a pending order and (optionally) put stock back."""
        row = self.conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if row is None:
            raise OrderError("order not found")
        if row["status"] != "pending":
            return
        if restock:
            for r in self.conn.execute(
                "SELECT product_id, qty FROM order_items WHERE order_id=?", (order_id,)
            ).fetchall():
                self.conn.execute(
                    "UPDATE products SET stock=stock+? WHERE id=?",
                    (r["qty"], r["product_id"]),
                )
        self.conn.execute("UPDATE orders SET status='canceled' WHERE id=?", (order_id,))
        self._log("order_canceled", order_id)
        self.conn.commit()

    def expire_stale(self, ttl_minutes: int) -> int:
        """Cancel pending orders older than TTL. Returns count."""
        rows = self.conn.execute(
            "SELECT id FROM orders WHERE status='pending' AND "
            "created_at < datetime('now', 'localtime', ?)",
            (f"-{int(ttl_minutes)} minutes",),
        ).fetchall()
        for r in rows:
            self.cancel(r["id"], restock=True)
        return len(rows)

    def pending_age_seconds(self, order_id: int) -> float | None:
        row = self.conn.execute(
            "SELECT created_at FROM orders WHERE id=? AND status='pending'", (order_id,)
        ).fetchone()
        if row is None:
            return None
        import datetime as dt
        created = dt.datetime.fromisoformat(row["created_at"])
        return (dt.datetime.now() - created).total_seconds()

    # ---------- events ----------

    def _log(self, kind: str, order_id: int | None = None, detail: str = "") -> None:
        self.conn.execute(
            "INSERT INTO events(kind, order_id, detail) VALUES(?,?,?)",
            (kind, order_id, detail),
        )

    def recent_events(self, limit: int = 50) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
