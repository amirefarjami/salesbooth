"""CHIZ Booth — kiosk screens: attract, product grid (cart), cart review,
payment method.

Panel: a 2×3 product grid on a portrait 480×800 screen with one button
beside each card — 1, 3, 5 down the LEFT side, 2, 4, 6 down the RIGHT —
plus the red confirm button (the only lit one) and «انصراف».

Flow: product button → into the cart (and its details show) → red → cart
review → red → pick QR (button 1) or card reader (button 2) → red → pay →
success animation → showcase unlocked for the operator → door sensor
starts the countdown.
"""
from __future__ import annotations

import math

import pygame

from core.config import DATA_DIR
from core.fa import fa_digits
from core.models import Product
from hardware.input import slot_index
from kiosk.theme import K, OFF_SM, arrow, marker_dot, plate, selected_card
from kiosk.widgets import ProductCard, load_product_image, price_fa, slot_tag

SLOTS = 6
COLS = 2

METHOD_INFO = {   # method: (title, subtitle)
    "qr": ("کیوآر کد", "با دوربین گوشی"),
    "card": ("کارتخوان", "کارت بانکی"),
}


class Screen:
    """Base screen; subclasses override handle/draw/tick."""

    idle_timeout = True       # main loop returns to attract after idling
    led_mode = "idle"

    def __init__(self, app) -> None:
        self.app = app

    def enter(self) -> None:
        self.app.led.set_mode(self.led_mode)

    def red_light(self) -> str:
        """Lamp in the red button: 'off' | 'on' | 'blink'."""
        return "off"

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


def slot_geometry(t, top: int = 84, card_h: int = 150, gap_y: int = 20,
                  margin_x: int = 36, gap_x: int = 20):
    """Card rect + side for slots 1..6: odd slots on the left column (next to
    the left buttons), even slots on the right."""
    card_w = (t.w - margin_x * 2 - gap_x) // COLS
    out = []
    for pos in range(SLOTS):
        row, col = divmod(pos, COLS)
        x = margin_x + col * (card_w + gap_x)
        y = top + 12 + row * (card_h + gap_y)
        out.append((pygame.Rect(x, y, card_w, card_h), "left" if col == 0 else "right"))
    return out


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

    def red_light(self) -> str:
        return "blink"            # «press the red button» is the call to action

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
        if action == "confirm":               # only the red button starts
            self.app.sounds.play("select")
            self.app.go("grid")

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
            ("دکمه‌ی کنار هر کالا = بنداز تو سبد", K["alt"]),
            ("دکمه‌ی قرمز = پرداخت با کیوآر یا کارت", K["danger"]),
            ("در ویترین باز می‌شه؛ خریدت رو بردار", K["hi"]),
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

        tag = t.text("@CHIZ_THING", "sm", K["hi"])
        made = t.text("MADE IN IRAN", "xs", K["alt_ink"])
        surf.blit(tag, tag.get_rect(midtop=(cx, 712)))
        surf.blit(made, made.get_rect(midtop=(cx, 740)))


# ---------------------------------------------------------------------------
# Product grid — every product button drops one into the cart
# ---------------------------------------------------------------------------

