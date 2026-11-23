// HEIC -> JPG/PNG. Native decode first (Safari/iOS, some Chromium builds with
// HEVC), then heic-decoder.ts. The photo never leaves the browser.
import { byId, fmtBytes, baseName, drawToCanvas, canvasToBlob, status, resultRow, filePicker, download } from "./common";
import { decodeHeicFallback, FALLBACK_NOTE } from "./heic-decoder";

const st = byId("heic-status");
const out = byId<HTMLUListElement>("heic-out");
const fmt = byId<HTMLSelectElement>("heic-format");
const q = byId<HTMLInputElement>("heic-q");
const qv = byId<HTMLOutputElement>("heic-qv");
const allRow = byId("heic-all-row");
let done: { blob: Blob; name: string }[] = [];
let last: File[] = [];

q.addEventListener("input", () => { qv.value = q.value; });
if (FALLBACK_NOTE) byId("heic-note").innerHTML = FALLBACK_NOTE;

async function decode(file: File): Promise<ImageBitmap> {
  try {
    const bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
    if (bmp.width && bmp.height) return bmp;
  } catch { /* no native HEIC: fall through */ }
  return decodeHeicFallback(file);
}

async function convert(files: File[]) {
  last = files;
  out.replaceChildren();
  done = [];
  allRow.hidden = true;
  const type = fmt.value;
  const ext = type === "image/png" ? "png" : "jpg";
  let fails = 0;
  for (const [i, f] of files.entries()) {
    status(st, `Converting ${i + 1} of ${files.length}…`);
    try {
      const bmp = await decode(f);
      const c = drawToCanvas(bmp, bmp.width, bmp.height, type === "image/jpeg" ? "#ffffff" : undefined);
      bmp.close();
      const blob = await canvasToBlob(c, type, Number(q.value) / 100);
      const name = `${baseName(f.name)}.${ext}`;
      done.push({ blob, name });
      out.append(resultRow({ text: `${name} · ${c.width} × ${c.height} · ${fmtBytes(blob.size)}`, blob, name, thumb: blob }));
    } catch (e) {
      fails++;
      status(st, `${f.name}: ${(e as Error).message}`, "error");
    }
  }
  if (!fails) status(st, `${done.length} photo${done.length === 1 ? "" : "s"} converted.`, "ok");
  allRow.hidden = done.length < 2;
}

// Changing the format re-converts what is already loaded.
fmt.addEventListener("change", () => { if (last.length) convert(last); });
q.addEventListener("change", () => { if (last.length) convert(last); });
byId("heic-all").addEventListener("click", async () => {
  for (const d of done) { download(d.blob, d.name); await new Promise((r) => setTimeout(r, 350)); }
});
byId("heic-sample").addEventListener("click", async () => {
  status(st, "Loading the sample…");
  // Same-origin static file (a 640 × 480 test pattern made by scripts/make_heic_sample.py).
  const r = await fetch("/samples/sample.heic").catch(() => null);
  if (!r?.ok) { status(st, "Could not load the sample. Check your connection and try again.", "error"); return; }
  convert([new File([await r.blob()], "sample.heic", { type: "image/heic" })]);
});
filePicker(byId("heic-drop"), byId<HTMLInputElement>("heic-file"), convert, "heic-to-jpg");
