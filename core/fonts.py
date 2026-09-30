"""CHIZ Booth — font loading and caching (Vazirmatn + Press Start 2P)."""
from __future__ import annotations

from pathlib import Path

import pygame

from core.config import ASSETS_DIR

FONT_DIR = ASSETS_DIR / "fonts"

_SIZES_FA = {"xs": 14, "sm": 17, "md": 21, "lg": 27, "xl": 34, "xxl": 44, "title": 56}
_SIZES_PX = {"xs": 10, "sm": 12, "md": 14, "lg": 18, "xl": 24, "xxl": 32, "title": 40}

_CANDIDATES = {
    "fa": ["Vazirmatn-Bold.ttf", "Vazirmatn-Regular.ttf"],
    "fa_bold": ["Vazirmatn-Bold.ttf"],
    "px": ["PressStart2P-Regular.ttf"],
}


def _find_font(candidates: list[str]) -> str | None:
    for name in candidates:
        p = FONT_DIR / name
        if p.is_file():
            return str(p)
    # fall back to bundled pygame font (built-in freesansbold.ttf)
    return None


class FontPack:
    """Lazy, cached font renders at named sizes."""

    def __init__(self) -> None:
        self._cache: dict[tuple, pygame.font.Font] = {}
        self._fa_path = _find_font(_CANDIDATES["fa"])
        self._fa_bold_path = _find_font(_CANDIDATES["fa_bold"]) or self._fa_path
        self._px_path = _find_font(_CANDIDATES["px"])
        self.have_custom = any([self._fa_path, self._px_path])

    def fa(self, size: str = "md", bold: bool | None = None) -> pygame.font.Font:
        key = ("fa", size, bold)
        if key not in self._cache:
            sz = _SIZES_FA.get(size, 21)
            path = self._fa_bold_path if bold or (bold is None and size in ("lg", "xl", "xxl", "title")) else self._fa_path
            if path:
                self._cache[key] = pygame.font.Font(path, sz)
            else:
                f = pygame.font.Font(None, int(sz * 1.35))
                f.set_bold(bool(bold))
                self._cache[key] = f
        return self._cache[key]

    def px(self, size: str = "md") -> pygame.font.Font:
        key = ("px", size)
        if key not in self._cache:
            sz = _SIZES_PX.get(size, 14)
            if self._px_path:
                self._cache[key] = pygame.font.Font(self._px_path, sz)
            else:
                self._cache[key] = pygame.font.Font(None, int(sz * 1.4))
        return self._cache[key]

    def mono_digits(self, n: int | str, size: str = "xxl") -> pygame.font.Font:
        return self.px(size)


def preload() -> None:
    """Call after pygame.init(); warms commonly used faces."""
    fp = FontPack()
    fp.fa("md")
    fp.px("md")
    return fp
