#!/usr/bin/env python3
"""Known-answer tests for the file tools added in UH-T2 (tools 1-5).

Each test opens the tool in a FRESH browser context, feeds it a known input
through the real file picker (set_input_files), and checks the known output
-- including the bytes of the downloaded file (pixel size, page count/order,
JPEG DPI) rather than just the on-screen text.

Privacy check, same run: every request the page makes is recorded; the test
fails if a tool page sends anything other than a GET to its own origin (the
page, its scripts/libraries, and the bundled sample file). The per-tool
request log is printed as evidence.

Usage:
    python3 scripts/test_file_tools.py                 # serves ./dist locally
    python3 scripts/test_file_tools.py --base https://deploy-preview-8--utility-helpers.netlify.app
"""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_tools import free_port, serve  # noqa: E402  (same local server as the 10 dev-tool tests)
from test_consent import block_preview_drawer, is_ad_loader  # noqa: E402

# Netlify injects its collaboration drawer into DEPLOY PREVIEWS only (not site code, absent in production).
# It is blocked, and its blocked requests are listed separately instead of counting as tool traffic.
PREVIEW_ONLY = ("/.netlify/scripts/cdp", "https://app.netlify.com/")

ROOT = Path(__file__).resolve().parent.parent
QR_TEXT = "https://utility-helpers.netlify.app/?q=known-answer"


# --------------------------------------------------------------------------- fixtures
def png_bytes(w: int, h: int) -> bytes:
    """A w x h RGB gradient PNG, stdlib only."""
    rows = b"".join(b"\x00" + bytes(v for x in range(w) for v in (x * 255 // w, y * 255 // h, 128))
                    for y in range(h))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 6)) + chunk(b"IEND", b""))


def jpeg_info(data: bytes) -> dict:
    """Width/height from the SOF marker, and the JFIF density (units, x, y)."""
    assert data[:2] == b"\xff\xd8", "not a JPEG"
    info: dict = {}
    if data[2:4] == b"\xff\xe0" and data[6:11] == b"JFIF\x00":
        info["dpi"] = (data[13], struct.unpack(">H", data[14:16])[0], struct.unpack(">H", data[16:18])[0])
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            info.update(w=w, h=h)
            return info
        seg = struct.unpack(">H", data[i + 2:i + 4])[0]
        i += 2 + seg
    raise ValueError("no SOF marker")


def png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def pdf_inspect(path: str) -> dict:
    out = subprocess.run(["node", str(ROOT / "scripts" / "pdf_fixture.mjs"), "inspect", path],
                         capture_output=True, text=True, check=True, cwd=ROOT)
    return json.loads(out.stdout)


def download(page, click_selector: str) -> bytes:
    with page.expect_download(timeout=30000) as d:
        page.click(click_selector)
    return Path(d.value.path()).read_bytes()


# --------------------------------------------------------------------------- tests
def t_resize_image(page, base, fx):
    page.goto(base + "/resize-image/", wait_until="domcontentloaded")
    page.set_input_files("#ri-file", fx["png"])
    page.wait_for_function("document.getElementById('ri-in').textContent.includes('1200 × 900')")
    page.fill("#ri-w", "600")
    h = page.input_value("#ri-h")
    page.click("#ri-go")
    page.wait_for_selector("#ri-out li")
    row = page.text_content("#ri-out li")
    jpg = jpeg_info(download(page, "#ri-out li button"))
    # second known answer: a size limit
    page.fill("#ri-target", "15")
    page.click("#ri-go")
    page.wait_for_function("document.getElementById('ri-status').textContent.startsWith('Done')")
    small = download(page, "#ri-out li button")
    obs = {"height_auto": h, "row": row, "jpeg": [jpg["w"], jpg["h"]], "limited_bytes": len(small)}
    ok = h == "450" and "600 × 450" in row and (jpg["w"], jpg["h"]) == (600, 450) and len(small) <= 15 * 1024
    return "resize-image", "1200x900 PNG, width 600; then max 15 KB", "600 × 450 JPG; second file <= 15360 bytes", obs, ok


