"""CHIZ Booth — layered configuration.

Precedence (lowest → highest):
    dataclass defaults  <  booth.toml  <  environment (CHIZ_*)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ASSETS_DIR = PROJECT_ROOT / "assets"

DEFAULT_TOML = PROJECT_ROOT / "booth.toml"


def _get(data: dict, path: list[str]) -> object | None:
    cur: object = data
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


@dataclass
class Config:
    # --- database ---
    db_path: Path = DATA_DIR / "booth.db"

    # --- kiosk window / rendering ---
    screen_w: int = 480
    screen_h: int = 800
    fullscreen: bool = False          # True on the Pi kiosk (via --fullscreen)
    fps: int = 60
    scanlines: bool = True            # CRT scanline overlay
    scanline_strength: int = 32       # 0-255 alpha for the dark lines

    # --- attract mode ---
    attract_timeout_s: int = 60       # idle seconds before attract screen

    # --- sound ---
    sound: bool = True
    sfx_volume: float = 0.8           # 0.0 – 1.0

    # --- LED strip ---
    led_count: int = 8                # pixels in the strip
    led_gpio: int = 18                # BCM pin for WS2812B data
    led_brightness: int = 160         # 0-255
    led_enabled: bool = True          # auto-disabled when driver missing

    # --- admin panel ---
    admin_host: str = "0.0.0.0"
    admin_port: int = 8000
    admin_pin: str = "1390"           # default PIN; change from panel later

    # --- network ---
    hostname: str = "chiz"

    # --- currency / locale ---
    currency: str = "تومان"
    locale: str = "fa"

    # --- payment ---
    # manual   : seller approves from the admin panel (always available)
    # free     : zero-cost items auto-approved (useful for testing)
    # zarinpal : QR + status polling (needs merchant id)
    payment_provider: str = "manual"
    zarinpal_merchant_id: str = ""
    zarinpal_sandbox: bool = True
    payment_poll_seconds: float = 3.0
    payment_timeout_s: int = 180      # give up waiting after this

    # --- orders ---
    order_ttl_minutes: int = 30       # pending orders older than this expire

    # --- hardware buttons (USB encoder keymap) ---
    keymap: dict = field(default_factory=lambda: {
        "up": pygame_keyname_to_code("up"),
        "down": pygame_keyname_to_code("down"),
        "left": pygame_keyname_to_code("left"),
        "right": pygame_keyname_to_code("right"),
        "confirm": pygame_keyname_to_code("return"),
        "cancel": pygame_keyname_to_code("escape"),
    })

    # --- runtime flags (not user-facing) ---
    headless: bool = False            # set by kiosk --headless


def pygame_keyname_to_code(name: str) -> int:
    """Map a pygame key name to its scancode constant without importing pygame."""
    # Keep this dependency-light: constants match pygame.constants.
    codes = {
        "up": 273, "down": 274, "left": 276, "right": 275,
        "return": 13, "escape": 27, "space": 32,
        "w": 119, "s": 115, "a": 97, "d": 100,
        "enter": 13, "backspace": 8,
    }
    return codes.get(name.lower(), 0)


def _apply_file(cfg: Config, path: Path) -> None:
    if not path.exists():
        return
    try:
        import tomllib  # py3.11+
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            return  # no TOML support available; defaults + env still work

    with open(path, "rb") as fh:
        try:
            data = tomllib.load(fh)
        except Exception:
            return

    for f in fields(Config):
        val = _get(data, ["booth", f.name])
        if val is None:
            val = _get(data, [f.name])
        if val is None:
            continue
        cur = getattr(cfg, f.name)
        if isinstance(cur, Path):
            val = Path(str(val))
            if not val.is_absolute():
                val = PROJECT_ROOT / val
        elif isinstance(cur, dict):
            merged = dict(cur)
            if isinstance(val, dict):
                merged.update({str(k): int(v) for k, v in val.items()})
            val = merged
        try:
            setattr(cfg, f.name, val)
        except Exception:
            pass


def _apply_env(cfg: Config, env: dict | None = None) -> None:
    env = os.environ if env is None else env
    for f in fields(Config):
        var = f"CHIZ_{f.name.upper()}"
        if var not in env:
            continue
        raw = env[var]
        cur = getattr(cfg, f.name)
        try:
            if isinstance(cur, bool):
                setattr(cfg, f.name, raw.strip().lower() in ("1", "true", "yes", "on"))
            elif isinstance(cur, int):
                setattr(cfg, f.name, int(raw))
            elif isinstance(cur, float):
                setattr(cfg, f.name, float(raw))
            elif isinstance(cur, Path):
                p = Path(raw)
                setattr(cfg, f.name, p if p.is_absolute() else PROJECT_ROOT / p)
            else:
                setattr(cfg, f.name, raw)
        except (ValueError, TypeError):
            pass


def load_config(toml_path: Path | None = None) -> Config:
    cfg = Config()
    _apply_file(cfg, toml_path or DEFAULT_TOML)
    _apply_env(cfg)
    return cfg

