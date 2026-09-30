"""CHIZ Booth — input layer.

The booth has 5 arcade buttons + 1 cancel, read from a zero-delay USB
encoder (which presents itself as a keyboard). In the laptop simulator
the same mapping works with the real keyboard, so no code differs.

    Action  Factory key      Default key
    UP      up               Up arrow
    DOWN    down             Down arrow
    LEFT    left             Left arrow
    RIGHT   right            Right arrow
    CONFIRM confirm          Return (big red button)
    CANCEL  cancel           Escape
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


# pygame key constants without importing pygame (kept in sync with SDL1.2/2)
_KEY_CODES = {
    "up": 273, "down": 274, "left": 276, "right": 275,
    "return": 13, "enter": 13, "escape": 27, "space": 32, "backspace": 8,
    "w": 119, "s": 115, "a": 97, "d": 100,
}


def key_code(name: str) -> int:
    return _KEY_CODES.get(name.strip().lower(), 0)


def build_action_map(cfg: Config) -> dict[int, Action]:
    """config keymap {action_name: key_code} -> {key_code: Action}."""
    out: dict[int, Action] = {}
    for name, code in (cfg.keymap or {}).items():
        try:
            out[int(code)] = Action(name)
        except (ValueError, KeyError):
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
                act = self.action_map.get(ev.key)
                if act is not None:
                    actions.append(act)
                elif ev.key == pygame.K_q and pygame.key.get_mods() & pygame.KMOD_CTRL:
                    self.quit_requested = True
        return actions
