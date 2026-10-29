"""CHIZ Booth — screen layout math shared by the kiosk and the admin panel.

Pure integers and tuples (no pygame) so the admin panel can ask for the
product-photo aspect ratio that the card actually uses — the upload cropper
must cut exactly to that rectangle.

The grid is 2 columns × 3 rows on the portrait panel. Every card is as tall
as the space above the action bar allows: the header is gone, so the cards
start near the frame and fill everything down to the info strip.
"""
from __future__ import annotations

COLS = 2
ROWS = 3
SLOTS = COLS * ROWS

MARGIN_X = 28        # stage margin left/right: room for the selected ring
GAP_X = 14           # between the two columns
GAP_Y = 12           # between rows
TOP = 28             # grid top: the selected ring stays inside the frame

PAD = 10             # paper margin inside a card (photo is inset by this)
TAB = 22             # top tab of the card: the price sticker
BOTTOM = 10          # photo stops this far above the card's bottom edge
NAME_H = 26          # height of the name label on the photo's bottom line

# action area under the grid: gap, info strip, cart ticket, hint line
CARD_GAP = 12        # between the last card row and the info strip
INFO_H = 46
TICKET_H = 58
ACTION_GAP = 10
HINT_H = 38
BOTTOM_MARGIN = 10


def card_w(screen_w: int) -> int:
    return (screen_w - MARGIN_X * 2 - GAP_X * (COLS - 1)) // COLS


def grid_bottom(screen_h: int) -> int:
    """Last pixel row the grid may use (the info strip starts below it)."""
    return (screen_h - HINT_H - TICKET_H - ACTION_GAP - INFO_H
            - BOTTOM_MARGIN - CARD_GAP)


def card_h(screen_h: int) -> int:
    return (grid_bottom(screen_h) - TOP - GAP_Y * (ROWS - 1)) // ROWS


def slots(screen_w: int, screen_h: int):
    """[(x, y, w, h, side)] for slots 1..6; odd = left column, even = right."""
    cw, ch = card_w(screen_w), card_h(screen_h)
    out = []
    for pos in range(SLOTS):
        row, col = divmod(pos, COLS)
        x = MARGIN_X + col * (cw + GAP_X)
        y = TOP + row * (ch + GAP_Y)
        out.append((x, y, cw, ch, "left" if col == 0 else "right"))
    return out


def photo_size(cw: int, ch: int) -> tuple[int, int]:
    """The picture window of a card: inset by PAD, from the tab down to the
    card's bottom edge (a BOTTOM-px inset). The name is centred on that line."""
    return cw - PAD * 2, ch - TAB - BOTTOM


def product_photo_aspect(screen_w: int = 480, screen_h: int = 800) -> float:
    w, h = photo_size(card_w(screen_w), card_h(screen_h))
    return w / h


#: width / height of the product photo window on the 480×800 panel.
#: The admin cropper cuts uploads to exactly this rectangle.
PRODUCT_PHOTO_ASPECT = product_photo_aspect()
