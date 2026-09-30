# SFX

Optional `.wav`/`.ogg` overrides for the built-in 8-bit synth engine.
If a file with the expected name exists (e.g. `coin.wav`), the sound module
loads it; otherwise it synthesizes the effect at runtime (`kiosk/sound.py`).

Expected names: `move`, `select`, `back`, `coin`, `success`, `error`, `boot`.
