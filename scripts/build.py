#!/usr/bin/env python3
"""Static site generator for Utility Helpers.

Zero dependencies (Python 3 stdlib only). Reads `site.config.json` and writes
plain HTML into the repository root, which Netlify publishes as-is.

Why a generator instead of hand-written HTML: ~12 pages must all carry a unique
title, meta description, canonical URL, Open Graph/Twitter tags and JSON-LD.
Hand-maintaining that across a dozen files is exactly the duplication that rots.
One manifest + one template keeps them in sync; the generated output is committed
so the deploy needs no build step.

Usage:
    python3 scripts/build.py            # regenerate the site
    python3 scripts/build.py --check    # verify invariants without writing
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "site.config.json"

# SEO field budgets (Google truncates around these widths).
TITLE_MAX = 60
DESC_MAX = 155

STYLE = """\
:root {
  --bg: #0b0d10;
  --panel: #14171c;
  --panel-2: #1a1e24;
  --border: #262b33;
  --fg: #e7e9ee;
  --muted: #9aa3af;
  --accent: #f59e0b;
  --accent-fg: #1a1206;
  --radius: 12px;
  --max: 68rem;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font: 16px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto,
        "Helvetica Neue", Arial, sans-serif;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.breadcrumb a { color: var(--muted); text-decoration: underline; }
a:focus-visible, button:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 4px;
}
.wrap { max-width: var(--max); margin: 0 auto; padding: 0 1.25rem; }
.skip {
  position: absolute; left: -9999px; top: 0;
  background: var(--accent); color: var(--accent-fg);
  padding: .6rem 1rem; z-index: 100; border-radius: 0 0 var(--radius) 0;
}
.skip:focus { left: 0; }
header.site {
  border-bottom: 1px solid var(--border);
  background: rgba(11, 13, 16, .85);
  backdrop-filter: blur(8px);
  position: sticky; top: 0; z-index: 10;
}
header.site .wrap {
  display: flex; align-items: center; justify-content: space-between;
  gap: 1rem; min-height: 3.75rem;
}
.brand { font-weight: 700; letter-spacing: -.01em; color: var(--fg); }
.brand span { color: var(--accent); }
header.site nav a { color: var(--muted); font-size: .9375rem; margin-left: 1rem; }
header.site nav a:hover { color: var(--fg); }
main { padding: 2.5rem 0 4rem; }
h1 { font-size: clamp(1.75rem, 1.2rem + 2.2vw, 2.6rem); line-height: 1.15; margin: 0 0 .75rem; letter-spacing: -.02em; }
h2 { font-size: 1.3rem; margin: 2.5rem 0 .75rem; letter-spacing: -.01em; }
.lede { color: var(--muted); font-size: 1.0625rem; max-width: 46rem; margin: 0 0 2rem; }
.grid {
  display: grid; gap: 1rem;
  grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
}
.tile {
  display: block; padding: 1.25rem; border: 1px solid var(--border);
  border-radius: var(--radius); background: var(--panel);
  color: var(--fg); transition: border-color .15s ease, transform .15s ease;
}
.tile:hover { border-color: var(--accent); transform: translateY(-2px); text-decoration: none; }
.tile .tile-title { margin: 0 0 .35rem; font-size: 1.0625rem; font-weight: 600; }
.tile p { margin: 0; color: var(--muted); font-size: .9375rem; }
.empty {
  border: 1px dashed var(--border); border-radius: var(--radius);
  padding: 2rem; color: var(--muted); text-align: center;
}
.tool { border: 1px solid var(--border); border-radius: var(--radius); background: var(--panel); padding: 1.25rem; }
label { display: block; font-size: .875rem; color: var(--muted); margin-bottom: .35rem; }
input, textarea, select, button {
  font: inherit; color: var(--fg); background: var(--panel-2);
  border: 1px solid var(--border); border-radius: 8px; padding: .6rem .7rem;
}
textarea { width: 100%; min-height: 9rem; resize: vertical; }
button {
  cursor: pointer; background: var(--accent); color: var(--accent-fg);
  border-color: var(--accent); font-weight: 600;
}
button:hover { filter: brightness(1.06); }
.faq { margin-top: 2.5rem; }
.faq details { border-bottom: 1px solid var(--border); padding: .9rem 0; }
.faq summary { cursor: pointer; font-weight: 600; }
.faq p { color: var(--muted); margin: .6rem 0 0; }
.breadcrumb { color: var(--muted); font-size: .875rem; margin-bottom: 1rem; }
footer.site {
  border-top: 1px solid var(--border); color: var(--muted);
  font-size: .875rem; padding: 1.75rem 0;
}
footer.site .wrap { display: flex; flex-wrap: wrap; gap: .5rem 1.5rem; justify-content: space-between; }
@media (prefers-reduced-motion: reduce) {
  .tile { transition: none; }
  .tile:hover { transform: none; }
}
"""

# Small progressive-enhancement helper used by tool pages. No framework, no CDN.
SITE_JS = """\
// Utility Helpers — tiny progressive-enhancement helpers. No framework, no CDN.
(function () {
  "use strict";

  // Copy a string to the clipboard; returns a Promise<boolean>.
  window.uhCopy = function (text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).then(function () { return true; },
        function () { return false; });
    }
    // Fallback for non-secure contexts (e.g. plain http:// on a LAN).
    try {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.top = "-1000px";
      document.body.appendChild(ta);
      ta.select();
      var ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return Promise.resolve(ok);
    } catch (e) {
      return Promise.resolve(false);
    }
  };

  // Stamp the current year into any [data-year] node.
  document.addEventListener("DOMContentLoaded", function () {
    var y = String(new Date().getFullYear());
    var nodes = document.querySelectorAll("[data-year]");
    for (var i = 0; i < nodes.length; i++) { nodes[i].textContent = y; }
  });
})();
"""


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def esc(text: str) -> str:
    """HTML-escape (attribute-safe: quotes escaped too)."""
    return html.escape(str(text), quote=True)


def esc_xml(text: str) -> str:
    """XML-escape for sitemap.xml."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;"))


