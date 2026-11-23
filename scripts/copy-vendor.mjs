// Copy LGPL libheif (via libheif-js) UNMODIFIED into public/vendor/libheif/ before
// `astro build`, next to its licence. It is loaded at run time as a separate file
// (never bundled or minified into our code), only by the HEIC -> JPG page and only
// when the browser cannot decode HEIC itself. Keeping it a separate, replaceable
// file is how the LGPL-3.0 terms are met; the page links the licence and source.
import { copyFileSync, mkdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const pkgDir = join(root, "node_modules", "libheif-js");
const { version } = JSON.parse(readFileSync(join(pkgDir, "package.json"), "utf8"));
const out = join(root, "public", "vendor", "libheif");
mkdirSync(out, { recursive: true });
copyFileSync(join(pkgDir, "libheif-wasm", "libheif-bundle.mjs"), join(out, "libheif-bundle.mjs"));
copyFileSync(join(pkgDir, "LICENSE"), join(out, "LICENSE.txt"));
copyFileSync(join(pkgDir, "libheif-wasm", "LICENSE"), join(out, "LICENSE-libheif-wasm.txt"));
console.log(`vendor: libheif-js ${version} -> public/vendor/libheif/`);
