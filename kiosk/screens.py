"""CHIZ Booth — kiosk screens: attract, product grid, order confirmation."""
from __future__ import annotations

import math
import random
from pathlib import Path

import pygame

from core.config import DATA_DIR
from core.fa import fa_digits, shape
from kiosk.theme import BTN_COLORS, PAL, lerp_color
from kiosk.widgets import Modal, ProductCard, load_product_image

ACTION_ORDER = ("up", "down", "left", "right", "confirm", "cancel")


class Screen:
    """Base screen; subclasses override handle/draw/tick."""

    def __init__(self, app) -> None:
        self.app = app

    def handle(self, action: str) -> None:  # pragma: no cover
        pass

    def tick(self, dt_ms: int) -> None:
        pass

    def draw(self, surf: pygame.Surface) -> None:  # pragma: no cover
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Attract mode — bouncing CHIZ logo + "press the red button" blink
# ---------------------------------------------------------------------------

class AttractScreen(Screen):
    def __init__(self, app) -> None:
        super().__init__(app)
        t = app.theme
        self.blink = 0.0
        self.logo = self._make_logo(t.fonts.px("title"), t.fonts.fa("title"))
        lx = random.randint(60, t.w - 60 - self.logo.get_width())
        ly = random.randint(80, t.h // 3)
        self.pos = [float(lx), float(ly)]
        self.vel = [130.0, 96.0]
        self.hint = t.fonts.fa("lg")
        self.sub = t.fonts.fa("sm")

    def _make_logo(self, f_px, f_fa) -> pygame.Surface:
        px = f_px.render("CHIZ", True, PAL["amber"])
        fa = f_fa.render(shape("باجه فروش چیز"), True, PAL["cream"])
        w = max(px.get_width(), fa.get_width()) + 40
        h = px.get_height() + fa.get_height() + 34
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(s, (16, 20, 52), (0, 0, w, h), border_radius=4)
        pygame.draw.rect(s, PAL["border_hi"], (0, 0, w, h), 3)
        s.blit(px, px.get_rect(midtop=(w // 2, 14)))
        s.blit(fa, fa.get_rect(midbottom=(w // 2, h - 12)))
        return s

    def tick(self, dt_ms: int) -> None:
        dt = dt_ms / 1000.0
        w, h = self.app.theme.w, self.app.theme.h
        self.pos[0] += self.vel[0] * dt
        self.pos[1] += self.vel[1] * dt
        if self.pos[0] <= 8 or self.pos[0] + self.logo.get_width() >= w - 8:
            self.vel[0] *= -1
            self.pos[0] = max(8, min(self.pos[0], w - 8 - self.logo.get_width()))
        if self.pos[1] <= 8 or self.pos[1] + self.logo.get_height() >= h - 8:
            self.vel[1] *= -1
            self.pos[1] = max(8, min(self.pos[1], h - 8 - self.logo.get_height()))
        self.blink += dt

    def handle(self, action: str) -> None:
        self.app.sounds.play("select")
        self.app.go("grid")

    def draw(self, surf: pygame.Surface) -> None:
        t = self.app.theme
        surf.fill(PAL["bg_deep"])
        # starfield
        for (sx, sy, spd) in self.app.stars:
            y = (sy + pygame.time.get_ticks() * spd * 0.02) % t.h
            surf.fill((60, 70, 130), (sx, int(y), 2, 2))
        surf.blit(self.logo, (int(self.pos[0]), int(self.pos[1])))
        if (self.blink % 1.0) < 0.62:
            ts = self.hint.render(shape("دکمه قرمز را بزن"), True, PAL["red"])
            surf.blit(ts, ts.get_rect(midbottom=(t.w // 2, t.h - 90)))
        sub = self.sub.render(shape("برای شروع خرید"), True, PAL["gray"])
        surf.blit(sub, sub.get_rect(midtop=(t.w // 2, t.h - 84)))
        self._draw_button_legend(surf, t, cy=t.h - 44)

    def _draw_button_legend(self, surf, t, cy: int) -> None:
        items = [("up", "بالا"), ("down", "پایین"), ("left", "چپ"),
                 ("right", "راست"), ("confirm", "تأیید")]
        widths = []
        for key, label in items:
            f = t.fonts.fa("xs")
            widths.append(22 + 8 + f.size(shape(label))[0] + 14)
        total = sum(widths)
        x = (t.w - total) // 2
        for (key, label), w in zip(items, widths):
            color = BTN_COLORS[key]
            pygame.draw.circle(surf, color, (x + 11, cy), 9)
            pygame.draw.circle(surf, lerp_color(color, (255, 255, 255), 0.35),
                               (x + 8, cy - 3), 3)
            f = t.fonts.fa("xs")
            ts = f.render(shape(label), True, PAL["cream"])
            surf.blit(ts, (x + 24, cy - ts.get_height() // 2))
            x += w


# ---------------------------------------------------------------------------
# Product grid — 2 columns, vertical scroll, 5-button navigation
# ---------------------------------------------------------------------------

class GridScreen(Screen):
    COLS = 2

    def __init__(self, app) -> None:
        super().__init__(app)
        self.products = app.booth.products.list_active()
        self.index = 0
        self.scroll = 0.0            # pixels of vertical scroll (positive = up)
        self.cards: list[ProductCard] = []
        self.images: dict[int, pygame.Surface] = {}
        self._layout()
        self.hint_font = app.theme.fonts.fa("xs")

    # layout ------------------------------------------------------------

    def _layout(self) -> None:
        t = self.app.theme
        self.top_bar = 64
        self.bottom_bar = 56
        pad = 14
        card_w = (t.w - pad * 3) // self.COLS
        card_h = 196
        self.card_h = card_h
        self.cards = []
        for i, p in enumerate(self.products):
            col = i % self.COLS
            row = i // self.COLS
            x = pad + col * (card_w + pad)
            y = self.top_bar + pad + row * (card_h + pad)
            self.cards.append(ProductCard(p, pygame.Rect(x, y, card_w, card_h), t))
        self.content_h = (self.top_bar + pad + len(self.products) * (card_h + pad)
                          + pad + self.bottom_bar)
        self.max_scroll = max(0, self.content_h - t.h)

    def reload_products(self) -> None:
        self.products = self.app.booth.products.list_active()
        self.index = min(self.index, max(0, len(self.products) - 1))
        self._layout()

    # helpers -----------------------------------------------------------

    def _visible_rows(self) -> tuple[int, int]:
        first = max(0, int(self.scroll) // (self.card_h + 14) - 1)
        rows_on_screen = (self.app.theme.h // (self.card_h + 14)) + 3
        return first, first + rows_on_screen

    def _ensure_visible(self) -> None:
        card = self.cards[self.index]
        y0, y1 = int(self.scroll), int(self.scroll) + self.app.theme.h
        top, bottom = card.rect.y, card.rect.y + card.rect.h
        margin = self.top_bar + 8
        if top - margin < y0:
            self.scroll = max(0, top - margin)
        elif bottom + self.bottom_bar > y1:
            self.scroll = min(self.max_scroll, bottom + self.bottom_bar - self.app.theme.h)

    def _image_for(self, idx: int) -> pygame.Surface | None:
        p = self.products[idx]
        if p.id not in self.images:
            card = self.cards[idx]
            self.images[p.id] = load_product_image(
                DATA_DIR, p.image_path, card.rect.w - 24, card.rect.h - 66)
        return self.images[p.id]

    # interaction -------------------------------------------------------

    def handle(self, action: str) -> None:
        n = len(self.products)
        if n == 0:
            if action == "confirm":
                self.app.sounds.play("back")
            return
        if action == "left" and self.index % self.COLS == 1:
            self.index -= 1
        elif action == "right" and self.index % self.COLS == 0 and self.index + 1 < n:
            self.index += 1
        elif action == "up" and self.index - self.COLS >= 0:
            self.index -= self.COLS
        elif action == "down" and self.index + self.COLS < n:
            self.index += self.COLS
        elif action == "confirm":
            self.app.sounds.play("select")
            self.app.open_confirm(self.products[self.index])
            return
        elif action == "cancel":
            self.app.sounds.play("back")
            self.app.go("attract")
            return
        else:
            return
        self.app.sounds.play("move")
        self._ensure_visible()

    def draw(self, surf: pygame.Surface) -> None:
        t = self.app.theme
        surf.fill(PAL["bg"])
        # header
        title = t.fonts.fa("lg").render(shape("چی می‌خوری؟"), True, PAL["amber"])
        surf.blit(title, title.get_rect(midtop=(t.w // 2, 12)))
        pygame.draw.line(surf, PAL["border"], (16, 58), (t.w - 16, 58), 2)

        # save scroll position, draw at unscrolled coords, restore
        old_y = [c.rect.y for c in self.cards]
        for i, card in enumerate(self.cards):
            card.rect.y -= int(self.scroll)
        first, last = self._visible_rows()
        for i, card in enumerate(self.cards):
            row = i // self.COLS
            if first <= row <= last:
                card.selected = (i == self.index)
                card.image = self._image_for(i)
                card.draw(surf)
        for card, y in zip(self.cards, old_y):
            card.rect.y = y

        # stock warning on selected card
        if self.products:
            p = self.products[self.index]
            if p.stock <= 2:
                msg = "آخرین تعداد!" if p.stock == 1 else f"فقط {fa_digits(p.stock)} عدد"
                warn = self.hint_font.render(shape(msg), True, PAL["red"])
                surf.blit(warn, warn.get_rect(midbottom=(t.w // 2, t.h - 40)))

        self._draw_footer(surf, t)

    def _draw_footer(self, surf, t) -> None:
        pygame.draw.rect(surf, PAL["bg_deep"], (0, t.h - 50, t.w, 50))
        pygame.draw.line(surf, PAL["border"], (0, t.h - 50), (t.w, t.h - 50), 2)
        n = len(self.products)
        if n:
            pos = t.fonts.px("sm").render(
                f"{self.index + 1}/{n}", True, PAL["gray"])
            surf.blit(pos, (12, t.h - 36))
        hint = self.hint_font.render(
            shape("قرمز: انتخاب  |  جهتی: حرکت  |  خروج: لغو"), True, PAL["gray"])
        surf.blit(hint, hint.get_rect(midright=(t.w - 12, t.h - 25)))


# ---------------------------------------------------------------------------
# Confirm screen — product summary + big red confirm / cancel
# ---------------------------------------------------------------------------

class ConfirmScreen(Screen):
    def __init__(self, app, product: Product, qty: int = 1) -> None:
        super().__init__(app)
        self.product = product
        self.qty = qty
        self.total = product.price_toman * qty
        t = app.theme
        self.image = load_product_image(DATA_DIR, product.image_path, 300, 300)
        self.modal = Modal(t, pygame.Rect(20, 140, t.w - 40, 520))

    def handle(self, action: str) -> None:
        if action == "confirm":
            self.app.sounds.play("coin")
            self.app.create_order(self.product, self.qty)
        elif action in ("cancel",):
            self.app.sounds.play("back")
            self.app.go("grid")
        elif action in ("up", "down"):
            pass  # single item; reserved for qty stepper later

    def draw(self, surf: pygame.Surface) -> None:
        t = self.app.theme
        self.modal.draw_frame(surf)
        cx = self.modal.rect.centerx
        y = self.modal.rect.y + 24

        title = t.fonts.fa("lg").render(shape("تأیید سفارش"), True, PAL["amber"])
        surf.blit(title, title.get_rect(midtop=(cx, y)))
        y += 60

        if self.image is not None:
            surf.blit(self.image, self.image.get_rect(midtop=(cx, y)))
            y += self.image.get_height() + 16

        name = t.fonts.fa("md").render(shape(self.product.name), True, PAL["cream"])
        surf.blit(name, name.get_rect(midtop=(cx, y)))
        y += 40

        qty_line = t.fonts.fa("sm").render(
            shape(f"{fa_digits(self.qty)} عدد"), True, PAL["gray"])
        surf.blit(qty_line, qty_line.get_rect(midtop=(cx, y)))
        y += 36

        price = t.fonts.px("xl").render(fa_digits(f"{self.total:,}"), True, PAL["green"])
        surf.blit(price, price.get_rect(midtop=(cx, y)))
        cur = t.fonts.fa("sm").render(shape("تومان"), True, PAL["cream"])
        surf.blit(cur, cur.get_rect(midtop=(cx, y + price.get_height() + 4)))
        y += price.get_height() + 44

        # action buttons
        ok_rect = pygame.Rect(cx - 150, y, 300, 64)
        no_rect = pygame.Rect(cx - 150, y + 80, 300, 52)
        pygame.draw.rect(surf, (10, 12, 34), ok_rect.move(0, 5))
        pygame.draw.rect(surf, PAL["red"], ok_rect, border_radius=6)
        pygame.draw.circle(surf, lerp_color(PAL["red"], (255, 255, 255), 0.4),
                           (ok_rect.left + 26, ok_rect.centery - 8), 10)
        ok_txt = t.fonts.fa("lg").render(shape("پرداخت و تأیید"), True, PAL["white"])
        surf.blit(ok_txt, ok_txt.get_rect(center=ok_rect.center))
        pygame.draw.rect(surf, (10, 12, 34), no_rect.move(0, 4))
        pygame.draw.rect(surf, PAL["gray_dark"], no_rect, border_radius=6)
        no_txt = t.fonts.fa("md").render(shape("انصراف"), True, PAL["cream"])
        surf.blit(no_txt, no_txt.get_rect(center=no_rect.center))

        hint = t.fonts.fa("xs").render(
            shape("قرمز: تأیید  |  لغو: برگشت"), True, PAL["gray"])
        surf.blit(hint, hint.get_rect(midtop=(cx, no_rect.bottom + 16)))
