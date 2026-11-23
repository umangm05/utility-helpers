// Astro (MIT) static build. Output: dist/ — one pre-rendered HTML page per
// tool at the same /<slug>/ URL as before. Netlify publishes dist/.
import { defineConfig } from "astro/config";
import config from "./site.config.json" with { type: "json" };

export default defineConfig({
  site: config.site.baseUrl,
  output: "static",
  trailingSlash: "ignore",
  build: { format: "directory", inlineStylesheets: "always" },
  compressHTML: true,
  devToolbar: { enabled: false },
});
