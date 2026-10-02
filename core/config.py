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
    scanlines: bool = False           # CRT scanline overlay (off: the
                                      # «کمیک قورمه» look is flat paper)
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
    payment_methods: list = field(default_factory=lambda: ["qr", "card"])
    pos_driver: str = "sim"           # card reader link: sim | none (PSP driver: TASKS #24)
    pos_sim_approve_s: float = 5.0    # simulator: «swipe» after N s (0 = never)
    payment_poll_seconds: float = 3.0
    payment_timeout_s: int = 180      # give up waiting after this

    # --- orders ---
    order_ttl_minutes: int = 30       # pending orders older than this expire

    # --- door lock (solenoid behind the glass, via relay) ---
    lock_enabled: bool = True         # auto-simulated when no GPIO lib
    lock_gpio: int = 17               # BCM pin driving the relay
    lock_active_high: bool = True     # relay board polarity
    door_open_s: int = 20             # countdown once the door is opened, for 1 item
    door_extra_per_item_s: int = 5    # + this for every extra item in the order
    door_warn_s: int = 5              # last N seconds: red light + alarm
    door_wait_s: int = 60             # unlocked but never opened → relock

    # --- door sensor (reed switch: closed door pulls the pin low) ---
    door_sensor_enabled: bool = True  # auto-simulated (key "d") without GPIO
    door_sensor_gpio: int = 27
    door_open_when_high: bool = True

    # --- booth lighting: MOSFET 1 = main light (PWM), MOSFET 2 = red lights ---
    lights_enabled: bool = True
    booth_light_gpio: int = 12
    warn_light_gpio: int = 13
    booth_light_dim: float = 0.15     # main light level during the warning

    # --- light inside the red confirm button (the only lit button) ---
    red_light_enabled: bool = True
    red_light_gpio: int = 22

    # --- hardware buttons (USB encoder keymap: key names or codes) ---
    keymap: dict = field(default_factory=lambda: {
        "slot1": "1", "slot2": "2", "slot3": "3",
        "slot4": "4", "slot5": "5", "slot6": "6",
        "confirm": "return",
        "cancel": "escape",
        "door_sim": "d",              # laptop only: open/close the door
    })

    # --- runtime flags (not user-facing) ---
    headless: bool = False            # set by kiosk --headless


def pygame_keyname_to_code(name: str) -> int:
    """Kept for old callers: key name -> pygame-ce key code."""
    from hardware.input import key_code
    return key_code(name)


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
                merged.update({str(k): v for k, v in val.items()})
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
            elif isinstance(cur, list):
                setattr(cfg, f.name, [x.strip() for x in raw.split(",") if x.strip()])
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

