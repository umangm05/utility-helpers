#!/usr/bin/env python3
"""Tool-first layout + "Try a sample" checks (UH polish D1 + D2).

D1  Every tool page (all tools in site.config.json), desktop 1280 x 900, fresh context:
    the tool (.tool) comes BEFORE the intro copy (.tool-intro) in the DOM, the tool's top
    edge is above the fold (< 900 px), and the intro paragraph is still on the page and
    non-empty.
D2  Each "Try a sample" button, ONE click in a fresh context, must (a) fetch the bundled
    file from /samples/ on this origin and (b) produce a result on screen. The home
    "Drop anything" sample buttons must each offer the matching tool, and following the
    offer must hand the sample over to that tool and produce its result there too.

Usage:
    python3 scripts/test_samples.py                 # serves ./dist locally
    python3 scripts/test_samples.py --base https://deploy-preview-N--utility-helpers.netlify.app
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_tools import free_port, serve  # noqa: E402
from test_consent import block_preview_drawer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FOLD = 900
# This build ships no (LGPL) fallback HEIC decoder: only Safari decodes HEIC natively, so in
# headless Chromium the HEIC known answer is the tool's honest "cannot open HEIC" message
# (same rule as test_file_tools.py). With a fallback decoder the real conversion is required.
NO_HEIC = "LIB_URL" not in (ROOT / "src" / "tools" / "heic-decoder.ts").read_text(encoding="utf-8")
HEIC_HONEST = "cannot open HEIC"

OK = "el => el && el.dataset.kind === 'ok'"

# slug, button, (selector that must be status-ok OR hold a result), sample paths expected, note
TOOL_SAMPLES = [
    ("resize-image", "#ri-sample", "#ri-status", ["/samples/sample-portrait.jpg"], "#ri-out li"),
    ("pdf-tools", "#pdf-sample", "#pdf-status", ["/samples/sample.pdf", "/samples/sample-portrait.jpg"], "#pdf-out li"),
    ("heic-to-jpg", "#heic-sample", "#heic-status", ["/samples/sample.heic"], "#heic-out li"),
    ("passport-size-photo", "#pp-sample", "#pp-meta", ["/samples/sample-portrait.jpg"], None),
    ("qr-code-generator", "#qr-sample", "#qr-scan-status", ["/samples/sample-qr.png"], None),
    ("background-remover", "#bg-sample", "#bg-status", ["/samples/sample-portrait.jpg"], None),
]

# home sample button -> tool chip to follow -> what that tool must show
HOME_SAMPLES = [
    ("photo", "resize-image", "#ri-in", "sample-portrait.jpg · 1200 × 1600"),
    ("pdf", "pdf-tools", "#pdf-summary", "2 pages"),
    ("heic", "heic-to-jpg", "#heic-status", "1 photo converted"),
    ("qr", "qr-code-generator", "#qr-result", "https://utility-helpers.netlify.app/"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base")
    ap.add_argument("--port", type=int, default=8098)
    ap.add_argument("--skip-bg", action="store_true", help="skip the slow AI background-remover sample")
    args = ap.parse_args()
    httpd = None
    if args.base:
        base = args.base.rstrip("/")
    else:
        port = free_port(args.port)
        base = f"http://127.0.0.1:{port}"
        httpd = serve(ROOT / "dist", port)
        time.sleep(0.3)
    tools = json.loads((ROOT / "site.config.json").read_text())["tools"]
    results: list[bool] = []

    def check(cond: bool, label: str, obs) -> None:
        results.append(bool(cond))
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}: {obs}")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()

        def ctx():
            c = browser.new_context(viewport={"width": 1280, "height": FOLD}, accept_downloads=True)
            block_preview_drawer(c)
            return c

        print(f"D1 tool-first layout at 1280 x {FOLD} against {base}\n" + "=" * 72)
        for t in tools:
            c = ctx()
            page = c.new_page()
            page.goto(f"{base}/{t['slug']}/", wait_until="load")
            obs = page.evaluate("""() => {
              const tool = document.querySelector('main .tool'), intro = document.querySelector('main .tool-intro');
              return { toolTop: tool ? Math.round(tool.getBoundingClientRect().top) : null,
                       toolFirst: !!(tool && intro && (tool.compareDocumentPosition(intro) & Node.DOCUMENT_POSITION_FOLLOWING)),
                       introChars: intro ? intro.textContent.trim().length : 0 };
            }""")
            check(obs["toolTop"] is not None and obs["toolTop"] < FOLD and obs["toolFirst"] and obs["introChars"] > 40,
                  f"/{t['slug']}/", obs)
            c.close()

        print(f"\nD2 'Try a sample' on each file tool (one click, fresh context)\n" + "=" * 72)
        for slug, btn, st, paths, rows in TOOL_SAMPLES:
            if slug == "background-remover" and args.skip_bg:
                continue
            c = ctx()
            page = c.new_page()
            got: list[str] = []
            page.on("request", lambda r: got.append(r.url))
            page.goto(f"{base}/{slug}/", wait_until="load")
            if slug == "qr-code-generator":
                page.click("#qr-tab-scan")
            page.click(btn)
            try:
                page.wait_for_function(f"(() => {{ const el = document.querySelector('{st}'); return ({OK})(el); }})",
                                       timeout=150_000)
                ok_state = True
            except Exception:
                ok_state = False
            text = page.text_content(st) or ""
            n_rows = page.locator(rows).count() if rows else None
            if slug == "qr-code-generator":
                text += " | " + page.input_value("#qr-result")
            fetched = sorted({u.split(base, 1)[-1] for u in got if "/samples/" in u})
            cond = ok_state and fetched == sorted(set(paths)) and (rows is None or n_rows >= 1)
            label = slug
            if slug == "heic-to-jpg" and NO_HEIC:
                cond, label = HEIC_HONEST in text and fetched == paths, f"{slug} (no HEIC decoder in Chromium: honest message)"
            check(cond, label, {"status": text.strip()[:90], "result_rows": n_rows, "fetched": fetched})
            c.close()

        print(f"\nD2 home 'Drop anything' sample buttons -> offer -> tool result\n" + "=" * 72)
        for kind, slug, sel, want in HOME_SAMPLES:
            if kind == "heic" and NO_HEIC:
                want = HEIC_HONEST
            c = ctx()
            page = c.new_page()
            page.goto(f"{base}/", wait_until="load")
            page.click(f"[data-sample={kind}]")
            chip = page.locator(f"#drop-result a[href='/{slug}/']")
            chip.wait_for(timeout=15_000)
            offer = (page.text_content("#drop-result") or "").strip()
            chip.click()
            page.wait_for_url(f"**/{slug}/")
            try:
                page.wait_for_function(
                    "([s, w]) => { const el = document.querySelector(s); return el && ((el.value ?? '') + el.textContent).includes(w); }",
                    arg=[sel, want], timeout=60_000)
                ok = True
            except Exception:
                ok = False
            el = page.locator(sel)
            seen = (el.input_value() if sel == "#qr-result" else el.text_content() or "").strip()
            check(ok, f"home sample '{kind}' -> /{slug}/", {"offer": offer[:80], "tool shows": seen[:80]})
            c.close()
        browser.close()
    if httpd:
        httpd.shutdown()
    print("\n" + "=" * 72 + f"\nResults: {sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
