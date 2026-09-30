"""CHIZ Booth — sales statistics for the admin dashboard."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class DayStats:
    day: str
    orders: int
    revenue: int


@dataclass
class TopProduct:
    name: str
    qty: int
    revenue: int


class Stats:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def today(self) -> dict:
        row = self.conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(total_toman),0) AS rev "
            "FROM orders WHERE status IN ('paid','delivered') "
            "AND date(created_at)=date('now','localtime')"
        ).fetchone()
        return {"orders": row["n"], "revenue": row["rev"]}

    def daily(self, days: int = 14) -> list[DayStats]:
        rows = self.conn.execute(
            "SELECT date(created_at) AS d, COUNT(*) AS n, "
            "COALESCE(SUM(total_toman),0) AS rev "
            "FROM orders WHERE status IN ('paid','delivered') "
            "AND created_at >= datetime('now','localtime', ?) "
            "GROUP BY d ORDER BY d",
            (f"-{int(days)} days",),
        ).fetchall()
        return [DayStats(day=r["d"], orders=r["n"], revenue=r["rev"]) for r in rows]

    def top_products(self, days: int = 30, limit: int = 5) -> list[TopProduct]:
        rows = self.conn.execute(
            "SELECT oi.name AS name, SUM(oi.qty) AS qty, "
            "SUM(oi.qty*oi.unit_price) AS rev "
            "FROM order_items oi JOIN orders o ON o.id=oi.order_id "
            "WHERE o.status IN ('paid','delivered') "
            "AND o.created_at >= datetime('now','localtime', ?) "
            "GROUP BY oi.name ORDER BY qty DESC LIMIT ?",
            (f"-{int(days)} days", limit),
        ).fetchall()
        return [TopProduct(name=r["name"], qty=r["qty"], revenue=r["rev"]) for r in rows]

    def rows_for_csv(self, days: int = 30) -> list[dict]:
        rows = self.conn.execute(
            "SELECT o.id, o.code, o.status, o.total_toman, o.provider, "
            "o.provider_ref, o.created_at, o.paid_at, "
            "GROUP_CONCAT(oi.name || ' x' || oi.qty, ', ') AS items "
            "FROM orders o LEFT JOIN order_items oi ON oi.order_id=o.id "
            "WHERE o.created_at >= datetime('now','localtime', ?) "
            "GROUP BY o.id ORDER BY o.id DESC",
            (f"-{int(days)} days",),
        ).fetchall()
        return [dict(r) for r in rows]
