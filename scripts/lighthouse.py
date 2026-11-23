#!/usr/bin/env python3
"""Mobile Lighthouse (perf / SEO / a11y) for home + every page in site.config.json.

Usage:  python3 scripts/lighthouse.py BASE_URL [--out DIR] [--runs N]
Needs:  node + npx (lighthouse@13.6.0, Apache-2.0, fetched on demand) and a
        Chrome/Chromium binary in CHROME_PATH. Lighthouse's default form factor is
        mobile (Moto G Power emulation, slow 4G throttling) — that is what is reported.
With --runs N the MEDIAN score per category is reported (Lighthouse perf varies run to run).
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


def run(url: str, out: Path) -> dict[str, int]:
    cmd = ["npx", "-y", "lighthouse@13.6.0", url, "--only-categories=" + ",".join(CATS),
           "--chrome-flags=--headless=new --no-sandbox", "--output=json", f"--output-path={out}", "--quiet"]
    subprocess.run(cmd, check=True, timeout=240)
    d = json.loads(out.read_text())
    return {c: round(d["categories"][c]["score"] * 100) for c in CATS}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--out", default=str(ROOT / ".verify" / "lighthouse"))
    ap.add_argument("--runs", type=int, default=1)
    args = ap.parse_args()
    base = args.base.rstrip("/")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((ROOT / "site.config.json").read_text(encoding="utf-8"))
    paths = ["/"] + [f"/{t['slug']}/" for t in cfg["tools"]] + ["/privacy/", "/suggest/"]
    rows, fails = [], []
    for p in paths:
        name = p.strip("/") or "home"
        runs = [run(base + p, out / f"{name}-{i}.json") for i in range(args.runs)]
        score = {c: int(statistics.median(r[c] for r in runs)) for c in CATS}
        rows.append((p, score))
        bad = [c for c in CATS if score[c] < 90]
        if bad:
            fails.append(f"{p}: {bad}")
        print(f"{p:32s} perf {score['performance']:3d}  seo {score['seo']:3d}  a11y {score['accessibility']:3d}"
              + ("  <-- below 90" if bad else ""), flush=True)
    md = ["| Page | Performance | SEO | Accessibility |", "|---|---|---|---|"]
    md += [f"| `{p}` | {s['performance']} | {s['seo']} | {s['accessibility']} |" for p, s in rows]
    (out / "summary.md").write_text("\n".join(md) + "\n")
    (out / "summary.json").write_text(json.dumps({p: s for p, s in rows}, indent=1))
    print(f"\nwrote {out / 'summary.md'}")
    print("ALL >= 90" if not fails else f"BELOW 90: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
