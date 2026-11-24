#!/usr/bin/env python3
"""Known-answer + offline tests for the UH-T3 tools (6-10) and the PWA.

Phase 1 (online), one FRESH browser context per tool:
  open the tool page, wait until the service worker controls it, feed a known input through
  the real UI and check the known output (for the background remover: the pixels/alpha of the
  result and the downloaded PNG's header).
Phase 2 (offline), same contexts:
  network switched off (context.set_offline) and, when testing ./dist locally, the HTTP server
  itself is SHUT DOWN, so nothing can come from the network. Each page is reloaded and the same
  known answer is checked again. One extra check opens a tool page the context never visited
  (precache), to show the whole site is available offline after the first visit.

Privacy, same run: every request the contexts make (page + service worker) is recorded; a test
fails if anything other than a GET to the site's own origin is sent. The per-tool request log is
printed as evidence. Netlify's deploy-preview drawer is blocked and listed separately.

Usage:
    python3 scripts/test_new_tools.py                 # serves ./dist locally
    python3 scripts/test_new_tools.py --base https://deploy-preview-10--utility-helpers.netlify.app
"""

from __future__ import annotations

import argparse
import struct
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_tools import free_port, serve  # noqa: E402
from test_consent import block_preview_drawer, is_ad_loader  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PREVIEW_ONLY = ("/.netlify/scripts/cdp", "https://app.netlify.com/")
TT_TEXT = "the quick brown fox jumps over the lazy dog while seven bright stars watch from far above the hills"


def text(page, sel: str) -> str:
    return (page.text_content(sel) or "").strip()


def wait_text(page, sel: str, needle: str, timeout: int = 30000) -> None:
    page.wait_for_function("([s, n]) => (document.querySelector(s)?.textContent || '').includes(n)",
                           arg=[sel, needle], timeout=timeout)


def controlled(page) -> bool:
    """Wait for the service worker to be active and controlling this page (precache done)."""
    page.wait_for_function("navigator.serviceWorker && navigator.serviceWorker.controller !== null", timeout=30000)
    return page.evaluate("navigator.serviceWorker.ready.then(r => !!r.active)")


# --------------------------------------------------------------------------- known answers
def ka_typing(page) -> tuple[dict, bool]:
    page.click("#tt-own summary")
    page.fill("#tt-text", TT_TEXT)
    page.select_option("#tt-dur", "15")
    page.fill("#tt-text", TT_TEXT)             # the duration change regenerated text; re-apply own text
    page.wait_for_function("document.getElementById('tt-words').value === 'custom'")
    t0 = time.time()
    page.fill("#tt-input", TT_TEXT[:50])       # 50 correct characters, then wait out the 15 s clock
    page.wait_for_selector("#tt-result:not([hidden])", timeout=25000)
    secs = round(time.time() - t0, 1)
    s = text(page, "#tt-summary")
    obs = {"wpm": text(page, "#tt-wpm"), "summary": s[:90], "wall_clock_s": secs}
    return obs, obs["wpm"] == "40" and s.startswith("40 WPM · 100% accuracy · 50 of 50 characters")


def ka_money(page) -> tuple[dict, bool]:
    obs = {"emi": text(page, "#emi-out"), "emi_interest": text(page, "#emi-int")}
    page.click("#mc-tab-sip")
    obs["sip"] = text(page, "#sip-out")
    page.click("#mc-tab-gst")
    page.fill("#gst-a", "1180")
    page.select_option("#gst-m", "remove")
    obs["gst"] = [text(page, "#gst-net"), text(page, "#gst-tax"), text(page, "#gst-half")]
    page.click("#mc-tab-pct")
    obs["pct"] = [text(page, "#p1-out"), text(page, "#p2-out"), text(page, "#p3-out")]
    ok = (obs["emi"] == "₹9,650" and obs["emi_interest"].startswith("₹13,16,052")
          and obs["sip"] == "₹11,61,695 (11.62 lakh)"
          and obs["gst"] == ["₹1,000.00", "₹180.00", "₹90.00"]
          and obs["pct"] == ["30", "15%", "+25% (increase)"])
    return obs, ok


def ka_age(page) -> tuple[dict, bool]:
    page.fill("#age-dob", "1990-05-15")
    page.fill("#age-on", "2026-11-23")
    obs = {"age": text(page, "#age-out"), "days": text(page, "#age-days"), "born": text(page, "#age-wd"),
           "next": text(page, "#age-next")}
    page.click("#dt-tab-diff")
    page.fill("#diff-a", "2026-01-01")
    page.fill("#diff-b", "2026-12-31")
    obs["diff"] = text(page, "#diff-out")
    page.check("#diff-incl")
    obs["diff_incl"] = text(page, "#diff-out")
    obs["weekdays_incl"] = text(page, "#diff-wd")
    ok = (obs["age"] == "36 years, 6 months, 8 days" and obs["days"] == "13,341" and obs["born"] == "Tuesday"
          and obs["next"] == "in 173 days (turning 37)" and obs["diff"] == "364 days"
          and obs["diff_incl"] == "365 days" and obs["weekdays_incl"] == "261")
    return obs, ok


