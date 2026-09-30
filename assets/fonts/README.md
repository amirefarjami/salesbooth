# Fonts

Put the following font files here (they are NOT committed to the repo):

- `Vazirmatn-Regular.ttf` — Persian UI text
  https://github.com/rastikerdar/vazirmatn/releases
- `Vazirmatn-Bold.ttf` — Persian headings (same release)
- `PressStart2P-Regular.ttf` — arcade numerals / Latin pixel text
  https://fonts.google.com/specimen/Press+Start+2P

`core/fonts.py` resolves fonts in this order:
1. exact file in `assets/fonts/`
2. any installed system font with a matching family name
3. Pygame's built-in default font (fallback — Persian will look poor)

A helper is provided:

    .venv/bin/python scripts/fetch_fonts.py
