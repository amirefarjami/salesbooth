"""CHIZ Booth — payment and pickup screens.

PayScreen   waits for the provider (QR gateway or the seller's approval),
            shows the order code, handles decline / retry / timeout.
DoorScreen  after payment: unlocks the showcase door and counts down
            (`door_open_s`); in the last `door_warn_s` seconds the light
            dims, turns red and an alarm beeps, then the door re-locks.
"""
from __future__ import annotations

import io
from concurrent.futures import Future, ThreadPoolExecutor

import pygame

from core.fa import fa_digits
from core.payment import PaymentCheck, PaymentStatus
from kiosk.screens import Screen, _press
from kiosk.theme import K, OFF_SM, plate, ring_progress
from kiosk.widgets import price_fa


def _qr_surface(payload: str, size: int) -> pygame.Surface | None:
    """Render a QR code (ink on paper) if the `qrcode` package is available."""
    try:
        import qrcode
    except ImportError:
        return None
    try:
        qr = qrcode.QRCode(border=2, box_size=8)
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#1d1409", back_color="#ffffff").convert("RGB")
        img = img.resize((size, size), resample=0)
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


class PayScreen(Screen):
    """Runs the provider flow against the active order."""

    idle_timeout = False      # has its own payment_timeout_s
    led_mode = "paywait"

    def __init__(self, app, order_id: int) -> None:
        super().__init__(app)
        self.order_id = order_id
        owi = app.booth.orders.get(order_id)
        self.code = owi.order.code if owi else "—"
        self.total = owi.order.total_toman if owi else app.pending_total
        self.product_id = owi.items[0].product_id if owi and owi.items else None
        self.status = PaymentStatus.PENDING
        self.message = ""
        self.done = False
        self.t_ms = 0
        self.since_check_ms = 0
        # network providers run in a worker so the screen never freezes;
        # DB-backed providers (manual/free) stay on the main thread (sqlite)
        self._threaded = app.provider.name == "zarinpal"
        self._pool = ThreadPoolExecutor(max_workers=1) if self._threaded else None
        self._job: Future | None = None
        self.start = None
        self.qr: pygame.Surface | None = None
        if self._threaded:
            self._job = self._pool.submit(app.provider.start, order_id, self.total,
                                          "خرید از باجه‌ی چیز")
        else:
            self._on_started(app.provider.start(order_id, self.total, "خرید از باجه‌ی چیز"))

    # --- flow ---

    def _on_started(self, start) -> None:
        self.start = start
        if not start.ok:
            self._fail(start.message_fa or "اتصال به درگاه برقرار نشد")
            return
        if start.qr_payload:
            self.qr = _qr_surface(start.qr_payload, 236)

    def _fail(self, message: str) -> None:
        # a declined / failed / timed-out order gives its stock back
        self.app.booth.orders.cancel(self.order_id, restock=True)
        self.status = PaymentStatus.DECLINED
        self.message = message
        self.done = True
        self.app.sounds.play("error")
        self.app.led.error()
        self._shutdown_pool()

    def _shutdown_pool(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=False)
            self._pool = None

    def _on_checked(self, chk: PaymentCheck) -> None:
        if chk.status == PaymentStatus.APPROVED:
            self.app.booth.orders.mark_paid(
                self.order_id, provider=self.start.provider, provider_ref=chk.ref)
            self.status = PaymentStatus.APPROVED
            self.done = True
            self._shutdown_pool()
            self.app.sounds.play("success")
            self.app.open_door(self.order_id, self.code)
        elif chk.status == PaymentStatus.DECLINED:
            self._fail(chk.message_fa or "پرداخت انجام نشد")
        elif chk.status == PaymentStatus.CANCELED:
            self.app.booth.orders.cancel(self.order_id, restock=True)
            self.done = True
            self._shutdown_pool()
            self.app.go("grid")

    def tick(self, dt_ms: int) -> None:
        self.t_ms += dt_ms
        if self.done:
            return
        cfg = self.app.booth.config

        # collect a finished background call
        if self._job is not None:
            if not self._job.done():
                return
            job, self._job = self._job, None
            try:
                result = job.result()
            except Exception:
                result = None
            if self.start is None:
                if result is None:
                    self._fail("اتصال به درگاه برقرار نشد")
                else:
                    self._on_started(result)
                return
            if result is not None:
                self._on_checked(result)
                if self.done:
                    return

        if self.start is None:
            return
        if self.t_ms > cfg.payment_timeout_s * 1000:
            self._fail("زمان پرداخت تمام شد")
            return

        self.since_check_ms += dt_ms
        if self.since_check_ms < cfg.payment_poll_seconds * 1000:
            return
        self.since_check_ms = 0
        if self._threaded:
            self._job = self._pool.submit(self.app.provider.check, self.start)
        else:
            self._on_checked(self.app.provider.check(self.start))

    def handle(self, action: str) -> None:
        if self.status == PaymentStatus.DECLINED:
            if action == "confirm" and self.product_id is not None:
                product = self.app.booth.products.get(self.product_id)
                self.app.sounds.play("select")
                if product is None or not self.app.create_order(product, 1):
                    self.message = "این کالا تمام شد"
                    self.app.sounds.play("error")
            elif action == "cancel":
                self.app.sounds.play("back")
                self.app.go("grid")
            return
        if action == "cancel" and not self.done:
            self.app.booth.orders.cancel(self.order_id, restock=True)
            self.done = True
            self._shutdown_pool()
            self.app.sounds.play("back")
            self.app.go("grid")

    # --- drawing ---

    def draw(self, surf: pygame.Surface) -> None:
        t = self.app.theme
        failed = self.status == PaymentStatus.DECLINED
        t.stage(surf)
        box = pygame.Rect(24, 64, t.w - 48, 640)
        t.modal(surf, box)
        if failed:
            self._draw_failed(surf, t, box)
        else:
            self._draw_waiting(surf, t, box)

    def _draw_waiting(self, surf, t, box) -> None:
        cx = box.centerx
        provider = self.start.provider if self.start else self.app.provider.name
        title = "اسکن کن، پرداخت کن" if provider == "zarinpal" else "پرداخت نزد فروشنده"
        t.title_box(surf, title, {"midtop": (cx, box.top - 22)}, "md")

        y = box.top + 40
        price = t.text(f"{price_fa(self.total)} تومان", "md")
        surf.blit(price, price.get_rect(midtop=(cx, y)))
        y += price.get_height() + 10

        if self.qr is not None:
            frame = self.qr.get_rect(midtop=(cx, y + 4)).inflate(16, 16)
            plate(surf, frame, (255, 255, 255))
            surf.blit(self.qr, self.qr.get_rect(center=frame.center))
            y = frame.bottom + 16
            t.kicker(surf, "با دوربین گوشی اسکن کن", {"midtop": (cx, y)},
                     size="sm", color=K["ink"], marker=K["alt"])
            y += 40
        elif self.start is None:
            # gateway request still in flight
            self._draw_dots(surf, cx, y + 70)
            msg = t.text("در حال اتصال به درگاه…", "sm")
            surf.blit(msg, msg.get_rect(midtop=(cx, y + 110)))
            y += 300
        else:
            lab = t.text("کد سفارشت رو به فروشنده بگو", "sm")
            surf.blit(lab, lab.get_rect(midtop=(cx, y + 14)))
            plate_r = pygame.Rect(0, 0, 260, 150)
            plate_r.midtop = (cx, y + 60)
            plate(surf, plate_r, K["hi"])
            code = t.text(fa_digits(self.code), "title", K["ink"], "display")
            surf.blit(code, code.get_rect(center=(plate_r.centerx, plate_r.centery + 6)))
            y = plate_r.bottom + 30
            self._draw_dots(surf, cx, y + 8)
            wait = t.text("منتظر تأیید فروشنده…", "sm", K["muted"])
            surf.blit(wait, wait.get_rect(midtop=(cx, y + 30)))
            y += 72

        if self.qr is not None:
            t.sticker(surf, f"کد سفارش {fa_digits(self.code)}", {"midtop": (cx, y)},
                      size="sm", fill=K["hi"])

        # time left
        cfg = self.app.booth.config
        left = max(0.0, 1.0 - self.t_ms / (cfg.payment_timeout_s * 1000))
        bar = pygame.Rect(box.left + 30, box.bottom - 92, box.w - 60, 20)
        t.progress_bar(surf, bar, left, K["alt"])
        secs = int(round(left * cfg.payment_timeout_s))
        lab = t.text(f"{fa_digits(secs)} ثانیه وقت داری", "xs", K["muted"])
        surf.blit(lab, lab.get_rect(midtop=(cx, bar.bottom + 6)))

        cancel = pygame.Rect(box.left + 24, box.bottom + 20, 150, 40)
        plate(surf, cancel, K["paper"], shadow=OFF_SM)
        c = t.text("انصراف", "sm")
        surf.blit(c, c.get_rect(center=cancel.center))

    def _draw_dots(self, surf, cx, y) -> None:
        k = (self.t_ms // 300) % 3
        for i in range(3):
            r = pygame.Rect(0, 0, 16, 16)
            r.center = (cx + (1 - i) * 28, y)   # RTL: fills right → left
            plate(surf, r, K["alt"] if i <= k else K["paper_2"], shadow=2, outline=2)

    def _draw_failed(self, surf, t, box) -> None:
        cx = box.centerx
        t.title_box(surf, "پرداخت ناموفق", {"midtop": (cx, box.top - 22)}, "md",
                    fill=K["danger"], color=K["danger_ink"])
        x = pygame.Rect(0, 0, 120, 120)
        x.midtop = (cx, box.top + 70)
        t.close_x(surf, x)
        msg = t.fit_text(self.message or "پرداخت انجام نشد", box.w - 48, ("md", "sm"))
        surf.blit(msg, msg.get_rect(midtop=(cx, x.bottom + 34)))
        sub = t.text("هزینه‌ای کم نشده؛ اگه شده بود به فروشنده بگو", "xs", K["muted"])
        surf.blit(sub, sub.get_rect(midtop=(cx, x.bottom + 74)))
        t.sticker(surf, f"کد سفارش {fa_digits(self.code)}",
                  {"midtop": (cx, x.bottom + 112)}, size="xs")

        ticket = pygame.Rect(box.left + 24, box.bottom - 150, box.w - 48, 68)
        t.go_ticket(surf, ticket, "دوباره امتحان کن", "md", pressed=_press(self.t_ms, 1600))
        cancel = pygame.Rect(box.left + 24, ticket.bottom + 18, box.w - 48, 46)
        t.button(surf, cancel, "انصراف", "paper", "md")


class DoorScreen(Screen):
    """Showcase door is unlocked: take the item, close the door."""

    idle_timeout = False
    led_mode = "success"

    def __init__(self, app, order_id: int, code: str) -> None:
        super().__init__(app)
        self.order_id = order_id
        self.code = code
        cfg = app.booth.config
        self.total_ms = max(5, int(cfg.door_open_s)) * 1000
        self.warn_ms = max(0, min(int(cfg.door_warn_s), int(cfg.door_open_s) - 1)) * 1000
        self.left_ms = self.total_ms
        self.warning = False
        self.finished = False
        self._last_beep = None
        app.lock.unlock()

    @property
    def seconds_left(self) -> int:
        return max(0, -(-self.left_ms // 1000))   # ceil

    def tick(self, dt_ms: int) -> None:
        if self.finished:
            return
        self.left_ms -= dt_ms
        if not self.warning and self.left_ms <= self.warn_ms:
            self.warning = True
            self.app.led.warn()
        elif not self.warning and self.app.led.mode == "idle":
            self.app.led.door()
        if self.warning and self.seconds_left != self._last_beep and self.left_ms > 0:
            self._last_beep = self.seconds_left
            self.app.sounds.play("alarm")
        if self.left_ms <= 0:
            self.finish()

    def finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        self.app.lock.lock()
        try:
            self.app.booth.orders.mark_delivered(self.order_id)
        except Exception:
            pass
        self.app.sounds.play("back")
        self.app.go("attract")

    def handle(self, action: str) -> None:
        # the buyer is done early: lock right away
        if action in ("confirm", "cancel"):
            self.finish()

    def draw(self, surf: pygame.Surface) -> None:
        t = self.app.theme
        warn = self.warning
        t.stage(surf, K["danger"] if warn else None)
        box = pygame.Rect(24, 64, t.w - 48, 640)
        t.modal(surf, box)
        cx = box.centerx
        if warn:
            t.title_box(surf, "در داره بسته می‌شه!", {"midtop": (cx, box.top - 22)}, "md",
                        fill=K["danger"], color=K["danger_ink"])
        else:
            t.title_box(surf, "پرداخت شد!", {"midtop": (cx, box.top - 22)}, "md")

        center = (cx, box.top + 210)
        frac = self.left_ms / self.total_ms
        ring_progress(surf, center, 128, 22, frac, K["danger"] if warn else K["alt"])
        num = t.text(fa_digits(self.seconds_left), "huge",
                     K["danger"] if warn else K["ink"], "display")
        surf.blit(num, num.get_rect(center=(center[0], center[1] + 12)))
        unit = t.text("ثانیه", "xs", K["muted"])
        surf.blit(unit, unit.get_rect(midtop=(center[0], center[1] + 62)))

        y = center[1] + 160
        head = "زود باش، در رو ببند!" if warn else "در ویترین باز شد"
        h = t.text(head, "lg", K["danger"] if warn else K["ink"], "display")
        surf.blit(h, h.get_rect(midtop=(cx, y)))
        sub = t.text("محصولت رو بردار و در رو ببند", "sm")
        surf.blit(sub, sub.get_rect(midtop=(cx, y + h.get_height() + 6)))
        t.sticker(surf, f"کد سفارش {fa_digits(self.code)}",
                  {"midtop": (cx, y + h.get_height() + 48)}, size="sm", fill=K["hi"])

        done = pygame.Rect(box.left + 24, box.bottom - 70, box.w - 48, 50)
        t.button(surf, done, "برداشتم، در رو قفل کن (قرمز)", "paper", "sm")