def ka_wheel(page) -> tuple[dict, bool]:
    page.fill("#sw-list", "Only One")
    page.click("#sw-spin")
    page.wait_for_selector("#sw-result[data-kind=ok]", timeout=15000)
    one = page.get_attribute("#sw-result", "data-winner")
    names = ["Asha", "Rahul", "Meera", "Vikram", "Zoya", "Kabir"]
    page.fill("#sw-list", "\n".join(names))
    page.click("#sw-spin")
    page.wait_for_function("document.getElementById('sw-result').dataset.kind === 'info'")
    page.wait_for_selector("#sw-result[data-kind=ok]", timeout=15000)
    six = page.get_attribute("#sw-result", "data-winner")
    page.click("#rp-tab-pick")
    page.select_option("#pk-mode", "number")
    page.fill("#pk-min", "7")
    page.fill("#pk-max", "7")
    page.click("#pk-go")
    num = page.get_attribute("#pk-out", "data-value")
    page.select_option("#pk-mode", "teams")
    page.fill("#pk-n", "2")
    page.click("#pk-go")
    team_sizes = sorted(page.eval_on_selector_all("#pk-out .team", "els => els.map(e => e.textContent.split(',').length)"))
    page.click("#rp-tab-dice")
    page.select_option("#dc-n", "3")
    page.click("#dc-roll")
    faces = [int(x) for x in (page.get_attribute("#dc-out", "data-faces") or "0").split(",")]
    total = int(page.get_attribute("#dc-out", "data-total") or -1)
    obs = {"single_entry_winner": one, "six_entry_winner": six, "number_7_to_7": num, "teams_of_6": team_sizes,
           "3d6": faces, "total": total}
    ok = (one == "Only One" and six in names and num == "7" and team_sizes == [3, 3] and len(faces) == 3
          and all(1 <= f <= 6 for f in faces) and total == sum(faces))
    return obs, ok


