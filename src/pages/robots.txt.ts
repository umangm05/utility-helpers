import type { APIRoute } from "astro";
import { pageUrl } from "../lib/site";

export const GET: APIRoute = () =>
  new Response(`User-agent: *\nAllow: /\n\nSitemap: ${pageUrl("/sitemap.xml")}\n`);
