// Pure validation + storage logic shared by the Netlify Functions.
//
// Privacy contract (SPEC D-UH-CONSENT-ANALYTICS): first-party only, no PII,
// never tool input/output content. Everything a client sends is passed through
// an allowlist here; unknown fields are dropped, not stored. No IP address and
// no user-agent string is ever written to a blob.
//
// The handlers take a `stores` object ({events, suggestions, ratelimit}) so the
// tests can run against an in-memory fake instead of Netlify Blobs.

import { createHash, randomBytes } from "node:crypto";

export const STORE_EVENTS = "uh-events";
export const STORE_SUGGESTIONS = "uh-suggestions";
export const STORE_RATELIMIT = "uh-ratelimit";

export const MAX_BODY_BYTES = 16 * 1024;
export const MAX_EVENTS_PER_BATCH = 50;
export const SUGGESTION_MAX_CHARS = 1000;
export const SUGGESTIONS_PER_HOUR = 5;
export const RAW_RETENTION_DAYS = 90;
export const RATELIMIT_RETENTION_DAYS = 2;

export const EVENT_TYPES = new Set(["view", "use", "opt", "act", "time", "err"]);
export const CONSENT_LEVELS = new Set(["all", "essential"]);
export const DEVICE_CLASSES = new Set(["mobile", "tablet", "desktop"]);
export const SUGGESTION_TYPES = new Set(["feature", "design", "bug", "remove"]);

const ID_RE = /^[a-f0-9]{24}$/;          // random client ids (12 bytes hex)
const SLUG_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const PATH_RE = /^\/[a-z0-9\-\/]{0,80}$/;
const CTRL_RE = /^[A-Za-z0-9_-]{1,40}$/;  // element ids / error names
// Option values are UI choices (unit names, case styles, lengths), never free text.
const OPT_VALUE_RE = /^[A-Za-z0-9 _.\/-]{0,40}$/;
const MAX_TIME_MS = 6 * 60 * 60 * 1000;

export const dayKey = (date) => date.toISOString().slice(0, 10);

export const blobKey = (date) =>
  `${dayKey(date)}/${date.getTime()}-${randomBytes(4).toString("hex")}`;

const intIn = (v, lo, hi) =>
  Number.isInteger(v) && v >= lo && v <= hi ? v : null;

/** Sanitise one client event. Returns null if it must not be stored. */
export function sanitizeEvent(raw) {
  if (!raw || typeof raw !== "object") return null;
  const e = raw.e;
  if (!EVENT_TYPES.has(e)) return null;
  const out = { e };
  if (typeof raw.tool === "string" && SLUG_RE.test(raw.tool) && raw.tool.length <= 40) {
    out.tool = raw.tool;
  }
  if (typeof raw.p === "string" && PATH_RE.test(raw.p)) out.p = raw.p;
  const ts = intIn(raw.ts, 0, 8.64e15);
  if (ts !== null) out.ts = ts;

  switch (e) {
    case "opt":
      if (typeof raw.id !== "string" || !CTRL_RE.test(raw.id)) return null;
      if (typeof raw.v !== "string" || !OPT_VALUE_RE.test(raw.v)) return null;
      out.id = raw.id;
      out.v = raw.v;
      break;
    case "act":
      if (typeof raw.id !== "string" || !CTRL_RE.test(raw.id)) return null;
      out.id = raw.id;
      break;
    case "time": {
      const ms = intIn(raw.ms, 0, MAX_TIME_MS);
      if (ms === null) return null;
      out.ms = ms;
      break;
    }
    case "err":
      if (raw.kind !== "js" && raw.kind !== "tool") return null;
      if (typeof raw.id !== "string" || !CTRL_RE.test(raw.id)) return null;
      out.kind = raw.kind;
      out.id = raw.id;
      break;
    default:
      break; // view / use carry no extra fields
  }
  return out;
}

/**
 * Validate a beacon batch. Returns {ok:true, record} or {ok:false, reason}.
 * `record` is exactly what gets written to the blob.
 */
export function sanitizeBatch(body, now = new Date()) {
  if (!body || typeof body !== "object") return { ok: false, reason: "body" };
  if (body.v !== 1) return { ok: false, reason: "version" };
  if (!CONSENT_LEVELS.has(body.c)) return { ok: false, reason: "consent" };
  if (typeof body.sid !== "string" || !ID_RE.test(body.sid)) return { ok: false, reason: "sid" };
  if (!Array.isArray(body.ev) || body.ev.length === 0) return { ok: false, reason: "events" };

  const record = {
    rcv: now.toISOString(),
    c: body.c,
    sid: body.sid,
    dev: DEVICE_CLASSES.has(body.dev) ? body.dev : "unknown",
  };
  // A persistent visitor id is only ever accepted under "Accept all".
  if (body.c === "all" && typeof body.vid === "string" && ID_RE.test(body.vid)) {
    record.vid = body.vid;
  }
  record.ev = body.ev.slice(0, MAX_EVENTS_PER_BATCH).map(sanitizeEvent).filter(Boolean);
  if (record.ev.length === 0) return { ok: false, reason: "events" };
  return { ok: true, record };
}

