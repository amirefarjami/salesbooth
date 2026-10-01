"""CHIZ Booth — kiosk screens: attract, product grid, order confirmation.

Panel layout (hand sketch): 2×3 product grid in the middle of a portrait
480×800 screen, three slot buttons on each side of the screen (one per
card), the big red button to confirm and «انصراف» under the screen.
"""
from __future__ import annotations

import math

import pygame

from core.config import DATA_DIR
from core.fa import fa_digits
from core.models import Product
from hardware.input import slot_index
from kiosk.theme import K, OFF_SM, arrow, marker_dot, plate
from kiosk.widgets import ProductCard, load_product_image, price_fa

PER_PAGE = 6
COLS = 2

PROVIDER_LABEL = {
    "zarinpal": "پرداخت با کیوآر کد (گوشی)",
    "manual": "پرداخت نزد فروشنده",
    "free": "حالت آزمایشی (رایگان)",
}


class Screen:
    """Base screen; subclasses override handle/draw/tick."""

    idle_timeout = True       # main loop returns to attract after idling
    led_mode = "idle"

    def __init__(self, app) -> None:
        self.app = app

    def enter(self) -> None:
        self.app.led.set_mode(self.led_mode)

    def handle(self, action: str) -> None:  # pragma: no cover
        pass

    def tick(self, dt_ms: int) -> None:
        pass

    def draw(self, surf: pygame.Surface) -> None:  # pragma: no cover
        raise NotImplementedError


def _press(t_ms: int, period: int = 1400) -> float:
    """0..1 'button press' curve: a quick sink every `period` ms."""
    p = (t_ms % period) / period
    return max(0.0, 1.0 - abs(p - 0.08) / 0.08) if p < 0.16 else 0.0


# ---------------------------------------------------------------------------
# Attract — brand slide (logo, slogan, how-to, «press red») alternating
# with the product posters; any button starts shopping
# ---------------------------------------------------------------------------

class AttractScreen(Screen):
    idle_timeout = False
    # (slide, seconds): the brand slide stays longest
    SLIDES = (("brand", 9), ("poster-1.jpg", 5), ("brand", 9), ("poster-2.jpg", 5))

    def __init__(self, app) -> None:
        super().__init__(app)
        self.t_ms = 0
        self.slide_ms = 0
        self.slide = 0

    def enter(self) -> None:
        super().enter()
        self.slide = 0
        self.slide_ms = 0

    def tick(self, dt_ms: int) -> None:
        self.t_ms += dt_ms
        self.slide_ms += dt_ms
        name, secs = self.SLIDES[self.slide]
        if self.slide_ms >= secs * 1000:
            self.slide_ms = 0
            self.slide = (self.slide + 1) % len(self.SLIDES)
            # skip posters whose file is missing
            if self.SLIDES[self.slide][0] != "brand" and \
                    self.app.theme.image(self.SLIDES[self.slide][0]) is None:
                self.slide = 0

    def handle(self, action: str) -> None:
        self.app.sounds.play("select")
        grid = self.app.go("grid")
        slot = slot_index(action)
        if slot is not None:
            grid.handle(action)   # a slot button jumps straight to its card

    def draw(self, surf: pygame.Surface) -> None:
        name = self.SLIDES[self.slide][0]
        if name == "brand":
            self._draw_brand(surf)
        else:
            self._draw_poster(surf, name)

    def _draw_brand(self, surf) -> None:
        t = self.app.theme
        t.stage(surf)
        cx = t.w // 2

        rc = t.image("recycle.png", height=40)
        if rc is not None:
            surf.blit(rc, (30, 28))

        bob = int(round(5 * math.sin(self.t_ms / 600)))
        logo = t.logo(210)
        if logo is not None:
            surf.blit(logo, logo.get_rect(center=(cx, 150 + bob)))
        slogan = t.image("chiz-slogan.png", width=300)
        if slogan is not None:
            surf.blit(slogan, slogan.get_rect(midtop=(cx, 272)))

        # how-to card (paper, kicker-rule heading, 3 numbered steps)
        card = pygame.Rect(36, 344, t.w - 72, 196)
        plate(surf, card, K["paper"])
        y = t.kicker_rule(surf, "چطوری بخرم؟", cx, card.top + 10, 140)
        steps = [
            ("دکمه‌ی کنار کالای دلخواهت رو بزن", K["alt"]),
            ("دکمه‌ی قرمز رو بزن و پرداخت کن", K["danger"]),
            ("در ویترین باز میشه؛ برش دار!", K["hi"]),
        ]
        for i, (label, col) in enumerate(steps):
            row_y = y + 14 + i * 44
            mx = card.right - 30
            marker_dot(surf, (mx, row_y + 12), 13, col)
            n = t.text(fa_digits(i + 1), "sm", K["ink"] if col == K["hi"] else K["alt_ink"])
            surf.blit(n, n.get_rect(center=(mx, row_y + 13)))
            s = t.fit_text(label, card.w - 70, ("sm", "xs"))
            surf.blit(s, s.get_rect(midright=(mx - 24, row_y + 12)))

        self._draw_cta(surf, 576)
        self._draw_footer(surf)

    def _draw_poster(self, surf, name: str) -> None:
        t = self.app.theme
        surf.fill(K["poster"])
        poster = t.image(name, width=t.w)
        if poster is not None:
            surf.blit(poster, (0, 0))
            # letterbox: continue the poster's bottom edge down the screen
            ph = poster.get_height()
            if ph < t.h:
                edge = poster.subsurface((0, ph - 24, poster.get_width(), 24))
                soft = pygame.transform.smoothscale(edge, (4, 1))   # average tones
                surf.blit(pygame.transform.smoothscale(soft, (t.w, t.h - ph)), (0, ph))
        # keep the red frame and the call to action on the poster slides too
        r = pygame.Rect(0, 0, t.w, t.h).inflate(-12, -12)
        pygame.draw.rect(surf, K["ink"], r, 12, border_radius=26)
        pygame.draw.rect(surf, K["frame"], r.inflate(-4, -4), 8, border_radius=24)
        self._draw_cta(surf, 664)

    def _draw_cta(self, surf, top: int) -> None:
        t = self.app.theme
        ticket = pygame.Rect(36, top, t.w - 72, 72)
        t.go_ticket(surf, ticket, "دکمه‌ی قرمز رو بزن", "lg", pressed=_press(self.t_ms))

    def _draw_footer(self, surf) -> None:
        t = self.app.theme
        cx = t.w // 2
        hint = t.text("هر دکمه‌ای شروع می‌کنه", "xs", K["alt_ink"], bold=False)
        surf.blit(hint, hint.get_rect(midtop=(cx, 668)))
        tag = t.text("@CHIZ_THING", "sm", K["hi"])
        made = t.text("MADE IN IRAN", "xs", K["alt_ink"])
        surf.blit(tag, tag.get_rect(midtop=(cx, 712)))
        surf.blit(made, made.get_rect(midtop=(cx, 740)))