class GridScreen(Screen):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.products: list[Product] = []
        self.cards: list[ProductCard] = []
        self.images: dict[tuple, pygame.Surface | None] = {}
        self.flash: dict[int, float] = {}
        self.pops: list[list] = []         # floating «+۱» [x, y, age_ms, text]
        self.focus: int | None = None      # slot whose details are shown
        self.toast = ""                    # short message over the action bar
        self.toast_ms = 0
        self.nudge_ms = 0
        self.t_ms = 0
        self.reload_products()

    # data / layout -----------------------------------------------------

    def reload_products(self) -> None:
        """First six active products (admin sort order) — one per button."""
        self.products = self.app.booth.products.list_active()[:SLOTS]
        self.images.clear()
        self._layout()

    def reset(self) -> None:
        self.focus = None
        self.pops.clear()
        self.toast = ""
        self.reload_products()

    def _layout(self) -> None:
        t = self.app.theme
        self.cards = []
        for pos, (p, (rect, side)) in enumerate(zip(self.products, slot_geometry(t))):
            card = ProductCard(p, rect, t, slot=pos + 1, side=side)
            key = (p.id, p.image_path)
            if key not in self.images:
                self.images[key] = load_product_image(
                    DATA_DIR, p.image_path, rect.w - 24, rect.h - 72)
            card.image = self.images[key]
            self.cards.append(card)
        if self.focus is not None and self.focus >= len(self.cards):
            self.focus = None

    def _say(self, msg: str) -> None:
        self.toast, self.toast_ms = msg, 1800

    # interaction -------------------------------------------------------

    def red_light(self) -> str:
        return "blink" if self.app.cart else "off"

    def handle(self, action: str) -> None:
        slot = slot_index(action)
        if slot is not None:
            self._press_slot(slot)
        elif action == "confirm":
            if self.app.cart:
                self.app.sounds.play("select")
                self.app.open_cart()
            else:
                self.app.sounds.play("back")
                self.nudge_ms = 1600
        elif action == "cancel":
            if self.app.cart_log:
                pid = self.app.cart_remove_last()
                name = next((p.name for p in self.products if p.id == pid), "")
                self._say(f"«{name}» از سبد برداشته شد")
                self.app.sounds.play("back")
            else:
                self.app.sounds.play("back")
                self.app.go("attract")

    def _press_slot(self, slot: int) -> None:
        if slot >= len(self.cards):
            self.app.sounds.play("back")
            return
        card = self.cards[slot]
        self.focus = slot
        self.flash[slot] = 1.0
        if card.left <= 0:
            self.app.sounds.play("error")
            self.app.led.error()
            self._say("از این کالا بیشتر نداریم")
            return
        self.app.cart_add(card.product.id)
        self.app.sounds.play("coin")
        self.pops.append([card.rect.centerx, card.rect.top + 40, 0, "+۱"])

    def tick(self, dt_ms: int) -> None:
        self.t_ms += dt_ms
        self.nudge_ms = max(0, self.nudge_ms - dt_ms)
        self.toast_ms = max(0, self.toast_ms - dt_ms)
        for k in list(self.flash):
            self.flash[k] = max(0.0, self.flash[k] - dt_ms / 160)
            if self.flash[k] == 0.0:
                del self.flash[k]
        for pop in self.pops:
            pop[2] += dt_ms
        self.pops = [p for p in self.pops if p[2] < 700]

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
        for pos, card in enumerate(self.cards):
            card.in_cart = self.app.cart.get(card.product.id, 0)
            card.selected = pos == self.focus
            card.flash = self.flash.get(pos, 0.0)
            card.draw(surf)
        for x, y, age, text in self.pops:   # «+۱» floats up and fades
            k = age / 700
            s = t.text(text, "lg", K["hi"], "display").copy()
            s.set_alpha(int(255 * (1 - k)))
            surf.blit(s, s.get_rect(center=(x, y - int(60 * k))))

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
        t.kicker(surf, "قیمت‌ها به تومان", {"topleft": (28, 32)},
                 color=K["alt_ink"], size="xs")

    def _draw_action_bar(self, surf, t) -> None:
        top = slot_geometry(t)[-1][0].bottom + 14
        # 1) details of the product last pressed (or the hint)
        info = pygame.Rect(36, top, t.w - 72, 46)
        if self.toast_ms:
            plate(surf, info, K["hi"], shadow=OFF_SM)
            s = t.fit_text(self.toast, info.w - 20, ("sm", "xs"))
            surf.blit(s, s.get_rect(center=info.center))
        elif self.focus is not None:
            card = self.cards[self.focus]
            p = card.product
            plate(surf, info, K["paper"], shadow=OFF_SM)
            name = t.fit_text(p.name, 180, ("sm", "xs"), K["ink"], "display")
            surf.blit(name, name.get_rect(midright=(info.right - 14, info.centery)))
            det = t.text(f"{price_fa(p.price_toman)} تومان  •  موجودی {fa_digits(card.left)}",
                         "xs", K["muted"])
            surf.blit(det, det.get_rect(midleft=(info.left + 12, info.centery)))
        else:
            plate(surf, info, K["hi"] if self.nudge_ms else K["paper"], shadow=OFF_SM)
            s = t.fit_text("دکمه‌ی کنار هر کالا = بنداز تو سبد", info.w - 70, ("sm", "xs"))
            surf.blit(s, s.get_rect(center=info.center))
            arrow(surf, (info.left + 12, info.centery), 10, "left")
            arrow(surf, (info.right - 12, info.centery), 10, "right")

        # 2) the cart ticket — red takes you to checkout
        ticket = pygame.Rect(36, info.bottom + 14, t.w - 72, 60)
        count = self.app.cart_count()
        if count:
            t.go_ticket(surf, ticket, "سبد خرید و پرداخت", "md",
                        pressed=_press(self.t_ms, 1600))
            foot = f"{fa_digits(count)} کالا  •  {price_fa(self.app.cart_total())} تومان"
        else:
            t.go_ticket(surf, ticket, "سبد خرید خالیه", "md", disabled=True)
            foot = "اول یه کالا انتخاب کن"
        foot_y = ticket.bottom + 20
        t.kicker(surf, foot, {"midright": (t.w - 36, foot_y)},
                 color=K["alt_ink"], size="xs", marker=K["danger"], round_marker=True)
        hint = "انصراف: برداشتن آخری" if count else "انصراف: برگشت"
        h = t.text(hint, "xs", K["alt_ink"], bold=False)
        surf.blit(h, h.get_rect(midleft=(36, foot_y)))


