"""CHIZ Booth — kiosk widgets in the «کمیک قورمه» look."""
from __future__ import annotations

import os
from pathlib import Path

import pygame

from core.fa import fa_digits
from core.models import Product
from kiosk.theme import K, RADIUS_SM, W, burst, plate, selected_card


def price_fa(amount: int) -> str:
    """150000 -> '۱۵۰,۰۰۰' (Persian digits; the brand font has no '٬')."""
    return fa_digits(f"{int(amount):,}")


class ProductCard:
    """One product slot on the 2×3 grid.

    Layout (from the hand sketch): photo on paper, the name under it, the
    price sticker on the top tab and a yellow «×n» badge for how many are already in the cart. Each card sits
    next to its own physical button, so it carries no number.
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
        self.in_cart = 0          # how many of this product are in the cart

    @property
    def sold_out(self) -> bool:
        return self.product.stock <= 0

    @property
    def left(self) -> int:
        """Still available after what is already in the cart."""
        return max(0, self.product.stock - self.in_cart)

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
        pygame.draw.rect(surf, K["paper_2"] if not self.selected else K["paper"], img_rect,
                         border_radius=6)
        if self.image is not None:
            img = self.image
            if self.sold_out:
                img = _greyed(img)
            surf.blit(img, img.get_rect(center=img_rect.center))
        else:
            ph = t.logo(min(64, img_rect.h - 16), alpha=90)
            if ph is not None:
                surf.blit(ph, ph.get_rect(center=img_rect.center))
        pygame.draw.rect(surf, K["ink"], img_rect, 2, border_radius=6)

        # name ---------------------------------------------------------
        name = t.fit_text(self.product.name, r.w - 24, ("xs",),
                          K["muted"] if self.sold_out else K["ink"], "display")
        surf.blit(name, name.get_rect(center=(r.centerx, r.bottom - name_h // 2 - 3)))

        # price: sticker on the top tab (right corner) -----------------
        if self.sold_out:
            t.sticker(surf, "تمام شد", {"topright": (r.right - 8, r.top - 12)},
                      fill=K["paper"], color=K["danger"], border=K["danger"], size="xs")
        else:
            # plain yellow sticker on the top tab (the burst was too busy
            # six times over; it stays only for the cart total)
            t.sticker(surf, price_fa(self.product.price_toman),
                      {"topright": (r.right - 8, r.top - 12)}, fill=K["hi"], size="sm")

        # in-cart badge («×۲») on the photo's outer bottom corner
        if self.in_cart:
            anchor = ({"bottomright": (img_rect.right + 2, img_rect.bottom + 6)}
                      if self.side == "left" else
                      {"bottomleft": (img_rect.left - 2, img_rect.bottom + 6)})
            t.sticker(surf, f"×{fa_digits(self.in_cart)}", anchor,
                      fill=K["hi"], size="sm", face="display")


def slot_tag(surf, t, center, n: int, muted: bool = False) -> pygame.Rect:
    """Purple rounded tag with «#n» in the style of the CHIZ hang tags."""
    num = t.text(fa_digits(n), "md", K["alt_ink"], "display")
    hash_ = t.text("#", "sm", K["alt_ink"], "display")
    w = num.get_width() + hash_.get_width() + 16
    tag = pygame.Rect(0, 0, max(42, w), 32)
    tag.center = center
    plate(surf, tag, K["muted"] if muted else K["alt"], shadow=2, radius=RADIUS_SM)
    x = tag.centerx - (num.get_width() + hash_.get_width() + 2) // 2
    surf.blit(hash_, hash_.get_rect(midleft=(x, tag.centery + 1)))
    surf.blit(num, num.get_rect(midleft=(x + hash_.get_width() + 2, tag.centery + 3)))
    return tag


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


__all__ = ["ProductCard", "slot_tag", "Modal", "load_product_image", "price_fa", "W"]
