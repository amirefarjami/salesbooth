"""CHIZ Booth — «کمیک قورمه» (Comic Ghormeh) theme for the kiosk screen.

A Pygame port of the Team Arena menu kit (team-arena docs/UI-KIT.md,
client/src/styles/kd.css), so the booth and the game share one look:

  * palette pal-a — saffron for selection / the main action, turquoise for
    markers, cream paper surfaces, ink outlines; flat, no texture
  * 3px ink outline + hard offset shadow (no blur), square corners —
    only marker dots are round
  * never text on a darker strip inside a card: a KICKER is ink text plus a
    small colour marker, a STICKER is a light fill with an ink outline
  * text on paper is always ink; white only on pomegranate / turquoise,
    never white on saffron
  * Lalezar only for titles, the brand, prices-as-headline and the big
    call to action; everything else Vazirmatn
"""
from __future__ import annotations

import math

import pygame

from core.fa import is_rtl, shape
from core.fonts import FontPack


def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# Tokens (same names/values as kd.css :root, minus the "--k-" prefix)
K = {
    "ink":          _hex("1d1409"),
    "paper":        _hex("fff6e0"),
    "paper_2":      _hex("f6e4b8"),
    "muted":        _hex("5a4a30"),
    "hi":           _hex("ffb800"),
    "hi_2":         _hex("ffe7a1"),
    "hover":        _hex("ffc83a"),
    "alt":          _hex("08767d"),
    "alt_ink":      _hex("ffffff"),
    "danger":       _hex("b3122d"),
    "danger_ink":   _hex("ffffff"),
    "danger_edge":  _hex("7a0a1e"),
    "ok":           _hex("0a6a30"),
    "line":         _hex("c4b796"),   # --k-line (28% ink) pre-blended on paper
    # stage behind the paper cards (turquoise, one step darker than --k-alt
    # so the turquoise slot markers still read against it)
    "stage":        _hex("06646a"),
    "stage_2":      _hex("0a7f86"),
}

# geometry (px)
W, W_SM, W_LG = 3, 2, 4          # outline: normal / chip / modal frame
OFF, OFF_SM, OFF_LG = 4, 3, 8    # hard shadow offset: card / small / modal

# Legacy names some tools still import (factory test, icon)
PAL = {
    "bg": K["stage"], "bg_deep": K["stage"], "panel": K["paper"],
    "cream": K["paper"], "amber": K["hi"], "red": K["danger"],
    "green": K["ok"], "gray": K["muted"], "white": (255, 255, 255),
    "black": K["ink"], "border": K["ink"], "border_hi": K["hi"],
    "gray_dark": K["paper_2"], "red_dark": K["danger_edge"], "blue": K["alt"],
    "panel_hi": K["hi_2"],
}
BTN_COLORS = {
    "up": K["hi"], "down": K["hi"], "left": K["alt"], "right": K["alt"],
    "confirm": K["danger"], "cancel": K["paper"],
}


def lerp_color(c1, c2, t: float):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------

def plate(surf: pygame.Surface, rect: pygame.Rect, fill=K["paper"],
          outline: int = W, shadow: int = OFF, border=K["ink"],
          dashed: bool = False) -> None:
    """Paper plate: hard ink shadow, fill, ink outline (the .k-card recipe)."""
    if shadow:
        pygame.draw.rect(surf, K["ink"], rect.move(shadow, shadow))
    pygame.draw.rect(surf, fill, rect)
    if outline:
        if dashed:
            dashed_rect(surf, rect, border, outline)
        else:
            pygame.draw.rect(surf, border, rect, outline)


def dashed_rect(surf, rect: pygame.Rect, color, width: int = W,
                dash: int = 9, gap: int = 6) -> None:
    x0, y0, x1, y1 = rect.left, rect.top, rect.right - width, rect.bottom - width
    for x in range(x0, x1, dash + gap):
        pygame.draw.rect(surf, color, (x, y0, min(dash, x1 - x + width), width))
        pygame.draw.rect(surf, color, (x, y1, min(dash, x1 - x + width), width))
    for y in range(y0, y1, dash + gap):
        pygame.draw.rect(surf, color, (x0, y, width, min(dash, y1 - y + width)))
        pygame.draw.rect(surf, color, (x1, y, width, min(dash, y1 - y + width)))


