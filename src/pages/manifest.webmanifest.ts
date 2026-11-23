// Web app manifest, generated from site.config.json (single source of truth).
// Makes the site installable; the service worker (/sw.js, scripts/gen-sw.mjs) makes it work offline.
import { site, tools } from "../lib/site";

const SHORTCUTS = ["pdf-tools", "resize-image", "emi-calculator", "background-remover"];

export function GET() {
  const manifest = {
    name: site.name,
    short_name: "Utility Helpers",
    description: site.description,
    id: "/",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#0b0d10",
    theme_color: site.themeColor,
    lang: "en",
    categories: ["utilities", "productivity"],
    icons: [
      { src: "/assets/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/assets/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/assets/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: SHORTCUTS.map((s) => tools.find((t) => t.slug === s)).filter(Boolean).map((t) => ({
      name: t!.name,
      url: `/${t!.slug}/`,
      icons: [{ src: "/assets/icon-192.png", sizes: "192x192", type: "image/png" }],
    })),
  };
  return new Response(JSON.stringify(manifest, null, 2), {
    headers: { "Content-Type": "application/manifest+json; charset=utf-8" },
  });
}
