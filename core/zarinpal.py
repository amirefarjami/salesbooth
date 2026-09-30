"""CHIZ Booth — Zarinpal payment gateway adapter.

Flow (https://docs.zarinpal.com):
  1. request  -> authority + redirect url (we render it as QR)
  2. payer approves on their phone
  3. verify   -> success/failure with ref_id

Sandbox: merchant id "00000000-0000-0000-0000-000000000000".
"""
from __future__ import annotations

import os

import httpx

from core.payment import PaymentCheck, PaymentStart, PaymentStatus, PaymentProvider

SANDBOX_MERCHANT = "00000000-0000-0000-0000-000000000000"
SANDBOX_BASE = "https://sandbox.zarinpal.com/pg/v4/payment"
LIVE_BASE = "https://payment.zarinpal.com/pg/v4/payment"
START_PAY = "https://sandbox.zarinpal.com/pg/StartPay/{authority}"


class ZarinpalProvider(PaymentProvider):
    name = "zarinpal"

    def __init__(self, merchant_id: str, sandbox: bool = True,
                 callback_base: str = "http://10.42.0.1:8000/admin",
                 http: httpx.Client | None = None) -> None:
        mid = merchant_id or SANDBOX_MERCHANT
        if os.environ.get("CHIZ_ZARINPAL_MERCHANT_ID"):
            mid = os.environ["CHIZ_ZARINPAL_MERCHANT_ID"]
        self.merchant_id = mid
        self.sandbox = sandbox
        self.base = SANDBOX_BASE if sandbox else LIVE_BASE
        self.startpay = ("https://sandbox.zarinpal.com/pg/StartPay/{authority}"
                         if sandbox else
                         "https://payment.zarinpal.com/pg/StartPay/{authority}")
        self.callback_base = os.environ.get("CHIZ_CALLBACK_BASE", callback_base)
        self.http = http or httpx.Client(timeout=15.0)
        self._pending: dict[str, PaymentStart] = {}

    # --- provider API -------------------------------------------------

    def start(self, order_id: int, amount_toman: int,
              description: str) -> PaymentStart:
        # Zarinpal v4 amounts are in RIALS (x10). API now accepts toman? docs:
        # v4 uses Rial; keep rial conversion here.
        rial = int(amount_toman) * 10
        payload = {
            "merchant_id": self.merchant_id,
            "amount": rial,
            "callback_url": f"{self.callback_base}?order={order_id}",
            "description": description[:500],
        }
        try:
            resp = self.http.post(f"{self.base}/request.json", json=payload)
            data = resp.json().get("data", {})
        except Exception:
            return PaymentStart(ok=False, provider=self.name, order_id=order_id,
                                amount=amount_toman,
                                message_fa="خطای شبکه در اتصال به درگاه")
        if data.get("code") == 100 and data.get("authority"):
            authority = data["authority"]
            url = self.startpay.format(authority=authority)
            st = PaymentStart(ok=True, provider=self.name, order_id=order_id,
                              amount=amount_toman, redirect_url=url,
                              authority=authority, qr_payload=url,
                              message_fa="QR را اسکن و پرداخت کنید")
            self._pending[authority] = st
            return st
        err = (resp.json().get("errors") or {}) if "resp" in dir() else {}
        return PaymentStart(ok=False, provider=self.name, order_id=order_id,
                            amount=amount_toman,
                            message_fa=f"درگاه خطا داد: {err or data}")

    def check(self, start: PaymentStart) -> PaymentCheck:
        """Poll the gateway: unpaid sessions stay PENDING until verify says paid.

        Zarinpal has no status-poll endpoint; verify only succeeds once the
        payer finished the redirect. A failed verify (code -50 etc.) means
        "not paid yet", which we treat as PENDING.
        """
        if not start.authority:
            return PaymentCheck(PaymentStatus.DECLINED, message_fa="authority نداریم")
        payload = {
            "merchant_id": self.merchant_id,
            "amount": int(start.amount) * 10,
            "authority": start.authority,
        }
        try:
            resp = self.http.post(f"{self.base}/verify.json", json=payload)
            body = resp.json()
        except Exception:
            return PaymentCheck(PaymentStatus.PENDING, message_fa="شبکه قطع، دوباره تلاش می‌کنیم")
        data = body.get("data") or {}
        code = data.get("code")
        if code in (100, 101):
            ref = str(data.get("ref_id") or "")
            return PaymentCheck(PaymentStatus.APPROVED, ref=ref, raw=data)
        if code == -50:  # not paid yet
            return PaymentCheck(PaymentStatus.PENDING)
        # anything else: unpaid so far — keep waiting until timeout
        return PaymentCheck(PaymentStatus.PENDING, raw=body)

    # --- helpers --------------------------------------------------------

    def qr_svg(self, start: PaymentStart) -> str | None:
        """Tiny QR renderer is overkill; kiosk renders URL with `qrcode` lib
        if available, else shows the short link text. Kept as hook."""
        return None


def provider_from_config(booth):
    from core.config import Config
    cfg = booth.config
    if (cfg.payment_provider or "").lower() == "zarinpal":
        return ZarinpalProvider(cfg.zarinpal_merchant_id, cfg.zarinpal_sandbox)
    from core.payment import ManualProvider
    return ManualProvider(booth)
