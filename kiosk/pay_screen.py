"""CHIZ Booth — payment screen: waiting, success, failure + pickup code."""
from __future__ import annotations

import pygame

from core.fa import fa_digits, shape
from core.payment import PaymentStatus
from kiosk.theme import PAL, lerp_color
from kiosk.widgets import Modal


class PayScreen:
    """Runs the provider flow against the active order."""

    def __init__(self, app, order_id: int) -> None:
        self.app = app
        self.order_id = order_id
        self.status = PaymentStatus.PENDING
        self.start = app.provider.start(order_id, app.pending_total, "خرید باجه چیز")
        self.t0 = pygame.time.get_ticks()
        self.last_check_ms: int | None = None
        self.done = False
        self.app.sounds.play("select")

    # --- flow ---

    def tick(self, dt_ms: int) -> None:
        now = pygame.time.get_ticks()
        cfg = self.app.booth.config
        if self.last_check_ms is not None and \
                (now - self.last_check_ms) / 1000.0 < cfg.payment_poll_seconds:
            return
        self.last_check_ms = now

        if self.start.ok and self.start.provider in ("manual",):
            self.app.led.paywait()
        chk = self.app.provider.check(self.start)
        if chk.status == PaymentStatus.APPROVED:
            owi = self.app.booth.orders.mark_paid(
                self.order_id, provider=self.start.provider, provider_ref=chk.ref)
            self.status = PaymentStatus.APPROVED
            self.done = True
            self.app.sounds.play("success")
            self.app.led.success(duration=0.1)  # short blip; full anim in draw
            self.app.celebrate_until = now + 2500
        elif chk.status == PaymentStatus.DECLINED:
            self.status = PaymentStatus.DECLINED
            self.done = True
            self.app.sounds.play("error")
            self.app.led.error(duration=0.1)
        elif chk.status == PaymentStatus.CANCELED:
            self.app.booth.orders.cancel(self.order_id, restock=True)
            self.app.go("grid")

        cfg = self.app.booth.config
        if not self.done and (now - self.t0) > cfg.payment_timeout_s * 1000:
            self.app.booth.orders.cancel(self.order_id, restock=True)
            self.status = PaymentStatus.DECLINED
            self.done = True
            self.app.sounds.play("error")

    def handle(self, action: str) -> None:
        if action == "cancel":
            if not self.done:
                self.app.booth.orders.cancel(self.order_id, restock=True)
            self.app.sounds.play("back")
            self.app.go("grid")

    # --- drawing ---

    def draw(self, surf: pygame.Surface) -> None:
        t = self.app.theme
        surf.fill(PAL["bg"])
        modal = Modal(t, pygame.Rect(24, 180, t.w - 48, 440))
        modal.draw_frame(surf)
        cx = t.w // 2

        if self.status == PaymentStatus.PENDING:
            self._draw_waiting(surf, t, cx)
        elif self.status == PaymentStatus.APPROVED:
            self._draw_success(surf, t, cx)
        else:
            self._draw_failed(surf, t, cx)

        hint = t.fonts.fa("xs").render(shape("لغو: برگشت به محصولات"), True, PAL["gray"])
        surf.blit(hint, hint.get_rect(midbottom=(cx, t.h - 20)))

    def _draw_waiting(self, surf, t, cx) -> None:
        owi = self.app.booth.orders.get(self.order_id)
        code = owi.order.code if owi else "—"
        title = t.fonts.fa("lg").render(shape("در انتظار پرداخت…"), True, PAL["amber"])
        surf.blit(title, title.get_rect(midtop=(cx, self.app.theme.h // 2 - 140)))

        dots = "." * (1 + (pygame.time.get_ticks() // 400) % 3)
        d = t.fonts.px("lg").render(dots, True, PAL["border_hi"])
        surf.blit(d, d.get_rect(midtop=(cx, self.app.theme.h // 2 - 84)))

        lab = t.fonts.fa("sm").render(shape("شماره سفارش شما"), True, PAL["gray"])
        surf.blit(lab, lab.get_rect(midtop=(cx, self.app.theme.h // 2 - 20)))
        code_s = t.fonts.px("xxl").render(code, True, PAL["green"])
        surf.blit(code_s, code_s.get_rect(midtop=(cx, self.app.theme.h // 2 + 14)))
        note = t.fonts.fa("sm").render(
            shape("پرداخت را انجام دهید یا به فروشنده مراجعه کنید"), True, PAL["cream"])
        surf.blit(note, note.get_rect(midtop=(cx, self.app.theme.h // 2 + 96)))

    def _draw_success(self, surf, t, cx) -> None:
        owi = self.app.booth.orders.get(self.order_id)
        code = owi.order.code if owi else "—"
        big = t.fonts.fa("xl").render(shape("پرداخت شد!"), True, PAL["green"])
        surf.blit(big, big.get_rect(midtop=(cx, t.h // 2 - 150)))

        check = t.fonts.px("title").render("OK", True, PAL["green"])
        surf.blit(check, check.get_rect(midtop=(cx, t.h // 2 - 90)))

        lab = t.fonts.fa("md").render(shape("کد تحویل شما"), True, PAL["cream"])
        surf.blit(lab, lab.get_rect(midtop=(cx, t.h // 2 + 10)))
        code_s = t.fonts.px("title").render(code, True, PAL["amber"])
        surf.blit(code_s, code_s.get_rect(midtop=(cx, t.h // 2 + 50)))
        note = t.fonts.fa("sm").render(
            shape("کد را به فروشنده نشان بده"), True, PAL["gray"])
        surf.blit(note, note.get_rect(midtop=(cx, t.h // 2 + 130)))

        # auto-return after celebration
        if pygame.time.get_ticks() > getattr(self.app, "celebrate_until", 0) + 4000:
            self.app.go("grid")

    def _draw_failed(self, surf, t, cx) -> None:
        big = t.fonts.fa("xl").render(shape("پرداخت ناموفق"), True, PAL["red"])
        surf.blit(big, big.get_rect(midtop=(cx, t.h // 2 - 100)))
        note = t.fonts.fa("md").render(
            shape("دوباره تلاش کن یا با فروشنده صحبت کن"), True, PAL["cream"])
        surf.blit(note, note.get_rect(midtop=(cx, t.h // 2 - 20)))
        retry = t.fonts.fa("sm").render(
            shape("قرمز: تلاش دوباره  |  لغو: خروج"), True, PAL["gray"])
        surf.blit(retry, retry.get_rect(midtop=(cx, t.h // 2 + 60)))

    # retry on confirm after failure
    def handle_retry(self, action: str) -> None:
        pass
