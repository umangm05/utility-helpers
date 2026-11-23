import type { APIRoute } from "astro";
import { tools, pageUrl } from "../lib/site";

// Indexable paths: home + tool pages + about + contact + privacy + suggest. 404 is noindex, excluded.
export const indexablePaths = ["/", ...tools.map((t) => `/${t.slug}/`), "/about/", "/contact/", "/privacy/", "/suggest/"];

const xml = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&apos;");

export const GET: APIRoute = () => new Response(
  `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
  indexablePaths.map((p) => `  <url>\n    <loc>${xml(pageUrl(p))}</loc>\n  </url>`).join("\n") +
  `\n</urlset>\n`,
  { headers: { "content-type": "application/xml; charset=utf-8" } });
