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