def jsonld(payload: dict) -> str:
    """Serialise JSON-LD, escaping the closing-tag sequence for safe inlining."""
    raw = json.dumps(payload, ensure_ascii=False, indent=2)
    return raw.replace("</", "<\\/")


def page_url(site: dict, path: str) -> str:
    return site["baseUrl"].rstrip("/") + path


# --------------------------------------------------------------------------- #
# templates
# --------------------------------------------------------------------------- #

def render_page(*, site: dict, title: str, description: str, path: str,
                body: str, jsonld_blocks: list[dict], noindex: bool = False) -> str:
    canonical = page_url(site, path)
    og_image = page_url(site, "/assets/og.png")

    head = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f'<title>{esc(title)}</title>',
        f'<meta name="description" content="{esc(description)}">',
        f'<link rel="canonical" href="{esc(canonical)}">',
    ]
    if noindex:
        head.append('<meta name="robots" content="noindex, follow">')
    else:
        head.append('<meta name="robots" content="index, follow">')

    head += [
        f'<meta name="theme-color" content="{esc(site["themeColor"])}">',
        # Open Graph
        '<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{esc(site["name"])}">',
        f'<meta property="og:title" content="{esc(title)}">',
        f'<meta property="og:description" content="{esc(description)}">',
        f'<meta property="og:url" content="{esc(canonical)}">',
        f'<meta property="og:image" content="{esc(og_image)}">',
        f'<meta property="og:locale" content="{esc(site["locale"])}">',
        # Twitter
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{esc(title)}">',
        f'<meta name="twitter:description" content="{esc(description)}">',
        f'<meta name="twitter:image" content="{esc(og_image)}">',
        # Assets (self-hosted — no external CDN for core functions)
        '<link rel="stylesheet" href="/assets/site.css">',
        '<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">',
        '<script defer src="/assets/site.js"></script>',
    ]
    for block in jsonld_blocks:
        head.append(f'<script type="application/ld+json">\n{jsonld(block)}\n</script>')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{chr(10).join('    ' + line for line in head)}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site">
  <div class="wrap">
    <a class="brand" href="/">Utility<span>Helpers</span></a>
    <nav aria-label="Primary">
      <a href="/">All tools</a>
      <a href="{esc(site['github'])}" rel="noopener">GitHub</a>
    </nav>
  </div>
</header>
<main id="main">
  <div class="wrap">
{body}
  </div>
</main>
<footer class="site">
  <div class="wrap">
    <p>&copy; <span data-year>2026</span> {esc(site['author'])}. No tracking, no uploads.</p>
    <p>Everything runs in your browser.</p>
  </div>
