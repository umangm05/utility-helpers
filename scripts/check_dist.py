#!/usr/bin/env python3
"""Build invariants for the Astro output (dist/). Stdlib only.

Ported from the pre-Astro generator's validate() (scripts/build.py @ 7476590),
but it now checks what is actually SHIPPED rather than the templates:

  * every page: <!DOCTYPE html>, exactly one <h1>, unique <title> and meta
    description (WARN past 60 / 155 chars)
  * tool slugs: unique, lowercase-kebab, required fields present
  * every tool in site.config.json has dist/<slug>/index.html, and the sitemap
    lists exactly home + tools + /about/ + /contact/ + /privacy/ + /suggest/
  * netlify/lib/tool-slugs.mjs matches site.config.json (no drift)
  * consent: /assets/site.js is shipped and every page loads it
  * ads: every indexable page carries Google's standard AdSense tag in <head>
    (unmodified, exactly once) + the google-adsense-account meta; noindex pages
    (404) carry neither
  * every page links /about/, /contact/ and /privacy/ (AdSense site review)

Usage:  python3 scripts/check_dist.py [--dist DIR]
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TITLE_MAX, DESC_MAX = 60, 155


def pages(dist: Path) -> dict[str, str]:
    out = {}
    for p in sorted(dist.rglob("*.html")):
        rel = p.relative_to(dist)
        if p.name == "index.html":
            route = "/" + str(rel.parent).replace(".", "").strip("/")
            route = route.rstrip("/") + "/"
        else:
            route = "/" + str(rel)
        out[route] = p.read_text(encoding="utf-8")
    return out


def meta(doc: str, name: str) -> str:
    m = re.search(r'<meta name="%s" content="([^"]*)"' % re.escape(name), doc)
    return html.unescape(m.group(1)) if m else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", default=str(ROOT / "dist"))
    dist = Path(ap.parse_args().dist)
    cfg = json.loads((ROOT / "site.config.json").read_text(encoding="utf-8"))
    tools = cfg["tools"]
    errors: list[str] = []
    warnings: list[str] = []

    found = pages(dist)
    print(f"Utility Helpers dist check — {len(found)} pages, {len(tools)} tools")
    titles: dict[str, str] = {}
    descs: dict[str, str] = {}
    for route, doc in found.items():
        m = re.search(r"<title>(.*?)</title>", doc, re.S)
        t = html.unescape(m.group(1)) if m else ""
        d = meta(doc, "description")
        if not t:
            errors.append(f"{route}: missing <title>")
        if t in titles:
            errors.append(f"duplicate <title> on {route} and {titles[t]}: {t!r}")
        titles[t] = route
        if d in descs:
            errors.append(f"duplicate meta description on {route} and {descs[d]}")
        descs[d] = route
        if len(t) > TITLE_MAX:
            warnings.append(f"{route}: title {len(t)} chars (> {TITLE_MAX})")
        if len(d) > DESC_MAX:
            warnings.append(f"{route}: description {len(d)} chars (> {DESC_MAX})")
        if len(re.findall(r"<h1[\s>]", doc)) != 1:
            errors.append(f"{route}: expected exactly one <h1>")
        if not doc.lstrip().lower().startswith("<!doctype html>"):
            errors.append(f"{route}: missing <!DOCTYPE html>")
        if 'src="/assets/site.js"' not in doc:
            errors.append(f"{route}: does not load /assets/site.js (consent/analytics)")
        noindex = 'content="noindex' in doc
        client = cfg["site"].get("adsenseClient", "")
        ad_tag = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={client}" '
                  'crossorigin="anonymous"></script>')
        head = doc.split("</head>", 1)[0]
        if not noindex and client:
            # Google's standard tag, unmodified, exactly once, in <head>.
            if head.count(ad_tag) != 1 or doc.count("adsbygoogle.js") != 1:
                errors.append(f"{route}: standard AdSense tag missing from <head>, altered, or duplicated")
            if meta(doc, "google-adsense-account") != client:
                errors.append(f"{route}: google-adsense-account meta missing/wrong")
        if noindex and ("adsbygoogle.js" in doc or meta(doc, "google-adsense-account")):
            errors.append(f"{route}: noindex page must not carry the AdSense tag")
        for link in ("/about/", "/contact/", "/privacy/"):
            if f'href="{link}"' not in doc:
                errors.append(f"{route}: no link to {link}")
        if "uh-ads-client" in doc:
            errors.append(f"{route}: stale uh-ads-client meta (ads are no longer injected by site.js)")

    # Source titles must fit: clampTitle() is only a safety net, and a clamped title reads as broken
    # (the hard slice it replaced shipped "... entirely on yo" as the home title).
    src_titles = {"site.homeTitle": cfg["site"].get("homeTitle", f"{cfg['site']['name']} — {cfg['site']['tagline']}")}
    src_titles.update({f"tool {t['slug']!r} title": t.get("title", "") for t in tools})
    for where, t in src_titles.items():
        if len(t) > TITLE_MAX:
            errors.append(f"{where} is {len(t)} chars (> {TITLE_MAX}); shorten it instead of letting the build clamp it")

    seen: set[str] = set()
    for t in tools:
        slug = t["slug"]
        if slug in seen:
            errors.append(f"duplicate tool slug: {slug!r}")
        seen.add(slug)
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            errors.append(f"tool slug not URL-safe: {slug!r}")
        for key in ("name", "summary", "title", "description", "section", "icon"):
            if not t.get(key):
                errors.append(f"tool {slug!r}: missing required field {key!r}")
        if f"/{slug}/" not in found:
            errors.append(f"tool {slug!r}: dist/{slug}/index.html not built")
        elif f'data-uh-tool="{slug}"' not in found[f"/{slug}/"]:
            errors.append(f"tool {slug!r}: <main> lacks data-uh-tool (usage events need it)")

    want = ["/"] + [f"/{t['slug']}/" for t in tools] + ["/about/", "/contact/", "/privacy/", "/suggest/"]
    sm = (dist / "sitemap.xml").read_text(encoding="utf-8") if (dist / "sitemap.xml").exists() else ""
    locs = [l.removeprefix(cfg["site"]["baseUrl"].rstrip("/")) for l in re.findall(r"<loc>(.*?)</loc>", sm)]
    if locs != want:
        errors.append(f"sitemap mismatch: {locs} != {want}")
    for f in ("robots.txt", "ads.txt", "assets/site.js", "assets/og.png", "assets/favicon.svg"):
        if not (dist / f).exists():
            errors.append(f"dist/{f} missing")

    slugs_mjs = (ROOT / "netlify" / "lib" / "tool-slugs.mjs").read_text(encoding="utf-8")
    m = re.search(r"export default (\[.*?\]);", slugs_mjs, re.S)
    if not m or json.loads(m.group(1)) != [t["slug"] for t in tools]:
        errors.append("netlify/lib/tool-slugs.mjs drifted from site.config.json (run npm run gen)")

    for w in warnings:
        print(f"  WARN  {w}")
    if errors:
        print("\nCHECK FAILED:")
        for e in errors:
            print(f"  ERROR {e}")
        return 1
    print(f"\nOK — invariants satisfied ({len(found)} pages, sitemap {len(locs)} URLs).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
