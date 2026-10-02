"""CHIZ Booth — application context shared by kiosk and admin panel."""
from __future__ import annotations

import sqlite3

from core.config import Config, load_config
from core.db import connect, init_schema
from core.orders import OrderRepo
from core.products import ProductRepo
from core.stats import Stats


class Booth:
    """One instance per process; owns the SQLite connection."""

    def __init__(self, config: Config, conn: sqlite3.Connection) -> None:
        self.config = config
        self.conn = conn
        self.products = ProductRepo(conn)
        self.orders = OrderRepo(conn)
        self.stats = Stats(conn)

    @classmethod
    def open(cls, config: Config | None = None, *, shared: bool = False) -> "Booth":
        cfg = config or load_config()
        conn = connect(cfg.db_path, shared=shared)
        init_schema(conn)
        return cls(cfg, conn)

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