def selected_card(surf, rect: pygame.Rect) -> None:
    """.k-card.is-selected: hi-2 fill, saffron ring standing 2px off, 7px drop."""
    ring = rect.inflate(12, 12)
    pygame.draw.rect(surf, K["ink"], rect.move(7, 7))
    pygame.draw.rect(surf, K["hi"], ring, 4)
    pygame.draw.rect(surf, K["hi_2"], rect)
    pygame.draw.rect(surf, K["ink"], rect, W)


def skew_box(surf, rect: pygame.Rect, fill=K["hi"], slant: int = 8,
             shadow: int = OFF) -> list:
    """Slanted title box (the modal-title / selected-tab parallelogram)."""
    def pts(r):
        return [(r.left + slant, r.top), (r.right, r.top),
                (r.right - slant, r.bottom), (r.left, r.bottom)]
    if shadow:
        pygame.draw.polygon(surf, K["ink"], pts(rect.move(shadow, shadow)))
    poly = pts(rect)
    pygame.draw.polygon(surf, fill, poly)
    pygame.draw.polygon(surf, K["ink"], poly, W)
    return poly


def star_points(cx: float, cy: float, r_out: float, r_in: float,
                n: int = 12, rot: float = 0.0) -> list:
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = rot - math.pi / 2 + i * math.pi / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def burst(surf, center, radius: int, fill=K["hi"]) -> None:
    """J4 comic burst: 12-point star, ink outline under a coloured star."""
    cx, cy = center
    pygame.draw.polygon(surf, K["ink"], star_points(cx, cy, radius + 3, radius * 0.78 + 3, rot=0.13))
    pygame.draw.polygon(surf, fill, star_points(cx, cy, radius, radius * 0.78, rot=0.13))


def marker_dot(surf, center, radius: int, fill=K["alt"]) -> None:
    """Round marker (the one shape allowed to be round): ink ring + fill."""
    pygame.draw.circle(surf, K["ink"], (center[0] + 2, center[1] + 2), radius + 2)
    pygame.draw.circle(surf, K["ink"], center, radius + 2)
    pygame.draw.circle(surf, fill, center, radius)


def arrow(surf, tip, size: int, direction: str = "left", color=K["ink"]) -> None:
    x, y = tip
    s = size
    if direction == "left":
        pts = [(x, y), (x + s, y - s * 0.7), (x + s, y + s * 0.7)]
    elif direction == "right":
        pts = [(x, y), (x - s, y - s * 0.7), (x - s, y + s * 0.7)]
    elif direction == "down":
        pts = [(x, y), (x - s * 0.7, y - s), (x + s * 0.7, y - s)]
    else:
        pts = [(x, y), (x - s * 0.7, y + s), (x + s * 0.7, y + s)]
    pygame.draw.polygon(surf, color, pts)


def ring_progress(surf, center, radius: int, width: int, frac: float,
                  color, track=K["paper_2"]) -> None:
    """Countdown ring: paper track + coloured arc (frac 1 = full)."""
    rect = pygame.Rect(0, 0, radius * 2, radius * 2)
    rect.center = center
    pygame.draw.circle(surf, track, center, radius, width)
    frac = max(0.0, min(1.0, frac))
    if frac > 0:
        start = math.pi / 2
        end = start + frac * 2 * math.pi
        # draw as thick polyline of small arcs (pygame arc leaves gaps)
        steps = max(2, int(90 * frac))
        for i in range(steps):
            a0 = start + (end - start) * i / steps
            a1 = start + (end - start) * (i + 1) / steps
            pts = []
            for a in (a0, a1):
                pts.append((center[0] + radius * math.cos(a), center[1] - radius * math.sin(a)))
            for a in (a1, a0):
                pts.append((center[0] + (radius - width) * math.cos(a),
                            center[1] - (radius - width) * math.sin(a)))
            pygame.draw.polygon(surf, color, pts)
    pygame.draw.circle(surf, K["ink"], center, radius + 1, 2)
    pygame.draw.circle(surf, K["ink"], center, radius - width, 2)


