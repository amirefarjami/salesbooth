#!/usr/bin/env python3
"""Embed the rendered kiosk PNGs into data/preview/index.html as base64
data URIs (the sandboxed HTML preview serves the single file only)."""
from __future__ import annotations

import base64
import re
from pathlib import Path

PREVIEW = Path(__file__).resolve().parent.parent / "data" / "preview"


def main() -> int:
    html_path = PREVIEW / "index.html"
    html = html_path.read_text(encoding="utf-8")
    total = 0

    def repl(m: re.Match) -> str:
        nonlocal total
        name = m.group(1)
        png = PREVIEW / name
        if not png.is_file():
            return m.group(0)
        data = base64.b64encode(png.read_bytes()).decode()
        total += len(data)
        return f'src="data:image/png;base64,{data}"'

    html = re.sub(r'src="([0-9][^"]+\.png)"', repl, html)
    html_path.write_text(html, encoding="utf-8")
    print(f"inlined {total // 1024} KB of base64 images into index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