def png_header(data: bytes) -> tuple[int, int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    w, h = struct.unpack(">II", data[16:24])
    return w, h, data[25]          # colour type 6 = RGBA


def ka_bg(page) -> tuple[dict, bool]:
    page.click("#bg-sample")          # one click: loads the bundled portrait AND removes the background
    wait_text(page, "#bg-in", "1200 × 1600")
    page.wait_for_function("['ok','error'].includes(document.getElementById('bg-status').dataset.kind)", timeout=120000)
    st = text(page, "#bg-status")
    ca = int(page.get_attribute("#bg-after", "data-center-alpha") or -1)
    ka = int(page.get_attribute("#bg-after", "data-corner-alpha") or -1)
    with page.expect_download(timeout=30000) as d:
        page.click("#bg-dl")
    w, h, ct = png_header(Path(d.value.path()).read_bytes())
    obs = {"status": st[:60], "center_alpha": ca, "corner_alpha": ka, "png": [w, h, f"colour type {ct}"]}
    ok = st.startswith("Background removed · 1200 × 1600") and ca >= 200 and ka <= 20 and (w, h, ct) == (1200, 1600, 6)
    return obs, ok


TOOLS = [  # name, path, known-answer fn, description of input -> expected
    ("typing-speed-test", "/typing-speed-test/", ka_typing,
     "own text, 15 s test, 50 correct characters typed", "40 WPM · 100% accuracy · 50 of 50 characters right"),
    ("emi-calculator", "/emi-calculator/", ka_money,
     "EMI 10,00,000 @10% 20 y; SIP 5,000 @12% 10 y; remove 18% GST from 1,180; 15% of 200, 30 of 200, 200->250",
     "₹9,650 (interest ₹13,16,052); ₹11,61,695; ₹1,000.00 + ₹180.00 (₹90.00 each); 30, 15%, +25%"),
    ("age-calculator", "/age-calculator/", ka_age,
     "born 1990-05-15, on 2026-11-23; 2026-01-01 -> 2026-12-31 (+ end date)",
     "36 y 6 m 8 d, 13,341 days, Tuesday, 173 days to 37th; 364 days / 365 incl., 261 weekdays"),
    ("spin-the-wheel", "/spin-the-wheel/", ka_wheel,
     "wheel ['Only One'] then 6 names; number 7..7; 6 names into 2 teams; 3d6",
     "winner 'Only One'; winner in list; 7; teams [3, 3]; 3 faces 1-6 summing to the total"),
    ("background-remover", "/background-remover/", ka_bg,
     "Try a sample (one click): bundled public/samples/sample-portrait.jpg, 1200x1600",
     "'Background removed · 1200 × 1600'; centre alpha >= 200, corner alpha <= 20; RGBA PNG 1200x1600"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", help="test a deployed site instead of ./dist")
    ap.add_argument("--port", type=int, default=8097)
    ap.add_argument("--only", help="comma-separated tool slugs")
    ap.add_argument("--verbose", action="store_true", help="list every requested path")
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
    tools = [t for t in TOOLS if not args.only or t[0] in args.only.split(",")]

    from playwright.sync_api import sync_playwright
    print(f"Known-answer + offline tests for tools 6-10 against {base}\n" + "=" * 72)
    results: list[bool] = []
    runs = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        # ---- phase 1: online
        for name, path, fn, inp, exp in tools:
            ctx = browser.new_context(accept_downloads=True, service_workers="allow")
            block_preview_drawer(ctx)
            reqs: list[tuple[str, str]] = []
            ctx.on("request", lambda r, reqs=reqs: reqs.append((r.method, r.url)))
            page = ctx.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e, errors=errors: errors.append(str(e)[:200]))
            try:
                page.goto(base + path, wait_until="load")
                sw = controlled(page)
                obs, ok = fn(page)
            except Exception as e:  # noqa: BLE001
                sw, obs, ok = False, {"error": str(e)[:400]}, False
            runs.append({"name": name, "path": path, "fn": fn, "ctx": ctx, "page": page, "reqs": reqs,
                         "errors": errors, "online": (obs, ok and sw), "inp": inp, "exp": exp, "sw": sw})

        # ---- phase 2: offline (network off; local server stopped)
        if httpd:
            httpd.shutdown()
            httpd.server_close()
        for r in runs:
            r["ctx"].set_offline(True)
            page = r["page"]
            try:
                # goto, not reload: tabs keep the last tab in the URL #fragment (deep link), the test starts fresh
                page.goto(base + r["path"], wait_until="load")
                obs, ok = r["fn"](page)
            except Exception as e:  # noqa: BLE001
                obs, ok = {"error": str(e)[:400]}, False
            r["offline"] = (obs, ok)
        # a page this context never visited, served from the precache
        extra = None
        if runs:
            page = runs[0]["page"]
            fresh, fresh_fn = ("/age-calculator/", ka_age) if runs[0]["name"] != "age-calculator" else \
                ("/emi-calculator/", ka_money)
            try:
                page.goto(base + fresh, wait_until="load")
                obs, ok = fresh_fn(page)
            except Exception as e:  # noqa: BLE001
                obs, ok = {"error": str(e)[:300]}, False
            extra = (obs, ok)

        # ---- report
        for r in runs:
            reqs = r["reqs"]
            injected = [u for m, u in reqs if u.startswith(PREVIEW_ONLY) or urlparse(u).path.startswith(PREVIEW_ONLY[0])]
            # AdSense loader GET (standard tag in <head>, aborted in tests): expected, but it
            # must never carry tool content.
            ads = [u for m, u in reqs if m == "GET" and is_ad_loader(u) and "?client=ca-pub-" in u and "&" not in u]
            reqs = [(m, u) for m, u in reqs if u not in injected and u not in ads]
            bad = [f"{m} {u}" for m, u in reqs
                   if not u.startswith(("blob:", "data:")) and (m != "GET" or not u.startswith(origin))]
            ok = r["online"][1] and r["offline"][1] and not bad and not r["errors"]
            results.append(ok)
            print(f"\n  [{'PASS' if ok else 'FAIL'}] {r['name']}  ({r['path']})")
            print(f"    Input:    {r['inp']}\n    Expected: {r['exp']}")
            print(f"    Online:   {'ok ' if r['online'][1] else 'BAD'} {r['online'][0]}  (service worker controlling: {r['sw']})")
            print(f"    Offline:  {'ok ' if r['offline'][1] else 'BAD'} {r['offline'][0]}")
            paths = sorted({urlparse(u).path for m, u in reqs if u.startswith(origin)})
            print(f"    Network:  {len(reqs)} requests (page + service worker), all GET {origin}: {not bad}")
            pages = [p for p in paths if p.endswith("/")]
            print(f"              {len(paths)} distinct paths: {len(pages)} pages (service-worker precache) + "
                  f"{len(paths) - len(pages)} files; heavy, cached on first use: "
                  f"{', '.join(p for p in paths if p.endswith(('.onnx', '.wasm'))) or 'none'}")
            if args.verbose:
                print(f"              paths: {', '.join(paths)}")
            if bad:
                print(f"    OFF-DEVICE REQUESTS: {bad}")
            if r["errors"]:
                print(f"    PAGE ERRORS: {r['errors']}")
            if injected:
                print(f"    Netlify preview drawer (blocked, preview-only, not site code): {len(injected)} requests")
        if extra is not None:
            results.append(extra[1])
            print(f"\n  [{'PASS' if extra[1] else 'FAIL'}] offline: {fresh} opened for the first time in the "
                  f"{runs[0]['name']} context (precache) -> {extra[0]}")
        for r in runs:
            r["ctx"].close()
        browser.close()
    print("\n" + "=" * 72 + f"\nResults: {sum(results)}/{len(results)} passed")
    return 0 if results and all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
