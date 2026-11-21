#!/usr/bin/env python3
"""Consent + usage-event contract test (SPEC utility-helpers-feedback-analytics §5).

Drives a real browser against a local static server and records every request
to /api/e. Asserts, per consent choice:

  * no choice yet  -> banner visible, ZERO /api/e requests while using a tool
  * Reject         -> ZERO /api/e requests, no session/visitor id stored
  * Essential only -> events sent, per-tab session id, NO visitor id
  * Accept all     -> events sent with a visitor id that survives a reload
  * always         -> text typed into a tool never appears in any payload;
                      content inputs (e.g. the unit-converter value) never
                      produce an option event

How requests are observed: Playwright does NOT report beacons sent from a page
that is unloading (pagehide), which is exactly when most batches go out. So the
count comes from two independent sources instead:
  * Chrome's own network log (--log-net-log), parsed for /api/e requests — this
    is the "network log" evidence SPEC §5.1 asks for, and works on the live site;
  * locally, a recording server that stores every POST body, so payload content
    can be asserted (on the live site, content is checked on the stored blobs
    via common/scripts/uh_usage_export.py instead).

Usage:  python3 scripts/test_consent.py [--base URL] [--netlog-dir DIR]
        (no --base: serves the repo on 127.0.0.1 with a recording /api/e)
"""

from __future__ import annotations

import argparse
import http.server
import json
import socketserver
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify import free_port  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

SECRET = "CANARY-do-not-store-7f3a"   # typed into tools; must never leave the page


RECEIVED: list[str] = []   # bodies POSTed to the local recording server


def serve_recording(root: Path, port: int):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(root), **kw)

        def log_message(self, format, *args):  # noqa: A002
            pass

        def do_POST(self):  # noqa: N802
            body = self.rfile.read(int(self.headers.get("content-length") or 0)).decode("utf-8", "replace")
            if self.path.split("?")[0] == "/api/e":
                RECEIVED.append(body)
            self.send_response(204)
            self.end_headers()

    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def netlog_requests(path: Path, match) -> int:
    """Count distinct network requests whose URL satisfies match() in a Chrome net-log file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    ids = set()
    for ev in data.get("events", []):
        url = (ev.get("params") or {}).get("url", "")
        if url and match(url):
            ids.add(ev.get("source", {}).get("id"))
    return len(ids)


def netlog_api_requests(path: Path) -> int:
    return netlog_requests(path, lambda u: u.split("?")[0].endswith("/api/e"))


def netlog_ads_requests(path: Path) -> int:
    """Requests to Google's AdSense loader (pagead2.googlesyndication.com)."""
    return netlog_requests(path, lambda u: "googlesyndication.com" in u or "adsbygoogle" in u)


def ads_tag(page) -> int:
    return page.evaluate("() => document.querySelectorAll('script[src*=adsbygoogle]').length")


class Phase:
    """One fresh browser (own profile + own net-log) per consent scenario."""

    def __init__(self, pw, name: str, netlog_dir: Path):
        self.netlog = netlog_dir / f"netlog-{name}.json"
        self.browser = pw.chromium.launch(args=[f"--log-net-log={self.netlog}",
                                                "--net-log-capture-mode=Default"])
        self.ctx = self.browser.new_context()
        self.page = self.ctx.new_page()
        self.start = len(RECEIVED)
        self.netlog_count: int | None = None

    @property
    def bodies(self) -> list[str]:
        return RECEIVED[self.start:]

    @property
    def batches(self) -> list[dict]:
        out = []
        for b in self.bodies:
            try:
                out.append(json.loads(b))
            except ValueError:
                out.append({"_unparsed": b})
        return out

    def close(self) -> int:
        self.ctx.close()
        self.browser.close()          # flushes and closes the net-log file
        self.netlog_count = netlog_api_requests(self.netlog)
        self.ads_count = netlog_ads_requests(self.netlog)
        return self.netlog_count


def use_tools(page, base: str):
    """Exercise a couple of tools the way a person would, typing the canary."""
    page.goto(base + "/word-counter/", wait_until="domcontentloaded")
    page.fill("#wc-input", f"hello {SECRET} world")
    page.goto(base + "/unit-converter/", wait_until="domcontentloaded")
    page.select_option("#uc-category", "temperature")
    page.fill("#uc-input", "4242")
    page.dispatch_event("#uc-input", "change")
    page.click("#uc-swap")
    page.goto(base + "/json-formatter/", wait_until="domcontentloaded")
    page.fill("#jf-input", "{" + SECRET)       # invalid JSON -> tool error box
    page.click("#jf-format")
    page.wait_for_timeout(100)
    page.goto(base + "/", wait_until="domcontentloaded")   # pagehide flushes the beacon
    page.wait_for_timeout(1200)


def storage(page) -> dict:
    return page.evaluate("""() => ({
        consent: localStorage.getItem('uh-consent'),
        vid: localStorage.getItem('uh-vid'),
        sid: sessionStorage.getItem('uh-sid'),
        localKeys: Object.keys(localStorage),
        sessionKeys: Object.keys(sessionStorage),
    })""")


