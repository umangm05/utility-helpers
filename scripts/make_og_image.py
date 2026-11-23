#!/usr/bin/env python3
"""Render the shared social-share image assets/og.png (1200x630).

Every page's og:image / twitter:image points at /assets/og.png (src/layouts/Base.astro).
This is a one-off asset generator, NOT part of the zero-dependency build: it needs
Pillow (`pip install pillow`). Re-run only when the site name, tagline or tool
list in site.config.json changes, then commit the PNG.

Usage:
    python3 scripts/make_og_image.py
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "assets" / "og.png"
W, H = 1200, 630
BG, PANEL, BORDER = "#0b0d10", "#14171c", "#262b33"
FG, MUTED, ACCENT, ACCENT_FG = "#e7e9ee", "#9aa3af", "#f59e0b", "#1a1206"
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size)


def main() -> int:
    cfg = json.loads((ROOT / "site.config.json").read_text(encoding="utf-8"))
    site, tools = cfg["site"], cfg["tools"]

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=ACCENT)

    # Brand mark: the favicon "V" chevron on an amber rounded square.
    x0, y0, s = 80, 90, 112
    d.rounded_rectangle([x0, y0, x0 + s, y0 + s], radius=24, fill=ACCENT)
    k = s / 32
    d.line([(x0 + 9 * k, y0 + 10 * k), (x0 + 16 * k, y0 + 23 * k), (x0 + 23 * k, y0 + 10 * k)],
           fill=ACCENT_FG, width=int(3.5 * k), joint="curve")

    d.text((x0 + s + 36, y0 + 4), site["name"], font=font("DejaVuSans-Bold.ttf", 76), fill=FG)
    d.text((x0 + s + 40, y0 + 92), "utility-helpers.netlify.app", font=font("DejaVuSans.ttf", 28), fill=ACCENT)
    d.text((80, 262), site["tagline"], font=font("DejaVuSans.ttf", 38), fill=FG)
    d.text((80, 316), "No signup. Nothing uploaded. Works offline.", font=font("DejaVuSans.ttf", 30), fill=MUTED)

    # Tool chips, wrapped onto as many rows as needed.
    f = font("DejaVuSans.ttf", 24)
    x, y, pad, gap = 80, 400, 18, 14
    for t in tools:
        w = d.textlength(t["name"], font=f) + 2 * pad
        if x + w > W - 80:
            x, y = 80, y + 58
        d.rounded_rectangle([x, y, x + w, y + 44], radius=22, fill=PANEL, outline=BORDER, width=2)
        d.text((x + pad, y + 8), t["name"], font=f, fill=FG)
        x += w + gap

    img.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT.relative_to(ROOT)} {img.size[0]}x{img.size[1]} {OUT.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
