"""CHIZ Booth — runtime controls the seller flips from the admin panel.

The kiosk runs as its own process (systemd), so the panel cannot call it
directly. Both sides instead share one small JSON file:

    data/control.json  →  {"booth_on": true, "brightness": 100}

The kiosk re-reads it every second (mtime check, no polling cost) and the
panel writes it atomically. Power is a *soft* off — the screen goes to a
standby card, the lights and LED strip go dark, the door stays locked and
the buttons are ignored — so the panel (and the WiFi) stay up and the booth
can always be switched back on remotely.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from core.config import DATA_DIR

CONTROL_PATH = DATA_DIR / "control.json"

DEFAULTS = {
    "booth_on": True,
    "brightness": 100,      # 0..100, scales every light in the booth
}


def _clamp(v, lo, hi, fallback):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return fallback


def read_control(path: Path | None = None) -> dict:
    """Current settings; defaults when the file is missing or unreadable."""
    p = Path(path or CONTROL_PATH)
    data = dict(DEFAULTS)
    try:
        raw = json.loads(p.read_text("utf-8"))
    except (OSError, ValueError):
        return data
    if isinstance(raw, dict):
        data["booth_on"] = bool(raw.get("booth_on", DEFAULTS["booth_on"]))
        data["brightness"] = _clamp(raw.get("brightness"),
                                    0, 100, DEFAULTS["brightness"])
    return data


def write_control(path: Path | None = None, **changes) -> dict:
    """Merge `changes` into the file atomically and return the new state."""
    p = Path(path or CONTROL_PATH)
    data = read_control(p)
    if "booth_on" in changes:
        data["booth_on"] = bool(changes["booth_on"])
    if "brightness" in changes:
        data["brightness"] = _clamp(changes["brightness"], 0, 100,
                                    data["brightness"])
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".control-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.replace(tmp, p)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return data


def control_mtime(path: Path | None = None) -> float:
    try:
        return Path(path or CONTROL_PATH).stat().st_mtime
    except OSError:
        return 0.0
