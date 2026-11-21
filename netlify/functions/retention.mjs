// Daily retention sweep: raw events 90 days, rate-limit buckets 2 days.
// Suggestions are explicit submissions for the committee and are kept.
import { getStore } from "@netlify/blobs";
import {
  RATELIMIT_RETENTION_DAYS,
  RAW_RETENTION_DAYS,
  STORE_EVENTS,
  STORE_RATELIMIT,
  pruneStore,
} from "../lib/core.mjs";

export default async () => {
  const events = await pruneStore(getStore(STORE_EVENTS), RAW_RETENTION_DAYS);
  const rl = await pruneStore(getStore(STORE_RATELIMIT), RATELIMIT_RETENTION_DAYS);
  console.log(JSON.stringify({ retention: { events, ratelimit: rl } }));
};

export const config = { schedule: "@daily" };
