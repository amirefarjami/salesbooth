#!/usr/bin/env python3
"""Download the fonts the kiosk needs (Vazirmatn + Press Start 2P)."""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

URLS = {
    # Vazirmatn direct TTFs from the rastikerdar release CDN
    "Vazirmatn-Regular.ttf": "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Regular.ttf",
    "Vazirmatn-Bold.ttf": "https://raw.githubusercontent.com/rastikerdar/vazirmatn/master/fonts/ttf/Vazirmatn-Bold.ttf",
    # Press Start 2P from the google/fonts repo
    "PressStart2P-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/pressstart2p/PressStart2P-Regular.ttf",
}


def main() -> int:
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    failed = []
    for name, url in URLS.items():
        dest = FONT_DIR / name
        if dest.is_file() and dest.stat().st_size > 10_000:
            print(f"ok      {name}")
            continue
        try:
            print(f"fetch   {name} ...", end=" ", flush=True)
            urllib.request.urlretrieve(url, dest)
            print(f"{dest.stat().st_size // 1024} KB")
        except Exception as e:
            failed.append(name)
            print(f"FAILED ({e})")
    if failed:
        print("\nmanual download needed:", ", ".join(failed))
        print("see assets/fonts/README.md")
        return 1
    print("\nall fonts ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
