// Passport / ID photo maker. Crop -> single photo at 300 DPI -> print sheet.
// Everything is drawn on canvases in this tab; nothing is uploaded.
import { byId, decodeImage, canvasToBlob, encodeUnder, status, download, filePicker, fmtBytes, fetchSample } from "./common";

const DPI = 300;
const mmToPx = (mm: number) => Math.round((mm / 25.4) * DPI);
const SHEETS = { "4x6": [1800, 1200], a4: [3508, 2480] } as const;   // long side first, at 300 DPI
const SHEET_NAME = { "4x6": "4×6 in", a4: "A4" } as const;

const sizeSel = byId<HTMLSelectElement>("pp-size");
const sheetSel = byId<HTMLSelectElement>("pp-sheet");
const kbIn = byId<HTMLInputElement>("pp-kb");
const lines = byId<HTMLInputElement>("pp-lines");
const work = byId("pp-work");
const ed = byId<HTMLCanvasElement>("pp-edit");
const zoomIn = byId<HTMLInputElement>("pp-zoom");
const meta = byId("pp-meta");
const st = byId("pp-status");
const preview = byId<HTMLImageElement>("pp-sheet-preview");

let bmp: ImageBitmap | null = null;
let cx = 0, cy = 0;   // image point under the frame centre (image px)
let zoom = 1;          // 1 = image just covers the frame

function photoPx(): [number, number] {
  const [w, h] = sizeSel.value.split("x").map(Number);
  return [mmToPx(w), mmToPx(h)];
}
const baseScale = (W: number, H: number) => Math.max(W / bmp!.width, H / bmp!.height);

function clamp() {
  if (!bmp) return;
  const [W, H] = photoPx();
  const s = baseScale(W, H) * zoom;
  const hw = W / 2 / s, hh = H / 2 / s;
  cx = Math.min(Math.max(cx, hw), bmp.width - hw);
  cy = Math.min(Math.max(cy, hh), bmp.height - hh);
}

/** Draw the current crop into ctx at w × h. */
function drawCrop(g: CanvasRenderingContext2D, w: number, h: number) {
  const [W, H] = photoPx();
  const s = baseScale(W, H) * zoom * (w / W);
  g.fillStyle = "#fff";
  g.fillRect(0, 0, w, h);
  g.imageSmoothingQuality = "high";
  g.drawImage(bmp!, cx - w / 2 / s, cy - h / 2 / s, w / s, h / s, 0, 0, w, h);
}

function photoCanvas(): HTMLCanvasElement {
  const [W, H] = photoPx();
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  drawCrop(c.getContext("2d")!, W, H);
  return c;
}

export interface Layout { W: number; H: number; cols: number; rows: number; m: number; g: number }
/** Most copies of a pw × ph photo on the sheet; margins + gaps preferred on a tie. */
export function layout(sheet: keyof typeof SHEETS, pw: number, ph: number): Layout {
  const [a, b] = SHEETS[sheet];
  let best: Layout | null = null;
  for (const [W, H] of [[a, b], [b, a]]) {
    for (const [m, g] of [[30, 15], [0, 0]]) {
      const cols = Math.floor((W - 2 * m + g) / (pw + g));
      const rows = Math.floor((H - 2 * m + g) / (ph + g));
      if (!best || cols * rows > best.cols * best.rows) best = { W, H, cols, rows, m, g };
    }
  }
  return best!;
}

function sheetCanvas(photo: HTMLCanvasElement): { c: HTMLCanvasElement; n: number; L: Layout } {
  const L = layout(sheetSel.value as keyof typeof SHEETS, photo.width, photo.height);
  const c = document.createElement("canvas");
  c.width = L.W;
  c.height = L.H;
  const g = c.getContext("2d")!;
  g.fillStyle = "#fff";
  g.fillRect(0, 0, L.W, L.H);
  const gw = L.cols * photo.width + (L.cols - 1) * L.g;
  const gh = L.rows * photo.height + (L.rows - 1) * L.g;
  const x0 = Math.round((L.W - gw) / 2), y0 = Math.round((L.H - gh) / 2);
  g.strokeStyle = "#9ca3af";
  g.lineWidth = 2;
  for (let r = 0; r < L.rows; r++) for (let k = 0; k < L.cols; k++) {
    const x = x0 + k * (photo.width + L.g), y = y0 + r * (photo.height + L.g);
    g.drawImage(photo, x, y);
    if (lines.checked) g.strokeRect(x + 1, y + 1, photo.width - 2, photo.height - 2);
  }
  return { c, n: L.cols * L.rows, L };
}

