// POST /api/suggest — public suggestion form feeding the weekly committee.
import { getStore } from "@netlify/blobs";
import {
  STORE_RATELIMIT,
  STORE_SUGGESTIONS,
  handleSuggest,
} from "../lib/core.mjs";
import TOOL_SLUGS from "../lib/tool-slugs.mjs";

const toolSlugs = new Set(TOOL_SLUGS);

export default async (req, context) =>
  handleSuggest(
    req,
    {
      suggestions: getStore(STORE_SUGGESTIONS),
      ratelimit: getStore({ name: STORE_RATELIMIT, consistency: "strong" }),
    },
    {
      toolSlugs,
      ip: context.ip,
      // The salt only needs to be unguessable from outside; the site id is not
      // public in page HTML, and the bucket rotates daily anyway.
      salt: process.env.UH_RL_SALT || context.site?.id || "uh",
    },
  );

export const config = {
  path: "/api/suggest",
  method: "POST",
  rateLimit: { windowLimit: 3, windowSize: 180, aggregateBy: ["ip", "domain"] },
};
