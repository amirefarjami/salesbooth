"""CHIZ Booth — payment provider abstraction."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class PaymentStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"
    CANCELED = "canceled"


@dataclass
class PaymentStart:
    ok: bool
    provider: str
    order_id: int
    amount: int
    message_fa: str = ""
    # gateway fields (zarinpal):
    redirect_url: str | None = None
    authority: str | None = None
    qr_payload: str | None = None


@dataclass
class PaymentCheck:
    status: PaymentStatus
    ref: str | None = None
    message_fa: str = ""
    raw: dict = field(default_factory=dict)


class PaymentProvider(ABC):
    """One provider per booth run; stateless per order."""

    name: str = "base"

    @abstractmethod
    def start(self, order_id: int, amount_toman: int, description: str) -> PaymentStart: ...

    @abstractmethod
    def check(self, start: PaymentStart) -> PaymentCheck: ...


class ManualProvider(PaymentProvider):
    """Seller approves from the admin panel; kiosk polls until then."""

    name = "manual"

    def __init__(self, booth) -> None:
        self.booth = booth

    def start(self, order_id, amount_toman, description) -> PaymentStart:
        return PaymentStart(ok=True, provider=self.name, order_id=order_id,
                            amount=amount_toman,
                            message_fa="نوبت فروشنده: تأیید از پنل مدیریت")

    def check(self, start: PaymentStart) -> PaymentCheck:
        owi = self.booth.orders.get(start.order_id)
        if owi is None:
            return PaymentCheck(PaymentStatus.DECLINED, message_fa="سفارش یافت نشد")
        if owi.order.status in ("paid", "delivered"):
            return PaymentCheck(PaymentStatus.APPROVED, ref="seller")
        return PaymentCheck(PaymentStatus.PENDING)


class FreeProvider(PaymentProvider):
    """Instantly approves (zero-cost testing / giveaway mode)."""

    name = "free"

    def start(self, order_id, amount_toman, description) -> PaymentStart:
        return PaymentStart(ok=True, provider=self.name, order_id=order_id,
                            amount=amount_toman, message_fa="پرداخت آزمایشی")

    def check(self, start: PaymentStart) -> PaymentCheck:
        return PaymentCheck(PaymentStatus.APPROVED, ref="free")


def provider_from_config(booth) -> PaymentProvider:
    kind = (booth.config.payment_provider or "manual").lower()
    if kind == "free":
        return FreeProvider()
    return ManualProvider(booth)