def t_pdf_tools(page, base, fx):
    page.goto(base + "/pdf-tools/", wait_until="domcontentloaded")
    page.set_input_files("#pdf-file", [fx["a"], fx["b"]])
    page.wait_for_function("document.getElementById('pdf-summary').textContent === '3 pages from 2 files'")
    # Move B1 (page 3) to the top: up, up.
    page.click("button[aria-label='Move page 3 up']")
    page.click("button[aria-label='Move page 2 up']")
    page.click("#pdf-build")
    page.wait_for_selector("#pdf-out li")
    merged = Path(fx["dir"]) / "merged.pdf"
    merged.write_bytes(download(page, "#pdf-out li button"))
    m = pdf_inspect(str(merged))
    page.fill("#pdf-range", "2-3")
    page.click("#pdf-extract")
    page.wait_for_selector("#pdf-out li")
    ext = Path(fx["dir"]) / "ext.pdf"
    ext.write_bytes(download(page, "#pdf-out li button"))
    e = pdf_inspect(str(ext))
    page.fill("#pdf-range", "1")
    page.click("#pdf-jpg")
    page.wait_for_function("document.getElementById('pdf-status').textContent.includes('image ready')", timeout=30000)
    jpg = jpeg_info(download(page, "#pdf-out li button"))
    # photo -> PDF on A4 (landscape photo -> landscape page)
    page.click("#pdf-clear")
    page.set_input_files("#pdf-file", fx["png"])
    page.wait_for_function("document.getElementById('pdf-summary').textContent === '1 page from 1 file'")
    page.click("#pdf-build")
    page.wait_for_selector("#pdf-out li")
    one = Path(fx["dir"]) / "photo.pdf"
    one.write_bytes(download(page, "#pdf-out li button"))
    p = pdf_inspect(str(one))
    obs = {"merged": m["sizes"], "extract_2_3": e["sizes"], "page1_jpg_150dpi": [jpg["w"], jpg["h"]], "photo_pdf": p["sizes"]}
    ok = (m["sizes"] == [[400, 400], [200, 200], [300, 300]] and e["sizes"] == [[200, 200], [300, 300]]
          and (jpg["w"], jpg["h"]) == (833, 833) and p["sizes"] == [[841.89, 595.28]])
    return ("pdf-tools", "a.pdf (200,300pt) + b.pdf (400pt); move p3 to top; extract 2-3; p1 -> JPG 150 DPI; PNG -> A4",
            "merged [400,200,300]; extract [200,300]; JPG 833x833; A4 landscape 841.89x595.28", obs, ok)


def t_heic_to_jpg(page, base, fx):
    page.goto(base + "/heic-to-jpg/", wait_until="domcontentloaded")
    page.set_input_files("#heic-file", fx["heic"])
    page.wait_for_function("['ok','error'].includes(document.getElementById('heic-status').dataset.kind)", timeout=60000)
    status = page.text_content("#heic-status")
    row = page.text_content("#heic-out li") if page.query_selector("#heic-out li") else ""
    jpg = jpeg_info(download(page, "#heic-out li button")) if row else {}
    obs = {"status": status, "row": row, "jpeg": [jpg.get("w"), jpg.get("h")]}
    if "LIB_URL" not in (ROOT / "src" / "tools" / "heic-decoder.ts").read_text(encoding="utf-8"):
        # Build without the (LGPL) fallback decoder: headless Chromium has no native HEIC, so the
        # known answer is the honest explanation, not a broken result.
        ok = "cannot open HEIC" in status and not row
        return ("heic-to-jpg", "sample.heic, no fallback decoder in this build", "honest 'cannot open HEIC' message",
                obs, ok)
    ok = "640 × 480" in row and (jpg.get("w"), jpg.get("h")) == (640, 480)
    return "heic-to-jpg", "public/samples/sample.heic (640x480 HEVC test pattern)", "sample.jpg 640 × 480", obs, ok


def t_qr(page, base, fx):
    page.goto(base + "/qr-code-generator/", wait_until="domcontentloaded")
    page.fill("#qr-text", QR_TEXT)
    page.wait_for_function("document.getElementById('qr-meta').dataset.kind === 'ok'")
    meta = page.text_content("#qr-meta")
    page.click("#qr-verify")
    page.wait_for_function("['ok','error'].includes(document.getElementById('qr-check').dataset.kind)", timeout=20000)
    check = page.text_content("#qr-check")
    png = download(page, "#qr-png")
    qr_png = Path(fx["dir"]) / "qr.png"
    qr_png.write_bytes(png)
    page.click("#qr-tab-scan")
    page.set_input_files("#qr-img", str(qr_png))
    page.wait_for_function("document.getElementById('qr-result').value !== ''", timeout=20000)
    scanned = page.input_value("#qr-result")
    # UPI payload
    page.click("#qr-tab-make")
    page.select_option("#qr-kind", "upi")
    page.fill("#qr-vpa", "shop@okicici")
    page.fill("#qr-payee", "Test Shop")
    page.fill("#qr-amt", "10")
    page.wait_for_function("document.getElementById('qr-meta').dataset.kind === 'ok'")
    page.click("#qr-verify")
    page.wait_for_function("document.getElementById('qr-check').textContent.includes('upi://')", timeout=20000)
    upi = page.text_content("#qr-check")
    obs = {"meta": meta, "check": check, "png": png_size(png), "scanned": scanned, "upi": upi}
    ok = (meta.startswith("Version 4 · 33 × 33") and check == f"Scans OK: {QR_TEXT}" and png_size(png) == (1024, 1024)
          and scanned == QR_TEXT and upi == "Scans OK: upi://pay?pa=shop@okicici&pn=Test%20Shop&am=10.00&cu=INR")
    return ("qr-code-generator", f"{QR_TEXT!r} (ECC M); scan the downloaded PNG; UPI shop@okicici / Test Shop / 10",
            "Version 4 · 33 × 33; scans back exactly; 1024 px PNG; upi://pay?pa=shop@okicici&pn=Test%20Shop&am=10.00&cu=INR",
            obs, ok)