</footer>
</body>
</html>
"""


def render_home(*, site: dict, tools: list[dict]) -> str:
    if tools:
        tiles = "\n".join(
            f"""        <a class="tile" href="/{esc(t['slug'])}/">
          <p class="tile-title">{esc(t['name'])}</p>
          <p>{esc(t['summary'])}</p>
        </a>""" for t in tools
        )
        grid = f'      <div class="grid">\n{tiles}\n      </div>'
    else:
        grid = ('      <div class="empty">\n'
                '        <p>Tools are on the way. Each one will run entirely in your browser.</p>\n'
                '      </div>')

    item_list = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": f"{site['name']} — all tools",
        "numberOfItems": len(tools),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": t["name"],
                "description": t["summary"],
                "url": page_url(site, f"/{t['slug']}/"),
            }
            for i, t in enumerate(tools)
        ],
    }
    website = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": site["name"],
        "url": page_url(site, "/"),
        "description": site["description"],
        "inLanguage": "en",
    }

    body = f"""    <h1>{esc(site['name'])}</h1>
    <p class="lede">{esc(site['description'])}</p>
{grid}"""

    return render_page(
        site=site,
        title=f"{site['name']} — {site['tagline']}"[:TITLE_MAX],
        description=site["description"],
        path="/",
        body=body,
        jsonld_blocks=[website, item_list],
    )


def render_tool(*, site: dict, tool: dict) -> str:
    faqs = tool.get("faq") or []
    faq_html = ""
    if faqs:
        rows = "\n".join(
            f"""      <details>
        <summary>{esc(q['q'])}</summary>
        <p>{esc(q['a'])}</p>
      </details>""" for q in faqs
        )
        faq_html = f"""
    <section class="faq" aria-labelledby="faq-heading">
      <h2 id="faq-heading">Frequently asked questions</h2>
{rows}
    </section>"""

    # `body_html` is authored markup for the tool UI; trusted (repo-owned).
    tool_ui = tool.get("body_html") or (
        '<div class="tool"><p>This tool is being built. '
        'It will run entirely in your browser.</p></div>'
    )

    blocks = [
        {
            "@context": "https://schema.org",
            "@type": "WebApplication",
            "name": tool["name"],
            "url": page_url(site, f"/{tool['slug']}/"),
            "description": tool["summary"],
            "applicationCategory": "UtilitiesApplication",
            "operatingSystem": "Any",
            "browserRequirements": "Requires JavaScript",
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": site["name"],
                 "item": page_url(site, "/")},
                {"@type": "ListItem", "position": 2, "name": tool["name"],
                 "item": page_url(site, f"/{tool['slug']}/")},
            ],
        },
    ]
    if faqs:
        blocks.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": q["q"],
                 "acceptedAnswer": {"@type": "Answer", "text": q["a"]}}
                for q in faqs
            ],
        })

    intro = tool.get("intro") or tool["summary"]
    body = f"""    <nav class="breadcrumb" aria-label="Breadcrumb">
      <a href="/">All tools</a> <span aria-hidden="true">/</span> {esc(tool['name'])}
    </nav>
    <h1>{esc(tool['name'])}</h1>
    <p class="lede">{esc(intro)}</p>
{tool_ui}{faq_html}"""

    return render_page(
        site=site,
        title=tool["title"][:TITLE_MAX],
        description=tool["description"][:DESC_MAX],
        path=f"/{tool['slug']}/",
        body=body,
        jsonld_blocks=blocks,
    )


def render_404(*, site: dict) -> str:
    body = """    <h1>Page not found</h1>
    <p class="lede">That URL does not exist on this site. It may have been
    renamed, or the link that brought you here may be out of date.</p>
    <p><a href="/">Browse all tools</a></p>"""
    return render_page(
        site=site,
        title=f"Page not found — {site['name']}"[:TITLE_MAX],
        description="That page does not exist. Browse the free browser tools on Utility Helpers instead.",
        path="/404.html",
        body=body,
        jsonld_blocks=[],
        noindex=True,
    )


def render_sitemap(*, site: dict, paths: list[str]) -> str:
    urls = "\n".join(
        f"  <url>\n    <loc>{esc_xml(page_url(site, p))}</loc>\n  </url>" for p in paths
    )
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"{urls}\n</urlset>\n")


def render_robots(*, site: dict) -> str:
    return (f"User-agent: *\n"
            f"Allow: /\n\n"
            f"Sitemap: {page_url(site, '/sitemap.xml')}\n")


def render_favicon(*, site: dict) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">\n'
        f'  <rect width="32" height="32" rx="7" fill="{esc(site["themeColor"])}"/>\n'
        '  <path d="M9 10l7 13 7-13" fill="none" stroke="#1a1206" '
        'stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>\n'
        '</svg>\n'
    )


# --------------------------------------------------------------------------- #
# invariants
# --------------------------------------------------------------------------- #

def validate(pages: list[dict], tools: list[dict]) -> list[str]:
    """Return a list of hard failures. Empty list == build is valid."""
    errors: list[str] = []
    warnings: list[str] = []

    titles: dict[str, str] = {}
    descs: dict[str, str] = {}
    for p in pages:
        t, d = p["title"], p["description"]
        if t in titles:
            errors.append(f"duplicate <title> on {p['path']} and {titles[t]}: {t!r}")
        titles[t] = p["path"]
        if d in descs:
            errors.append(f"duplicate meta description on {p['path']} and {descs[d]}")
        descs[d] = p["path"]

        if len(t) > TITLE_MAX:
            warnings.append(f"{p['path']}: title {len(t)} chars (> {TITLE_MAX})")
        if len(d) > DESC_MAX:
            warnings.append(f"{p['path']}: description {len(d)} chars (> {DESC_MAX})")

        h1s = re.findall(r"<h1[\s>]", p["html"])
        if len(h1s) != 1:
            errors.append(f"{p['path']}: expected exactly one <h1>, found {len(h1s)}")
        if not p["html"].lstrip().startswith("<!DOCTYPE html>"):
            errors.append(f"{p['path']}: missing <!DOCTYPE html>")

    # Tool slugs must be unique and URL-safe.
    seen: set[str] = set()
    for t in tools:
        slug = t["slug"]
        if slug in seen:
            errors.append(f"duplicate tool slug: {slug!r}")
        seen.add(slug)
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            errors.append(f"tool slug not URL-safe (want lowercase-kebab): {slug!r}")
        for key in ("name", "summary", "title", "description"):
            if not t.get(key):
                errors.append(f"tool {slug!r}: missing required field {key!r}")

    for w in warnings:
        print(f"  WARN  {w}")
    return errors


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #

def build(check_only: bool = False) -> int:
    site = json.loads(CONFIG.read_text(encoding="utf-8"))
    site_cfg = site["site"]
    tools = site.get("tools", [])

    pages: list[dict] = []

    def add(path: str, title: str, description: str, html_out: str):
        pages.append({"path": path, "title": title,
                      "description": description, "html": html_out})

    home = render_home(site=site_cfg, tools=tools)
    add("/", f"{site_cfg['name']} — {site_cfg['tagline']}"[:TITLE_MAX],
        site_cfg["description"], home)

    for t in tools:
        page = render_tool(site=site_cfg, tool=t)
        add(f"/{t['slug']}/", t["title"][:TITLE_MAX], t["description"][:DESC_MAX], page)

    notfound = render_404(site=site_cfg)
    add("/404.html", f"Page not found — {site_cfg['name']}"[:TITLE_MAX],
        "That page does not exist. Browse the free browser tools on Utility Helpers instead.",
        notfound)

    print(f"Utility Helpers — building {len(pages)} pages, {len(tools)} tools")
    errors = validate(pages, tools)
    if errors:
        print("\nBUILD FAILED:")
        for e in errors:
            print(f"  ERROR {e}")
        return 1

    if check_only:
        print("\nOK — invariants satisfied (no files written).")
        return 0

    # Write page files.
    for p in pages:
        if p["path"] == "/":
            dest = ROOT / "index.html"
        else:
            dest = ROOT / p["path"].lstrip("/")
            if p["path"].endswith("/"):
                dest = dest / "index.html"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(p["html"], encoding="utf-8")
        print(f"  wrote {dest.relative_to(ROOT)}")

    # Assets.
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "assets" / "site.css").write_text(STYLE, encoding="utf-8")
    (ROOT / "assets" / "site.js").write_text(SITE_JS, encoding="utf-8")
    (ROOT / "assets" / "favicon.svg").write_text(render_favicon(site=site_cfg), encoding="utf-8")
    print("  wrote assets/site.css, assets/site.js, assets/favicon.svg")

    # Indexable paths: home + tool pages. 404 is noindex, excluded.
    indexable = ["/"] + [f"/{t['slug']}/" for t in tools]
    (ROOT / "sitemap.xml").write_text(
        render_sitemap(site=site_cfg, paths=indexable), encoding="utf-8")
    print("  wrote sitemap.xml")

    (ROOT / "robots.txt").write_text(render_robots(site=site_cfg), encoding="utf-8")
    print("  wrote robots.txt")

    print("\nOK — build complete.")
    return 0


if __name__ == "__main__":
    sys.exit(build(check_only="--check" in sys.argv))
