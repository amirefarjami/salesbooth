"""CHIZ Booth — SQLite connection + schema management."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    price_toman INTEGER NOT NULL CHECK (price_toman >= 0),
    stock       INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    image_path  TEXT,
    active      INTEGER NOT NULL DEFAULT 1,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT NOT NULL UNIQUE,           -- short pickup code like 12
    status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','paid','delivered','canceled','expired')),
    total_toman  INTEGER NOT NULL CHECK (total_toman >= 0),
    provider     TEXT NOT NULL,                  -- manual / free / zarinpal
    provider_ref TEXT,                           -- authority / ref id
    meta         TEXT,                           -- JSON blob (extra info)
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    paid_at      TEXT,
    delivered_at TEXT
);

CREATE TABLE IF NOT EXISTS order_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    name       TEXT NOT NULL,                    -- snapshot of name at sale time
    unit_price INTEGER NOT NULL,
    qty        INTEGER NOT NULL CHECK (qty > 0)
);

CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    kind       TEXT NOT NULL,                    -- order_created / payment_approved / ...
    order_id   INTEGER,
    detail     TEXT
);

CREATE INDEX IF NOT EXISTS idx_orders_status   ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created  ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_items_order     ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_events_kind     ON events(kind);
"""


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open the booth database with sane pragmas."""
    p = Path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create tables if missing and stamp schema version."""
    conn.executescript(_SCHEMA)
    conn.execute(
        "INSERT INTO schema_meta(key, value) VALUES('schema_version', ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def reset_db(db_path: Path | str) -> sqlite3.Connection:
    """Delete the DB file and recreate the schema. Test/dev helper."""
    p = Path(db_path)
    if p.exists():
        p.unlink()
    conn = connect(p)
    init_schema(conn)
    return conn
