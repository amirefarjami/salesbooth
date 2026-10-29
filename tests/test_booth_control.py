"""Panel-controlled booth: power, master light level, screensaver playlist.

Also guards the one number the panel and the kiosk must agree on — the
product-card photo aspect the upload cropper cuts to.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from core import control as control_mod  # noqa: E402
from core import layout  # noqa: E402
from core.media import MediaItem, in_window, parse_hhmm  # noqa: E402


# ------------------------------------------------------------------ controls

def test_control_roundtrip_and_clamps(tmp_path):
    path = tmp_path / "control.json"
    assert control_mod.read_control(path) == control_mod.DEFAULTS      # no file

    state = control_mod.write_control(path, brightness=140)
    assert state["brightness"] == 100                                  # clamped
    state = control_mod.write_control(path, brightness=-5, booth_on=False)
    assert state == {"booth_on": False, "brightness": 0}
    assert json.loads(path.read_text("utf-8"))["booth_on"] is False

    path.write_text("not json", "utf-8")                               # corrupt
    assert control_mod.read_control(path)["brightness"] == 100


# ------------------------------------------------------------------ playlist

def test_hhmm_window_edges_and_midnight_wrap():
    assert parse_hhmm("09:05") == 9 * 60 + 5
    assert parse_hhmm("") is None and parse_hhmm("junk") is None

    assert in_window("", "", datetime(2026, 1, 1, 3, 0))
    assert in_window("10:00", "18:00", datetime(2026, 1, 1, 12, 0))
    assert not in_window("10:00", "18:00", datetime(2026, 1, 1, 19, 0))
    # overnight window: 22:00 → 02:00
    assert in_window("22:00", "02:00", datetime(2026, 1, 1, 23, 30))
    assert in_window("22:00", "02:00", datetime(2026, 1, 1, 1, 0))
    assert not in_window("22:00", "02:00", datetime(2026, 1, 1, 12, 0))


def test_video_length_comes_from_its_frames():
    video = MediaItem(id=1, kind="video", path="media/video/a/0001.jpg",
                      frames_dir="media/video/a", fps=12, frame_count=96,
                      duration_s=8)
    assert video.seconds == pytest.approx(8.0)
    still = MediaItem(id=2, kind="image", path="media/screens/a.jpg", duration_s=5)
    assert still.seconds == 5


def test_photo_aspect_matches_the_card():
    cw, ch = layout.card_w(480), layout.card_h(800)
    w, h = layout.photo_size(cw, ch)
    assert layout.PRODUCT_PHOTO_ASPECT == pytest.approx(w / h)


# ------------------------------------------------------------------ kiosk

@pytest.fixture()
def kiosk(tmp_path, monkeypatch):
    from kiosk.app import KioskApp

    path = tmp_path / "control.json"
    path.write_text(json.dumps({"booth_on": True, "brightness": 100}), "utf-8")
    monkeypatch.setattr(control_mod, "CONTROL_PATH", path)
    pygame = pytest.importorskip("pygame")
    pygame.init()
    from core.config import Config

    cfg = Config()
    cfg.db_path = tmp_path / "k.db"
    cfg.sound = False
    cfg.led_enabled = False
    cfg.lock_enabled = False
    cfg.red_light_enabled = False
    cfg.lights_enabled = True
    app = KioskApp(cfg, headless=True)
    for i in range(2):
        app.booth.products.create(f"کالا {i}", 10_000, stock=3, sort_order=i)

    def set_control(**changes):
        state = control_mod.write_control(path, **changes)
        stamp = path.stat().st_mtime + 5
        os.utime(path, (stamp, stamp))     # guarantee a new mtime
        app._control_poll = 0.0            # don't wait the poll interval
        return state

    yield app, set_control
    app.shutdown()


def test_power_off_ignores_buttons_and_wakes_up(kiosk):
    app, set_control = kiosk
    app.go("grid")
    app.step(16, ["slot1"])
    assert app.cart

    set_control(booth_on=False)
    app.step(16)
    assert app.cart == {}                        # the cart is dropped
    app.step(16, ["slot1", "confirm"])           # buttons do nothing
    assert app.cart == {} and app.current_name == "grid"
    for _ in range(6):                           # the cross-fade takes 0.4 s
        app.step(100)
    assert app.lights.main == 0.0                # the booth goes dark
    assert app.lights.red == 0.0

    set_control(booth_on=True)
    app.step(16)
    assert app.current_name == "attract"


def test_brightness_slider_scales_every_light(kiosk):
    app, set_control = kiosk
    set_control(brightness=50)
    app.step(16)
    assert app.lights.master == pytest.approx(0.5)
    assert app.led.master == pytest.approx(0.5)
    set_control(brightness=0)
    app.step(16)
    assert app.lights.master == 0.0 and app.led.master == 0.0


def test_screensaver_playlist_from_panel(kiosk):
    app, _ = kiosk
    attract = app._screens["attract"]
    assert attract.SLIDES[0][0] == "brand"

    app.booth.media.create(MediaItem(id=None, kind="image",
                                     path="img/products/demo_tx.png", duration_s=4))
    app.booth.media.create(MediaItem(id=None, kind="video", path="media/video/x/0001.jpg",
                                     frames_dir="media/video/x", fps=12,
                                     frame_count=120, duration_s=8))
    attract._build_playlist()
    kinds = [s["kind"] for s in attract.playlist]
    assert kinds == ["brand", "image", "video"]
    assert attract.playlist[1]["secs"] == 4
    assert attract.playlist[2]["secs"] == pytest.approx(10.0)   # its own length

    # a window that is closed right now hides the item
    app.booth.media.update(1, start_time="03:00", end_time="03:30")
    now = datetime.now()
    if not (3 <= now.hour < 3 or (now.hour == 3 and now.minute <= 30)):
        attract._build_playlist()
        assert "image" not in [s["kind"] for s in attract.playlist]
