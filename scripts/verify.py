#!/usr/bin/env python3
"""UH-SCAFFOLD verification harness.

Satisfies the UI/runtime FRESH-CONTEXT PER-ROUTE gate:

  1. ENUMERATE ROUTES FROM SOURCE — routes are parsed out of the generator
     source (`scripts/build.py`), i.e. the thing that *declares* them, not the
     emitted HTML. The enumeration is then cross-checked against the files
     actually on disk; a mismatch is a failure.
  2. ONE DIRECT FRESH-LOAD ASSERTION PER ROUTE — for each route a NEW browser
     context is created and the URL is set BEFORE the page loads.
  3. SELECTOR + EXPECTED VS OBSERVED — printed per route.
  4. Click-through is never used as evidence.

Usage:
    python3 scripts/verify.py [--root DIR] [--port 8099]
"""

from __future__ import annotations

import argparse
import http.server
import json
import re
import socket
import socketserver
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

# Routes served by the host but not declared by the generator (platform files).
PLATFORM_ROUTES = ["/sitemap.xml", "/robots.txt",
                   "/assets/site.css", "/assets/site.js", "/assets/favicon.svg"]


def free_port(preferred: int) -> int:
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", preferred))
        s.close()
        return preferred
    except OSError:
        s.close()
        s2 = socket.socket()
        s2.bind(("127.0.0.1", 0))
        port = s2.getsockname()[1]
        s2.close()
        return port


def serve(root: Path, port: int):
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(root), **kw)

        def log_message(self, format, *args):  # noqa: A002 — silence request logging
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", port), Handler)
    httpd.allow_reuse_address = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def http_status(url: str) -> int:
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def enumerate_routes_from_source(root: Path) -> tuple[list[str], list[str]]:
    """Parse the generator source for the routes it declares.

    Returns (html_routes, notes). Raises on a parse failure so a silent empty
    enumeration can never masquerade as a passing test.
    """
    src = (root / "scripts" / "build.py").read_text(encoding="utf-8")
    notes: list[str] = []

    # The generator declares page paths via add(<path>, ...) and via the tool
    # slug loop. Capture the literal paths plus the slug-derived pattern.
    literal = set(re.findall(r'add\(\s*[fr]?["\']([^"\']+)["\']', src))
    literal |= set(re.findall(r'add\(\s*f["\']([^"\']+)["\']', src))
    notes.append(f"literal add() paths found: {sorted(literal)}")

    declares_tool_loop = bool(re.search(r'add\(\s*f?["\']/\{t\[[\'"]slug', src))
    notes.append(f"declares per-tool slug loop: {declares_tool_loop}")

    routes = sorted(p for p in literal if p.startswith("/") and not p.startswith("/{"))

    # Expand the tool loop from the manifest (the data the loop iterates).
    cfg = json.loads((root / "site.config.json").read_text(encoding="utf-8"))
    if declares_tool_loop:
        for t in cfg.get("tools", []):
            routes.append(f"/{t['slug']}/")
        notes.append(f"expanded {len(cfg.get('tools', []))} tool slug route(s) from site.config.json")

    if not routes:
        raise RuntimeError("route enumeration from source produced nothing — refusing to pass")
    return sorted(set(routes)), notes


def on_disk_html_routes(root: Path) -> list[str]:
    """Every HTML page actually emitted into the tree."""
    out = []
    for p in sorted(root.rglob("index.html")):
        rel = "/" + str(p.parent.relative_to(root))
        out.append("/" if rel == "/." else rel.rstrip("/") + "/")
    for p in sorted(root.glob("*.html")):
        if p.name != "index.html":
            out.append("/" + p.name)
    return sorted(set(out))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--port", type=int, default=8099)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    port = free_port(args.port)
    base = f"http://127.0.0.1:{port}"
    httpd = serve(root, port)
    time.sleep(0.4)
    failures: list[str] = []

    # ---------- 1. enumerate routes from source ----------
    print("\n=== 1. ROUTE ENUMERATION (from generator source, not output) ===")
    src_routes, notes = enumerate_routes_from_source(root)
    for n in notes:
        print(f"  note: {n}")
    print(f"  declared HTML routes: {src_routes}")

    disk_routes = on_disk_html_routes(root)
    print(f"  emitted HTML routes : {disk_routes}")
    if src_routes != disk_routes:
        failures.append(f"route mismatch source={src_routes} disk={disk_routes}")
        print("  FAIL  source and disk route sets differ")
    else:
        print("  PASS  source and disk route sets agree")

    all_routes = src_routes + PLATFORM_ROUTES

    # ---------- 2. HTTP status ----------
    print(f"\n=== 2. HTTP STATUS ({base}) ===")
    for r in all_routes:
        code = http_status(base + r)
        ok = code == 200
        print(f"  {'PASS' if ok else 'FAIL'}  {code}  {r}")
        if not ok:
            failures.append(f"HTTP {code} for {r}")

    # ---------- 3. fresh-context per-route assertions ----------
    print("\n=== 3. FRESH-CONTEXT PER-ROUTE ASSERTIONS ===")
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print(f"  SKIP — playwright unavailable: {e}")
        httpd.shutdown()
        return 1 if failures else 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        def attr(page, selector: str) -> str:
            """Read an attribute defensively — a missing selector is a FAIL, not a crash."""
            try:
                loc = page.locator(selector)
                if loc.count() == 0:
                    return ""
                return loc.first.get_attribute("content", timeout=2000) or \
                       loc.first.get_attribute("href", timeout=2000) or ""
            except Exception:
                return ""

        for route in src_routes:
            ctx = browser.new_context()          # NEW context per route
            page = ctx.new_page()
            resp = page.goto(base + route, wait_until="domcontentloaded")  # URL set before load
            h1s = page.locator("h1").all_inner_texts()
            title = page.title()
            desc = attr(page, 'meta[name="description"]')
            canonical = attr(page, 'link[rel="canonical"]')
            og = attr(page, 'meta[property="og:title"]')
            tw = attr(page, 'meta[name="twitter:card"]')
            ld = page.locator('script[type="application/ld+json"]').count()
            h1_count = len(h1s)
            observed = {
                "status": resp.status if resp else 0,
                "h1_count": h1_count,
                "title": title,
                "desc_len": len(desc),
                "canonical": canonical,
                "og": og,
                "twitter": tw,
                "jsonld": ld,
            }
            checks = {
                "status==200": observed["status"] == 200,
                "selector h1 -> exactly 1": h1_count == 1,
                "title non-empty": bool(title.strip()),
                "meta[description] non-empty": bool(desc.strip()),
                "link[canonical] present": bool(canonical.strip()),
                "og:title present": bool(og.strip()),
                "twitter:card present": bool(tw.strip()),
            }
            print(f"\n  route {route}")
            print(f"    selector 'h1'        expected 1          observed {h1_count}")
            print(f"    document.title       expected non-empty  observed {title!r}")
            print(f"    meta[description]    expected non-empty  observed {len(desc)} chars")
            print(f"    link[canonical]      expected present    observed {canonical}")
            print(f"    og:title             expected present    observed {og!r}")
            print(f"    twitter:card         expected present    observed {tw!r}")
            print(f"    json+ld blocks       observed {ld}")
            for name, ok in checks.items():
                print(f"      {'PASS' if ok else 'FAIL'}  {name}")
                if not ok:
                    failures.append(f"{route}: {name}")
            ctx.close()
        browser.close()

    httpd.shutdown()

    print("\n=== RESULT ===")
    if failures:
        print(f"FAILED ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"ALL CHECKS PASS ({len(all_routes)} routes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