# ---------------------------------------------------------------------------
# Cart review — what is in the cart, the total, red = choose payment
# ---------------------------------------------------------------------------

class CartScreen(Screen):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.t_ms = 0

    def red_light(self) -> str:
        return "blink"

    def handle(self, action: str) -> None:
        if action == "confirm":
            self.app.sounds.play("select")
            self.app.open_methods()
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
        t.title_box(surf, "سبد خرید", {"midtop": (cx, box.top - 22)}, "md")

        y = box.top + 44
        for line in self.app.cart_lines():
            p, qty = line
            row = pygame.Rect(box.left + 20, y, box.w - 40, 52)
            pygame.draw.line(surf, K["line"], (row.left, row.bottom), (row.right, row.bottom), 2)
            name = t.fit_text(p.name, 190, ("sm", "xs"), K["ink"], "display")
            surf.blit(name, name.get_rect(midright=(row.right, row.centery)))
            q = t.text(f"×{fa_digits(qty)}", "md", K["alt"], "display")
            surf.blit(q, q.get_rect(center=(row.centerx - 30, row.centery + 2)))
            lt = t.text(f"{price_fa(p.price_toman * qty)}", "sm")
            surf.blit(lt, lt.get_rect(midleft=(row.left, row.centery)))
            y += 56

        total_y = max(y + 26, box.top + 330)
        lab = t.text("جمع کل", "sm", K["muted"])
        surf.blit(lab, lab.get_rect(midright=(box.right - 24, total_y + 40)))
        burst_r = t.price_burst(surf, (cx - 20, total_y + 40),
                                price_fa(self.app.cart_total()), 220, 82, "xl")
        cur = t.text("تومان", "sm", K["muted"])
        surf.blit(cur, cur.get_rect(midright=(burst_r.left - 2, burst_r.centery + 4)))

        ticket = pygame.Rect(box.left + 24, box.bottom - 150, box.w - 48, 68)
        t.go_ticket(surf, ticket, "انتخاب روش پرداخت", "md", pressed=_press(self.t_ms, 1600))
        back = pygame.Rect(box.left + 24, ticket.bottom + 18, box.w - 48, 46)
        t.button(surf, back, "انصراف: برگشت به محصولات", "paper", "md")


# ---------------------------------------------------------------------------
# Payment method — button 1 (left) = QR, button 2 (right) = card reader
# ---------------------------------------------------------------------------

