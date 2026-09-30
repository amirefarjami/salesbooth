"""CHIZ Booth — Persian text shaping.

Pygame renders plain Unicode without OpenType shaping, so Persian/Arabic
text needs reshaping (contextual glyph forms) + bidi reordering first.
"""
from __future__ import annotations

try:
    import arabic_reshaper
    from bidi.algorithm import get_display

    _HAS_SHAPING = True
except ImportError:  # pragma: no cover - degraded but functional
    _HAS_SHAPING = False

_reshaper = None
if _HAS_SHAPING:  # pragma: no branch
    _reshaper = arabic_reshaper.ArabicReshaper(
        configuration={"delete_harakat": False, "support_ligatures": True}
    )

# Persian + ASCII digit pairs for pixel-font numerals
_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def shape(text: str) -> str:
    """Return a render-ready string for pygame font.render()."""
    if not text:
        return ""
    if _HAS_SHAPING:
        try:
            return get_display(_reshaper.reshape(text))
        except Exception:
            return text
    return text


def fa_digits(s: str | int) -> str:
    """Convert ASCII digits to Persian digits."""
    return str(s).translate(_FA_DIGITS)


def is_rtl(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06FF" for ch in text)
