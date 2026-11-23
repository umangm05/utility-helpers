import type { APIRoute } from "astro";
import { site } from "../lib/site";

// Authorises Google as the seller for this publisher ID. Without it the
// /* -> 404 rule would answer /ads.txt with a 404.
export const GET: APIRoute = () => {
  const pub = (site.adsenseClient ?? "").replace(/^ca-/, "");
  return new Response(pub ? `google.com, ${pub}, DIRECT, f08c47fec0942fa0\n` : "");
};
