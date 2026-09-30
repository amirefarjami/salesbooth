"""CHIZ Booth — lightweight typed views over SQLite rows."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Product:
    id: int | None
    name: str
    price_toman: int
    stock: int
    image_path: str | None = None
    active: bool = True
    sort_order: int = 0

    @classmethod
    def from_row(cls, row) -> "Product":
        return cls(
            id=row["id"],
            name=row["name"],
            price_toman=row["price_toman"],
            stock=row["stock"],
            image_path=row["image_path"],
            active=bool(row["active"]),
            sort_order=row["sort_order"],
        )


@dataclass
class OrderItem:
    product_id: int
    name: str = ""
    unit_price: int = 0
    qty: int = 1


@dataclass
class Order:
    id: int | None
    code: str
    status: str = "pending"
    total_toman: int = 0
    provider: str = "manual"
    provider_ref: str | None = None
    items: list[OrderItem] = None  # type: ignore[assignment]
    created_at: str = ""
    paid_at: str | None = None

    def __post_init__(self) -> None:
        if self.items is None:
            self.items = []
