"""CHIZ Booth — «کمیک قورمه» (Comic Ghormeh) theme in the CHIZ brand colours.

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
from core.config import ASSETS_DIR
from core.fonts import FontPack

IMG_DIR = ASSETS_DIR / "img"


def _HAS_DIGIT(label: str) -> bool:
    return any(ch.isdigit() for ch in label)   # ASCII, ۰-۹ and ٠-٩


def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# Tokens. Structure and names follow kd.css; the colours are the CHIZ
# brand (logo + booth art): navy stage, red frame, yellow, purple, white
# sticker plates and the logo's dark outline.
K = {
    "ink":          _hex("2e2e33"),   # logo outline: lines, shadows, text
    "paper":        _hex("ffffff"),   # sticker-white plates
    "paper_2":      _hex("e4e9f4"),   # sunken / disabled (navy-tinted)
    "muted":        _hex("46507a"),   # secondary text on white (7.6:1)
    "hi":           _hex("fff100"),   # brand yellow: selection, main action
    "hi_2":         _hex("fff8a8"),   # selected card fill
    "hover":        _hex("ffe600"),
    "alt":          _hex("7b3e95"),   # brand purple: markers, rings
    "alt_ink":      _hex("ffffff"),
    "danger":       _hex("ec1f24"),   # brand red: frame, red button, errors
    "danger_ink":   _hex("ffffff"),
    "danger_edge":  _hex("a5121a"),
    "ok":           _hex("0a7a3a"),
    "line":         _hex("c3cad9"),
    "stage":        _hex("244085"),   # brand navy behind everything
    "stage_2":      _hex("2f4f9e"),
    "frame":        _hex("ec1f24"),   # the red rounded frame of the booth art
    "burst_rim":    _hex("f7931e"),   # orange inner rim of the price burst
    "poster":       _hex("b0901f"),   # sand of the posters (slide letterbox)
}

# geometry (px)
RADIUS, RADIUS_SM, RADIUS_LG = 10, 6, 16   # rounded like the booth art
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
          dashed: bool = False, radius: int = RADIUS) -> None:
    """Sticker plate: hard ink shadow, fill, ink outline, rounded corners."""
    if shadow:
        pygame.draw.rect(surf, K["ink"], rect.move(shadow, shadow), border_radius=radius)
    pygame.draw.rect(surf, fill, rect, border_radius=radius)
    if outline:
        if dashed:   # disabled: thin muted outline (dashes fight the radius)
            pygame.draw.rect(surf, border, rect, 2, border_radius=radius)
        else:
            pygame.draw.rect(surf, border, rect, outline, border_radius=radius)


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
    """Selected card: light-yellow fill, yellow ring standing off, 7px drop."""
    ring = rect.inflate(14, 14)
    pygame.draw.rect(surf, K["ink"], rect.move(7, 7), border_radius=RADIUS)
    pygame.draw.rect(surf, K["ink"], ring.inflate(4, 4), 2, border_radius=RADIUS + 7)
    pygame.draw.rect(surf, K["hi"], ring, 5, border_radius=RADIUS + 6)
    pygame.draw.rect(surf, K["hi_2"], rect, border_radius=RADIUS)
    pygame.draw.rect(surf, K["ink"], rect, W, border_radius=RADIUS)


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
        self._images: dict[str, pygame.Surface | bool] = {}

    def build_scanlines(self, strength: int) -> pygame.Surface:
        self.scanlines = make_scanline_overlay(self.w, self.h, strength)
        return self.scanlines

    # text ---------------------------------------------------------------

    def text(self, s: str, size: str = "md", color=K["ink"],
             face: str = "body", bold: bool = True) -> pygame.Surface:
        """Render (and cache) a label; Persian is shaped automatically.
        face="display" tries Sina Bold, then Lalezar, then Vazirmatn Bold —
        the first one that has a real glyph for every character."""
        key = (s, size, color, face, bold)
        surf = self._text_cache.get(key)
        if surf is None:
            label = shape(s) if is_rtl(s) else s
            font = None
            if face == "display":
                # Sina Bold's digits are mis-encoded (۶ draws as ۱, ۷ as U):
                # anything with a number goes to Lalezar so prices stay right
                brand = None if _HAS_DIGIT(label) else self.fonts.brand(size)
                for cand in (brand, self.fonts.display(size)):
                    if cand is not None and self._covers(cand, label):
                        font = cand
                        break
            elif face == "px":
                font = self.fonts.px(size)
            if font is None:
                font = self.fonts.fa(size, bold)
            surf = font.render(label, True, color)
            if len(self._text_cache) > 600:
                self._text_cache.clear()
            self._text_cache[key] = surf
        return surf

    def _covers(self, font: pygame.font.Font, label: str) -> bool:
        """True when `font` has a real glyph for every char of `label`
        (a missing glyph renders identical to the .notdef box)."""
        cache = self.__dict__.setdefault("_glyph_ok", {})

        def raw(ch: str) -> bytes:
            g = font.render(ch, False, (0, 0, 0))
            return pygame.image.tobytes(g, "RGB") if hasattr(pygame.image, "tobytes") \
                else pygame.image.tostring(g, "RGB")
        fid = id(font)
        notdef = cache.get((fid, "\uffff"))
        if notdef is None:
            notdef = cache[(fid, "\uffff")] = raw("\uffff")
        for ch in set(label):
            if ch.isspace():
                continue
            ok = cache.get((fid, ch))
            if ok is None:
                ok = cache[(fid, ch)] = raw(ch) != notdef
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
        pygame.draw.rect(surf, K["ink"], r.move(2, 2), border_radius=RADIUS_SM)
        pygame.draw.rect(surf, fill, r, border_radius=RADIUS_SM)
        pygame.draw.rect(surf, border, r, W_SM, border_radius=RADIUS_SM)
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
        t = self.text(label, size, K["ink"], "display")
        surf.blit(t, t.get_rect(midtop=(center_x, top)))
        y = top + t.get_height() + 2
        pygame.draw.rect(surf, K["hi"], (center_x - width // 2, y + 3, width, 4))
        pygame.draw.rect(surf, K["ink"], (center_x - width // 2, y, width, W))
        return y + 9

    def title_box(self, surf, label: str, anchor: dict, size: str = "md",
                  fill=K["hi"], color=K["ink"], slant: int = 0) -> pygame.Rect:
        """Title plate: rounded yellow box with a Lalezar label."""
        t = self.text(label, size, color, "display")
        r = pygame.Rect(0, 0, t.get_width() + 34, t.get_height() + 2)
        for k, v in anchor.items():
            setattr(r, k, v)
        plate(surf, r, fill, radius=RADIUS)
        surf.blit(t, t.get_rect(center=(r.centerx, r.centery + 2)))
        return r

    def image(self, name: str, height: int | None = None, width: int | None = None,
              alpha: int = 255) -> pygame.Surface | None:
        """A brand asset from assets/img, scaled (cached). None if missing."""
        key = ("__img__", name, height, width, alpha)
        surf = self._text_cache.get(key)
        if surf is not None:
            return surf
        src = self._images.get(name)
        if src is None:
            try:
                src = pygame.image.load(str(IMG_DIR / name))
                try:
                    src = src.convert_alpha() if name.endswith(".png") else src.convert()
                except pygame.error:
                    pass  # headless preview: no display format
            except (pygame.error, FileNotFoundError):
                src = False
            self._images[name] = src
        if not src:
            return None
        w, h = src.get_size()
        if height and not width:
            width = max(1, int(w * height / h))
        elif width and not height:
            height = max(1, int(h * width / w))
        surf = src if not width else pygame.transform.smoothscale(src, (width, height))
        if alpha < 255:
            surf = surf.copy()
            surf.set_alpha(alpha)
        self._text_cache[key] = surf
        return surf

    def logo(self, height: int, alpha: int = 255) -> pygame.Surface | None:
        """The planet logo (assets/img/chiz-logo.png) scaled to `height`."""
        return self.image("chiz-logo.png", height=height, alpha=alpha)

    def price_burst(self, surf, center, label: str, w: int, h: int,
                    size: str = "sm", seed: int = 0) -> pygame.Rect:
        """Comic price burst from the brand art: jagged yellow star with an
        orange inner rim and a red outer rim, ink digits in the middle."""
        cx, cy = center
        rnd = [0.82, 1.0, 0.86, 0.97, 0.8, 1.0, 0.9, 0.95, 0.83, 1.0, 0.88, 0.96, 0.84, 0.99]
        n = len(rnd)

        def pts(grow: float) -> list:
            out = []
            for i in range(n * 2):
                a = -math.pi / 2 + i * math.pi / n + 0.1
                if i % 2 == 0:
                    k = rnd[(i // 2 + seed) % n]
                    rx, ry = w / 2 * k + grow, h / 2 * k + grow
                else:
                    rx, ry = w / 2 * 0.72 + grow * 0.7, h / 2 * 0.62 + grow * 0.7
                out.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
            return out
        pygame.draw.polygon(surf, K["ink"], [(x + 3, y + 3) for x, y in pts(3)])
        pygame.draw.polygon(surf, K["danger"], pts(3))
        pygame.draw.polygon(surf, K["burst_rim"], pts(0))
        pygame.draw.polygon(surf, K["hi"], pts(-3))
        t = self.fit_text(label, int(w * 0.66), (size, "sm", "xs"), K["ink"], "display")
        surf.blit(t, t.get_rect(center=(cx, cy + 2)))
        return pygame.Rect(cx - w // 2, cy - h // 2, w, h)

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
        pygame.draw.rect(surf, K["ink"], rect.move(5, 5), border_radius=RADIUS)
        pygame.draw.rect(surf, K["paper"], r, border_radius=RADIUS)
        stub_w = min(64, r.h)
        stub = pygame.Rect(r.right - stub_w, r.top, stub_w, r.h)
        pygame.draw.rect(surf, K["hi"], stub, border_top_right_radius=RADIUS,
                         border_bottom_right_radius=RADIUS)
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
        pygame.draw.rect(surf, K["ink"], r, W, border_radius=RADIUS)
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
        # Sina runs large: one step down from the requested size, and the
        # label never takes more than ~60% of the button height
        steps = ("xs", "sm", "md", "lg", "xl")
        start = max(0, steps.index(size) - 1) if size in steps else 1
        t = self.fit_text(label, rect.w - 16, steps[start::-1], color, "display")
        if t.get_height() > rect.h * 0.8:
            t = self.fit_text(label, rect.w - 16, ("xs",), color, "display")
        surf.blit(t, t.get_rect(center=rect.center))

    def stage(self, surf, color=None, frame=None) -> None:
        """Navy stage inside the red rounded frame of the booth art."""
        surf.fill(color or K["stage"])
        r = pygame.Rect(0, 0, self.w, self.h).inflate(-12, -12)
        pygame.draw.rect(surf, K["ink"], r, 12, border_radius=26)
        pygame.draw.rect(surf, frame or K["frame"], r.inflate(-4, -4), 8, border_radius=24)

    def modal(self, surf, rect: pygame.Rect) -> None:
        """Modal frame: white plate, 4px ink frame, 8px hard drop."""
        plate(surf, rect, K["paper"], outline=W_LG, shadow=OFF_LG, radius=RADIUS_LG)

    def progress_bar(self, surf, rect: pygame.Rect, frac: float,
                     color=K["hi"]) -> None:
        pygame.draw.rect(surf, K["paper_2"], rect, border_radius=rect.h // 2)
        inner = rect.inflate(-6, -6)
        fw = int(inner.w * max(0.0, min(1.0, frac)))
        if fw > 0:
            # the bar empties from the right edge
            pygame.draw.rect(surf, color, (inner.left, inner.top, fw, inner.h),
                             border_radius=inner.h // 2)
        pygame.draw.rect(surf, K["ink"], rect, W_SM + 1, border_radius=rect.h // 2)
