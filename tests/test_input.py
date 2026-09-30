"""Tests for hardware input mapping (no pygame needed)."""
from core.config import Config, pygame_keyname_to_code
from hardware.input import Action, build_action_map, key_code


def test_key_code_lookup():
    assert key_code("return") == 13
    assert key_code("RETURN") == 13
    assert key_code("nonsense") == 0


def test_default_keymap_maps_all_actions():
    cfg = Config()
    m = build_action_map(cfg)
    assert set(m.values()) == set(Action)
    assert m[13] == Action.CONFIRM
    assert m[27] == Action.CANCEL
    assert m[pygame_keyname_to_code("up")] == Action.UP


def test_custom_keymap():
    cfg = Config()
    cfg.keymap = {"up": key_code("w"), "down": key_code("s"),
                  "left": key_code("a"), "right": key_code("d"),
                  "confirm": key_code("space"), "cancel": key_code("escape")}
    m = build_action_map(cfg)
    assert m[key_code("space")] == Action.CONFIRM
    assert m[key_code("w")] == Action.UP
