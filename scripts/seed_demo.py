#!/usr/bin/env python3
"""Seed demo products (CHIZ merch, from the design brief)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.booth import Booth  # noqa: E402


DEMO = [
    ("دستگاه دستی بلی", 150_000, 5),
    ("پک انرژی", 120_000, 10),
    ("نورد دستگاه", 90_000, 8),
    ("پک ترکیبی مالت", 200_000, 6),
    ("ست کامل چیز", 450_000, 3),
    ("پلاک کوچک چیز", 60_000, 12),
]


def main() -> int:
    booth = Booth.open()
    have = {p.name for p in booth.products.list_all()}
    added = 0
    for i, (name, price, stock) in enumerate(DEMO, start=1):
        if name in have:
            continue
        booth.products.create(name, price, stock=stock, sort_order=i)
        added += 1
    print(f"seeded {added} products ({len(have)} already present)")
    booth.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