def t_passport(page, base, fx):
    page.goto(base + "/passport-size-photo/", wait_until="domcontentloaded")
    page.set_input_files("#pp-file", fx["png"])
    page.wait_for_function("document.getElementById('pp-meta').dataset.kind === 'ok'")
    meta = page.text_content("#pp-meta")
    single = jpeg_info(download(page, "#pp-single"))
    sheet = jpeg_info(download(page, "#pp-sheetbtn"))
    page.select_option("#pp-size", "50.8x50.8")
    page.wait_for_function("document.getElementById('pp-meta').textContent.includes('600 × 600')")
    meta2 = page.text_content("#pp-meta")
    obs = {"meta": meta, "single": [single["w"], single["h"], single.get("dpi")], "sheet": [sheet["w"], sheet["h"]],
           "meta_2x2": meta2}
    ok = ("413 × 531 px at 300 DPI · 8 photos on a 4×6 in sheet" in meta and (single["w"], single["h"]) == (413, 531)
          and single.get("dpi") == (1, 300, 300) and (sheet["w"], sheet["h"]) == (1800, 1200)
          and "6 photos on a 4×6 in sheet" in meta2)
    return ("passport-size-photo", "1200x900 photo; 35x45 mm; then 2x2 in",
            "413 × 531 px JPG tagged 300 DPI; 1800 × 1200 sheet with 8 photos; 2x2 in -> 600 × 600, 6 photos", obs, ok)


ALL = [t_resize_image, t_pdf_tools, t_heic_to_jpg, t_qr, t_passport]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", help="test a deployed site instead of ./dist")
    ap.add_argument("--port", type=int, default=8098)
    ap.add_argument("--only", help="comma-separated test names")
    args = ap.parse_args()
    httpd = None
    if args.base:
        base = args.base.rstrip("/")
    else:
        port = free_port(args.port)
        base = f"http://127.0.0.1:{port}"
        httpd = serve(ROOT / "dist", port)
        time.sleep(0.3)
    origin = "{0.scheme}://{0.netloc}".format(urlparse(base))

    tmp = tempfile.mkdtemp(prefix="uh-ft-")
    subprocess.run(["node", str(ROOT / "scripts" / "pdf_fixture.mjs"), "make", tmp], check=True, cwd=ROOT,
                   capture_output=True)
    png = Path(tmp) / "photo.png"
    png.write_bytes(png_bytes(1200, 900))
    fx = {"dir": tmp, "png": str(png), "a": str(Path(tmp) / "a.pdf"), "b": str(Path(tmp) / "b.pdf"),
          "heic": str(ROOT / "public" / "samples" / "sample.heic")}

    from playwright.sync_api import sync_playwright
    print(f"Known-answer tests for the 5 file tools against {base}\n" + "=" * 70)
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for fn in ALL:
            if args.only and fn.__name__[2:].replace("_", "-") not in args.only.split(","):
                continue
            ctx = browser.new_context(accept_downloads=True)
            block_preview_drawer(ctx)
            page = ctx.new_page()
            reqs: list[tuple[str, str]] = []
            page.on("request", lambda r, reqs=reqs: reqs.append((r.method, r.url)))
            try:
                name, inp, exp, obs, ok = fn(page, base, fx)
            except Exception as e:  # noqa: BLE001
                name, inp, exp, obs, ok = fn.__name__, "", "", {"error": str(e)[:400]}, False
            injected = [u for m, u in reqs if u.startswith(PREVIEW_ONLY) or urlparse(u).path.startswith(PREVIEW_ONLY[0])]
            # AdSense loader GET (standard tag in <head>, aborted in tests): expected, but it
            # must never carry tool content.
            ads = [u for m, u in reqs if m == "GET" and is_ad_loader(u) and "?client=ca-pub-" in u and "&" not in u]
            reqs = [(m, u) for m, u in reqs if u not in injected and u not in ads]
            bad = [f"{m} {u}" for m, u in reqs
                   if not u.startswith(("blob:", "data:")) and (m != "GET" or not u.startswith(origin))]
            # Consent banner analytics are off in a fresh context (no choice made), so nothing else may appear.
            ok = ok and not bad
            results.append(ok)
            print(f"\n  [{'PASS' if ok else 'FAIL'}] {name}")
            print(f"    Input:    {inp}\n    Expected: {exp}\n    Observed: {obs}")
            paths = sorted({urlparse(u).path for m, u in reqs if u.startswith(origin)})
            print(f"    Network:  {len(reqs)} requests, all GET {origin}: {not bad}; paths: {', '.join(paths)}")
            if bad:
                print(f"    OFF-DEVICE REQUESTS: {bad}")
            if injected:
                print(f"    Netlify preview drawer (blocked, preview-only, not site code): {len(injected)} requests")
            ctx.close()
        browser.close()
    if httpd:
        httpd.shutdown()
    print("\n" + "=" * 70 + f"\nResults: {sum(results)}/{len(results)} passed")
    return 0 if results and all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
