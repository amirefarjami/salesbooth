"""CHIZ Booth — retro arcade theme: palette, panels, scanlines."""
from __future__ import annotations

import math

import pygame

from core.fonts import FontPack


# Malibu-blue booth palette with CRT cream/amber accents
PAL = {
    "bg":          (10, 12, 34),
    "bg_deep":     (6, 7, 22),
    "panel":       (22, 28, 68),
    "panel_hi":    (38, 48, 110),
    "border":      (86, 104, 200),
    "border_hi":   (140, 160, 255),
    "cream":       (255, 240, 200),
    "amber":       (255, 196, 60),
    "red":         (232, 48, 48),
    "red_dark":    (140, 20, 20),
    "green":       (60, 220, 120),
    "blue":        (64, 96, 255),
    "gray":        (130, 140, 180),
    "gray_dark":   (60, 66, 100),
    "white":       (255, 255, 255),
    "black":       (0, 0, 0),
}

BTN_COLORS = {
    "up":    PAL["amber"],
    "down":  PAL["green"],
    "left":  PAL["blue"],
    "right": PAL["red_dark"],
    "confirm": PAL["red"],
}


def lerp_color(c1, c2, t: float):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def draw_pixel_panel(surf: pygame.Surface, rect: pygame.Rect,
                     fill=(22, 28, 68), border=(140, 160, 255),
                     border_dark=(20, 24, 60), thickness: int = 3,
                     corner: int = 6) -> None:
    """Chunky pixel-art style panel with notched corners."""
    pygame.draw.rect(surf, fill, rect)
    # corner notches for a beveled pixel look
    r = rect
    for cx, cy in ((r.left, r.top), (r.right - corner, r.top),
                   (r.left, r.bottom - corner), (r.right - corner, r.bottom - corner)):
        pygame.draw.rect(surf, border_dark, (cx, cy, corner, corner))
    pygame.draw.rect(surf, border, r, thickness)
    # inner highlight
    inner = rect.inflate(-2 * thickness, -2 * thickness)
    pygame.draw.rect(surf, lerp_color(fill, (255, 255, 255), 0.08), inner, 1)


def make_scanline_overlay(w: int, h: int, strength: int = 32,
                          period: int = 3) -> pygame.Surface:
    """Pre-rendered CRT scanlines (dark rows every `period` px)."""
    overlay = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(0, h, period):
        pygame.draw.line(overlay, (0, 0, 0, strength), (0, y), (w, y))
    # subtle vertical vignette bands like a curved tube
    edge = pygame.Surface((w, h), pygame.SRCALPHA)
    for x in range(w):
        a = int(20 * (abs(x - w / 2) / (w / 2)) ** 2)
        pygame.draw.line(edge, (0, 0, 20, a), (x, 0), (x, h))
    overlay.blit(edge, (0, 0))
    return overlay


class Blinker:
    """Time-based blink helper for retro UI emphasis."""

    def __init__(self, period_ms: int = 500) -> None:
        self.period = period_ms
        self.t0 = pygame.time.get_ticks()

    def on(self) -> bool:
        return ((pygame.time.get_ticks() - self.t0) // self.period) % 2 == 0

    def pulse(self) -> float:
        """0..1..0 smooth pulse in [0,1]."""
        t = (pygame.time.get_ticks() % self.period) / self.period
        return 0.5 - 0.5 * math.cos(2 * math.pi * t)


class Theme:
    """Bundles palette + fonts + screen-size-derived metrics."""

    def __init__(self, fonts: FontPack, w: int, h: int) -> None:
        self.fonts = fonts
        self.w = w
        self.h = h
        self.scanlines: pygame.Surface | None = None

    def build_scanlines(self, strength: int) -> pygame.Surface:
        self.scanlines = make_scanline_overlay(self.w, self.h, strength)
        return self.scanlines

    # convenience text renderers -------------------------------------

    def text_fa(self, s, size: str = "md", color=PAL["cream"], bold=None):
        f = self.fonts.fa(size, bold)
        return f.render(s, True, color)

    def text_px(self, s, size: str = "md", color=PAL["amber"]):
        f = self.fonts.px(size)
        return f.render(s, True, color)
