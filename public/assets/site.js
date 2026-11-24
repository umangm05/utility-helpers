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
  }
  window.uhConsent = { get: consent, set: choose, open: function () { showBanner(true); } };

  // Ads are NOT governed by this banner: the standard AdSense tag sits in
  // <head> (src/layouts/Base.astro) and Google's certified consent message
  // (AdSense Privacy & messaging) asks EEA/UK/CH visitors about ad cookies.

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
    else begin();
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
