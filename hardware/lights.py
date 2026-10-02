"""CHIZ Booth — booth lighting on two MOSFET channels, as light «scenes».

MOSFET 1 (`booth_light_gpio`) drives the booth's main light (PWM-dimmable).
MOSFET 2 (`warn_light_gpio`) drives the red lights (PWM too).

Each kiosk screen names a scene; short effects play on top of it:

  scenes    attract    main breathes 60–100 % every 4 s; every 25 s an
                       «insert coin» call: two short red pulses (+ the red
                       button lamp blinks fast — see `calling`)
            shop       steady 85 % (headroom for the add-to-cart blip)
            paywait    calm slow pulse while the payment is pending
            celebrate  payment approved: main pulses softly on every note
                       of the fanfare, red switches on its phrases, then
                       full light on the final chord
            door       100 %: the showcase lit while the door is open
            warn       last seconds / overtime: main dims, red on
  effects   poweron    red pressed on attract: main ramps up in 0.5 s
            blip       product added: a short brighter flash
            fail       payment failed: two slow red pulses, main dips

Changing scene cross-fades over 0.4 s. No full on/off flashing faster than
3 times a second (photosensitivity). Without GPIO a simulator keeps the
same API and the levels can be inspected (tests, laptop).
"""
from __future__ import annotations

import math

# fanfare note starts (seconds) — the same timeline as kiosk/sound.py
FANFARE_NOTES = (0.00, 0.12, 0.24, 0.36, 0.60, 0.72, 1.05, 1.17, 1.29)
FANFARE_PHRASES = (0.00, 0.60, 1.05)        # red lights switch only here
FANFARE_CHORD = 1.29

ATTRACT_PERIOD = 25.0                        # «insert coin» every 25 s
ATTRACT_CALL_AT = 22.0                       # …inside each period
EFFECT_LEN = {"poweron": 0.5, "blip": 0.18, "fail": 1.6}


class BoothLights:
    XFADE_S = 0.4

    def __init__(self, config) -> None:
        self.enabled = bool(getattr(config, "lights_enabled", True))
        self.dim = float(getattr(config, "booth_light_dim", 0.15))
        self.shop_level = float(getattr(config, "booth_light_level", 0.85))
        self.mode = "attract"
        self.scene_t = 0.0                   # seconds since the scene began
        self.effect: str | None = None
        self.effect_t = 0.0
        self._from = (1.0, 0.0)              # levels when the scene changed
        self.main = 1.0                      # current output levels 0..1
        self.red = 0.0
        self.calling = False                 # attract «insert coin» moment
        self._main_dev = self._red_dev = None
        if self.enabled:
            try:
                from gpiozero import PWMOutputDevice  # type: ignore

                self._main_dev = PWMOutputDevice(int(getattr(config, "booth_light_gpio", 12)),
                                                 initial_value=1.0, frequency=500)
                self._red_dev = PWMOutputDevice(int(getattr(config, "warn_light_gpio", 13)),
                                                initial_value=0.0, frequency=500)
            except Exception:
                self._main_dev = self._red_dev = None

    @property
    def simulated(self) -> bool:
        return self._main_dev is None

    # --- control ---

    def set(self, mode: str) -> None:
        if mode != self.mode:
            self._from = (self.main, self.red)
            self.mode = mode
            self.scene_t = 0.0

    def trigger(self, effect: str) -> None:
        if effect in EFFECT_LEN:
            self.effect = effect
            self.effect_t = 0.0

    # --- scenes ---

    def _scene(self, mode: str, t: float) -> tuple[float, float]:
        if mode == "attract":
            main = 0.8 + 0.2 * math.cos(2 * math.pi * t / 4.0)     # 60–100 %, 4 s
            ph = t % ATTRACT_PERIOD - ATTRACT_CALL_AT
            red = 1.0 if (0 <= ph < 0.15 or 0.35 <= ph < 0.5) else 0.0
            return main, red
        if mode == "paywait":
            return 0.72 + 0.13 * math.cos(2 * math.pi * t / 2.5), 0.0
        if mode == "celebrate":
            if t >= FANFARE_CHORD:
                return 1.0, 0.0                                    # full on the chord
            last = max(n for n in FANFARE_NOTES if n <= t)
            main = 0.7 + 0.3 * math.exp(-(t - last) / 0.05)        # soft pulse per note
            phrase = sum(1 for p in FANFARE_PHRASES if p <= t) - 1
            return main, 1.0 if phrase % 2 == 0 else 0.0
        if mode == "door":
            return 1.0, 0.0
        if mode == "warn":
            return self.dim, 1.0
        return self.shop_level, 0.0                                # shop / default

    def _apply_effect(self, main: float, red: float) -> tuple[float, float]:
        e, t = self.effect, self.effect_t
        if e == "poweron":
            k = min(1.0, t / EFFECT_LEN["poweron"])
            main = 0.2 + (main - 0.2) * (1 - (1 - k) ** 3)          # ease-out ramp
        elif e == "blip":
            k = t / EFFECT_LEN["blip"]
            main = main + (1.0 - main) * max(0.0, 1.0 - k)
        elif e == "fail":
            red = 1.0 if (0.0 <= t < 0.4 or 0.7 <= t < 1.1) else 0.0
            if t < 0.6:
                main = min(main, 0.4)
            elif t < 0.9:
                main = 0.4 + (main - 0.4) * (t - 0.6) / 0.3
        return main, red

    def tick(self, dt_ms: int) -> None:
        if not self.enabled:
            return
        dt = dt_ms / 1000.0
        self.scene_t += dt
        main, red = self._scene(self.mode, self.scene_t)
        if self.scene_t < self.XFADE_S:                            # cross-fade in
            k = self.scene_t / self.XFADE_S
            main = self._from[0] + (main - self._from[0]) * k
            red = self._from[1] + (red - self._from[1]) * k
        if self.effect is not None:
            self.effect_t += dt
            if self.effect_t >= EFFECT_LEN[self.effect]:
                self.effect = None
            else:
                main, red = self._apply_effect(main, red)
        ph = self.scene_t % ATTRACT_PERIOD - ATTRACT_CALL_AT
        self.calling = self.mode == "attract" and 0 <= ph < 1.2
        self.main = max(0.0, min(1.0, main))
        self.red = max(0.0, min(1.0, red))
        if self._main_dev is not None:
            self._main_dev.value = self.main
            self._red_dev.value = self.red

    def cleanup(self) -> None:
        if self._main_dev is not None:
            try:
                self._main_dev.value = 1.0     # leave the booth lit, red off
                self._red_dev.value = 0.0
                self._main_dev.close()
                self._red_dev.close()
            except Exception:
                pass
