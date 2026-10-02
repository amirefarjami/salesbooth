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


class CardReaderProvider(ManualProvider):
    """Standalone POS card reader next to the booth: the buyer pays on it,
    the operator sees the approved slip and confirms from the admin panel."""

    name = "card"

    def start(self, order_id, amount_toman, description) -> PaymentStart:
        return PaymentStart(ok=True, provider=self.name, order_id=order_id,
                            amount=amount_toman,
                            message_fa="کارت رو روی کارتخوان بکش؛ اپراتور تأیید می‌کنه")


METHODS = ("qr", "card")


def provider_for_method(booth, method: str) -> PaymentProvider:
    """Provider behind a payment method the buyer picks on the screen.
    payment_provider = "free" turns every method into instant test approval."""
    cfg = booth.config
    if (cfg.payment_provider or "").lower() == "free":
        return FreeProvider()
    if method == "qr":
        from core.zarinpal import ZarinpalProvider  # lazy: imports httpx

        return ZarinpalProvider(cfg.zarinpal_merchant_id, cfg.zarinpal_sandbox)
    return CardReaderProvider(booth)


def provider_from_config(booth) -> PaymentProvider:
    """Legacy single-provider setup (manual | free | zarinpal)."""
    kind = (booth.config.payment_provider or "manual").lower()
    if kind == "free":
        return FreeProvider()
    if kind == "zarinpal":
        from core.zarinpal import ZarinpalProvider  # lazy: imports httpx

        cfg = booth.config
        return ZarinpalProvider(cfg.zarinpal_merchant_id, cfg.zarinpal_sandbox)
    return ManualProvider(booth)
