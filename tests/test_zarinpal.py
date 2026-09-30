"""Tests for the Zarinpal adapter (mocked HTTP)."""
from __future__ import annotations

import pytest

from core.payment import PaymentStart, PaymentStatus
from core.zarinpal import ZarinpalProvider


class FakeHTTP:
    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.calls: list[tuple] = []

    def post(self, url, json=None):
        self.calls.append((url, json))
        return FakeResp(self.responses.pop(0))


class FakeResp:
    def __init__(self, body: dict):
        self._body = body

    def json(self):
        return self._body


def _provider(http):
    return ZarinpalProvider(merchant_id="test-mid", sandbox=True, http=http)


def test_request_success_returns_authority_and_url():
    http = FakeHTTP([{"data": {"code": 100, "authority": "A000123"}}])
    p = _provider(http)
    st = p.start(7, 150000, "خرید")
    assert st.ok and st.authority == "A000123"
    assert "StartPay/A000123" in st.redirect_url
    # amount sent in rials
    assert http.calls[0][1]["amount"] == 1_500_000


def test_request_failure():
    http = FakeHTTP([{"data": {}, "errors": {"code": -9}}])
    p = _provider(http)
    st = p.start(7, 150000, "خرید")
    assert not st.ok


def test_verify_paid():
    http = FakeHTTP([
        {"data": {"code": 100, "authority": "A1"}},
        {"data": {"code": 100, "ref_id": 777}},
    ])
    p = _provider(http)
    st = p.start(7, 10000, "x")
    chk = p.check(st)
    assert chk.status == PaymentStatus.APPROVED
    assert chk.ref == "777"


def test_verify_already_verified_code_101():
    http = FakeHTTP([
        {"data": {"code": 100, "authority": "A1"}},
        {"data": {"code": 101, "ref_id": 777}},
    ])
    p = _provider(http)
    st = p.start(7, 10000, "x")
    assert p.check(st).status == PaymentStatus.APPROVED


def test_verify_not_paid_yet_is_pending():
    http = FakeHTTP([
        {"data": {"code": 100, "authority": "A1"}},
        {"errors": {"code": -50}},
    ])
    p = _provider(http)
    st = p.start(7, 10000, "x")
    assert p.check(st).status == PaymentStatus.PENDING


def test_network_error_is_pending():
    class BoomHTTP:
        def post(self, url, json=None):
            raise ConnectionError("down")

    p = _provider(BoomHTTP())
    st = p.start(7, 10000, "x")
    assert not st.ok
    chk = p.check(PaymentStart(ok=True, provider="zarinpal", order_id=7,
                               amount=10000, authority="A9"))
    assert chk.status == PaymentStatus.PENDING
