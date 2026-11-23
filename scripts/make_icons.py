#!/usr/bin/env python3
"""Render the PWA / home-screen icons from the favicon design (amber tile + dark "V" tick).

One-off asset generator like make_og_image.py (needs Pillow). Output, committed:
  public/assets/icon-192.png, icon-512.png       (purpose "any": rounded tile)
  public/assets/icon-maskable-512.png            (purpose "maskable": full bleed, mark inside the 80% safe zone)
  public/assets/apple-touch-icon.png  (180x180)  (iOS rounds the corners itself)

Usage:  python3 scripts/make_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "assets"
AMBER = (245, 158, 11, 255)
INK = (26, 18, 6, 255)
SS = 4  # supersampling for smooth edges


def icon(size: int, *, rounded: bool, mark_scale: float) -> Image.Image:
    s = size * SS
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if rounded:
        d.rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 7 / 32), fill=AMBER)
    else:
        d.rectangle((0, 0, s, s), fill=AMBER)
    # favicon.svg path: M9 10 l7 13 7-13 on a 32 grid, stroke 3.5, round caps/joins
    k = s / 32 * mark_scale
    off = s / 2 - 16 * k
    pts = [(9 * k + off, 10 * k + off), (16 * k + off, 23 * k + off), (23 * k + off, 10 * k + off)]
    w = max(1, int(3.5 * k))
    d.line(pts, fill=INK, width=w, joint="curve")
    r = w / 2
    for x, y in (pts[0], pts[2]):
        d.ellipse((x - r, y - r, x + r, y + r), fill=INK)
    return im.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    icon(192, rounded=True, mark_scale=1).save(OUT / "icon-192.png", optimize=True)
    icon(512, rounded=True, mark_scale=1).save(OUT / "icon-512.png", optimize=True)
    icon(512, rounded=False, mark_scale=0.72).save(OUT / "icon-maskable-512.png", optimize=True)
    icon(180, rounded=False, mark_scale=0.85).convert("RGB").save(OUT / "apple-touch-icon.png", optimize=True)
    for f in ("icon-192.png", "icon-512.png", "icon-maskable-512.png", "apple-touch-icon.png"):
        print(f, (OUT / f).stat().st_size, "bytes")


if __name__ == "__main__":
    main()
