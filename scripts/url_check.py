#!/usr/bin/env python3
"""Old-vs-new URL check: every URL the PREVIOUS build served must still answer
200 with the same path on the target deploy (no ranking loss).

The old URL set is read from a git ref's committed sitemap.xml (the pre-Astro
build committed its output), plus the platform files it served.

Usage:  python3 scripts/url_check.py BASE_URL [--old-ref master]
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import urllib.error
import urllib.request

PLATFORM = ["/sitemap.xml", "/robots.txt", "/ads.txt", "/404.html",
            "/assets/site.js", "/assets/og.png", "/assets/favicon.svg"]


def status(url: str, method: str = "GET") -> tuple[int, str]:
    req = urllib.request.Request(url, method=method, headers={"user-agent": "uh-url-check"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, url


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--old-ref", default="master")
    a = ap.parse_args()
    base = a.base.rstrip("/")
    sm = subprocess.run(["git", "show", f"{a.old_ref}:sitemap.xml"], capture_output=True, text=True, check=True).stdout
    old = [re.sub(r"^https?://[^/]+", "", u) for u in re.findall(r"<loc>(.*?)</loc>", sm)]
    new_sm = urllib.request.urlopen(base + "/sitemap.xml", timeout=20).read().decode()
    new = [re.sub(r"^https?://[^/]+", "", u) for u in re.findall(r"<loc>(.*?)</loc>", new_sm)]
    fails = []
    print(f"old URLs ({a.old_ref} sitemap): {len(old)}   new sitemap: {len(new)}\n")
    print(f"{'path':34s} {'status':6s} in-new-sitemap  final-url")
    for p in old + PLATFORM:
        code, final = status(base + p)
        in_sm = "yes" if p in new else ("n/a" if p in PLATFORM else "NO")
        ok = code == 200 and final.rstrip("/") == (base + p).rstrip("/") and in_sm != "NO"
        print(f"{p:34s} {code:<6d} {in_sm:14s}  {final}{'' if ok else '   <-- FAIL'}")
        if not ok:
            fails.append(p)
    code, _ = status(base + "/this-page-does-not-exist-uh/")
    print(f"\n{'/this-page-does-not-exist-uh/':34s} {code:<6d} (expect 404)")
    if code != 404:
        fails.append("404 handling")
    print("\nRESULT:", "ALL OLD URLS 200 + LISTED IN SITEMAP" if not fails else f"FAIL {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
