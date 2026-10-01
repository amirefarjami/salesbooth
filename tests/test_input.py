"""Tests for hardware input mapping (no pygame needed)."""
from core.config import Config
from hardware.input import SLOT_ACTIONS, Action, build_action_map, key_code, slot_index

# pygame-ce 2.x (SDL2) constants, pinned here so a regression to the SDL1
# values (K_UP == 273) is caught without importing pygame
K_UP, K_DOWN, K_LEFT, K_RIGHT = 1073741906, 1073741905, 1073741904, 1073741903


def test_key_code_lookup():
    assert key_code("return") == 13
    assert key_code("RETURN") == 13
    assert key_code("escape") == 27
    assert key_code("1") == ord("1")
    assert key_code("w") == ord("w")
    assert key_code("nonsense") == 0


def test_arrow_codes_are_sdl2():
    assert (key_code("up"), key_code("down"), key_code("left"), key_code("right")) == \
        (K_UP, K_DOWN, K_LEFT, K_RIGHT)


def test_arrow_codes_match_pygame():
    import pygame
    assert key_code("up") == pygame.K_UP
    assert key_code("right") == pygame.K_RIGHT
    assert key_code("f5") == pygame.K_F5
    assert key_code("kp1") == pygame.K_KP1
    assert key_code("kp0") == pygame.K_KP0


def test_raw_codes_accepted():
    assert key_code(1073741906) == K_UP
    assert key_code("1073741906") == K_UP


def test_default_keymap_maps_all_actions():
    m = build_action_map(Config())
    assert set(m.values()) == set(Action)
    assert m[13] == Action.CONFIRM
    assert m[27] == Action.CANCEL
    assert m[K_UP] == Action.UP
    assert [m[ord(str(i))] for i in range(1, 7)] == list(SLOT_ACTIONS)


def test_custom_keymap():
    cfg = Config()
    cfg.keymap = {"up": "w", "down": "s", "confirm": "space", "cancel": "escape",
                  "slot1": "a", "bogus": "x"}
    m = build_action_map(cfg)
    assert m[key_code("space")] == Action.CONFIRM
    assert m[key_code("w")] == Action.UP
    assert m[ord("a")] == Action.SLOT1
    assert ord("x") not in m


def test_slot_index():
    assert slot_index("slot1") == 0
    assert slot_index("slot6") == 5
    assert slot_index("confirm") is None
