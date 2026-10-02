"""CHIZ Booth — input layer.

Booth panel: the screen in the middle, three product buttons on each side
(one per card), the big red CONFIRM button (the only one with a light) and
CANCEL («انصراف»). Eight buttons in all, through a zero-delay USB encoder
that presents itself as a keyboard, so the laptop simulator is identical.

    Action   Default key   Physical button
    SLOT1    1             left column,  top
    SLOT2    2             right column, top
    SLOT3    3             left column,  middle
    SLOT4    4             right column, middle
    SLOT5    5             left column,  bottom
    SLOT6    6             right column, bottom
    CONFIRM  return        big red button (lit)
    CANCEL   escape        «انصراف»
    DOOR_SIM d             laptop only: open/close the showcase door

Many «Zero Delay» encoders show up as a GAMEPAD instead of a keyboard; then
map its buttons as "joy0", "joy1", … (make factory-test shows each
button's number when pressed).

UP/DOWN/LEFT/RIGHT stay mappable for old joystick panels and tests.
Keymap values in booth.toml may be key names ("1", "return", "f5"),
gamepad buttons ("joy3") or raw pygame key codes (ints).
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
    DOOR_SIM = "door_sim"


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


JOY_BASE = 0x7000_0000          # gamepad button N → JOY_BASE + N


def key_code(name: str | int) -> int:
    """Key name, "joyN" or raw code -> lookup code; 0 if unknown."""
    if isinstance(name, int):
        return name
    n = str(name).strip().lower()
    if n.startswith("joy") and n[3:].isdigit():
        return JOY_BASE + int(n[3:])
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
    """Translates pygame keyboard AND gamepad events into booth actions."""

    def __init__(self, cfg: Config) -> None:
        self.action_map = build_action_map(cfg)
        self.quit_requested = False
        self._pads: dict = {}
        try:
            import pygame

            pygame.joystick.init()
            for i in range(pygame.joystick.get_count()):
                self._open_pad(i)
        except Exception:
            pass

    def _open_pad(self, index: int) -> None:
        import pygame

        try:
            js = pygame.joystick.Joystick(index)
            self._pads[js.get_instance_id()] = js   # keep a reference: events need it
        except pygame.error:
            pass

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
            elif ev.type == pygame.JOYBUTTONDOWN:
                act = self.action_map.get(JOY_BASE + ev.button)
                if act is not None:
                    actions.append(act)
            elif ev.type == pygame.JOYDEVICEADDED:
                self._open_pad(ev.device_index)     # encoder plugged in later
        return actions
