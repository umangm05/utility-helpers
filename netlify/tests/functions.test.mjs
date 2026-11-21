// node --test netlify/tests/ — runs the function handlers against an in-memory store.
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  MAX_BODY_BYTES,
  SUGGESTIONS_PER_HOUR,
  handleEvents,
  handleSuggest,
  pruneStore,
  sanitizeBatch,
  sanitizeEvent,
} from "../lib/core.mjs";

class MemStore {
  constructor() { this.data = new Map(); }
  async setJSON(k, v) { this.data.set(k, JSON.stringify(v)); }
  async get(k) { return this.data.has(k) ? JSON.parse(this.data.get(k)) : null; }
  async list() { return { blobs: [...this.data.keys()].map((key) => ({ key })) }; }
  async delete(k) { this.data.delete(k); }
  values() { return [...this.data.values()].map((v) => JSON.parse(v)); }
}

const SID = "a".repeat(24);
const VID = "b".repeat(24);
const NOW = new Date("2026-11-21T10:00:00Z");
const post = (path, body, headers = {}) =>
  new Request(`https://utility-helpers.netlify.app${path}`, {
    method: "POST",
    body: typeof body === "string" ? body : JSON.stringify(body),
    headers: { "content-type": "text/plain", ...headers },
  });

test("essential batch never stores a visitor id", async () => {
  const r = sanitizeBatch({ v: 1, c: "essential", sid: SID, vid: VID, dev: "desktop", ev: [{ e: "view", p: "/" }] }, NOW);
  assert.equal(r.ok, true);
  assert.equal("vid" in r.record, false);
});

test("accept-all batch keeps the visitor id", async () => {
  const r = sanitizeBatch({ v: 1, c: "all", sid: SID, vid: VID, dev: "mobile", ev: [{ e: "view", p: "/" }] }, NOW);
  assert.equal(r.record.vid, VID);
});

test("reject / unknown consent is refused", () => {
  for (const c of ["reject", "", undefined, "ALL"]) {
    assert.equal(sanitizeBatch({ v: 1, c, sid: SID, ev: [{ e: "view" }] }).ok, false);
  }
});

test("free-text smuggled into events is dropped", () => {
  // Unknown fields vanish; option values that look like content are rejected.
  const ev = sanitizeEvent({ e: "use", tool: "json-formatter", text: '{"secret":1}', value: "hunter2" });
  assert.deepEqual(Object.keys(ev).sort(), ["e", "tool"]);
  assert.equal(sanitizeEvent({ e: "opt", id: "tc-format", v: "this is: a pasted sentence!" }), null);
  assert.equal(sanitizeEvent({ e: "opt", id: "tc-format", v: "x".repeat(41) }), null);
  assert.deepEqual(sanitizeEvent({ e: "opt", id: "uc-from", v: "fl oz" }), { e: "opt", id: "uc-from", v: "fl oz" });
  assert.equal(sanitizeEvent({ e: "err", kind: "js", id: "Unexpected token } in JSON" }), null);
  assert.equal(sanitizeEvent({ e: "view", p: "/word-counter/?q=hello" }).p, undefined);
});

test("stored event blob has no ip / user agent / unknown keys", async () => {
  const events = new MemStore();
  const res = await handleEvents(
    post("/api/e", { v: 1, c: "all", sid: SID, vid: VID, dev: "desktop", ua: "Mozilla", ip: "1.2.3.4",
      ev: [{ e: "act", id: "jf-format", tool: "json-formatter", p: "/json-formatter/", ts: 1 }] },
      { origin: "https://utility-helpers.netlify.app", "user-agent": "Mozilla/5.0", "x-nf-client-connection-ip": "1.2.3.4" }),
    { events }, NOW);
  assert.equal(res.status, 204);
  const [rec] = events.values();
  assert.deepEqual(Object.keys(rec).sort(), ["c", "dev", "ev", "rcv", "sid", "vid"]);
  assert.equal(JSON.stringify(rec).includes("1.2.3.4"), false);
  assert.equal(JSON.stringify(rec).includes("Mozilla"), false);
  assert.ok([...events.data.keys()][0].startsWith("2026-11-21/"));
});

test("events: cross-origin, oversize and GET are refused", async () => {
  const events = new MemStore();
  const ok = { v: 1, c: "essential", sid: SID, ev: [{ e: "view" }] };
  assert.equal((await handleEvents(post("/api/e", ok, { origin: "https://evil.example" }), { events })).status, 403);
  assert.equal((await handleEvents(post("/api/e", "x".repeat(MAX_BODY_BYTES + 1)), { events })).status, 413);
  assert.equal((await handleEvents(new Request("https://utility-helpers.netlify.app/api/e"), { events })).status, 405);
  assert.equal(events.data.size, 0);
});

const ctx = { toolSlugs: new Set(["word-counter"]), ip: "9.9.9.9", salt: "s" };
const suggestStores = () => ({ suggestions: new MemStore(), ratelimit: new MemStore() });

test("suggest: JSON happy path stores type/tool/text only", async () => {
  const stores = suggestStores();
  const res = await handleSuggest(
    post("/api/suggest", { type: "feature", tool: "word-counter", text: "  Add reading time  ", email: "x@y.z" },
      { "content-type": "application/json" }), stores, ctx, NOW);
  assert.equal(res.status, 201);
  const [rec] = stores.suggestions.values();
  assert.deepEqual(rec, { rcv: NOW.toISOString(), type: "feature", tool: "word-counter", text: "Add reading time" });
  // the rate-limit bucket key is a hash, never the raw ip
  assert.equal([...stores.ratelimit.data.keys()].some((k) => k.includes("9.9.9.9")), false);
});

test("suggest: form post redirects, honeypot stores nothing, limits enforced", async () => {
  const stores = suggestStores();
  const form = (fields) => post("/api/suggest", new URLSearchParams(fields).toString(),
    { "content-type": "application/x-www-form-urlencoded" });

  const spam = await handleSuggest(form({ type: "bug", text: "buy pills", website: "http://spam" }), stores, ctx, NOW);
  assert.equal(spam.status, 303);
  assert.equal(stores.suggestions.data.size, 0);

  const long = await handleSuggest(form({ type: "bug", text: "x".repeat(1001) }), stores, ctx, NOW);
  assert.equal(long.headers.get("location"), "/suggest/?error=text-long");

  const badType = await handleSuggest(form({ type: "rant", text: "hello there" }), stores, ctx, NOW);
  assert.equal(badType.headers.get("location"), "/suggest/?error=type");

  for (let i = 0; i < SUGGESTIONS_PER_HOUR; i++) {
    const r = await handleSuggest(form({ type: "design", text: `idea ${i}` }), stores, ctx, NOW);
    assert.equal(r.headers.get("location"), "/suggest/?sent=1");
  }
  const limited = await handleSuggest(form({ type: "design", text: "one more" }), stores, ctx, NOW);
  assert.equal(limited.headers.get("location"), "/suggest/?error=rate-limited");
  assert.equal(stores.suggestions.data.size, SUGGESTIONS_PER_HOUR);
});

test("retention prunes only day-keys older than the window", async () => {
  const s = new MemStore();
  await s.setJSON("2026-08-22/1-a", {}); // 91 days before NOW -> pruned
  await s.setJSON("2026-08-23/1-b", {}); // 90 days -> kept (cutoff is exclusive)
  await s.setJSON("2026-11-21/1-c", {});
  assert.equal(await pruneStore(s, 90, NOW), 1);
  assert.deepEqual([...s.data.keys()].sort(), ["2026-08-23/1-b", "2026-11-21/1-c"]);
});
