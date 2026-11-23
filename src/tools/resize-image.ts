// Image resize & compress. Everything happens on a <canvas> in this tab.
import { byId, fmtBytes, baseName, decodeImage, drawToCanvas, canvasToBlob, encodeUnder, status, resultRow,
  filePicker, fetchSample } from "./common";

interface Item { file: File; bmp: ImageBitmap }
const EXT: Record<string, string> = { "image/jpeg": "jpg", "image/webp": "webp", "image/png": "png" };

const fileIn = byId<HTMLInputElement>("ri-file");
const inInfo = byId("ri-in");
const wIn = byId<HTMLInputElement>("ri-w");
const hIn = byId<HTMLInputElement>("ri-h");
const lock = byId<HTMLInputElement>("ri-lock");
const fmt = byId<HTMLSelectElement>("ri-format");
const q = byId<HTMLInputElement>("ri-q");
const qv = byId<HTMLOutputElement>("ri-qv");
const target = byId<HTMLInputElement>("ri-target");
const go = byId<HTMLButtonElement>("ri-go");
const st = byId("ri-status");
const out = byId<HTMLUListElement>("ri-out");
let items: Item[] = [];

const num = (el: HTMLInputElement) => { const n = Math.round(Number(el.value)); return n > 0 ? n : 0; };

async function load(files: File[]) {
  const imgs = files.filter((f) => f.type.startsWith("image/") || /\.(jpe?g|png|webp|gif|bmp|avif)$/i.test(f.name));
  if (!imgs.length) { status(inInfo, "Those files are not images this tool can open.", "error"); return; }
  status(inInfo, "Reading…");
  const next: Item[] = [];
  for (const file of imgs) {
    try { next.push({ file, bmp: await decodeImage(file) }); }
    catch { status(st, `Could not open ${file.name}. HEIC photos: use the HEIC to JPG tool first.`, "error"); }
  }
  if (!next.length) { status(inInfo, "No image could be opened.", "error"); return; }
  items.forEach((i) => i.bmp.close());
  items = next;
  const first = items[0];
  wIn.value = String(first.bmp.width);
  hIn.value = String(first.bmp.height);
  const total = items.reduce((s, i) => s + i.file.size, 0);
  status(inInfo, items.length === 1
    ? `${first.file.name} · ${first.bmp.width} × ${first.bmp.height} · ${fmtBytes(first.file.size)}`
    : `${items.length} images · ${fmtBytes(total)} in total (size boxes show the first one)`);
  out.replaceChildren();
  status(st, "");
}

// Keep proportions: editing one side recomputes the other from the first image.
function sync(from: "w" | "h") {
  if (!lock.checked || !items.length) return;
  const { width, height } = items[0].bmp;
  if (from === "w" && num(wIn)) hIn.value = String(Math.max(1, Math.round(num(wIn) * height / width)));
  if (from === "h" && num(hIn)) wIn.value = String(Math.max(1, Math.round(num(hIn) * width / height)));
}
wIn.addEventListener("input", () => sync("w"));
hIn.addEventListener("input", () => sync("h"));
q.addEventListener("input", () => { qv.value = q.value; });

function targetSize(bmp: ImageBitmap): [number, number] {
  const w = num(wIn), h = num(hIn);
  if (!lock.checked) return [w || bmp.width, h || bmp.height];
  // Fit inside the box (works for a batch of differently-sized images).
  const s = Math.min(w ? w / bmp.width : Infinity, h ? h / bmp.height : Infinity);
  const k = Number.isFinite(s) ? s : 1;
  return [Math.max(1, Math.round(bmp.width * k)), Math.max(1, Math.round(bmp.height * k))];
}

async function run() {
  if (!items.length) { status(st, "Choose an image first (or press Try a sample).", "error"); return; }
  go.disabled = true;
  out.replaceChildren();
  let type = fmt.value;
  const maxKB = num(target);
  let note = "";
  if (maxKB && type === "image/png") { type = "image/jpeg"; note = " PNG has no quality setting, so a size limit saves as JPG."; }
  let before = 0, after = 0, misses = 0;
  try {
    for (const [i, it] of items.entries()) {
      status(st, `Working… ${i + 1} of ${items.length}`);
      const [w, h] = targetSize(it.bmp);
      let canvas = drawToCanvas(it.bmp, w, h, type === "image/jpeg" ? "#ffffff" : undefined);
      let blob: Blob;
      if (maxKB) {
        const r = await encodeUnder(canvas, type, maxKB * 1024);
        blob = r.blob; canvas = r.canvas;
        if (!r.fits) misses++;
      } else {
        blob = await canvasToBlob(canvas, type, Number(q.value) / 100);
      }
      before += it.file.size; after += blob.size;
      const pct = Math.round((1 - blob.size / it.file.size) * 100);
      // Older Safari silently encodes PNG when asked for WebP: name the file after what we got.
      const name = `${baseName(it.file.name)}-${canvas.width}x${canvas.height}.${EXT[blob.type] ?? EXT[type]}`;
      const change = pct >= 0 ? `−${pct}%` : `+${-pct}%`;
      out.append(resultRow({ text: `${name} · ${canvas.width} × ${canvas.height} · ${fmtBytes(blob.size)} (${change})`,
        blob, name, thumb: blob }));
    }
    const miss = misses ? ` ${misses} could not reach ${maxKB} KB even at the lowest quality.` : "";
    status(st, `Done: ${fmtBytes(before)} → ${fmtBytes(after)}.${note}${miss}`, misses ? "error" : "ok");
  } catch (e) {
    status(st, `Something went wrong: ${(e as Error).message}`, "error");
  } finally {
    go.disabled = false;
  }
}
go.addEventListener("click", run);

// Try a sample: load the bundled photo and compress it with the current settings in one click.
byId("ri-sample").addEventListener("click", async () => {
  status(inInfo, "Loading the sample…");
  try { await load([await fetchSample("photo")]); }
  catch (e) { status(inInfo, (e as Error).message, "error"); return; }
  if (items.length) await run();
});
filePicker(byId("ri-drop"), fileIn, load, "resize-image");