/** Validate a suggestion. Honeypot hits return {ok:true, spam:true}. */
export function sanitizeSuggestion(fields, toolSlugs, now = new Date()) {
  const get = (k) => (typeof fields[k] === "string" ? fields[k] : "");
  if (get("website").trim() !== "") return { ok: true, spam: true };
  const type = get("type");
  if (!SUGGESTION_TYPES.has(type)) return { ok: false, reason: "type" };
  // Strip control characters except newlines/tabs; collapse runaway blank lines.
  const text = get("text")
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  if (text.length < 3) return { ok: false, reason: "text-short" };
  if (text.length > SUGGESTION_MAX_CHARS) return { ok: false, reason: "text-long" };
  const tool = get("tool");
  const record = { rcv: now.toISOString(), type, text };
  if (tool && toolSlugs.has(tool)) record.tool = tool;
  return { ok: true, spam: false, record };
}

let warnedNoSalt = false;
function warnNoSalt() {
  if (warnedNoSalt) return;
  warnedNoSalt = true;
  console.warn("uh: UH_RL_SALT is not set; per-client suggestion cap disabled (platform rate limit still applies)");
}

/** One-way, daily-salted client fingerprint used ONLY as a rate-limit bucket key. */
export function clientBucket(ip, now, salt) {
  const h = createHash("sha256").update(`${salt}|${dayKey(now)}|${ip || "unknown"}`).digest("hex");
  return `${dayKey(now)}/${now.toISOString().slice(11, 13)}/${h.slice(0, 32)}`;
}

export function sameOrigin(req) {
  const origin = req.headers.get("origin");
  if (!origin) return true; // sendBeacon/no-cors from same page may omit it
  try {
    return new URL(origin).host === new URL(req.url).host;
  } catch {
    return false;
  }
}

async function readBody(req) {
  const text = await req.text();
  if (Buffer.byteLength(text, "utf8") > MAX_BODY_BYTES) return { tooLarge: true };
  return { text };
}

const empty = (status, headers = {}) =>
  new Response(null, { status, headers: { "cache-control": "no-store", ...headers } });
const json = (status, payload) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });

/** POST /api/e — batched usage events. */
export async function handleEvents(req, stores, now = new Date()) {
  if (req.method !== "POST") return empty(405, { allow: "POST" });
  if (!sameOrigin(req)) return empty(403);
  const { text, tooLarge } = await readBody(req);
  if (tooLarge) return empty(413);
  let body;
  try {
    body = JSON.parse(text);
  } catch {
    return empty(400);
  }
  const res = sanitizeBatch(body, now);
  if (!res.ok) return empty(400);
  await stores.events.setJSON(blobKey(now), res.record);
  return empty(204);
}

/** POST /api/suggest — JSON (fetch) or form-encoded (no-JS fallback). */
export async function handleSuggest(req, stores, { toolSlugs, ip, salt }, now = new Date()) {
  if (req.method !== "POST") return empty(405, { allow: "POST" });
  if (!sameOrigin(req)) return empty(403);
  const ctype = (req.headers.get("content-type") || "").toLowerCase();
  const isForm = !ctype.includes("application/json");
  const { text, tooLarge } = await readBody(req);
  const reply = (status, code) =>
    isForm
      ? empty(303, { location: `/suggest/?${status < 300 ? "sent=1" : `error=${code}`}` })
      : json(status, status < 300 ? { ok: true } : { ok: false, error: code });
  if (tooLarge) return reply(413, "too-long");

  let fields;
  try {
    fields = isForm ? Object.fromEntries(new URLSearchParams(text)) : JSON.parse(text);
  } catch {
    return reply(400, "invalid");
  }
  if (!fields || typeof fields !== "object") return reply(400, "invalid");

  const res = sanitizeSuggestion(fields, toolSlugs, now);
  if (!res.ok) return reply(400, res.reason);
  if (res.spam) return reply(200, "ok"); // pretend success; store nothing

  // Per-client hourly cap. Needs a secret salt (UH_RL_SALT): with a guessable
  // salt the daily hash of an IP can be brute-forced back to the IP, so with no
  // salt we skip the cap entirely (the platform rate limit in suggest.mjs still
  // applies) rather than store a reversible key.
  if (salt) {
    const bucket = clientBucket(ip, now, salt);
    const seen = (await stores.ratelimit.get(bucket, { type: "json" })) || { n: 0 };
    if (seen.n >= SUGGESTIONS_PER_HOUR) return reply(429, "rate-limited");
    await stores.ratelimit.setJSON(bucket, { n: seen.n + 1 });
  } else {
    warnNoSalt();
  }

  await stores.suggestions.setJSON(blobKey(now), res.record);
  return reply(201, "ok");
}

/** Delete day-prefixed keys older than `days`. Returns number deleted. */
export async function pruneStore(store, days, now = new Date()) {
  const cutoff = dayKey(new Date(now.getTime() - days * 86400000));
  const { blobs } = await store.list();
  let deleted = 0;
  for (const { key } of blobs) {
    const day = key.slice(0, 10);
    if (/^\d{4}-\d{2}-\d{2}$/.test(day) && day < cutoff) {
      await store.delete(key);
      deleted += 1;
    }
  }
  return deleted;
}
