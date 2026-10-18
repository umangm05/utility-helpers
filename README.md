# Utility Helpers

Free browser tools that run **entirely on your device**. No uploads, no accounts,
no tracking, no backend.

Live site: https://utility-helpers.netlify.app

## What this is

A static, serverless site. Every page is plain HTML committed to the repository
root — there is **no framework runtime and no external CDN dependency** for core
functionality. Netlify publishes the repo as-is.

```
.
├── site.config.json      ← the single source of truth (site meta + tool list)
├── scripts/build.py      ← stdlib-only generator; writes the HTML below
├── index.html            ← GENERATED — home page with the tool grid
├── <tool-slug>/index.html← GENERATED — one page per tool
├── 404.html              ← GENERATED — not-found page (noindex)
├── sitemap.xml           ← GENERATED — indexable URLs
├── robots.txt            ← GENERATED — allow all + sitemap pointer
├── assets/
│   ├── site.css          ← GENERATED — styles
│   ├── site.js           ← GENERATED — tiny helpers (no framework)
│   └── favicon.svg       ← GENERATED
└── netlify.toml          ← publish = "." (no build step)
```

> **Generated files are committed.** That is deliberate: the deploy needs no
> build step, so Netlify ships the repo exactly as it appears here. If you edit
> `site.config.json` or `scripts/build.py`, re-run the generator and commit the
> regenerated output in the same commit.

## Add a tool

1. **Write the entry** in `site.config.json` under `tools`:

   ```json
   {
     "slug": "word-counter",
     "name": "Word Counter",
     "summary": "Count words, characters and reading time as you type.",
     "title": "Word Counter — Free Online Word & Character Count",
     "description": "Count words, characters, sentences and reading time instantly. Runs in your browser — nothing you paste is ever uploaded.",
     "intro": "Paste or type your text to see live word, character and reading-time counts.",
     "body_html": "<div class=\"tool\"><label for=\"wc\">Your text</label><textarea id=\"wc\"></textarea><p id=\"wc-out\"></p></div>",
     "faq": [
       { "q": "Is my text uploaded?", "a": "No. Counting happens in your browser." }
     ]
   }
   ```

   | Field | Required | Notes |
   |-------|----------|-------|
   | `slug` | yes | lowercase-kebab, URL-safe; becomes `/<slug>/` |
   | `name` | yes | shown as the tile title and page `<h1>` |
   | `summary` | yes | one line, shown on the home tile |
   | `title` | yes | SEO `<title>`, keep ≤ 60 chars |
   | `description` | yes | meta description, keep ≤ 155 chars |
   | `intro` | no | 80–120 word lede; falls back to `summary` |
   | `body_html` | no | the tool UI markup (repo-owned, trusted) |
   | `faq` | no | list of `{q, a}`; emits FAQPage JSON-LD |

2. **Regenerate and verify:**

   ```bash
   python3 scripts/build.py          # writes index.html, <slug>/index.html, sitemap.xml
   python3 scripts/build.py --check  # invariants only, writes nothing
   ```

3. **Check the new tool in a browser** (see *Local verification* below).

The generator enforces, and will refuse to build on:
- duplicate `<title>` or duplicate meta description across pages
- anything other than exactly one `<h1>` per page
- a slug that is not lowercase-kebab, or a missing required field

It warns (without failing) when a title exceeds 60 chars or a description 155.

## Deploy

The site is live at **https://utility-helpers.netlify.app**.

**Status:** Deployed 2026-10-17 via the Netlify CLI. The site is linked to
the `utility-helpers` Netlify project (ID `ed5fcc96-8610-4e22-8bab-0d247eb93d03`).

### How to redeploy

```bash
cd /root/projects/utility-helpers
npx netlify deploy --prod
```

`netlify.toml` sets `publish = "."` (no build step), security headers,
`/assets/*` caching, and a custom 404 fallback.

**Note:** Git continuous deployment is NOT connected — pushing to a branch
does not auto-trigger a deploy. Deploys are manual via the CLI command above.
To enable Git CD, connect the repo in the Netlify dashboard under
Site configuration → Build & deploy → Continuous deployment.

## Local verification

```bash
# Serve the folder over HTTP (do not open the files with file:// — the
# canonical/absolute paths and asset URLs need a real origin).
python3 -m http.server 8080

# Then check the required routes:
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/sitemap.xml
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/robots.txt
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/404.html
```

## Google Search Console

Add your verification file at `google-site-verification.html` (or any name GSC
provides). Format:

```html
<html>
  <head>
    <meta name="google-site-verification" content="YOUR_TOKEN_HERE" />
    <title>Google Search Console verification</title>
  </head>
  <body>Google Search Console verification file</body>
</html>
```

Do NOT fake a token — this file must match the exact value Google gives you.
Once deployed, verify at `https://utility-helpers.netlify.app/google-site-verification.html`.

## Conventions

- **No backend, ever.** A tool that needs a server does not belong here.
- **No external CDN** for core functionality — self-host CSS/JS.
- **Progressive enhancement:** the page must render and read correctly with
  JavaScript disabled; JS only adds interaction.
- **One `<h1>` per page**; semantic landmarks (`header`/`main`/`nav`/`footer`).
- **Unique `title` + `description`** on every page — enforced by the generator.
- **Never put secrets in this repo** — it is public and fully static.
