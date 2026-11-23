#!/usr/bin/env python3
"""Mobile Lighthouse (perf / SEO / a11y) for home + every page in site.config.json.

Usage:  python3 scripts/lighthouse.py BASE_URL [--out DIR] [--runs N] [--from-json]
Needs:  node + npx (lighthouse@13.6.0, Apache-2.0, fetched on demand) and a
        Chrome/Chromium binary in CHROME_PATH. Lighthouse's default form factor is
        mobile (Moto G Power emulation, slow 4G throttling) — that is what is reported.
With --runs N the MEDIAN score per category is reported (perf varies run to run).
--from-json re-summarises the reports already in --out without re-running.

Deploy previews: Netlify adds `x-robots-tag: noindex` to every deploy-preview
response (never to production), which fails the SEO `is-crawlable` audit. The
summary therefore also reports "SEO excl. preview noindex": the SEO score with
that one audit removed — computed ONLY when it is the sole failing SEO audit and
its source is exactly that header; otherwise the column shows the raw score.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATS = ("performance", "seo", "accessibility")
PREVIEW_HEADER = "x-robots-tag: noindex"


def run(url: str, out: Path) -> None:
    cmd = ["npx", "-y", "lighthouse@13.6.0", url, "--only-categories=" + ",".join(CATS),
           "--chrome-flags=--headless=new --no-sandbox", "--output=json", f"--output-path={out}", "--quiet",
           # Netlify's deploy-preview drawer (not site code, absent in production).
           "--blocked-url-patterns=*/.netlify/scripts/cdp*", "--blocked-url-patterns=*app.netlify.com*"]
    subprocess.run(cmd, check=True, timeout=240)


def scores(report: Path) -> dict:
    d = json.loads(report.read_text())
    s: dict = {c: round(d["categories"][c]["score"] * 100) for c in CATS}
    refs = [r for r in d["categories"]["seo"]["auditRefs"]
            if r["weight"] > 0 and d["audits"][r["id"]].get("score") is not None]
    failing = [r["id"] for r in refs if d["audits"][r["id"]]["score"] < 1]
    sources = [i.get("source") for i in d["audits"]["is-crawlable"].get("details", {}).get("items", [])]
    if failing == ["is-crawlable"] and sources == [PREVIEW_HEADER]:
        kept = [r for r in refs if r["id"] != "is-crawlable"]
        s["seo_ex_preview"] = round(100 * sum(r["weight"] * d["audits"][r["id"]]["score"] for r in kept)
                                    / sum(r["weight"] for r in kept))
    else:
        s["seo_ex_preview"] = s["seo"]
    s["lcp"] = d["audits"]["largest-contentful-paint"]["displayValue"].replace("\u00a0", " ")
    s["cls"] = float(d["audits"]["cumulative-layout-shift"]["numericValue"])
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--out", default=str(ROOT / ".verify" / "lighthouse"))
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--from-json", action="store_true")
    args = ap.parse_args()
    base = args.base.rstrip("/")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((ROOT / "site.config.json").read_text(encoding="utf-8"))
    paths = ["/"] + [f"/{t['slug']}/" for t in cfg["tools"]] + ["/privacy/", "/suggest/"]
    keys = ("performance", "seo", "seo_ex_preview", "accessibility")
    rows, fails = [], []
    for p in paths:
        name = p.strip("/") or "home"
        reports = []
        for i in range(args.runs):
            f = out / f"{name}-{i}.json"
            if not args.from_json:
                run(base + p, f)
            if f.exists():
                reports.append(scores(f))
        if not reports:
            fails.append(f"{p}: no report")
            continue
        med: dict = {k: int(statistics.median(r[k] for r in reports)) for k in keys}
        med["runs"] = len(reports)
        med["lcp"] = " / ".join(r["lcp"] for r in reports)
        med["cls"] = round(max(r["cls"] for r in reports), 3)
        rows.append((p, med))
        bad = [k for k in ("performance", "seo_ex_preview", "accessibility") if med[k] < 90]
        if bad:
            fails.append(f"{p}: {bad}")
        print(f"{p:32s} perf {med['performance']:3d}  seo {med['seo']:3d} (excl. preview noindex {med['seo_ex_preview']:3d})"
              f"  a11y {med['accessibility']:3d}  runs {med['runs']}" + ("  <-- below 90" if bad else ""), flush=True)
    md = ["| Page | Perf | SEO raw | SEO excl. preview `noindex` | A11y | runs | LCP per run | max CLS |",
          "|---|---|---|---|---|---|---|---|"]
    md += [f"| `{p}` | {s['performance']} | {s['seo']} | {s['seo_ex_preview']} | {s['accessibility']} | {s['runs']} "
           f"| {s['lcp']} | {s['cls']} |" for p, s in rows]
    (out / "summary.md").write_text("\n".join(md) + "\n")
    (out / "summary.json").write_text(json.dumps({p: s for p, s in rows}, indent=1))
    print(f"\nwrote {out / 'summary.md'}")
    print("ALL >= 90" if not fails else f"BELOW 90: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
