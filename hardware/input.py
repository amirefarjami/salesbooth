"""CHIZ Booth — input layer.

Booth panel (from the hand sketch): the screen sits in the middle with
three arcade buttons on each side, one per product slot, plus the big
red CONFIRM button and a CANCEL («انصراف») button under the
screen. Every button goes through a zero-delay USB encoder that presents
itself as a keyboard, so the laptop simulator uses the same mapping.

    Action   Default key   Physical button
    SLOT1    1             right column, top     (RTL: first product)
    SLOT2    2             left column,  top
    SLOT3    3             right column, middle
    SLOT4    4             left column,  middle
    SLOT5    5             right column, bottom
    SLOT6    6             left column,  bottom
    CONFIRM  return        big red button
    CANCEL   escape        «انصراف» under the screen
    UP/DOWN  up/down       optional page buttons (and the old joystick)
    LEFT/RIGHT left/right  optional (old 5-button joystick layout)

Keymap values in booth.toml may be key names ("1", "return", "f5") or
raw pygame key codes (ints).
"""
from __future__ import annotations

from enum import Enum

from core.config import Config


class Action(Enum):
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    CONFIRM = "confirm"
    CANCEL = "cancel"
    SLOT1 = "slot1"
    SLOT2 = "slot2"
    SLOT3 = "slot3"
    SLOT4 = "slot4"
    SLOT5 = "slot5"
    SLOT6 = "slot6"


SLOT_ACTIONS = (Action.SLOT1, Action.SLOT2, Action.SLOT3,
                Action.SLOT4, Action.SLOT5, Action.SLOT6)


def slot_index(action: str) -> int | None:
    """'slot3' -> 2; anything else -> None."""
    if action.startswith("slot") and action[4:].isdigit():
        return int(action[4:]) - 1
    return None


# SDL2 / pygame-ce 2.x key codes. Arrow and F-keys are scancode|1<<30,
# NOT the SDL1 values (273..276) — those never fire under pygame 2.
_SC = 1 << 30
_KEY_CODES = {
    "up": _SC | 82, "down": _SC | 81, "left": _SC | 80, "right": _SC | 79,
    "return": 13, "enter": 13, "kp_enter": _SC | 88,
    "escape": 27, "esc": 27, "space": 32, "backspace": 8, "tab": 9,
    **{f"f{i}": _SC | (57 + i) for i in range(1, 13)},
    **{f"kp{i}": _SC | (89 + (i - 1) % 10) for i in range(1, 10)},
    "kp0": _SC | 98,
}


def key_code(name: str | int) -> int:
    """Key name (or raw code) -> pygame-ce key code; 0 if unknown."""
    if isinstance(name, int):
        return name
    n = str(name).strip().lower()
    if n.lstrip("-").isdigit() and len(n) > 1:
        return int(n)                      # raw code given as a string
    if n in _KEY_CODES:
        return _KEY_CODES[n]
    if len(n) == 1 and n.isprintable():
        return ord(n)                      # letters, digits, punctuation
    return 0


def build_action_map(cfg: Config) -> dict[int, Action]:
    """config keymap {action_name: key name|code} -> {key_code: Action}."""
    out: dict[int, Action] = {}
    for name, key in (cfg.keymap or {}).items():
        code = key_code(key)
        if not code:
            continue
        try:
            out[code] = Action(name)
        except ValueError:
            continue
    return out


class KeyboardInput:
    """Translates pygame events into booth actions."""

    def __init__(self, cfg: Config) -> None:
        self.action_map = build_action_map(cfg)
        self.quit_requested = False

    def pump(self) -> list[Action]:
        """Drain the pygame event queue; returns actions pressed this frame."""
        import pygame

        actions: list[Action] = []
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.quit_requested = True
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_q and ev.mod & pygame.KMOD_CTRL:
                    self.quit_requested = True
                    continue
                act = self.action_map.get(ev.key)
                if act is not None:
                    actions.append(act)
        return actions