def run(base: str, local: bool, netlog_dir: Path) -> list[str]:
    failures: list[str] = []

    def check(cond: bool, label: str, observed=""):
        print(f"    {'PASS' if cond else 'FAIL'}  {label}" + (f"  (observed: {observed})" if observed != "" else ""))
        if not cond:
            failures.append(label)

    with sync_playwright() as pw:
        # ---- 1. no choice: banner shows, nothing is sent -------------------
        print("\n=== no choice yet ===")
        ph = Phase(pw, "nochoice", netlog_dir); page = ph.page
        page.goto(base + "/", wait_until="domcontentloaded")
        check(page.is_visible("#uh-consent"), "banner visible on first visit")
        use_tools(page, base)
        check(page.is_visible("#uh-consent"), "banner still shown on later pages until chosen")
        n = ph.close()
        check(n == 0, "network log: zero /api/e requests before a choice", n)
        check(ph.ads_count == 0, "network log: adsbygoogle NOT requested before a choice", ph.ads_count)
        if local:
            check(len(ph.bodies) == 0, "server: zero /api/e bodies received", len(ph.bodies))

        # ---- 2. Reject ------------------------------------------------------
        print("\n=== Reject ===")
        ph = Phase(pw, "reject", netlog_dir); page = ph.page
        page.goto(base + "/", wait_until="domcontentloaded")
        page.click("[data-uh-choice=reject]")
        check(not page.is_visible("#uh-consent"), "banner hidden after Reject")
        use_tools(page, base)
        st = storage(page)
        check(st["localKeys"] == ["uh-consent"] and st["sessionKeys"] == [],
              "Reject -> only the choice itself is stored", st)
        n = ph.close()
        check(n == 0, "network log: Reject -> zero /api/e requests", n)
        check(ph.ads_count == 0, "network log: Reject -> adsbygoogle never requested", ph.ads_count)
        if local:
            check(len(ph.bodies) == 0, "server: Reject -> zero /api/e bodies received", len(ph.bodies))

        # ---- 3. Essential only ---------------------------------------------
        print("\n=== Essential only ===")
        ph = Phase(pw, "essential", netlog_dir); page = ph.page
        page.goto(base + "/", wait_until="domcontentloaded")
        page.click("[data-uh-choice=essential]")
        use_tools(page, base)
        st = storage(page)
        check(st["vid"] is None and st["sid"] is not None, "Essential -> session id only in storage", st)
        n = ph.close()
        check(n > 0, "network log: Essential -> /api/e requests sent", n)
        check(ph.ads_count == 0, "network log: Essential -> adsbygoogle never requested", ph.ads_count)
        if local:
            batches = ph.batches
            evs = [e for b in batches for e in b.get("ev", [])]
            kinds = sorted({e["e"] for e in evs})
            check(all(b.get("c") == "essential" for b in batches) and batches, "every batch labelled essential",
                  len(batches))
            check(all("vid" not in b for b in batches), "Essential -> no visitor id in any batch")
            check({"view", "use", "opt", "act", "time", "err"} <= set(kinds), "all six event kinds observed", kinds)
            opts = [(e["id"], e["v"]) for e in evs if e["e"] == "opt"]
            check(("uc-category", "temperature") in opts, "select option recorded", opts)
            check(all(i != "uc-input" for i, _ in opts), "content input (uc-input) never recorded as an option")
            check(all(SECRET not in r and "4242" not in r for r in ph.bodies),
                  "typed tool content never appears in any payload")

        # ---- 4. Accept all, then downgrade to Reject -----------------------
        print("\n=== Accept all ===")
        ph = Phase(pw, "accept", netlog_dir); page = ph.page
        page.goto(base + "/", wait_until="domcontentloaded")
        page.click("[data-uh-choice=all]")
        check(ads_tag(page) == 1, "Accept -> adsbygoogle loader injected once", ads_tag(page))
        use_tools(page, base)
        vid1 = storage(page)["vid"]
        page.reload(wait_until="domcontentloaded")
        page.goto(base + "/word-counter/", wait_until="domcontentloaded")
        page.goto(base + "/", wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
        vid2 = storage(page)["vid"]
        check(bool(vid1) and vid1 == vid2, "Accept -> persistent visitor id survives navigation/reload", (vid1, vid2))
        if local:
            vids = {b.get("vid") for b in ph.batches}
            check(vids == {vid1}, "Accept -> every batch carries that visitor id", vids)
            check(all(SECRET not in r for r in ph.bodies), "typed tool content never appears in any payload")

        print("\n=== change to Reject via footer 'Privacy choices' ===")
        page.click("[data-uh-consent-open]")
        page.click("[data-uh-choice=reject]")
        before = len(RECEIVED)
        use_tools(page, base)
        st = storage(page)
        check(st["vid"] is None and st["sid"] is None, "switching to Reject deletes both ids", st)
        check(ads_tag(page) == 0, "after switching to Reject the next page has no adsbygoogle tag", ads_tag(page))
        n = ph.close()
        check(n > 0, "network log: Accept phase sent /api/e requests", n)
        check(ph.ads_count > 0, "network log: Accept -> adsbygoogle requested", ph.ads_count)
        if local:
            check(len(RECEIVED) == before, "after switching to Reject nothing more is sent", len(RECEIVED) - before)
    return failures


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", help="test a deployed site instead of the local tree")
    ap.add_argument("--netlog-dir", help="keep Chrome net-log files here (evidence)")
    args = ap.parse_args()
    netlog_dir = Path(args.netlog_dir or tempfile.mkdtemp(prefix="uh-netlog-"))
    netlog_dir.mkdir(parents=True, exist_ok=True)
    print(f"net-log files: {netlog_dir}")
    if args.base:
        failures = run(args.base.rstrip("/"), local=False, netlog_dir=netlog_dir)
    else:
        root = Path(__file__).resolve().parent.parent
        port = free_port(8098)
        httpd = serve_recording(root, port)
        try:
            failures = run(f"http://127.0.0.1:{port}", local=True, netlog_dir=netlog_dir)
        finally:
            httpd.shutdown()
    print("\n=== RESULT ===")
    print("ALL CONSENT CHECKS PASS" if not failures else f"{len(failures)} FAILURE(S): {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