/** Write 300 DPI into the JPEG's JFIF header so printers keep the real size. */
async function withDpi(blob: Blob): Promise<Blob> {
  const b = new Uint8Array(await blob.arrayBuffer());
  const jfif = b[2] === 0xff && b[3] === 0xe0 && String.fromCharCode(...b.slice(6, 10)) === "JFIF";
  if (!jfif) return blob;
  b[13] = 1;                       // units: dots per inch
  b[14] = DPI >> 8; b[15] = DPI & 0xff;
  b[16] = DPI >> 8; b[17] = DPI & 0xff;
  return new Blob([b], { type: "image/jpeg" });
}

// ---- editor ------------------------------------------------------------------
function drawEditor() {
  if (!bmp) return;
  const [W, H] = photoPx();
  const scale = Math.min(2, window.devicePixelRatio || 1);
  const w = Math.round(288 * scale), h = Math.round((288 * H / W) * scale);
  if (ed.width !== w || ed.height !== h) { ed.width = w; ed.height = h; }
  const g = ed.getContext("2d")!;
  drawCrop(g, w, h);
  // Face guide (editor only): oval for the face, lines for the top of the head and the chin.
  g.save();
  g.strokeStyle = "rgba(245,158,11,.95)";
  g.lineWidth = 2 * scale;
  g.setLineDash([6 * scale, 5 * scale]);
  g.beginPath();
  g.ellipse(w / 2, h * 0.46, w * 0.3, h * 0.34, 0, 0, Math.PI * 2);
  g.stroke();
  g.beginPath();
  g.moveTo(w * 0.2, h * 0.1); g.lineTo(w * 0.8, h * 0.1);
  g.moveTo(w * 0.2, h * 0.82); g.lineTo(w * 0.8, h * 0.82);
  g.stroke();
  g.restore();
}

let previewUrl = "";
let pending = 0;
function refresh() {
  if (!bmp) return;
  clamp();
  drawEditor();
  clearTimeout(pending);
  pending = window.setTimeout(async () => {
    const photo = photoCanvas();
    const { c, n, L } = sheetCanvas(photo);
    const sheet = sheetSel.value as keyof typeof SHEETS;
    const small = document.createElement("canvas");
    small.width = 600;
    small.height = Math.round(600 * L.H / L.W);
    small.getContext("2d")!.drawImage(c, 0, 0, small.width, small.height);
    const blob = await canvasToBlob(small, "image/jpeg", 0.85);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(blob);
    preview.src = previewUrl;
    preview.width = small.width / 2;
    preview.height = small.height / 2;
    const [mw, mh] = sizeSel.value.split("x").map(Number);
    status(meta, `${Math.round(mw)} × ${Math.round(mh)} mm · ${photo.width} × ${photo.height} px at ${DPI} DPI · `
      + `${n} photos on a ${SHEET_NAME[sheet]} sheet`, "ok");
  }, 120);
}

function load(b: ImageBitmap) {
  bmp?.close();
  bmp = b;
  zoom = 1;
  zoomIn.value = "100";
  cx = b.width / 2;
  cy = b.height / 2;
  work.hidden = false;
  status(st, "");
  refresh();
}

async function loadFiles(files: File[]) {
  const f = files.find((x) => x.type.startsWith("image/")) ?? files[0];
  if (!f) return;
  try { load(await decodeImage(f)); }
  catch { status(st, "That file is not a photo this browser can open (HEIC: convert it to JPG first).", "error"); work.hidden = false; }
}

