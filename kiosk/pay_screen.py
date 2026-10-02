"""CHIZ Booth — payment and pickup screens.

PayScreen      waits for the chosen method: the Zarinpal QR gateway, or the
               card reader (the operator checks the slip and confirms in
               the admin panel); decline / retry / timeout.
SuccessScreen  a short celebration once the payment is approved.
DoorScreen     the semi-automatic hand-over: the showcase lock is released
               for the operator; the door sensor starts the countdown when
               the door opens; the last seconds go red with an alarm; the
               lock catches again when the door is closed.
"""
from __future__ import annotations

import io
from concurrent.futures import Future, ThreadPoolExecutor

import pygame

from core.fa import fa_digits
from core.payment import PaymentCheck, PaymentStatus
import math
import random

from kiosk.screens import Screen, _card_icon, _press
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

    def __init__(self, app, order_id: int, provider=None, method: str = "card") -> None:
        super().__init__(app)
        self.order_id = order_id
        self.provider = provider or app.provider_for(method)
        self.method = method
        owi = app.booth.orders.get(order_id)
        self.code = owi.order.code if owi else "—"
        self.total = owi.order.total_toman if owi else app.pending_total
        self.status = PaymentStatus.PENDING
        self.message = ""
        self.done = False
        self.t_ms = 0
        self.since_check_ms = 0
        # network providers run in a worker so the screen never freezes;
        # DB-backed providers (manual/free) stay on the main thread (sqlite)
        self._threaded = self.provider.name in ("zarinpal", "card")  # network / device I/O
        self._pool = ThreadPoolExecutor(max_workers=1) if self._threaded else None
        self._job: Future | None = None
        self.start = None
        self.qr: pygame.Surface | None = None
        if self._threaded:
            self._job = self._pool.submit(self.provider.start, order_id, self.total,
                                          "خرید از باجه‌ی چیز")
        else:
            self._on_started(self.provider.start(order_id, self.total, "خرید از باجه‌ی چیز"))

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
        self.app.lights.trigger("fail")
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
            self.app.open_success(self.order_id, self.code)
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
            self._job = self._pool.submit(self.provider.check, self.start)
        else:
            self._on_checked(self.provider.check(self.start))

    def red_light(self) -> str:
        return "blink" if self.status == PaymentStatus.DECLINED else "off"

    def lights_mode(self) -> str:
        return "paywait" if self.status == PaymentStatus.PENDING else "shop"

    def handle(self, action: str) -> None:
        if self.status == PaymentStatus.DECLINED:
            if action == "confirm":
                self.app.sounds.play("select")
                if not self.app.create_order(self.method):
                    self.message = "یکی از کالاها تموم شد"
                    self.app.sounds.play("error")
            elif action == "cancel":
                self.app.sounds.play("back")
                self.app.open_methods()
            return
        if action == "cancel" and not self.done:
            if hasattr(self.provider, "cancel"):
                self.provider.cancel()          # abort the sale on the reader
            self.app.booth.orders.cancel(self.order_id, restock=True)
            self.done = True
            self._shutdown_pool()
            self.app.sounds.play("back")
            self.app.open_methods()

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
        provider = self.start.provider if self.start else self.provider.name
        title = {"zarinpal": "اسکن کن، پرداخت کن", "card": "پرداخت با کارتخوان"}.get(
            provider, "پرداخت نزد فروشنده")
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
        elif provider == "card":
            _card_icon(surf, (cx, y + 70), K["ink"])
            lab = t.text("مبلغ روی کارتخوان اومده", "sm")
            surf.blit(lab, lab.get_rect(midtop=(cx, y + 130)))
            sub = t.text("فقط کارت بکش و رمزت رو بزن", "sm", K["alt"])
            surf.blit(sub, sub.get_rect(midtop=(cx, y + 162)))
            plate_r = pygame.Rect(0, 0, 220, 96)
            plate_r.midtop = (cx, y + 204)
            plate(surf, plate_r, K["hi"])
            kl = t.text("کد سفارش", "xs", K["ink"])
            surf.blit(kl, kl.get_rect(midtop=(plate_r.centerx, plate_r.top + 6)))
            code = t.text(fa_digits(self.code), "xl", K["ink"], "display")
            surf.blit(code, code.get_rect(center=(plate_r.centerx, plate_r.centery + 12)))
            y = plate_r.bottom + 26
            self._draw_dots(surf, cx, y + 8)
            wait = t.text("منتظر تأیید پرداخت…", "sm", K["muted"])
            surf.blit(wait, wait.get_rect(midtop=(cx, y + 30)))
            y += 72
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
            wait = t.text("منتظر تأیید پرداخت…", "sm", K["muted"])
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
        # all three full, then they empty from the right, then refill
        gone = (self.t_ms // 350) % 4
        for i in range(3):                  # i = 0 is the leftmost
            r = pygame.Rect(0, 0, 16, 16)
            r.center = (cx + (i - 1) * 28, y)
            plate(surf, r, K["alt"] if i < 3 - gone else K["paper_2"], shadow=2, outline=2)

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


class SuccessScreen(Screen):
    """Payment approved: burst rings, confetti and a big check (~3 s)."""

    idle_timeout = False
    led_mode = "success"
    DURATION_MS = 3200

    def lights_mode(self) -> str:
        return "celebrate"        # pulses with the fanfare
    def __init__(self, app, order_id: int, code: str) -> None:
        super().__init__(app)
        self.order_id = order_id
        self.code = code
        owi = app.booth.orders.get(order_id)
        self.total = owi.order.total_toman if owi else 0
        self.t_ms = 0
        rnd = random.Random(order_id)
        cols = (K["hi"], K["danger"], K["alt"], (255, 255, 255))
        self.confetti = [  # x, start_y, speed, sway, size, colour
            (rnd.uniform(30, app.theme.w - 30), rnd.uniform(-300, -10),
             rnd.uniform(220, 420), rnd.uniform(0, 6.3), rnd.randint(6, 12),
             cols[i % len(cols)]) for i in range(46)]
        app.sounds.play("fanfare")

    def tick(self, dt_ms: int) -> None:
        self.t_ms += dt_ms
        if self.t_ms >= self.DURATION_MS:
            self.app.open_door(self.order_id, self.code)

    def handle(self, action: str) -> None:
        pass   # nothing to cancel any more; the door step follows by itself

    def draw(self, surf: pygame.Surface) -> None:
        t = self.app.theme
        t.stage(surf)
        cx, cy = t.w // 2, 300
        sec = self.t_ms / 1000.0

        # expanding burst rings
        for k in range(3):
            age = sec - k * 0.35
            if age > 0:
                r = int(60 + age * 420)
                if r < 520:
                    pygame.draw.circle(surf, K["hi"] if k % 2 == 0 else K["danger"],
                                       (cx, cy), r, 10)
        # the badge pops in with a small overshoot
        k = min(1.0, sec / 0.45)
        scale = 1.0 + 0.25 * math.sin(k * math.pi) if k < 1 else 1.0
        rad = int(110 * scale * min(1.0, sec / 0.2 + 0.2))
        t.price_burst(surf, (cx, cy), "", rad * 2 + 40, rad * 2 + 30, seed=3)
        pygame.draw.circle(surf, K["ink"], (cx + 4, cy + 4), rad - 18)
        pygame.draw.circle(surf, K["ok"], (cx, cy), rad - 18)
        pygame.draw.circle(surf, K["ink"], (cx, cy), rad - 18, 4)
        if sec > 0.3:   # the check draws itself
            d = min(1.0, (sec - 0.3) / 0.35)
            p0, p1, p2 = (cx - 42, cy + 2), (cx - 12, cy + 34), (cx + 46, cy - 34)
            pts = [p0]
            if d < 0.4:
                f = d / 0.4
                pts.append((p0[0] + (p1[0] - p0[0]) * f, p0[1] + (p1[1] - p0[1]) * f))
            else:
                f = (d - 0.4) / 0.6
                pts += [p1, (p1[0] + (p2[0] - p1[0]) * f, p1[1] + (p2[1] - p1[1]) * f)]
            pygame.draw.lines(surf, (255, 255, 255), False, pts, 16)

        # confetti
        for x, y0, v, sway, size, col in self.confetti:
            y = y0 + v * sec
            if 0 < y < t.h:
                xx = x + 14 * math.sin(sway + sec * 5)
                pygame.draw.rect(surf, col, (int(xx), int(y), size, size // 2 + 2))

        box = pygame.Rect(36, 470, t.w - 72, 190)
        plate(surf, box, K["paper"])
        h = t.text("پرداخت موفق!", "xl", K["ok"], "display")
        surf.blit(h, h.get_rect(midtop=(box.centerx, box.top + 16)))
        amt = t.text(f"{price_fa(self.total)} تومان", "md", K["ink"])
        surf.blit(amt, amt.get_rect(midtop=(box.centerx, box.top + 92)))
        t.sticker(surf, f"کد سفارش {fa_digits(self.code)}",
                  {"midtop": (box.centerx, box.top + 136)}, size="sm", fill=K["hi"])
        msg = t.text("الان ویترین باز می‌شه…", "sm", K["alt_ink"])
        surf.blit(msg, msg.get_rect(midtop=(cx, box.bottom + 24)))


class DoorScreen(Screen):
    """Semi-automatic hand-over (an operator is always at the booth).

    wait      lock released; the operator opens the showcase and hands over
              the items listed on screen. No door opening within
              `door_wait_s` → lock again.
    open      the door sensor saw the door open: the lock coil is released
              so it catches on closing; `door_open_s` countdown.
    overtime  time is up and the door is still open: red + alarm until shut.
    done      door shut (or never opened): thanks, then back to attract.
    Without a door sensor the countdown starts right at unlock.
    """

    idle_timeout = False
    led_mode = "door"
    DONE_MS = 2600

    def lights_mode(self) -> str:
        """MOSFET 1 dims the booth, MOSFET 2 adds the red lights."""
        return "warn" if self.warning else "door"

    def __init__(self, app, order_id: int, code: str) -> None:
        super().__init__(app)
        self.order_id = order_id
        self.code = code
        owi = app.booth.orders.get(order_id)
        self.items = [(it.name, it.qty) for it in owi.items] if owi else []
        cfg = app.booth.config
        # 20 s for one item, +5 s for every extra item (counted by quantity)
        units = max(1, sum(q for _, q in self.items))
        open_s = max(5, int(cfg.door_open_s)) + max(0, int(cfg.door_extra_per_item_s)) * (units - 1)
        self.open_ms = open_s * 1000
        self.warn_ms = max(0, min(int(cfg.door_warn_s), open_s - 1)) * 1000
        self.wait_ms = max(10, int(cfg.door_wait_s)) * 1000
        self.has_sensor = bool(getattr(app.door, "enabled", False))
        self.state = "wait"
        self.state_ms = 0
        self.left_ms = self.open_ms
        self.delivered = False
        self._last_beep = None
        app.lock.unlock()
        if not self.has_sensor:
            self._to("open")

    # --- state machine ---

    def _to(self, state: str) -> None:
        self.state = state
        self.state_ms = 0
        if state == "open":
            self.left_ms = self.open_ms
            if self.has_sensor:
                self.app.lock.lock()     # coil off: the latch catches on closing
            self.app.led.door()
        elif state == "overtime":
            self.app.led.warn()
        elif state == "done":
            self.app.lock.lock()
            self.app.led.idle()
            if self.delivered:
                try:
                    self.app.booth.orders.mark_delivered(self.order_id)
                except Exception:
                    pass
                self.app.sounds.play("success")
            else:
                self.app.sounds.play("back")

    @property
    def warning(self) -> bool:
        return self.state == "overtime" or (self.state == "open" and self.left_ms <= self.warn_ms)

    @property
    def seconds_left(self) -> int:
        return max(0, -(-self.left_ms // 1000))   # ceil

    def tick(self, dt_ms: int) -> None:
        self.state_ms += dt_ms
        door_open = self.app.door.is_open if self.has_sensor else True
        if self.state == "wait":
            if door_open:
                self.delivered = True
                self._to("open")
            elif self.state_ms >= self.wait_ms:
                self._to("done")
        elif self.state in ("open", "overtime"):
            if self.has_sensor and not door_open:
                self._to("done")
                return
            if self.state == "open":
                self.left_ms -= dt_ms
                if self.left_ms <= self.warn_ms and self.app.led.mode != "warn":
                    self.app.led.warn()
                if self.left_ms <= 0:
                    if self.has_sensor:
                        self._to("overtime")
                    else:
                        self.delivered = True
                        self._to("done")
                        return
            if self.warning:
                beat = self.seconds_left if self.state == "open" else self.state_ms // 1000
                if beat != self._last_beep:
                    self._last_beep = beat
                    self.app.sounds.play("alarm")
        elif self.state == "done" and self.state_ms >= self.DONE_MS:
            self.app.go("attract")

    def handle(self, action: str) -> None:
        pass   # the door sensor drives this screen, not the buttons

    # --- drawing ---

    def draw(self, surf: pygame.Surface) -> None:
        t = self.app.theme
        warn = self.warning
        t.stage(surf, K["danger"] if warn else None, K["hi"] if warn else None)
        box = pygame.Rect(24, 64, t.w - 48, 640)
        t.modal(surf, box)
        cx = box.centerx
        if self.state == "wait":
            self._draw_wait(surf, t, box, cx)
        elif self.state == "done":
            self._draw_done(surf, t, box, cx)
        else:
            self._draw_countdown(surf, t, box, cx, warn)

    def _draw_items(self, surf, t, box, top: int) -> int:
        y = top
        for name, qty in self.items[:6]:
            row = t.fit_text(f"{name}  ×{fa_digits(qty)}", box.w - 40, ("md", "sm"))
            surf.blit(row, row.get_rect(midtop=(box.centerx, y)))
            y += 36
        return y

    def _draw_wait(self, surf, t, box, cx) -> None:
        t.title_box(surf, "قفل ویترین باز شد", {"midtop": (cx, box.top - 22)}, "md")
        y = t.kicker_rule(surf, "اقلام برای تحویل", cx, box.top + 40, 180)
        y = self._draw_items(surf, t, box, y + 12)
        t.sticker(surf, f"کد سفارش {fa_digits(self.code)}", {"midtop": (cx, y + 14)},
                  size="md", fill=K["hi"])
        msg = t.fit_text("در ویترین رو باز کن و خریدت رو بردار", box.w - 40,
                         ("md", "sm"), K["ink"], "display")
        surf.blit(msg, msg.get_rect(midtop=(cx, box.top + 430)))
        frac = 1 - self.state_ms / self.wait_ms
        bar = pygame.Rect(box.left + 30, box.bottom - 70, box.w - 60, 18)
        t.progress_bar(surf, bar, frac, K["alt"])

    def _draw_countdown(self, surf, t, box, cx, warn) -> None:
        if self.state == "overtime":
            t.title_box(surf, "در رو ببندید!", {"midtop": (cx, box.top - 22)}, "md",
                        fill=K["danger"], color=K["danger_ink"])
        elif warn:
            t.title_box(surf, "در داره بسته می‌شه!", {"midtop": (cx, box.top - 22)}, "md",
                        fill=K["danger"], color=K["danger_ink"])
        else:
            t.title_box(surf, "در ویترین باز است", {"midtop": (cx, box.top - 22)}, "md")
        center = (cx, box.top + 190)
        frac = self.left_ms / self.open_ms if self.state == "open" else 0
        ring_progress(surf, center, 122, 22, frac, K["danger"] if warn else K["alt"])
        if self.state == "open":
            num = t.text(fa_digits(self.seconds_left), "huge",
                         K["danger"] if warn else K["ink"], "display")
            surf.blit(num, num.get_rect(center=(center[0], center[1] + 12)))
            unit = t.text("ثانیه", "xs", K["muted"])
            surf.blit(unit, unit.get_rect(midtop=(center[0], center[1] + 60)))
        else:
            t.close_x(surf, pygame.Rect(center[0] - 50, center[1] - 50, 100, 100))
        y = center[1] + 150
        head = ("زمان تموم شد، در رو ببندید" if self.state == "overtime"
                else "زود باش، در رو ببند!" if warn else "اقلامت رو بردار")
        h = t.fit_text(head, box.w - 40, ("lg", "md", "sm"),
                       K["danger"] if warn else K["ink"], "display")
        surf.blit(h, h.get_rect(midtop=(cx, y)))
        self._draw_items(surf, t, box, y + h.get_height() + 14)

    def _draw_done(self, surf, t, box, cx) -> None:
        if self.delivered:
            t.title_box(surf, "ممنون از خریدت!", {"midtop": (cx, box.top - 22)}, "md")
            logo = t.logo(200)
            if logo is not None:
                surf.blit(logo, logo.get_rect(center=(cx, box.top + 210)))
            msg = t.text("ویترین قفل شد", "lg", K["ink"], "display")
            surf.blit(msg, msg.get_rect(midtop=(cx, box.top + 360)))
            tag = t.text("@CHIZ_THING", "md", K["alt"])
            surf.blit(tag, tag.get_rect(midtop=(cx, box.top + 430)))
        else:
            t.title_box(surf, "ویترین دوباره قفل شد", {"midtop": (cx, box.top - 22)}, "md")
            msg = t.text("در باز نشد", "lg", K["ink"], "display")
            surf.blit(msg, msg.get_rect(midtop=(cx, box.top + 180)))
            sub = t.fit_text("اپراتور می‌تونه از پنل، سفارش رو تحویل‌شده ثبت کنه",
                             box.w - 40, ("sm", "xs"), K["muted"])
            surf.blit(sub, sub.get_rect(midtop=(cx, box.top + 250)))
            t.sticker(surf, f"کد سفارش {fa_digits(self.code)}",
                      {"midtop": (cx, box.top + 300)}, size="md", fill=K["hi"])
