"""CHIZ Booth — payment screen: waiting, success, failure + pickup code."""
from __future__ import annotations

import pygame

from core.fa import fa_digits, shape
from core.payment import PaymentStatus
from kiosk.theme import PAL, lerp_color
from kiosk.widgets import Modal


def _qr_surface(payload: str, size: int) -> pygame.Surface | None:
    """Render a QR code if the `qrcode` package is available."""
    try:
        import qrcode  # optional dependency
    except ImportError:
        return None
    try:
        img = qrcode.make(payload).convert("RGB")
        img = img.resize((size, size))
        import io
        buf = io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        surf = pygame.image.load(buf)
        try:
            surf = surf.convert()
        except pygame.error:
            pass  # headless: no display format yet
        return surf
    except Exception:
        return None


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
        self.qr: pygame.Surface | None = None
        if self.start.ok and self.start.qr_payload:
            self.qr = _qr_surface(self.start.qr_payload, 260)
        self.app.sounds.play("select")

    # --- flow ---

    def tick(self, dt_ms: int) -> None:
        now = pygame.time.get_ticks()
        cfg = self.app.booth.config
        if self.last_check_ms is not None and \
                (now - self.last_check_ms) / 1000.0 < cfg.payment_poll_seconds:
            return
        self.last_check_ms = now

        if self.start.ok and self.start.provider == "manual":
            self.app.led.paywait()
        chk = self.app.provider.check(self.start)
        if chk.status == PaymentStatus.APPROVED:
            self.app.booth.orders.mark_paid(
                self.order_id, provider=self.start.provider, provider_ref=chk.ref)
            self.status = PaymentStatus.APPROVED
            self.done = True
            self.app.sounds.play("success")
            self.app.celebrate_until = now + 3500
        elif chk.status == PaymentStatus.DECLINED:
            self.status = PaymentStatus.DECLINED
            self.done = True
            self.app.sounds.play("error")
            self.app.led.error(duration=0.1)
        elif chk.status == PaymentStatus.CANCELED:
            self.app.booth.orders.cancel(self.order_id, restock=True)
            self.app.go("grid")
            return

        if not self.done and (now - self.t0) > cfg.payment_timeout_s * 1000:
            self.app.booth.orders.cancel(self.order_id, restock=True)
            self.status = PaymentStatus.DECLINED
            self.done = True
            self.app.sounds.play("error")

    def handle(self, action: str) -> None:
        if self.status == PaymentStatus.DECLINED and action == "confirm":
            # retry: fresh pending order for the same product
            self.app.sounds.play("select")
            items = self.app.booth.orders.get(self.order_id)
            if items and items.items:
                self.app.create_order(
                    self.app.booth.products.get(items.items[0].product_id), 1)
            return
        if action == "cancel":
            if not self.done:
                self.app.booth.orders.cancel(self.order_id, restock=True)
            self.app.sounds.play("back")
            self.app.go("grid")

    # --- drawing ---

    def draw(self, surf: pygame.Surface) -> None:
        t = self.app.theme
        surf.fill(PAL["bg"])
        modal = Modal(t, pygame.Rect(24, 140, t.w - 48, 520))
        modal.draw_frame(surf)
        cx = t.w // 2

        if self.status == PaymentStatus.PENDING:
            self._draw_waiting(surf, t, cx)
        elif self.status == PaymentStatus.APPROVED:
            self._draw_success(surf, t, cx)
        else:
            self._draw_failed(surf, t, cx)

        hint = t.fonts.fa("xs").render(
            shape("لغو: برگشت به محصولات"), True, PAL["gray"])
        surf.blit(hint, hint.get_rect(midbottom=(cx, t.h - 16)))

    def _draw_waiting(self, surf, t, cx) -> None:
        owi = self.app.booth.orders.get(self.order_id)
        code = owi.order.code if owi else "—"
        title = t.fonts.fa("lg").render(shape("پرداخت"), True, PAL["amber"])
        surf.blit(title, title.get_rect(midtop=(cx, self.modal_top() + 18)))

        y = self.modal_top() + 70
        if self.qr is not None:
            surf.blit(self.qr, self.qr.get_rect(midtop=(cx, y)))
            y += self.qr.get_height() + 12
            lab = t.fonts.fa("sm").render(
                shape("با گوشی QR را اسکن و کارت بزن"), True, PAL["cream"])
            surf.blit(lab, lab.get_rect(midtop=(cx, y)))
            y += 34
        else:
            dots = "." * (1 + (pygame.time.get_ticks() // 400) % 3)
            d = t.fonts.px("lg").render(dots, True, PAL["border_hi"])
            surf.blit(d, d.get_rect(midtop=(cx, y)))
            y += 44
            lab = t.fonts.fa("sm").render(
                shape("پرداخت را انجام دهید یا به فروشنده مراجعه کنید"),
                True, PAL["cream"])
            surf.blit(lab, lab.get_rect(midtop=(cx, y)))
            y += 36

        # manual-approval path also shows the pickup code big
        lab2 = t.fonts.fa("sm").render(shape("کد سفارش"), True, PAL["gray"])
        surf.blit(lab2, lab2.get_rect(midtop=(cx, y)))
        code_s = t.fonts.px("xl").render(code, True, PAL["green"])
        surf.blit(code_s, code_s.get_rect(midtop=(cx, y + 26)))

    def _draw_success(self, surf, t, cx) -> None:
        owi = self.app.booth.orders.get(self.order_id)
        code = owi.order.code if owi else "—"
        big = t.fonts.fa("xl").render(shape("پرداخت شد!"), True, PAL["green"])
        surf.blit(big, big.get_rect(midtop=(cx, self.modal_top() + 24)))

        check = t.fonts.px("title").render("OK", True, PAL["green"])
        surf.blit(check, check.get_rect(midtop=(cx, self.modal_top() + 84)))

        lab = t.fonts.fa("md").render(shape("کد تحویل شما"), True, PAL["cream"])
        surf.blit(lab, lab.get_rect(midtop=(cx, self.modal_top() + 190)))
        code_s = t.fonts.px("title").render(code, True, PAL["amber"])
        surf.blit(code_s, code_s.get_rect(midtop=(cx, self.modal_top() + 232)))
        note = t.fonts.fa("sm").render(
            shape("کد را به فروشنده نشان بده"), True, PAL["gray"])
        surf.blit(note, note.get_rect(midtop=(cx, self.modal_top() + 320)))

    def _draw_failed(self, surf, t, cx) -> None:
        big = t.fonts.fa("xl").render(shape("پرداخت ناموفق"), True, PAL["red"])
        surf.blit(big, big.get_rect(midtop=(cx, self.modal_top() + 60)))
        note = t.fonts.fa("md").render(
            shape("دوباره تلاش کن یا با فروشنده صحبت کن"), True, PAL["cream"])
        surf.blit(note, note.get_rect(midtop=(cx, self.modal_top() + 140)))
        retry = t.fonts.fa("sm").render(
            shape("قرمز: تلاش دوباره  |  لغو: خروج"), True, PAL["gray"])
        surf.blit(retry, retry.get_rect(midtop=(cx, self.modal_top() + 200)))

    def modal_top(self) -> int:
        return 140