# ---------------------------------------------------------------------------
# Theme: fonts + text helpers + composite widgets
# ---------------------------------------------------------------------------

class Blinker:
    """Time-based blink helper."""

    def __init__(self, period_ms: int = 500) -> None:
        self.period = period_ms
        self.t0 = pygame.time.get_ticks()

    def on(self) -> bool:
        return ((pygame.time.get_ticks() - self.t0) // self.period) % 2 == 0

    def pulse(self) -> float:
        t = (pygame.time.get_ticks() % self.period) / self.period
        return 0.5 - 0.5 * math.cos(2 * math.pi * t)


def make_scanline_overlay(w: int, h: int, strength: int = 32,
                          period: int = 3) -> pygame.Surface:
    """Optional CRT scanlines (off by default in the Ghormeh look)."""
    overlay = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(0, h, period):
        pygame.draw.line(overlay, (0, 0, 0, strength), (0, y), (w, y))
    return overlay


class Theme:
    """Bundles tokens + fonts + screen-size metrics + drawing helpers."""

    def __init__(self, fonts: FontPack, w: int, h: int) -> None:
        self.fonts = fonts
        self.w = w
        self.h = h
        self.scanlines: pygame.Surface | None = None
        self._text_cache: dict[tuple, pygame.Surface] = {}

    def build_scanlines(self, strength: int) -> pygame.Surface:
        self.scanlines = make_scanline_overlay(self.w, self.h, strength)
        return self.scanlines

    # text ---------------------------------------------------------------

    def text(self, s: str, size: str = "md", color=K["ink"],
             face: str = "body", bold: bool = True) -> pygame.Surface:
        """Render (and cache) a label; Persian is shaped automatically."""
        key = (s, size, color, face, bold)
        surf = self._text_cache.get(key)
        if surf is None:
            label = shape(s) if is_rtl(s) else s
            if face == "display" and not self._display_covers(label):
                face = "body"   # Lalezar lacks some presentation forms
            if face == "display":
                font = self.fonts.display(size)
            elif face == "px":
                font = self.fonts.px(size)
            else:
                font = self.fonts.fa(size, bold)
            surf = font.render(label, True, color)
            if len(self._text_cache) > 600:
                self._text_cache.clear()
            self._text_cache[key] = surf
        return surf

    def _display_covers(self, label: str) -> bool:
        """True when Lalezar has a real glyph for every char of `label`
        (a missing glyph renders identical to the .notdef box)."""
        cache = self.__dict__.setdefault("_glyph_ok", {})
        font = self.fonts.display("xs")
        if "\uffff" not in cache:
            cache["\uffff"] = pygame.image.tobytes(font.render("\uffff", False, (0, 0, 0)), "RGB") \
                if hasattr(pygame.image, "tobytes") else pygame.image.tostring(
                    font.render("\uffff", False, (0, 0, 0)), "RGB")
        notdef = cache["\uffff"]
        for ch in set(label):
            if ch.isspace():
                continue
            ok = cache.get(ch)
            if ok is None:
                g = font.render(ch, False, (0, 0, 0))
                raw = pygame.image.tobytes(g, "RGB") if hasattr(pygame.image, "tobytes") \
                    else pygame.image.tostring(g, "RGB")
                ok = raw != notdef
                cache[ch] = ok
            if not ok:
                return False
        return True

    def fit_text(self, s: str, max_w: int, sizes=("md", "sm", "xs"),
                 color=K["ink"], face: str = "body") -> pygame.Surface:
        """Largest size from `sizes` that fits in max_w (else squeeze)."""
        for size in sizes:
            t = self.text(s, size, color, face)
            if t.get_width() <= max_w:
                return t
        t = self.text(s, sizes[-1], color, face)
        return pygame.transform.smoothscale(
            t, (max_w, max(1, int(t.get_height() * max_w / t.get_width()))))

    # legacy helpers ------------------------------------------------------

    def text_fa(self, s, size: str = "md", color=K["ink"], bold=None):
        return self.fonts.fa(size, bold).render(shape(s), True, color)

    def text_px(self, s, size: str = "md", color=K["ink"]):
        return self.fonts.px(size).render(s, True, color)

    # composite widgets ----------------------------------------------------

    def sticker(self, surf, label: str, anchor: dict, fill=K["paper"],
                color=K["ink"], size: str = "sm", border=K["ink"],
                face: str = "body", pad_x: int = 9, pad_y: int = 1) -> pygame.Rect:
        """.k-sticker: light fill + 2px ink outline + 2px drop. `anchor` is a
        pygame Rect kwarg such as {"topright": (x, y)}."""
        t = self.text(label, size, color, face)
        r = pygame.Rect(0, 0, t.get_width() + pad_x * 2, t.get_height() + pad_y * 2)
        for k, v in anchor.items():
            setattr(r, k, v)
        pygame.draw.rect(surf, K["ink"], r.move(2, 2))
        pygame.draw.rect(surf, fill, r)
        pygame.draw.rect(surf, border, r, W_SM)
        surf.blit(t, t.get_rect(center=r.center))
        return r

    def kicker(self, surf, label: str, anchor: dict, color=K["muted"],
               marker=K["hi"], size: str = "xs", round_marker: bool = False) -> pygame.Rect:
        """.k-kicker: ink/muted text + a small square (or dot) marker on the
        start edge (right side in RTL)."""
        t = self.text(label, size, color)
        r = pygame.Rect(0, 0, t.get_width() + 15, t.get_height())
        for k, v in anchor.items():
            setattr(r, k, v)
        m = pygame.Rect(0, 0, 9, 9)
        m.midright = (r.right, r.centery + 1)
        if round_marker:
            pygame.draw.circle(surf, K["ink"], m.center, 5)
            pygame.draw.circle(surf, marker, m.center, 3)
        else:
            pygame.draw.rect(surf, marker, m)
            pygame.draw.rect(surf, K["ink"], m, 2)
        surf.blit(t, t.get_rect(midright=(m.left - 6, r.centery)))
        return r

    def kicker_rule(self, surf, label: str, center_x: int, top: int,
                    width: int, size: str = "sm") -> int:
        """.k-kicker-rule: centred heading with an ink rule + saffron under-rule.
        Returns the y just below it."""
        t = self.text(label, size, K["ink"])
        surf.blit(t, t.get_rect(midtop=(center_x, top)))
        y = top + t.get_height() + 2
        pygame.draw.rect(surf, K["hi"], (center_x - width // 2, y + 3, width, 4))
        pygame.draw.rect(surf, K["ink"], (center_x - width // 2, y, width, W))
        return y + 9

    def title_box(self, surf, label: str, anchor: dict, size: str = "md",
                  fill=K["hi"], color=K["ink"], slant: int = 10) -> pygame.Rect:
        """Modal title: slanted saffron box with Lalezar label."""
        t = self.text(label, size, color, "display")
        r = pygame.Rect(0, 0, t.get_width() + 34 + slant, t.get_height() + 2)
        for k, v in anchor.items():
            setattr(r, k, v)
        skew_box(surf, r, fill, slant)
        surf.blit(t, t.get_rect(center=(r.centerx, r.centery + 2)))
        return r

    def close_x(self, surf, rect: pygame.Rect) -> None:
        """.k-modal-x: pomegranate square with a white ×."""
        plate(surf, rect, K["danger"], shadow=OFF_SM)
        c = rect.center
        d = rect.w // 4
        for sx in (-1, 1):
            pygame.draw.line(surf, K["danger_ink"], (c[0] - d, c[1] - d * sx),
                             (c[0] + d, c[1] + d * sx), 4)

    def go_ticket(self, surf, rect: pygame.Rect, label: str, size: str = "lg",
                  pressed: float = 0.0, red_dot: bool = True,
                  disabled: bool = False) -> None:
        """.k-btn-go START ticket: cream plate, ink label in Lalezar, saffron
        stub with an ink arrow on the START edge (right, RTL). `red_dot` puts
        the booth's big red button on the stub so the action names its key.
        `pressed` 0..1 sinks it toward the shadow (press animation)."""
        if disabled:
            plate(surf, rect, K["paper_2"], shadow=0, dashed=True, border=K["muted"])
            t = self.text(label, size, K["muted"], "display")
            surf.blit(t, t.get_rect(center=rect.center))
            return
        sink = int(round(4 * pressed))
        r = rect.move(sink, sink)
        pygame.draw.rect(surf, K["ink"], rect.move(5, 5))
        pygame.draw.rect(surf, K["paper"], r)
        stub_w = min(64, r.h)
        stub = pygame.Rect(r.right - stub_w, r.top, stub_w, r.h)
        pygame.draw.rect(surf, K["hi"], stub)
        pygame.draw.line(surf, K["ink"], (stub.left, r.top), (stub.left, r.bottom - 1), W)
        if red_dot:
            rad = max(9, stub_w // 2 - 12)
            cx, cy = stub.centerx, stub.centery
            pygame.draw.circle(surf, K["ink"], (cx, cy), rad + 3)
            pygame.draw.circle(surf, K["danger"], (cx, cy), rad)
            pygame.draw.circle(surf, lerp_color(K["danger"], (255, 255, 255), 0.45),
                               (cx - rad // 3, cy - rad // 3), max(2, rad // 3))
        else:
            arrow(surf, (stub.centerx - 6, stub.centery), 12, "left")
        pygame.draw.rect(surf, K["ink"], r, W)
        body = pygame.Rect(r.left, r.top, r.w - stub_w, r.h)
        t = self.fit_text(label, body.w - 20, (size, "md", "sm"), K["ink"], "display")
        surf.blit(t, t.get_rect(center=(body.centerx, body.centery + 2)))

    def button(self, surf, rect: pygame.Rect, label: str, kind: str = "paper",
               size: str = "md") -> None:
        """.k-btn (paper) / .k-btn-primary (saffron) / .k-btn-danger."""
        fill, color = {
            "paper": (K["paper"], K["ink"]),
            "primary": (K["hi"], K["ink"]),
            "danger": (K["danger"], K["danger_ink"]),
            "alt": (K["alt"], K["alt_ink"]),
        }[kind]
        plate(surf, rect, fill, shadow=OFF)
        t = self.fit_text(label, rect.w - 16, (size, "sm", "xs"), color)
        surf.blit(t, t.get_rect(center=rect.center))

    def stage(self, surf, color=None) -> None:
        """Flat stage colour behind the paper (no texture)."""
        surf.fill(color or K["stage"])

    def modal(self, surf, rect: pygame.Rect) -> None:
        """.k-modal frame: paper, 4px ink frame, 8px hard drop."""
        plate(surf, rect, K["paper"], outline=W_LG, shadow=OFF_LG)

    def progress_bar(self, surf, rect: pygame.Rect, frac: float,
                     color=K["hi"]) -> None:
        pygame.draw.rect(surf, K["paper_2"], rect)
        inner = rect.inflate(-6, -6)
        fw = int(inner.w * max(0.0, min(1.0, frac)))
        if fw > 0:
            # RTL: the bar drains toward the start (right) edge
            pygame.draw.rect(surf, color, (inner.right - fw, inner.top, fw, inner.h))
        pygame.draw.rect(surf, K["ink"], rect, W_SM + 1)
