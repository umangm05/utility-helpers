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
.btn-ghost { background: var(--panel-2); color: var(--fg); border-color: var(--border); }
.linkbtn {
  background: none; border: 0; padding: 0; color: var(--accent);
  font: inherit; font-weight: inherit; text-decoration: underline; cursor: pointer;
}
[data-uh-js][hidden] { display: none; }
.consent {
  position: fixed; left: 1rem; right: 1rem; bottom: 1rem; z-index: 50;
  max-width: 42rem; margin: 0 auto; padding: 1rem 1.25rem;
  background: var(--panel); border: 1px solid var(--border); border-radius: var(--radius);
  box-shadow: 0 12px 32px rgba(0, 0, 0, .5);
}
.consent[hidden] { display: none; }
.consent p { margin: 0 0 .6rem; font-size: .9375rem; }
.consent .consent-title { font-weight: 700; font-size: 1rem; }
.consent .consent-note { color: var(--muted); font-size: .875rem; }
.consent .actions { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .75rem; }
.consent .actions button { min-height: 44px; flex: 1 1 8rem; }
.suggest-cta { margin-top: 1rem; font-size: .9375rem; }
/* Links inside running text must not rely on colour alone (WCAG 1.4.1). */
.consent a, footer.site a, .prose a, .suggest-cta a, .muted a { text-decoration: underline; }
.hp { position: absolute; left: -9999px; width: 1px; height: 1px; overflow: hidden; }
.form-grid { display: grid; gap: 1rem; max-width: 36rem; }
.form-grid select, .form-grid textarea { width: 100%; }
.muted { color: var(--muted); }
.prose { max-width: 46rem; }
.prose li { margin: .35rem 0; }
.prose table { border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: .9375rem; }
.prose th, .prose td { border: 1px solid var(--border); padding: .5rem .6rem; text-align: left; vertical-align: top; }
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

  // ------------------------------------------------------------------------
  // Consent + first-party usage events (SPEC: utility-helpers-feedback-analytics).
  //
  //   reject     -> nothing is sent, nothing is stored except the choice itself
  //   essential  -> anonymous events + a random per-tab session id (sessionStorage)
  //   all        -> the same + a random persistent visitor id (localStorage)
  //
  // Nothing is sent before a choice is made. Tool input/output is NEVER read:
  // only control ids, option values of <select>/checkbox/radio/range (and number
  // inputs explicitly marked data-uh-opt), button ids, visible time and error ids.
  // ------------------------------------------------------------------------
  var CONSENT_KEY = "uh-consent", VID_KEY = "uh-vid", SID_KEY = "uh-sid";
  var ENDPOINT = "/api/e";
  var LEVELS = { all: 1, essential: 1, reject: 1 };
  var queue = [], flushTimer = null, viewed = false, used = false;
  var visibleSince = null, visibleMs = 0;

  function store(kind) { try { return window[kind]; } catch (e) { return null; } }
  function getItem(kind, k) { var s = store(kind); try { return s ? s.getItem(k) : null; } catch (e) { return null; } }
  function setItem(kind, k, v) { var s = store(kind); try { if (s) s.setItem(k, v); } catch (e) {} }
  function removeItem(kind, k) { var s = store(kind); try { if (s) s.removeItem(k); } catch (e) {} }

  function consent() {
    var v = getItem("localStorage", CONSENT_KEY);
    return LEVELS[v] ? v : null;
  }
  function tracking() { var c = consent(); return c === "all" || c === "essential"; }

  function randomId() {
    var a = new Uint8Array(12), out = "";
    (window.crypto || window.msCrypto).getRandomValues(a);
    for (var i = 0; i < a.length; i++) out += (a[i] < 16 ? "0" : "") + a[i].toString(16);
    return out;
  }
  function idFrom(kind, key) {
    var v = getItem(kind, key);
    if (!/^[a-f0-9]{24}$/.test(v || "")) { v = randomId(); setItem(kind, key, v); }
    return v;
  }
  // Bring stored ids in line with the current choice (e.g. after a downgrade).
  function applyStorage(c) {
    if (c !== "all") removeItem("localStorage", VID_KEY);
    if (c !== "all" && c !== "essential") removeItem("sessionStorage", SID_KEY);
  }

  function toolSlug() {
    var m = document.getElementById("main");
    return (m && m.getAttribute("data-uh-tool")) || null;
  }
  function deviceClass() {
    var w = window.innerWidth || 1024;
    return w < 768 ? "mobile" : w < 1024 ? "tablet" : "desktop";
  }

  function track(type, data) {
    if (!tracking()) return;
    var ev = { e: type, p: location.pathname, ts: Date.now() };
    var tool = toolSlug();
    if (tool) ev.tool = tool;
    if (data) for (var k in data) if (Object.prototype.hasOwnProperty.call(data, k)) ev[k] = data[k];
    queue.push(ev);
    if (queue.length >= 20) flush(false);
    else if (!flushTimer) flushTimer = setTimeout(function () { flush(false); }, 5000);
  }

  function flush(unloading) {
    if (flushTimer) { clearTimeout(flushTimer); flushTimer = null; }
    var c = consent();
    if (!queue.length || (c !== "all" && c !== "essential")) { queue = []; return; }
    var body = { v: 1, c: c, sid: idFrom("sessionStorage", SID_KEY), dev: deviceClass(), ev: queue.splice(0, 50) };
    if (c === "all") body.vid = idFrom("localStorage", VID_KEY);
    var payload = JSON.stringify(body);
    var sent = false;
    if (navigator.sendBeacon) {
      try { sent = navigator.sendBeacon(ENDPOINT, new Blob([payload], { type: "text/plain" })); } catch (e) {}
    }
    if (!sent && window.fetch) {
      fetch(ENDPOINT, { method: "POST", body: payload, keepalive: !!unloading,
        headers: { "content-type": "text/plain" } })["catch"](function () {});
    }
    if (queue.length) flush(unloading);
  }

  // Visible time on the page, reported when the tab is hidden or closed.
  function startClock() { if (visibleSince === null && document.visibilityState !== "hidden") visibleSince = Date.now(); }
  function stopClock() {
    if (visibleSince !== null) { visibleMs += Date.now() - visibleSince; visibleSince = null; }
    if (visibleMs > 0) { track("time", { ms: Math.round(visibleMs) }); visibleMs = 0; }
    flush(true);
  }

  function begin() {
    if (!tracking() || viewed) return;
    viewed = true;
    track("view");
    startClock();
  }

  // --- tool interaction (scoped to the tool UI on tool pages only) ---------
  function inTool(el) {
    if (!toolSlug() || !el || !el.closest) return null;
    return el.closest("#main .tool");
  }
  function markUsed() { if (!used) { used = true; track("use"); } }
  function controlId(el) {
    var id = el.id || el.getAttribute("name") || "";
    return /^[A-Za-z0-9_-]{1,40}$/.test(id) ? id : null;
  }
  function optionValue(el) {
    var tag = el.tagName, type = (el.type || "").toLowerCase();
    if (tag === "SELECT") return el.value;
    if (type === "checkbox" || type === "radio") return el.checked ? "1" : "0";
    if (type === "range") return el.value;
    if (el.hasAttribute("data-uh-opt")) return el.value;
    return null; // text, textarea, number (content), color, date... never read
  }

  document.addEventListener("input", function (ev) { if (inTool(ev.target)) markUsed(); }, true);
  document.addEventListener("change", function (ev) {
    var el = ev.target;
    if (!inTool(el)) return;
    markUsed();
    var id = controlId(el), v = optionValue(el);
    if (id && v !== null) track("opt", { id: id, v: String(v).slice(0, 40) });
  }, true);
  document.addEventListener("click", function (ev) {
    var btn = ev.target && ev.target.closest ? ev.target.closest("button") : null;
    var tool = inTool(btn);
    if (!tool) return;
    markUsed();
    var id = controlId(btn);
    if (id) track("act", { id: id });
    // Tool-level errors: report WHICH error box became visible, never its text.
    setTimeout(function () {
      var errs = tool.querySelectorAll("[id$='-error']");
      for (var i = 0; i < errs.length; i++) {
        if (errs[i].offsetParent !== null && errs[i].textContent) track("err", { kind: "tool", id: errs[i].id });
      }
    }, 0);
  }, true);
  window.addEventListener("error", function (ev) {
    var name = ev && ev.error && ev.error.name;
    track("err", { kind: "js", id: /^[A-Za-z]{1,40}$/.test(name || "") ? name : "Error" });
  });

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "hidden") stopClock(); else startClock();
  });
  window.addEventListener("pagehide", stopClock);

  // --- banner --------------------------------------------------------------
  function banner() { return document.getElementById("uh-consent"); }
  function showBanner(focus) {
    var b = banner();
    if (!b) return;
    b.hidden = false;
    if (focus) { var first = b.querySelector("button"); if (first) first.focus(); }
  }
  function renderState() {
    var c = consent();
    var nodes = document.querySelectorAll("[data-uh-consent-state]");
    var label = { all: "Accept all", essential: "Essential only", reject: "Reject" }[c] || "not chosen yet";
    for (var i = 0; i < nodes.length; i++) nodes[i].textContent = label;
  }
  function choose(c) {
    if (!LEVELS[c]) return;
    if (c === "reject") { queue = []; if (flushTimer) { clearTimeout(flushTimer); flushTimer = null; } }
    setItem("localStorage", CONSENT_KEY, c);
    applyStorage(c);
    var b = banner();
    if (b) b.hidden = true;
    renderState();
    begin();
    loadAds();
  }
  window.uhConsent = { get: consent, set: choose, open: function () { showBanner(true); } };

  // --- ads -----------------------------------------------------------------
  // Google AdSense sets third-party cookies, so adsbygoogle.js is requested
  // ONLY after "Accept all". No choice / Essential only / Reject -> never
  // requested. Withdrawing consent stops it on the next page load (a loaded
  // third-party script cannot be unloaded from the current page).
  var adsLoaded = false;
  function loadAds() {
    if (adsLoaded || consent() !== "all") return;
    var meta = document.querySelector('meta[name="uh-ads-client"]');
    var client = meta && meta.getAttribute("content");
    if (!client || !/^ca-pub-[0-9]{10,20}$/.test(client)) return;
    adsLoaded = true;
    var s = document.createElement("script");
    s.async = true;
    s.crossOrigin = "anonymous";
    s.src = "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=" + client;
    document.head.appendChild(s);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var c = consent();
    applyStorage(c);
    var b = banner();
    if (b) {
      var btns = b.querySelectorAll("[data-uh-choice]");
      for (var i = 0; i < btns.length; i++) {
        btns[i].addEventListener("click", function () { choose(this.getAttribute("data-uh-choice")); });
      }
    }
    var jsOnly = document.querySelectorAll("[data-uh-js]");
    for (var k = 0; k < jsOnly.length; k++) jsOnly[k].hidden = false;
    var openers = document.querySelectorAll("[data-uh-consent-open]");
    for (var j = 0; j < openers.length; j++) {
      openers[j].addEventListener("click", function () { showBanner(true); });
    }
    renderState();
    if (!c) showBanner(false);
    else { begin(); loadAds(); }
  });

  // --- suggestion form (/suggest/) ----------------------------------------
  // An explicit submission, independent of the analytics choice above.
  document.addEventListener("DOMContentLoaded", function () {
    var form = document.getElementById("uh-suggest");
    if (!form) return;
    var status = document.getElementById("uh-suggest-status");
    var count = document.getElementById("uh-suggest-count");
    var text = form.elements.text, btn = form.querySelector("button[type=submit]");
    var MSG = {
      sent: "Thanks! Your suggestion was sent to the review committee.",
      "rate-limited": "That is a lot of suggestions in a short time. Please try again in an hour.",
      "text-long": "Please keep it under 1000 characters.",
      "text-short": "Please write a little more so we know what to change.",
      type: "Please pick what kind of suggestion this is.",
      invalid: "Something was wrong with that submission. Please try again.",
      network: "Could not reach the server. Check your connection and try again."
    };
    var params = new URLSearchParams(location.search);
    var preTool = params.get("tool");
    if (preTool && form.elements.tool) {
      for (var i = 0; i < form.elements.tool.options.length; i++) {
        if (form.elements.tool.options[i].value === preTool) form.elements.tool.value = preTool;
      }
    }
    if (params.get("sent")) status.textContent = MSG.sent;
    else if (params.get("error")) status.textContent = MSG[params.get("error")] || MSG.invalid;

    function updateCount() { if (count) count.textContent = (1000 - text.value.length) + " characters left"; }
    text.addEventListener("input", updateCount);
    updateCount();

    form.addEventListener("submit", function (ev) {
      if (!window.fetch) return; // plain form POST fallback
      ev.preventDefault();
      var payload = {
        type: form.elements.type.value,
        tool: form.elements.tool ? form.elements.tool.value : "",
        text: text.value,
        website: form.elements.website ? form.elements.website.value : ""
      };
      btn.disabled = true;
      status.textContent = "Sending…";
      fetch("/api/suggest", { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify(payload) })
        .then(function (r) {
          return r.json()["catch"](function () { return {}; }).then(function (j) {
            if (r.ok) { status.textContent = MSG.sent; form.reset(); updateCount(); }
            else status.textContent = MSG[j.error] || (r.status === 429 ? MSG["rate-limited"] : MSG.invalid);
          });
        }, function () { status.textContent = MSG.network; })
        .then(function () { btn.disabled = false; });
    });
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

CONSENT_BANNER = """\
<section class="consent" id="uh-consent" aria-label="Privacy choices" hidden>
  <p class="consent-title">Help us decide which tools to improve?</p>
  <p>We would like to count which tools, options and buttons get used, and for how long.
  What you type and the results stay on your device &mdash; we never see them.
  <a href="/privacy/">How this works</a></p>
  <p class="consent-note"><strong>Essential only</strong>: anonymous counts, no ID kept between visits.
  <strong>Accept all</strong>: adds a random ID so we can tell when you come back, and shows
  Google ads, which use cookies.
  <strong>Reject</strong>: nothing is sent.</p>
  <div class="actions">
    <button type="button" data-uh-choice="all">Accept all</button>
    <button type="button" class="btn-ghost" data-uh-choice="essential">Essential only</button>
    <button type="button" class="btn-ghost" data-uh-choice="reject">Reject</button>
  </div>
</section>"""


def render_page(*, site: dict, title: str, description: str, path: str,
                body: str, jsonld_blocks: list[dict], noindex: bool = False,
                tool_slug: str | None = None) -> str:
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
    # Google AdSense — only on indexable content pages (not the noindex 404,
    # which AdSense treats as a no-content page). The loader is NOT emitted
    # statically: site.js injects adsbygoogle.js only after "Accept all"
    # (D-UH-CONSENT-ANALYTICS). This meta just tells it which client to load.
    if site.get("adsenseClient") and not noindex:
        head.append(f'<meta name="uh-ads-client" content="{esc(site["adsenseClient"])}">')
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
      <a href="/suggest/">Suggest</a>
      <a href="{esc(site['github'])}" rel="noopener">GitHub</a>
    </nav>
  </div>
</header>
<main id="main"{f' data-uh-tool="{esc(tool_slug)}"' if tool_slug else ''}>
  <div class="wrap">
{body}
  </div>
</main>
<footer class="site">
  <div class="wrap">
    <p>&copy; <span data-year>2026</span> {esc(site['author'])}. Tools run in your browser &mdash; what you type never leaves your device.</p>
    <p><a href="/privacy/">Privacy</a><span data-uh-js hidden> &middot; <button type="button" class="linkbtn" data-uh-consent-open>Privacy choices</button></span> &middot; <a href="/suggest/">Suggest a feature</a></p>
  </div>
</footer>
{CONSENT_BANNER}
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
{tool_ui}
    <p class="suggest-cta"><a href="/suggest/?tool={esc(tool['slug'])}">Suggest an improvement to this tool</a></p>{faq_html}"""

    return render_page(
        site=site,
        tool_slug=tool["slug"],
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


PRIVACY_TITLE = "Privacy — what Utility Helpers counts and what it never sees"
PRIVACY_DESC = ("Tool input never leaves your device. With your consent we count which tools, "
                "options and buttons get used. Reject and nothing is sent.")


def render_privacy(*, site: dict) -> str:
    body = """    <h1>Privacy</h1>
    <p class="lede">Every tool runs in your browser. What you type, paste, generate or convert
    never leaves your device. If you allow it, we count how the tools are used so we know
    which ones to improve and which ones nobody needs.</p>
    <div class="prose">
    <p>Your current choice: <strong data-uh-consent-state>not chosen yet</strong>.
    <span data-uh-js hidden><button type="button" class="linkbtn" data-uh-consent-open>Change your privacy choices</button></span></p>

    <h2>The three choices</h2>
    <table>
      <thead><tr><th scope="col">Choice</th><th scope="col">What is sent</th><th scope="col">What is stored in your browser</th></tr></thead>
      <tbody>
        <tr><td>Reject</td><td>Nothing.</td><td>Only the fact that you chose Reject.</td></tr>
        <tr><td>Essential only</td><td>Anonymous usage events (listed below) with a random session id that is
          forgotten when you close the tab.</td><td>Your choice, plus the per-tab session id.</td></tr>
        <tr><td>Accept all</td><td>The same events, plus a random visitor id so we can see whether people come
          back and which tools they use together. Google ads are also loaded (see below).</td><td>Your choice, the session id,
          the random visitor id, and Google&rsquo;s advertising cookies.</td></tr>
      </tbody>
    </table>
    <p>Nothing is sent before you choose. You can change your mind at any time from the
    &ldquo;Privacy choices&rdquo; link at the bottom of every page; switching to Reject or
    Essential only deletes the visitor id from your browser.</p>

    <h2>What a usage event contains</h2>
    <ul>
      <li>Which page was opened and which tool was used.</li>
      <li>Which options were picked (for example a unit pair, a text case, a password length).</li>
      <li>Which buttons were pressed (for example Copy, Format, Encode) and whether the tool showed an error.</li>
      <li>How long the page was visible.</li>
      <li>A rough device class: mobile, tablet or desktop.</li>
    </ul>

    <h2>What we never collect</h2>
    <ul>
      <li>Anything you type, paste or get back from a tool: text, JSON, passwords, URLs, colours, dates.</li>
      <li>Your name, email or any account. There are no accounts.</li>
      <li>Your IP address, browser fingerprint or user agent. Our code never stores them; the only device detail is mobile, tablet or desktop.</li>
      <li>Data for anyone else. There are no third-party analytics scripts. The only third party
      is Google AdSense, and only if you choose Accept all.</li>
    </ul>

    <h2>Ads</h2>
    <p>The site is kept free by Google AdSense. The ad script is loaded <strong>only after you
    choose Accept all</strong>. With no choice, Essential only or Reject, your browser never
    contacts Google&rsquo;s ad servers. When it is loaded, Google may set cookies and use them to
    show and measure ads; that is governed by
    <a href="https://policies.google.com/technologies/ads">Google&rsquo;s advertising policy</a>,
    not by us. Ads never see what you type into a tool. If you later switch to Essential only or
    Reject, ads stop from the next page you open; Google&rsquo;s cookies can be cleared in your
    browser settings.</p>

    <h2>Where it goes and for how long</h2>
    <p>Events go to a small first-party function on this site and are stored in the site&rsquo;s own
    storage on Netlify, our host. Raw events are deleted after 90 days. We keep only
    aggregated counts, such as &ldquo;Word Counter was used 120 times this week&rdquo;.</p>

    <h2>Suggestions</h2>
    <p>The <a href="/suggest/">suggestion form</a> is separate from the choices above: it sends only
    what you write in it, plus the kind of suggestion and the tool it is about. Please leave
    personal details out. Suggestions are read by the people deciding what to build next.</p>

    <h2>The code</h2>
    <p>The site is open source. You can read exactly what is sent in
    <a href="{github}/blob/master/scripts/build.py" rel="noopener">scripts/build.py</a> and
    <a href="{github}/blob/master/netlify/lib/core.mjs" rel="noopener">netlify/lib/core.mjs</a>.</p>
    </div>""".replace("{github}", esc(site["github"]))
    return render_page(site=site, title=PRIVACY_TITLE[:TITLE_MAX], description=PRIVACY_DESC,
                       path="/privacy/", body=body, jsonld_blocks=[])


SUGGEST_TITLE = "Suggest a feature or change — Utility Helpers"
SUGGEST_DESC = ("Ask for a new tool, a design change, report a bug, or tell us what to remove. "
                "Suggestions go straight to the people who decide what gets built.")


def render_suggest(*, site: dict, tools: list[dict]) -> str:
    tool_opts = "\n".join(
        f'          <option value="{esc(t["slug"])}">{esc(t["name"])}</option>' for t in tools)
    body = f"""    <h1>Suggest a feature or change</h1>
    <p class="lede">Want a new tool, a better design, found a bug, or think something should go?
    Tell us. Every suggestion is read when we decide what to build next.</p>
    <form class="tool" id="uh-suggest" action="/api/suggest" method="post">
      <div class="form-grid">
        <div>
          <label for="s-type">What kind of suggestion?</label>
          <select id="s-type" name="type" required>
            <option value="feature">New feature or tool</option>
            <option value="design">Design or usability change</option>
            <option value="bug">Something is broken</option>
            <option value="remove">Remove or simplify something</option>
          </select>
        </div>
        <div>
          <label for="s-tool">Which tool is it about? (optional)</label>
          <select id="s-tool" name="tool">
            <option value="">The whole site / a new tool</option>
{tool_opts}
          </select>
        </div>
        <div>
          <label for="s-text">Your suggestion</label>
          <textarea id="s-text" name="text" maxlength="1000" minlength="3" required rows="6"
            aria-describedby="uh-suggest-count uh-suggest-note"></textarea>
          <p id="uh-suggest-count" class="muted" style="margin:.35rem 0 0;font-size:.875rem">Up to 1000 characters.</p>
        </div>
        <div class="hp" aria-hidden="true">
          <label for="s-website">Leave this field empty</label>
          <input id="s-website" name="website" type="text" tabindex="-1" autocomplete="off">
        </div>
        <div><button type="submit">Send suggestion</button></div>
        <p id="uh-suggest-status" role="status" aria-live="polite" style="margin:0"></p>
        <p id="uh-suggest-note" class="muted" style="margin:0;font-size:.875rem">Please do not include
        personal details. Only your text, the kind of suggestion and the tool are stored.
        <a href="/privacy/">Privacy</a></p>
      </div>
    </form>"""
    return render_page(site=site, title=SUGGEST_TITLE[:TITLE_MAX], description=SUGGEST_DESC,
                       path="/suggest/", body=body, jsonld_blocks=[])


def render_tool_slugs(tools: list[dict]) -> str:
    slugs = json.dumps([t["slug"] for t in tools], indent=2)
    return ("// GENERATED by scripts/build.py from site.config.json — do not edit.\n"
            "// The suggestion function accepts only these tool slugs.\n"
            f"export default {slugs};\n")


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

    add("/privacy/", PRIVACY_TITLE[:TITLE_MAX], PRIVACY_DESC, render_privacy(site=site_cfg))
    add("/suggest/", SUGGEST_TITLE[:TITLE_MAX], SUGGEST_DESC,
        render_suggest(site=site_cfg, tools=tools))

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

    # Server-side allowlist of tool slugs for the suggestion function.
    (ROOT / "netlify" / "lib").mkdir(parents=True, exist_ok=True)
    (ROOT / "netlify" / "lib" / "tool-slugs.mjs").write_text(render_tool_slugs(tools), encoding="utf-8")
    print("  wrote netlify/lib/tool-slugs.mjs")

    # Indexable paths: home + tool pages + privacy + suggest. 404 is noindex, excluded.
    indexable = ["/"] + [f"/{t['slug']}/" for t in tools] + ["/privacy/", "/suggest/"]
    (ROOT / "sitemap.xml").write_text(
        render_sitemap(site=site_cfg, paths=indexable), encoding="utf-8")
    print("  wrote sitemap.xml")

    (ROOT / "robots.txt").write_text(render_robots(site=site_cfg), encoding="utf-8")
    print("  wrote robots.txt")

    # ads.txt — authorises Google as the seller for this publisher ID.
    # Without it, the /* → 404 redirect would answer /ads.txt with a 404.
    if site_cfg.get("adsenseClient"):
        pub_id = site_cfg["adsenseClient"].removeprefix("ca-")
        (ROOT / "ads.txt").write_text(
            f"google.com, {pub_id}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
        print("  wrote ads.txt")

    print("\nOK — build complete.")
    return 0


if __name__ == "__main__":
    sys.exit(build(check_only="--check" in sys.argv))
