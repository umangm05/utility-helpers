// Service worker for Utility Helpers: installable + offline.
//
// Generated into dist/sw.js by scripts/gen-sw.mjs, which replaces the two
// placeholders below with this build's precache list and version.
//
// Privacy: the worker only ever handles same-origin GET requests for the site's
// own pages and files. It never touches /api/* (consent-gated usage events,
// suggestion form), POSTs, or any cross-origin request (AdSense) — those go
// straight to the network exactly as without a worker. It sends nothing itself
// except GETs of this site's own files.
//
// Strategy
//   install   precache every page + the small shared assets of this build
//   navigate  network first (fresh content online, 3.5 s timeout), cache fallback offline
//   assets    cache first: hashed /_astro/ bundles never change under one name; the big lazy
//             libraries (pdf.js, ONNX runtime wasm) and /models/ are cached the first time a
//             tool uses them, so that tool then works offline too
//   activate  drop old precaches, and runtime entries no longer part of this build

const VERSION = "__UH_VERSION__";
const PRECACHE = __UH_PRECACHE__;
const BUILD_FILES = new Set(__UH_BUILD_FILES__);
const PRE = `uh-pre-${VERSION}`;
const RT = "uh-rt-v1";
const NAV_TIMEOUT_MS = 3500;
const CACHE_FIRST = ["/_astro/", "/assets/", "/sfx/", "/models/", "/samples/"];

self.addEventListener("install", (event) => {
  // Static routing (Chromium 123+): /api/* never even reaches this worker, so the
  // usage beacons sent while a page unloads go straight to the network.
  if (event.addRoutes && typeof URLPattern === "function") {
    try {
      event.addRoutes([
        { condition: { urlPattern: new URLPattern({ pathname: "/api/*" }) }, source: "network" },
        { condition: { urlPattern: new URLPattern({ pathname: "/.netlify/*" }) }, source: "network" },
      ]);
    } catch { /* older engine: the fetch handler below skips these paths too */ }
  }
  event.waitUntil(caches.open(PRE).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const k of await caches.keys()) {
      if (k.startsWith("uh-pre-") && k !== PRE) await caches.delete(k);
    }
    const rt = await caches.open(RT);
    for (const req of await rt.keys()) {
      const p = new URL(req.url).pathname;
      if (!BUILD_FILES.has(p)) await rt.delete(req);
    }
    await self.clients.claim();
  })());
});

async function fromCache(req) {
  return (await caches.match(req, { ignoreSearch: true })) || null;
}

async function navigate(event) {
  const req = event.request;
  const url = new URL(req.url);
  const network = fetch(req).then(async (res) => {
    if (res.ok && res.type === "basic") {
      const c = await caches.open(PRE);
      await c.put(url.pathname, res.clone());
    }
    return res;
  });
  network.catch(() => {});   // handled below; avoid an unhandled rejection after a timeout
  const timeout = new Promise((resolve) => setTimeout(resolve, NAV_TIMEOUT_MS, null));
  try {
    const res = await Promise.race([network, timeout]);
    if (res) return res;
    const cached = await offlinePage(url);
    return cached || (await network);
  } catch {
    return (await offlinePage(url)) || Response.error();
  }
}

async function offlinePage(url) {
  let p = url.pathname;
  if (!p.endsWith("/") && !p.includes(".")) p += "/";
  return (await caches.match(p, { ignoreSearch: true })) || (await caches.match("/404.html"));
}

async function cacheFirst(req) {
  const hit = await fromCache(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok && res.type === "basic" && !req.headers.has("range")) {
    const c = await caches.open(RT);
    await c.put(req, res.clone());
  }
  return res;
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/.netlify/")) return;
  if (req.mode === "navigate") { event.respondWith(navigate(event)); return; }
  if (CACHE_FIRST.some((p) => url.pathname.startsWith(p))) event.respondWith(cacheFirst(req));
});
