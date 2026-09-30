"""CHIZ Booth — product catalog repository."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from core.models import Product


class ProductRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ---------- queries ----------

    def list_active(self) -> list[Product]:
        rows = self.conn.execute(
            "SELECT * FROM products WHERE active=1 ORDER BY sort_order, id"
        ).fetchall()
        return [Product.from_row(r) for r in rows]

    def list_all(self) -> list[Product]:
        rows = self.conn.execute(
            "SELECT * FROM products ORDER BY active DESC, sort_order, id"
        ).fetchall()
        return [Product.from_row(r) for r in rows]

    def get(self, product_id: int) -> Product | None:
        row = self.conn.execute(
            "SELECT * FROM products WHERE id=?", (product_id,)
        ).fetchone()
        return Product.from_row(row) if row else None

    # ---------- mutations ----------

    def create(self, name: str, price_toman: int, stock: int = 0,
               image_path: str | None = None, sort_order: int = 0,
               active: bool = True) -> Product:
        cur = self.conn.execute(
            "INSERT INTO products(name, price_toman, stock, image_path, sort_order, active) "
            "VALUES(?,?,?,?,?,?)",
            (name.strip(), int(price_toman), int(stock), image_path, int(sort_order),
             1 if active else 0),
        )
        self.conn.commit()
        return self.get(cur.lastrowid)  # type: ignore[arg-type]

    def update(self, product_id: int, **cols) -> None:
        allowed = {"name", "price_toman", "stock", "image_path", "active", "sort_order"}
        sets, vals = [], []
        for k, v in cols.items():
            if k not in allowed or v is None:
                continue
            sets.append(f"{k}=?")
            vals.append(int(v) if isinstance(v, bool) else v)
        if not sets:
            return
        sets.append("updated_at=datetime('now','localtime')")
        vals.append(product_id)
        self.conn.execute(f"UPDATE products SET {', '.join(sets)} WHERE id=?", vals)
        self.conn.commit()

    def delete(self, product_id: int) -> None:
        self.conn.execute("DELETE FROM products WHERE id=?", (product_id,))
        self.conn.commit()

    def set_stock(self, product_id: int, stock: int) -> None:
        self.update(product_id, stock=max(0, int(stock)))

    def adjust_stock(self, product_id: int, delta: int) -> int | None:
        p = self.get(product_id)
        if p is None or p.id is None:
            return None
        new = max(0, p.stock + int(delta))
        self.set_stock(product_id, new)
        return new

    # ---------- image helper ----------

    @staticmethod
    def delete_image(db_path: Path | str, rel_path: str | None) -> None:
        """Remove a product image file (relative to data dir). Best effort."""
        if not rel_path:
            return
        p = Path(db_path).parent / rel_path
        try:
            if p.is_file() and "products" in p.parts:
                p.unlink()
        except OSError:
            pass
