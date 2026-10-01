# Fonts

These fonts are committed (both are OFL-licensed, free to redistribute):

- `Vazirmatn-Regular.ttf` / `Vazirmatn-Bold.ttf` — Persian UI text
  https://github.com/rastikerdar/vazirmatn (OFL)
- `PressStart2P-Regular.ttf` — arcade numerals / Latin pixel text
  https://fonts.google.com/specimen/Press+Start+2P (OFL)

If they are ever missing, restore them with:

    .venv/bin/python scripts/fetch_fonts.py

`core/fonts.py` falls back to pygame's built-in font if files are absent
(Persian will render unshaped — always restore the real fonts).

## Brand display font — Sina Bold (`SSINABD.TTF`), NOT in git

The CHIZ slogan face. It is copyrighted (© 1998 MRT / Win2Farsi) with no
redistribution license and this repo is public, so the file is git-ignored.
Copy it onto every machine by hand:

    scp SSINABD.TTF pi@chiz.local:~/salesbooth/assets/fonts/

Without it the kiosk falls back to Lalezar automatically. Its digits are
mis-encoded (۶ draws as ۱, ۷ as U), so `kiosk/theme.py` never uses it for
any text that contains a number — prices and codes always come from Lalezar.
