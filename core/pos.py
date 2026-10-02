"""CHIZ Booth — card reader (POS) link.

The booth pushes the amount to the card reader; the buyer only swipes the
card and enters the PIN; the reader reports approved/declined back to the
booth. No operator in the loop.

Iranian PSPs (Sepehr, Saman, Pasargad, Parsian, …) each ship their own
"PC-POS" protocol (TCP over LAN or serial), so the actual wire format is a
driver chosen in booth.toml (`pos_driver`). Every driver implements:

    begin(amount_rial, ref)  push the amount; returns at once
    poll()                   -> PosResult("pending" | "approved" | "declined")
    cancel()                 abort the pending sale on the device

Drivers here:
    sim     laptop simulator: approves after `pos_sim_approve_s` seconds
            (0 = never answers, to try the timeout path)
    none    no card reader configured (the method shows as unavailable)
The real PSP driver is added once the device and its PC-POS spec are in
hand (TASKS #24); it only has to fill in this same three-method interface.
"""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class PosResult:
    status: str              # "pending" | "approved" | "declined"
    ref: str | None = None   # RRN / trace number from the reader
    message_fa: str = ""


class PosError(Exception):
    """The reader is unreachable or rejected the request outright."""


class PosDriver:
    name = "base"

    def begin(self, amount_rial: int, ref: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def poll(self) -> PosResult:  # pragma: no cover
        raise NotImplementedError

    def cancel(self) -> None:
        pass


class SimPos(PosDriver):
    """Laptop simulator: the «buyer» swipes after a few seconds."""

    name = "sim"

    def __init__(self, approve_after_s: float = 5.0) -> None:
        self.approve_after_s = float(approve_after_s)
        self._t0: float | None = None
        self._ref = ""
        self.amount_rial = 0

    def begin(self, amount_rial: int, ref: str) -> None:
        self.amount_rial = int(amount_rial)
        self._ref = ref
        self._t0 = time.monotonic()
        print(f"POS: amount {self.amount_rial:,} rial pushed to the reader (ref {ref})")

    def poll(self) -> PosResult:
        if self._t0 is None:
            return PosResult("declined", message_fa="تراکنشی شروع نشده")
        if self.approve_after_s > 0 and time.monotonic() - self._t0 >= self.approve_after_s:
            return PosResult("approved", ref=f"SIM{self._ref}")
        return PosResult("pending")

    def cancel(self) -> None:
        self._t0 = None


class NoPos(PosDriver):
    name = "none"

    def begin(self, amount_rial: int, ref: str) -> None:
        raise PosError("no card reader configured")

    def poll(self) -> PosResult:
        return PosResult("declined", message_fa="کارتخوان وصل نیست")


def driver_from_config(cfg) -> PosDriver:
    kind = (getattr(cfg, "pos_driver", "sim") or "sim").lower()
    if kind == "sim":
        return SimPos(getattr(cfg, "pos_sim_approve_s", 5.0))
    return NoPos()
