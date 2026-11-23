// Post-build step: write dist/sw.js from scripts/sw.template.js.
//
// PRECACHE  = every page of this build + every shared file up to MAX_PRECACHE bytes
//             (so all pages and the small tools work offline right after the first visit).
//             Larger files (pdf.js, the ONNX runtime wasm, the background-remover model)
//             are cached at runtime the first time a tool needs them.
// VERSION   = hash of (path, content) of everything precached + the worker template, so any
//             change to the build installs a fresh worker and drops the old precache.
// BUILD_FILES = every file in dist/, used to prune stale runtime-cache entries.
//
// Usage: node scripts/gen-sw.mjs   (run by `npm run build` after `astro build`)
import { createHash } from "node:crypto";
import { readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const DIST = join(ROOT, "dist");
const MAX_PRECACHE = 300 * 1024;
// Crawler/platform files and the share image: nothing a visitor needs offline.
const SKIP = new Set(["/sw.js", "/robots.txt", "/ads.txt", "/sitemap.xml", "/_headers", "/_redirects",
  "/assets/og.png"]);   // og.png: social-share image, never shown in the page

function walk(dir) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
}

const files = walk(DIST).map((p) => ({ p, url: "/" + relative(DIST, p).split(sep).join("/") }))
  .filter((f) => !f.url.endsWith(".map"));
const buildFiles = files.map((f) => f.url);
const pre = [];
const hash = createHash("sha256");
for (const f of files.sort((a, b) => a.url.localeCompare(b.url))) {
  if (SKIP.has(f.url)) continue;
  const size = statSync(f.p).size;
  if (size > MAX_PRECACHE) continue;
  // Pages are requested as /slug/ (directory URL), not /slug/index.html.
  const url = f.url === "/index.html" ? "/" : f.url.endsWith("/index.html") ? f.url.slice(0, -"index.html".length) : f.url;
  pre.push(url);
  hash.update(url).update(readFileSync(f.p));
}
const tpl = readFileSync(join(ROOT, "scripts", "sw.template.js"), "utf8");
const version = hash.update(tpl).digest("hex").slice(0, 12);
const out = tpl
  .replace('"__UH_VERSION__"', JSON.stringify(version))
  .replace("__UH_PRECACHE__", JSON.stringify(pre))
  .replace("__UH_BUILD_FILES__", JSON.stringify(buildFiles));
if (out.includes("__UH_")) throw new Error("gen-sw: a placeholder was not replaced");
writeFileSync(join(DIST, "sw.js"), out);
const bytes = pre.reduce((s, u) => {
  const f = files.find((x) => x.url === u || x.url === (u === "/" ? "/index.html" : u + "index.html"));
  return s + (f ? statSync(f.p).size : 0);
}, 0);
console.log(`gen-sw: dist/sw.js version ${version}: ${pre.length} URLs precached (${(bytes / 1024).toFixed(0)} KB), ` +
  `${files.length - pre.length} left to runtime caching`);
