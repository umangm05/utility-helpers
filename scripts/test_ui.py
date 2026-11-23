#!/usr/bin/env python3
"""Behaviour tests for the revamped UI (UH-T1): command bar, recent tools,
drop-anything zone, theme toggle — plus the privacy contract that none of it
touches the network.

Serves dist/ locally and drives Chromium with Playwright. Every request the
page makes is recorded; any request that is not a same-origin GET for a static
file is a failure (tool input must never leave the device).

Usage:  python3 scripts/test_ui.py   (after `npm run build`)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify import free_port, serve  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CANARY = '{"canary": "ui-7f3a-do-not-send"}'


def main() -> int:
    port = free_port(8097)
    base = f"http://127.0.0.1:{port}"
    httpd = serve(ROOT / "dist", port)
    failures: list[str] = []

    def check(cond: bool, label: str, observed=""):
        print(f"  {'PASS' if cond else 'FAIL'}  {label}" + (f"  (observed: {observed})" if observed != "" else ""))
        if not cond:
            failures.append(label)

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        requests: list[str] = []
        ctx.on("request", lambda r: requests.append(f"{r.method} {r.url} {r.post_data or ''}"))
        # "Essential only": usage beacons DO fire, so the canary check below also
        # proves the drop/prefill path never ends up in an /api/e payload.
        ctx.add_init_script("try{if(!localStorage.getItem('uh-consent'))localStorage.setItem('uh-consent','essential')}catch(e){}")
        page = ctx.new_page()

        print("\n=== command bar ===")
        page.goto(base + "/", wait_until="load")
        page.keyboard.press("Control+k")
        check(page.locator("#uh-cmd").evaluate("d => d.open"), "Ctrl+K opens the command bar")
        page.keyboard.type("json")
        opts = page.locator("#uh-cmd-list [role=option]").all_inner_texts()
        check(bool(opts) and opts[0].startswith("JSON Formatter"), "typing 'json' ranks JSON Formatter first", opts[:3])
        page.keyboard.press("Enter")
        page.wait_for_url("**/json-formatter/")
        check(page.url.endswith("/json-formatter/"), "Enter navigates to the tool", page.url)

        print("\n=== recent tools ===")
        page.goto(base + "/word-counter/", wait_until="load")
        page.goto(base + "/", wait_until="load")
        recent = page.locator("#recent-list a").all_inner_texts()
        check(recent[:2] == ["Word Counter", "JSON Formatter"], "home lists recent tools, newest first", recent)
        check(page.locator("#recent").is_visible(), "recent section visible")

        print("\n=== drop anything ===")
        page.fill("#drop-text", CANARY)
        offered = page.locator("#drop-result a").all_inner_texts()
        check(bool(offered) and offered[0] == "JSON Formatter", "JSON text -> JSON Formatter offered first", offered)
        page.locator("#drop-result a", has_text="JSON Formatter").click()
        page.wait_for_url("**/json-formatter/")
        check(page.input_value("#jf-input") == CANARY, "tool page is prefilled with the dropped text")
        check(page.evaluate("sessionStorage.getItem('uh-drop')") is None, "hand-off key removed after use")
        page.goto(base + "/", wait_until="load")
        page.set_input_files("#drop-file", files=[{"name": "photo.png", "mimeType": "image/png", "buffer": b"\x89PNG"}])
        msg = page.locator("#drop-result").inner_text()
        check("on the way" in msg, "image file -> honest 'not yet' + suggest link", msg)

        print("\n=== theme ===")
        page.click(".theme-toggle")
        t1 = page.evaluate("document.documentElement.getAttribute('data-theme')")
        page.reload(wait_until="load")
        t2 = page.evaluate("document.documentElement.getAttribute('data-theme')")
        check(t1 in ("light", "dark") and t1 == t2, "theme toggle persists across reload", f"{t1} -> {t2}")

        print("\n=== reject keeps no recents ===")
        page.evaluate("localStorage.setItem('uh-consent','reject')")
        page.goto(base + "/color-picker/", wait_until="load")
        check(page.evaluate("localStorage.getItem('uh-recent')") is None, "Reject -> uh-recent removed / not written")

        print("\n=== network ===")
        bad = [r for r in requests if not r.startswith(f"GET {base}/") and "/api/e" not in r]
        leaked = [r for r in requests if "ui-7f3a" in r]
        check(not leaked, "dropped/typed canary never appears in any request", leaked)
        check(not bad, "UI makes no non-GET or cross-origin requests (besides consented /api/e)", bad[:5])
        ctx.close()
        browser.close()
    httpd.shutdown()

    print("\n=== RESULT ===")
    print("ALL UI CHECKS PASS" if not failures else f"{len(failures)} FAILURE(S): {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