// Drag / pinch / wheel / keys.
const pts = new Map<number, { x: number; y: number }>();
let pinch0 = 0, zoom0 = 1;
function edScale() {   // image px per CSS px of the editor
  const [W, H] = photoPx();
  return 1 / (baseScale(W, H) * zoom * (ed.clientWidth / W));
}
function setZoom(z: number) {
  zoom = Math.min(4, Math.max(1, z));
  zoomIn.value = String(Math.round(zoom * 100));
  refresh();
}
ed.addEventListener("pointerdown", (e) => { ed.setPointerCapture(e.pointerId); pts.set(e.pointerId, { x: e.clientX, y: e.clientY }); });
ed.addEventListener("pointermove", (e) => {
  const p = pts.get(e.pointerId);
  if (!p || !bmp) return;
  if (pts.size === 2) {
    pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const [a, b] = [...pts.values()];
    const d = Math.hypot(a.x - b.x, a.y - b.y);
    if (!pinch0) { pinch0 = d; zoom0 = zoom; }
    setZoom(zoom0 * d / pinch0);
    return;
  }
  const k = edScale();
  cx -= (e.clientX - p.x) * k;
  cy -= (e.clientY - p.y) * k;
  pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
  refresh();
});
const lift = (e: PointerEvent) => { pts.delete(e.pointerId); if (pts.size < 2) pinch0 = 0; };
ed.addEventListener("pointerup", lift);
ed.addEventListener("pointercancel", lift);
ed.addEventListener("wheel", (e) => { e.preventDefault(); setZoom(zoom * (e.deltaY < 0 ? 1.06 : 1 / 1.06)); }, { passive: false });
ed.addEventListener("keydown", (e) => {
  if (!bmp) return;
  const k = edScale() * 8;
  const moves: Record<string, [number, number]> = { ArrowLeft: [k, 0], ArrowRight: [-k, 0], ArrowUp: [0, k], ArrowDown: [0, -k] };
  if (moves[e.key]) { e.preventDefault(); cx += moves[e.key][0]; cy += moves[e.key][1]; refresh(); }
  else if (e.key === "+" || e.key === "=") { e.preventDefault(); setZoom(zoom * 1.1); }
  else if (e.key === "-") { e.preventDefault(); setZoom(zoom / 1.1); }
});
zoomIn.addEventListener("input", () => setZoom(Number(zoomIn.value) / 100));
[sizeSel, sheetSel, lines].forEach((el) => el.addEventListener("change", refresh));

// ---- downloads ----------------------------------------------------------------
const tag = () => `${sizeSel.value.replace("50.8x50.8", "2x2in").replace(/^(\d+x\d+)$/, "$1mm")}`;
byId("pp-single").addEventListener("click", async () => {
  if (!bmp) return;
  const photo = photoCanvas();
  const kb = Number(kbIn.value);
  if (kb > 0) {
    // Pixel size is the official size at 300 DPI, so only the JPG quality may change.
    const r = await encodeUnder(photo, "image/jpeg", kb * 1024, false);
    const blob = await withDpi(r.blob);
    download(blob, `passport-photo-${tag()}.jpg`);
    status(st, r.fits ? `Saved ${fmtBytes(blob.size)} (${r.canvas.width} × ${r.canvas.height} px).`
      : `Could not get under ${kb} KB without shrinking the photo below its official size; `
        + `saved the lowest-quality version (${fmtBytes(blob.size)}).`, r.fits ? "ok" : "error");
    return;
  }
  const blob = await withDpi(await canvasToBlob(photo, "image/jpeg", 0.95));
  download(blob, `passport-photo-${tag()}.jpg`);
  status(st, `Saved ${fmtBytes(blob.size)}.`, "ok");
});
byId("pp-sheetbtn").addEventListener("click", async () => {
  if (!bmp) return;
  const { c, n } = sheetCanvas(photoCanvas());
  const blob = await withDpi(await canvasToBlob(c, "image/jpeg", 0.95));
  download(blob, `passport-photos-${tag()}-${sheetSel.value}-sheet.jpg`);
  status(st, `Saved a sheet of ${n} photos (${fmtBytes(blob.size)}). Print it at actual size.`, "ok");
});

// ---- Try a sample: the bundled portrait, cropped to the selected size in one click --------
byId("pp-sample").addEventListener("click", async () => {
  status(st, "Loading the sample…");
  try { await loadFiles([await fetchSample("photo")]); }
  catch (e) { status(st, (e as Error).message, "error"); }
});

filePicker(byId("pp-drop"), byId<HTMLInputElement>("pp-file"), loadFiles, "passport-size-photo");
