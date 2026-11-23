#!/usr/bin/env python3
"""Build the bundled "Try a sample" files in public/samples/ (except sample.heic,
which scripts/make_heic_sample.py makes).

  sample-portrait.jpg  1200 x 1600 illustrated head-and-shoulders portrait on a studio
                       backdrop. Used by Image Resizer, Background Remover, Passport Photo,
                       PDF tools (as the photo page) and the home "Drop anything" zone.
  sample.pdf           2-page A4 document (vector text, pdf-lib). PDF tools + drop zone.
  sample-qr.png        QR code for https://utility-helpers.netlify.app/ (qrcode-generator,
                       the same library the QR tool ships). QR scanner + drop zone.

Why self-made: every pixel and byte is drawn by this script, so there is no third-party
image, font file or photo in the repo and no licence question. The PDF uses the PDF
standard-14 Helvetica (a built-in font name, nothing embedded from a font file).
Output is deterministic (seeded noise), so re-running produces the same files.

Usage:  python3 scripts/make_samples.py
Needs:  Pillow + numpy (dev only; the outputs are committed), node with node_modules installed.
"""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "samples"
SITE = "https://utility-helpers.netlify.app/"


def node(js: str) -> bytes:
    """Run an ES-module snippet with the repo's node_modules and return its stdout."""
    return subprocess.run(["node", "--input-type=module", "-e", js], cwd=ROOT, check=True,
                          capture_output=True, timeout=60).stdout


def portrait() -> bytes:
    w, h = 1200, 1600
    # Studio backdrop: soft vertical gradient + vignette.
    y = np.linspace(0, 1, h)[:, None]
    x = np.linspace(-1, 1, w)[None, :]
    top, bottom = np.array([226, 233, 242]), np.array([176, 190, 207])
    bg = top + (bottom - top) * y[..., None]
    bg = bg * (1 - 0.18 * (x ** 2))[..., None]
    img = Image.fromarray(bg.clip(0, 255).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(img)
    s = w / 900                                                   # drawn on a 900-wide grid
    def e(cx, cy, rx, ry, fill):
        d.ellipse([(cx - rx) * s, (cy - ry) * s, (cx + rx) * s, (cy + ry) * s], fill=fill)
    e(450, 1250, 400, 330, (31, 59, 99))                           # shoulders (jacket)
    d.polygon([(385 * s, 935 * s), (450 * s, 1050 * s), (515 * s, 935 * s)], fill=(240, 240, 236))  # collar
    d.rectangle([395 * s, 760 * s, 505 * s, 940 * s], fill=(190, 130, 88))                       # neck
    e(450, 570, 190, 245, (198, 138, 92))                          # face
    e(262, 585, 26, 48, (186, 126, 82)); e(638, 585, 26, 48, (186, 126, 82))                     # ears
    d.pieslice([245 * s, 300 * s, 655 * s, 560 * s], 180, 360, fill=(43, 29, 20))              # hair
    e(268, 470, 22, 60, (43, 29, 20)); e(632, 470, 22, 60, (43, 29, 20))                         # sideburns
    e(385, 565, 30, 18, (250, 250, 248)); e(515, 565, 30, 18, (250, 250, 248))                   # eyes
    e(385, 565, 14, 14, (40, 28, 22)); e(515, 565, 14, 14, (40, 28, 22))
    d.line([(350 * s, 520 * s), (420 * s, 512 * s)], fill=(43, 29, 20), width=int(10 * s))     # brows
    d.line([(480 * s, 512 * s), (550 * s, 520 * s)], fill=(43, 29, 20), width=int(10 * s))
    d.line([(450 * s, 590 * s), (438 * s, 640 * s), (458 * s, 645 * s)], fill=(160, 100, 66), width=int(6 * s))
    d.arc([395 * s, 620 * s, 505 * s, 700 * s], 20, 160, fill=(122, 59, 42), width=int(8 * s))  # smile
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    # Fine sensor-like grain so it compresses like a real photo (seeded: deterministic).
    grain = np.random.default_rng(7).normal(0, 2.5, (h, w, 1))
    arr = (np.asarray(img, dtype=np.float32) + grain).clip(0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr, "RGB").save(buf, "JPEG", quality=85, optimize=True)
    return buf.getvalue()


def pdf() -> bytes:
    return node("""
import { PDFDocument, StandardFonts, rgb } from "pdf-lib";
const d = await PDFDocument.create();
d.setTitle("Utility Helpers sample PDF"); d.setAuthor("Utility Helpers"); d.setProducer("pdf-lib");
const fixed = new Date("2026-11-23T00:00:00Z"); d.setCreationDate(fixed); d.setModificationDate(fixed);
const bold = await d.embedFont(StandardFonts.HelveticaBold);
const font = await d.embedFont(StandardFonts.Helvetica);
const lines = [
  ["This is a sample PDF made by Utility Helpers.", "Try merging it with a photo, splitting it,", "extracting a page or turning it into JPGs."],
  ["Every tool runs in your browser.", "Nothing you add here is uploaded."],
];
for (const [i, body] of lines.entries()) {
  const p = d.addPage([595.28, 841.89]);
  p.drawRectangle({ x: 0, y: 841.89 - 90, width: 595.28, height: 90, color: rgb(0.96, 0.62, 0.04) });
  p.drawText(`Sample document, page ${i + 1} of 2`, { x: 48, y: 841.89 - 58, size: 24, font: bold, color: rgb(0.1, 0.1, 0.12) });
  body.forEach((t, k) => p.drawText(t, { x: 48, y: 680 - k * 26, size: 16, font, color: rgb(0.2, 0.2, 0.24) }));
  p.drawText(String(i + 1), { x: 290, y: 40, size: 12, font, color: rgb(0.4, 0.4, 0.45) });
}
process.stdout.write(Buffer.from(await d.save({ useObjectStreams: true })));
""")


def qr_png() -> bytes:
    raw = node(f"""
import qrcode from "qrcode-generator";
const q = qrcode(0, "M"); q.addData({json.dumps(SITE)}); q.make();
const n = q.getModuleCount(), m = [];
for (let r = 0; r < n; r++) {{ let row = ""; for (let c = 0; c < n; c++) row += q.isDark(r, c) ? "1" : "0"; m.push(row); }}
process.stdout.write(JSON.stringify(m));
""")
    rows = json.loads(raw)
    n, cell, quiet = len(rows), 12, 4
    side = (n + 2 * quiet) * cell
    img = Image.new("L", (side, side), 255)
    d = ImageDraw.Draw(img)
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            if v == "1":
                x, y = (c + quiet) * cell, (r + quiet) * cell
                d.rectangle([x, y, x + cell - 1, y + cell - 1], fill=0)
    buf = io.BytesIO()
    img.convert("1").save(buf, "PNG", optimize=True)
    return buf.getvalue()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in (("sample-portrait.jpg", portrait()), ("sample.pdf", pdf()), ("sample-qr.png", qr_png())):
        (OUT / name).write_bytes(data)
        print(f"{name}: {len(data):,} bytes")


if __name__ == "__main__":
    main()
