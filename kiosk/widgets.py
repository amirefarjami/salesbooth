"""CHIZ Booth — kiosk widgets in the «کمیک قورمه» look."""
from __future__ import annotations

import os
from pathlib import Path

import pygame

from core.fa import fa_digits
from core.models import Product
from kiosk.theme import K, W, burst, marker_dot, plate, selected_card


def price_fa(amount: int) -> str:
    """150000 -> '۱۵۰٬۰۰۰' (Persian digits + Arabic thousands separator)."""
    return fa_digits(f"{int(amount):,}".replace(",", "٬"))


class ProductCard:
    """One product slot on the 2×3 grid.

    Layout (from the hand sketch): photo on paper, the name under an ink
    hairline, a price sticker on a tab poking out of the top corner, a
    turquoise numbered dot on the OUTER edge pointing at the physical slot
    button beside the screen, and a red burst when stock is low.
    """

    def __init__(self, product: Product, rect: pygame.Rect, theme,
                 slot: int, side: str, image: pygame.Surface | None = None) -> None:
        self.product = product
        self.rect = rect
        self.theme = theme
        self.slot = slot          # 1-based number printed on the marker
        self.side = side          # "right" | "left": which edge faces its button
        self.image = image
        self.selected = False
        self.flash = 0.0          # 0..1 press feedback (sinks the card)

    @property
    def sold_out(self) -> bool:
        return self.product.stock <= 0

    def draw(self, surf: pygame.Surface) -> None:
        t = self.theme
        sink = int(round(3 * self.flash))
        r = self.rect.move(sink, sink)

        if self.sold_out:
            plate(surf, r, K["paper_2"], shadow=0, dashed=True, border=K["muted"])
        elif self.selected:
            selected_card(surf, r)
        else:
            plate(surf, r, K["paper"], shadow=4 - sink)

        # photo window (ink frame) -------------------------------------
        name_h = 38
        img_rect = pygame.Rect(r.x + 10, r.y + 22, r.w - 20, r.h - 22 - name_h - 8)
        pygame.draw.rect(surf, K["paper_2"] if not self.selected else K["paper"], img_rect)
        if self.image is not None:
            img = self.image
            if self.sold_out:
                img = _greyed(img)
            surf.blit(img, img.get_rect(center=img_rect.center))
        else:
            ph = t.text("چیز", "lg", K["line"], "display")
            surf.blit(ph, ph.get_rect(center=img_rect.center))
        pygame.draw.rect(surf, K["ink"], img_rect, 2)

        # name under an ink hairline (no dark strip behind text) ------
        line_y = r.bottom - name_h - 3
        pygame.draw.line(surf, K["ink"], (r.x + 10, line_y), (r.right - 11, line_y), 2)
        name = t.fit_text(self.product.name, r.w - 24, ("sm", "xs"),
                          K["muted"] if self.sold_out else K["ink"])
        surf.blit(name, name.get_rect(center=(r.centerx, r.bottom - name_h // 2 - 3)))

        # price sticker on the top tab (start = right edge) -------------
        if self.sold_out:
            t.sticker(surf, "تمام شد", {"topright": (r.right - 8, r.top - 12)},
                      fill=K["paper"], color=K["danger"], border=K["danger"], size="xs")
        else:
            t.sticker(surf, price_fa(self.product.price_toman),
                      {"topright": (r.right - 8, r.top - 12)},
                      fill=K["hi"] if not self.selected else K["paper"], size="sm")

        # low-stock burst («فقط ۲ تا») ---------------------------------
        if 0 < self.product.stock <= 2:
            c = (r.left + 30, r.top + 28)
            burst(surf, c, 25, K["danger"])
            lab = t.text(f"{fa_digits(self.product.stock)} تا", "xs", K["danger_ink"])
            surf.blit(lab, lab.get_rect(center=(c[0], c[1] + 1)))

        # slot marker on the outer edge, pointing at its button -------
        mx = r.right if self.side == "right" else r.left
        my = r.centery - 6
        marker_dot(surf, (mx, my), 15, K["muted"] if self.sold_out else K["alt"])
        num = t.text(fa_digits(self.slot), "sm", K["alt_ink"])
        surf.blit(num, num.get_rect(center=(mx, my + 1)))


def _greyed(img: pygame.Surface) -> pygame.Surface:
    try:
        g = pygame.transform.grayscale(img)
    except AttributeError:  # very old pygame
        g = img.copy()
    veil = pygame.Surface(g.get_size(), pygame.SRCALPHA)
    veil.fill((*K["paper_2"], 120))
    g.blit(veil, (0, 0))
    return g


def load_product_image(data_dir, image_path: str | None,
                       max_w: int, max_h: int) -> pygame.Surface | None:
    if not image_path:
        return None
    p = image_path if os.path.isabs(image_path) else (Path(data_dir) / image_path)
    if not Path(p).is_file():
        return None
    try:
        img = pygame.image.load(str(p))
    except pygame.error:
        return None
    try:
        img = img.convert_alpha() if img.get_alpha() is not None else img.convert()
    except pygame.error:
        pass  # no display yet (headless preview render) — use as loaded
    return _fit(img, max_w, max_h)


def _fit(img: pygame.Surface, max_w: int, max_h: int) -> pygame.Surface:
    w, h = img.get_size()
    scale = min(max_w / w, max_h / h)
    if abs(scale - 1.0) > 0.01:
        img = pygame.transform.smoothscale(
            img, (max(1, int(w * scale)), max(1, int(h * scale))))
    return img


class Modal:
    """Paper modal on the flat stage (kept for older callers)."""

    def __init__(self, theme, rect: pygame.Rect) -> None:
        self.theme = theme
        self.rect = rect

    def draw_frame(self, surf: pygame.Surface, dim_alpha: int = 0) -> pygame.Surface:
        self.theme.modal(surf, self.rect)
        return surf


__all__ = ["ProductCard", "Modal", "load_product_image", "price_fa", "W"]