class MethodScreen(Screen):
    SLOT_OF = {"qr": 0, "card": 1}

    def __init__(self, app) -> None:
        super().__init__(app)
        self.methods = [m for m in app.cfg.payment_methods if m in self.SLOT_OF] or ["card"]
        self.choice: str | None = self.methods[0] if len(self.methods) == 1 else None
        self.t_ms = 0
        self.error = ""

    def red_light(self) -> str:
        return "blink" if self.choice else "off"

    def handle(self, action: str) -> None:
        slot = slot_index(action)
        if slot is not None:
            pick = next((m for m in self.methods if self.SLOT_OF[m] == slot), None)
            if pick is None:
                self.app.sounds.play("back")
                return
            self.choice = pick
            self.error = ""
            self.app.sounds.play("move")
        elif action == "confirm":
            if not self.choice:
                self.app.sounds.play("back")
                return
            self.app.sounds.play("coin")
            if not self.app.create_order(self.choice):
                self.error = "یکی از کالاها همین الان تموم شد"
                self.app.sounds.play("error")
        elif action == "cancel":
            self.app.sounds.play("back")
            self.app.open_cart()

    def tick(self, dt_ms: int) -> None:
        self.t_ms += dt_ms

    def draw(self, surf: pygame.Surface) -> None:
        t = self.app.theme
        t.stage(surf)
        cx = t.w // 2
        t.title_box(surf, "روش پرداخت", {"midtop": (cx, 22)}, "md")
        geo = slot_geometry(t)
        for m in ("qr", "card"):
            rect, side = geo[self.SLOT_OF[m]]
            rect = rect.inflate(0, 40).move(0, 30)
            on = m in self.methods
            if not on:
                plate(surf, rect, K["paper_2"], shadow=0, dashed=True, border=K["muted"])
            elif self.choice == m:
                selected_card(surf, rect)
            else:
                plate(surf, rect, K["paper"])
            icon_c = (rect.centerx, rect.top + 64)
            (_qr_icon if m == "qr" else _card_icon)(surf, icon_c, K["ink"] if on else K["muted"])
            title, sub = METHOD_INFO[m]
            tt = t.text(title, "sm", K["ink"] if on else K["muted"], "display")
            surf.blit(tt, tt.get_rect(midtop=(rect.centerx, rect.top + 112)))
            st = t.text(sub if on else "فعلاً غیرفعال", "xs", K["muted"])
            surf.blit(st, st.get_rect(midtop=(rect.centerx, rect.top + 150)))
            x = rect.left if side == "left" else rect.right
            slot_tag(surf, t, (x, rect.centery), self.SLOT_OF[m] + 1, muted=not on)

        y = geo[0][0].bottom + 100
        plate(surf, pygame.Rect(36, y, t.w - 72, 64), K["paper"], shadow=OFF_SM)
        lab = t.text("مبلغ قابل پرداخت", "xs", K["muted"])
        surf.blit(lab, lab.get_rect(midright=(t.w - 50, y + 32)))
        amt = t.text(f"{price_fa(self.app.cart_total())} تومان", "lg", K["ink"], "display")
        surf.blit(amt, amt.get_rect(midleft=(50, y + 34)))

        if self.error:
            t.sticker(surf, self.error, {"midtop": (cx, y + 84)}, size="xs",
                      color=K["danger"], border=K["danger"])
        ticket = pygame.Rect(36, 612, t.w - 72, 64)
        label = "پرداخت" if self.choice else "اول روش پرداخت رو بزن"
        t.go_ticket(surf, ticket, label, "md", pressed=_press(self.t_ms, 1600),
                    disabled=not self.choice)
        h = t.text("دکمه‌ی ۱: کیوآر  •  دکمه‌ی ۲: کارتخوان  •  انصراف: برگشت",
                   "xs", K["alt_ink"], bold=False)
        surf.blit(h, h.get_rect(midtop=(cx, ticket.bottom + 20)))


def _qr_icon(surf, center, color) -> None:
    cx, cy = center
    box = pygame.Rect(0, 0, 70, 70)
    box.center = (cx, cy)
    pygame.draw.rect(surf, (255, 255, 255), box, border_radius=6)
    pygame.draw.rect(surf, color, box, 3, border_radius=6)
    for dx, dy in ((-1, -1), (1, -1), (-1, 1)):
        f = pygame.Rect(0, 0, 20, 20)
        f.center = (cx + dx * 18, cy + dy * 18)
        pygame.draw.rect(surf, color, f, 4)
        pygame.draw.rect(surf, color, f.inflate(-12, -12))
    for i, (dx, dy) in enumerate(((10, 10), (20, 14), (14, 22), (22, 24), (6, 22))):
        pygame.draw.rect(surf, color, (cx + dx - 3, cy + dy - 3, 6, 6))


def _card_icon(surf, center, color) -> None:
    cx, cy = center
    body = pygame.Rect(0, 0, 54, 76)
    body.center = (cx, cy)
    pygame.draw.rect(surf, K["paper_2"], body, border_radius=8)
    pygame.draw.rect(surf, color, body, 3, border_radius=8)
    screen = pygame.Rect(body.left + 9, body.top + 9, body.w - 18, 18)
    pygame.draw.rect(surf, K["alt"], screen, border_radius=3)
    for r in range(3):
        for c in range(3):
            pygame.draw.rect(surf, color, (body.left + 11 + c * 12, body.top + 34 + r * 11, 8, 7),
                             border_radius=2)
    card = pygame.Rect(0, 0, 44, 28)
    card.midbottom = (cx + 26, body.top + 14)
    pygame.draw.rect(surf, K["hi"], card, border_radius=4)
    pygame.draw.rect(surf, color, card, 2, border_radius=4)
