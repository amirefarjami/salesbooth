"""CHIZ Booth — procedural 8-bit SFX engine (no external assets needed)."""
from __future__ import annotations

import math
import struct

import pygame


class SoundEngine:
    """Synthesizes retro chiptune effects with numpy-free pure Python."""

    def __init__(self, config) -> None:
        self.enabled = bool(getattr(config, "sound", True))
        self.volume = float(getattr(config, "sfx_volume", 0.8))
        self._sounds: dict[str, pygame.mixer.Sound] = {}
        self.ok = False
        if not self.enabled:
            return
        try:
            pygame.mixer.pre_init(22050, -16, 1, 256)  # small buffer = snappy
            pygame.mixer.init()
            self.ok = True
        except pygame.error:
            self.enabled = False

    def _make(self, gen, dur: float) -> pygame.mixer.Sound:
        rate = 22050
        n = int(rate * dur)
        buf = bytearray()
        for i in range(n):
            t = i / rate
            v = max(-1.0, min(1.0, gen(t, i / n)))
            buf += struct.pack("<h", int(v * 32000))
        return pygame.mixer.Sound(buffer=bytes(buf))

    def load(self) -> None:
        if not self.ok:
            return
        synth = {   # name: (generator, seconds)
            "move": (self._sfx_move, 0.06),
            "select": (self._sfx_select, 0.18),
            "back": (self._sfx_back, 0.12),
            "coin": (self._sfx_coin, 0.45),
            "success": (self._sfx_success, 0.6),
            "error": (self._sfx_error, 0.35),
            "boot": (self._sfx_boot, 0.4),
            "alarm": (self._sfx_alarm, 0.3),
        }
        for name, (gen, dur) in synth.items():
            try:
                self._sounds[name] = self._make(gen, dur)
            except pygame.error:
                continue

    # --- effect definitions (t: seconds, p: 0..1 progress) ---

    def _sfx_move(self, t, p):
        f = 620 + 140 * p
        env = 1.0 - p
        return 0.5 * env * math.sin(2 * math.pi * f * t)

    def _sfx_select(self, t, p):
        f = 440 + 660 * (1 - math.exp(-30 * t))
        env = math.exp(-8 * t)
        return 0.6 * env * math.sin(2 * math.pi * f * t)

    def _sfx_back(self, t, p):
        f = 500 - 260 * p
        env = 1.0 - p
        return 0.45 * env * math.sin(2 * math.pi * f * t)

    def _sfx_coin(self, t, p):
        # classic double-bleep coin
        if t < 0.08:
            return 0.6 * math.sin(2 * math.pi * 988 * t)
        return 0.6 * math.sin(2 * math.pi * 1319 * (t - 0.08)) * math.exp(-6 * (t - 0.08))

    def _sfx_success(self, t, p):
        # rising arpeggio C-E-G-C
        notes = [523.25, 659.25, 783.99, 1046.5]
        i = min(3, int(t / 0.09))
        lt = t - i * 0.09
        env = math.exp(-5 * lt)
        return 0.55 * env * (math.sin(2 * math.pi * notes[i] * lt)
                             + 0.3 * math.sin(2 * math.pi * notes[i] * 2 * lt))

    def _sfx_error(self, t, p):
        f = 180 - 60 * p
        env = (1.0 - p) * (0.7 + 0.3 * math.sin(2 * math.pi * 30 * t))
        return 0.5 * env * math.sin(2 * math.pi * f * t)

    def _sfx_boot(self, t, p):
        f = 220 + 440 * p * p
        env = 0.9 - 0.4 * p
        return 0.4 * env * math.sin(2 * math.pi * f * t)

    def _sfx_alarm(self, t, p):
        # two-tone square-ish beep for the closing showcase door
        f = 880 if t < 0.12 else 660
        sq = 1.0 if math.sin(2 * math.pi * f * t) >= 0 else -1.0
        return 0.35 * sq * (1.0 - p) ** 0.5

    # --- API ---

    def play(self, name: str) -> None:
        if not self.ok or not self.enabled:
            return
        snd = self._sounds.get(name)
        if snd:
            snd.set_volume(self.volume)
            snd.play()

    def shutdown(self) -> None:
        if self.ok:
            try:
                pygame.mixer.quit()
            except pygame.error:
                pass
