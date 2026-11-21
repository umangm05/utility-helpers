// POST /api/e — anonymous, consent-gated usage events (see netlify/lib/core.mjs).
import { getStore } from "@netlify/blobs";
import { STORE_EVENTS, handleEvents } from "../lib/core.mjs";

export default async (req) =>
  handleEvents(req, { events: getStore(STORE_EVENTS) });

export const config = {
  path: "/api/e",
  method: "POST",
  // Free plan allows 2 code-based rules per project: one here, one on /api/suggest.
  rateLimit: { windowLimit: 60, windowSize: 60, aggregateBy: ["ip", "domain"] },
};
