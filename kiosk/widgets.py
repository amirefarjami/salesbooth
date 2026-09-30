"""CHIZ Booth — kiosk UI widgets (button, product card, modal)."""
from __future__ import annotations

import os
from pathlib import Path

import pygame

from core.fa import fa_digits, shape
from core.format import format_toman
from core.models import Product


class Widget:
    def __init__(self, rect: pygame.Rect) -> None:
        self.rect = rect

    def draw(self, surf: pygame.Surface) -> None:  # pragma: no cover
        raise NotImplementedError


class TextButton(Widget):
    """Chunky retro button with pressed/selected states."""

    def __init__(self, rect: pygame.Rect, label_fa: str = "",
                 label_px: str = "", theme=None,
                 fill=(22, 28, 68), accent=(140, 160, 255),
                 text_color=(255, 240, 200), font_size: str = "md",
                 px_size: str = "sm") -> None:
        super().__init__(rect)
        self.label_fa = label_fa
        self.label_px = label_px
        self.theme = theme
        self.fill = fill
        self.accent = accent
        self.text_color = text_color
        self.font_size = font_size
        self.px_size = px_size
        self.selected = False
        self.offset = 0

    def draw(self, surf: pygame.Surface) -> None:
        r = self.rect.move(0, self.offset)
        fill = self.fill
        border = self.accent
        if self.selected:
            fill = tuple(min(255, int(c * 1.35)) for c in self.fill)
            border = (255, 220, 120)
        pygame.draw.rect(surf, (10, 12, 34), r.move(0, 4))  # drop shadow
        pygame.draw.rect(surf, fill, r)
        pygame.draw.rect(surf, border, r, 3 if self.selected else 2)
        if self.theme:
            f = self.theme.fonts.fa(self.font_size, True) if self.label_fa else self.theme.fonts.px(self.px_size)
            label = shape(self.label_fa) if self.label_fa else self.label_px
            tsurf = f.render(label, True, self.text_color)
            surf.blit(tsurf, tsurf.get_rect(center=r.center))


class ProductCard(Widget):
    """Selectable product tile with pixel frame, photo, name and price."""

    def __init__(self, product: Product, rect: pygame.Rect, theme,
                 image: pygame.Surface | None = None) -> None:
        super().__init__(rect)
        self.product = product
        self.theme = theme
        self.image = image
        self.selected = False

    def draw(self, surf: pygame.Surface) -> None:
        r = self.rect
        t = self.theme
        frame = (255, 210, 90) if self.selected else (86, 104, 200)
        bg = (30, 38, 92) if self.selected else (18, 24, 58)
        pygame.draw.rect(surf, (8, 10, 26), r.move(0, 5))
        pygame.draw.rect(surf, bg, r)
        pygame.draw.rect(surf, frame, r, 3 if self.selected else 2)

        # image area
        img_rect = pygame.Rect(r.x + 10, r.y + 10, r.w - 20, r.h - 62)
        if self.image is not None:
            scaled = pygame.transform.smoothscale(
                self.image, (img_rect.w, img_rect.h))
            surf.blit(scaled, img_rect)
        else:
            placeholder = t.fonts.fa("xl").render("چیز", True, (90, 100, 160))
            surf.blit(placeholder, placeholder.get_rect(center=img_rect.center))
        pygame.draw.rect(surf, (60, 72, 140), img_rect, 2)

        # name + price
        f_name = t.fonts.fa("sm")
        name_s = f_name.render(shape(self.product.name), True, (255, 240, 200))
        surf.blit(name_s, name_s.get_rect(midtop=(r.centerx, r.bottom - 46)))
        f_price = t.fonts.px("sm")
        price_s = f_price.render(fa_digits(f"{self.product.price_toman:,}"), True,
                                 (255, 196, 60))
        surf.blit(price_s, price_s.get_rect(midbottom=(r.centerx, r.bottom - 12)))
        f_cur = t.fonts.fa("xs")
        cur_s = f_cur.render(shape("تومان"), True, (150, 160, 200))
        surf.blit(cur_s, (r.right - 14 - cur_s.get_width(), r.bottom - 32))


def load_product_image(data_dir, image_path: str | None,
                       max_w: int, max_h: int) -> pygame.Surface | None:
    if not image_path:
        return None
    p = image_path if os.path.isabs(image_path) else (Path(data_dir) / image_path)
    if not p.is_file():
        return None
    try:
        img = pygame.image.load(str(p)).convert()
    except pygame.error:
        return None
    return _fit(img, max_w, max_h)


def _fit(img: pygame.Surface, max_w: int, max_h: int) -> pygame.Surface:
    w, h = img.get_size()
    scale = min(max_w / w, max_h / h, 1.0)
    if scale < 1.0:
        img = pygame.transform.smoothscale(
            img, (int(w * scale), int(h * scale)))
    return img


class Modal:
    """Dimmed full-screen modal box."""

    def __init__(self, theme, rect: pygame.Rect) -> None:
        self.theme = theme
        self.rect = rect

    def draw_frame(self, surf: pygame.Surface,
                   dim_alpha: int = 180) -> pygame.Surface:
        dim = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 10, dim_alpha))
        surf.blit(dim, (0, 0))
        r = self.rect
        pygame.draw.rect(surf, (8, 10, 26), r.move(0, 6))
        pygame.draw.rect(surf, (22, 28, 68), r)
        pygame.draw.rect(surf, (255, 210, 90), r, 3)
        return surf