# ---------------------------------------------------------------------------
# Product grid — 2×3 per page, one physical button per card
# ---------------------------------------------------------------------------

class GridScreen(Screen):
    TOP = 84
    CARD_H = 170
    GAP_Y = 22
    MARGIN_X = 36
    GAP_X = 20

    def __init__(self, app) -> None:
        super().__init__(app)
        self.products: list[Product] = []
        self.page = 0
        self.selected: int | None = None   # index into self.products
        self.cards: list[ProductCard] = []
        self.images: dict[tuple, pygame.Surface | None] = {}
        self.flash: dict[int, float] = {}
        self.nudge_ms = 0                  # «pick something first» hint
        self.t_ms = 0
        self.reload_products()

    # data / layout -----------------------------------------------------

    @property
    def pages(self) -> int:
        return max(1, math.ceil(len(self.products) / PER_PAGE))

    def reload_products(self) -> None:
        keep = None
        if self.selected is not None and self.selected < len(self.products):
            keep = self.products[self.selected].id
        self.products = self.app.booth.products.list_active()
        self.page = min(self.page, self.pages - 1)
        self.selected = next((i for i, p in enumerate(self.products) if p.id == keep), None)
        self.images.clear()
        self._layout()

    def reset(self) -> None:
        self.page = 0
        self.selected = None
        self.reload_products()

    def _layout(self) -> None:
        t = self.app.theme
        card_w = (t.w - self.MARGIN_X * 2 - self.GAP_X) // COLS
        self.cards = []
        start = self.page * PER_PAGE
        for pos, p in enumerate(self.products[start:start + PER_PAGE]):
            row, col = divmod(pos, COLS)
            # RTL: the first card of each row is on the RIGHT
            x = t.w - self.MARGIN_X - card_w - col * (card_w + self.GAP_X)
            y = self.TOP + 12 + row * (self.CARD_H + self.GAP_Y)
            side = "right" if col == 0 else "left"
            card = ProductCard(p, pygame.Rect(x, y, card_w, self.CARD_H), t,
                               slot=pos + 1, side=side)
            key = (p.id, p.image_path)
            if key not in self.images:
                self.images[key] = load_product_image(
                    DATA_DIR, p.image_path, card_w - 24, self.CARD_H - 82)
            card.image = self.images[key]
            self.cards.append(card)

    def _set_page(self, page: int) -> None:
        page = max(0, min(self.pages - 1, page))
        if page != self.page:
            self.page = page
            self._layout()

    # interaction -------------------------------------------------------

    def handle(self, action: str) -> None:
        n = len(self.products)
        slot = slot_index(action)
        if slot is not None:
            self._press_slot(slot)
        elif action == "confirm":
            if self.selected is None:
                self.app.sounds.play("back")
                self.nudge_ms = 1600
            else:
                self.app.sounds.play("select")
                self.app.open_confirm(self.products[self.selected])
        elif action == "cancel":
            self.app.sounds.play("back")
            if self.selected is not None:
                self.selected = None
            else:
                self.app.go("attract")
        elif n and action in ("up", "down", "left", "right"):
            self._move(action)

    def _press_slot(self, slot: int) -> None:
        if slot >= len(self.cards):
            self.app.sounds.play("back")
            return
        idx = self.page * PER_PAGE + slot
        self.flash[slot] = 1.0
        if self.products[idx].stock <= 0:
            self.app.sounds.play("error")
            self.app.led.error()
            return
        if self.selected == idx:
            # second press on the same button = go (handy with one hand)
            self.app.sounds.play("select")
            self.app.open_confirm(self.products[idx])
            return
        self.selected = idx
        self.app.sounds.play("move")

    def _move(self, action: str) -> None:
        """Joystick / page buttons: walk the selection, crossing pages."""
        n = len(self.products)
        if self.selected is None:
            self.selected = self.page * PER_PAGE
        else:
            i = self.selected
            col = (i % PER_PAGE) % COLS
            step = {"up": -COLS, "down": COLS}.get(action, 0)
            if action == "right" and col == 1:
                step = -1           # RTL: right goes back to column 0
            elif action == "left" and col == 0:
                step = 1
            j = i + step
            if step == 0 or not (0 <= j < n):
                return
            self.selected = j
        self._set_page(self.selected // PER_PAGE)
        self.app.sounds.play("move")

    def tick(self, dt_ms: int) -> None:
        self.t_ms += dt_ms
        self.nudge_ms = max(0, self.nudge_ms - dt_ms)
        for k in list(self.flash):
            self.flash[k] = max(0.0, self.flash[k] - dt_ms / 140)
            if self.flash[k] == 0.0:
                del self.flash[k]

    # drawing -----------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        t = self.app.theme
        t.stage(surf)
        self._draw_header(surf, t)

        if not self.products:
            box = pygame.Rect(40, 280, t.w - 80, 160)
            plate(surf, box, K["paper"])
            msg = t.text("فعلاً کالایی نداریم", "lg", K["ink"], "display")
            surf.blit(msg, msg.get_rect(center=(box.centerx, box.centery - 16)))
            sub = t.text("به‌زودی برمی‌گردیم!", "sm", K["muted"])
            surf.blit(sub, sub.get_rect(center=(box.centerx, box.centery + 30)))
        start = self.page * PER_PAGE
        for pos, card in enumerate(self.cards):
            card.selected = (start + pos == self.selected)
            card.flash = self.flash.get(pos, 0.0)
            card.draw(surf)

        self._draw_action_bar(surf, t)

    def _draw_header(self, surf, t) -> None:
        logo = t.image("chiz-wordmark.png", height=60)
        right = t.w - 24
        if logo is not None:
            r = logo.get_rect(topright=(right, 14))
            surf.blit(logo, r)
            right = r.left - 10
        t.kicker(surf, "باجه‌ی فروش", {"topright": (right, 30)},
                 color=K["alt_ink"], marker=K["hi"], size="sm")
        if self.pages > 1:
            t.sticker(surf, f"صفحه {fa_digits(self.page + 1)} از {fa_digits(self.pages)}",
                      {"topleft": (28, 26)}, size="xs")
        else:
            t.kicker(surf, "قیمت‌ها به تومان", {"topleft": (28, 32)},
                     color=K["alt_ink"], size="xs")

    def _draw_action_bar(self, surf, t) -> None:
        bar_top = self.TOP + 12 + 3 * (self.CARD_H + self.GAP_Y) + 4
        ticket = pygame.Rect(36, bar_top, t.w - 72, 64)
        if self.selected is not None:
            p = self.products[self.selected]
            t.go_ticket(surf, ticket, f"خرید {p.name}", "md",
                        pressed=_press(self.t_ms, 1600))
            info = f"{price_fa(p.price_toman)} تومان  •  قرمز: خرید"
        else:
            # the hint card: arrows point out to the side buttons
            plate(surf, ticket, K["hi"] if self.nudge_ms else K["paper"])
            lab = t.fit_text("دکمه‌ی کنار کالا رو بزن", ticket.w - 90, ("md", "sm"))
            surf.blit(lab, lab.get_rect(center=ticket.center))
            arrow(surf, (ticket.right - 14, ticket.centery), 14, "right")
            arrow(surf, (ticket.left + 14, ticket.centery), 14, "left")
            info = "بعد دکمه‌ی قرمز"
        # footer: info on the start side, the cancel hint over the real button
        foot_y = ticket.bottom + 20
        t.kicker(surf, info, {"midright": (t.w - 36, foot_y)},
                 color=K["alt_ink"], size="xs", marker=K["danger"], round_marker=True)
        cancel = pygame.Rect(36, foot_y - 15, 112, 30)
        plate(surf, cancel, K["paper"], shadow=OFF_SM)
        lab = t.text("انصراف" if self.selected is None else "بی‌خیال", "xs")
        surf.blit(lab, lab.get_rect(midright=(cancel.right - 10, cancel.centery)))
        arrow(surf, (cancel.left + 16, cancel.centery + 7), 8, "down")


# ---------------------------------------------------------------------------
# Confirm — product summary, price headline, red-button ticket
# ---------------------------------------------------------------------------

class ConfirmScreen(Screen):
    def __init__(self, app, product: Product, qty: int = 1) -> None:
        super().__init__(app)
        self.product = product
        self.qty = qty
        self.total = product.price_toman * qty
        self.image = load_product_image(DATA_DIR, product.image_path, 190, 190)
        self.error = ""
        self.t_ms = 0

    def handle(self, action: str) -> None:
        if action == "confirm" and self.error:
            self.app.go("grid")
        elif action == "confirm":
            self.app.sounds.play("coin")
            if not self.app.create_order(self.product, self.qty):
                self.error = "این کالا همین الان تمام شد"
                self.app.sounds.play("error")
        elif action == "cancel":
            self.app.sounds.play("back")
            self.app.go("grid")

    def tick(self, dt_ms: int) -> None:
        self.t_ms += dt_ms

    def draw(self, surf: pygame.Surface) -> None:
        t = self.app.theme
        t.stage(surf)
        box = pygame.Rect(24, 64, t.w - 48, 640)
        t.modal(surf, box)
        cx = box.centerx
        t.title_box(surf, "تأیید خرید", {"midtop": (cx, box.top - 22)}, "md")

        img_box = pygame.Rect(0, 0, 210, 210)
        img_box.midtop = (cx, box.top + 44)
        plate(surf, img_box, K["paper_2"], shadow=OFF_SM)
        if self.image is not None:
            surf.blit(self.image, self.image.get_rect(center=img_box.center))
        else:
            ph = t.logo(120, alpha=90)
            if ph is not None:
                surf.blit(ph, ph.get_rect(center=img_box.center))
        pygame.draw.rect(surf, K["ink"], img_box, 3, border_radius=10)

        y = img_box.bottom + 18
        name = t.fit_text(self.product.name, box.w - 60, ("lg", "md", "sm"))
        surf.blit(name, name.get_rect(midtop=(cx, y)))
        y += name.get_height() + 4
        y = t.kicker_rule(surf, f"{fa_digits(self.qty)} عدد", cx, y, 120, "xs")

        # price headline in the brand's comic burst, «تومان» beside it
        burst_r = t.price_burst(surf, (cx + 18, y + 44), price_fa(self.total), 230, 84, "xl")
        cur = t.text("تومان", "sm", K["muted"])
        surf.blit(cur, cur.get_rect(midright=(burst_r.left - 2, burst_r.centery + 4)))
        y += 98

        method = PROVIDER_LABEL.get(self.app.provider.name, self.app.provider.name)
        t.kicker(surf, method, {"midtop": (cx, y)}, size="xs", marker=K["alt"],
                 round_marker=True)
        y += 34

        if self.error:
            t.sticker(surf, self.error, {"midtop": (cx, y - 6)}, size="xs",
                      color=K["danger"], border=K["danger"])
            y += 30

        ticket = pygame.Rect(box.left + 24, max(y, box.bottom - 150), box.w - 48, 68)
        t.go_ticket(surf, ticket, "پرداخت", "lg", pressed=_press(self.t_ms, 1600),
                    disabled=bool(self.error))
        cancel = pygame.Rect(box.left + 24, ticket.bottom + 18, box.w - 48, 46)
        t.button(surf, cancel, "انصراف", "paper", "md")

        hint = t.text("قرمز: پرداخت   •   انصراف: برگشت", "xs", K["alt_ink"], bold=False)
        surf.blit(hint, hint.get_rect(midtop=(cx, box.bottom + 22)))
