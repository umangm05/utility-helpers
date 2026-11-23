// Shared helpers for the file tools (image, PDF, HEIC, QR, passport photo).
//
// Privacy contract: every function here works on in-memory Blobs/canvases.
// Nothing is uploaded; the only fetch() in the file tools is the same-origin
// GET of a bundled sample file when the user presses "Try a sample".

export const byId = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10 * 1024 ? 1 : 0)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

export function baseName(name: string): string {
  return name.replace(/\.[^.]+$/, "") || "file";
}

/** Decode any image the browser understands, honouring EXIF orientation. */
export async function decodeImage(blob: Blob): Promise<ImageBitmap> {
  try {
    return await createImageBitmap(blob, { imageOrientation: "from-image" });
  } catch {
    // Some browsers only decode via <img> (e.g. SVG); rasterise through it.
    const url = URL.createObjectURL(blob);
    try {
      const img = new Image();
      img.decoding = "async";
      img.src = url;
      await img.decode();
      return await createImageBitmap(img);
    } finally {
      URL.revokeObjectURL(url);
    }
  }
}

export function canvasToBlob(canvas: HTMLCanvasElement, type: string, quality?: number): Promise<Blob> {
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error(`Could not encode ${type}`))), type, quality));
}

export function drawToCanvas(src: CanvasImageSource, w: number, h: number, background?: string): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(w));
  c.height = Math.max(1, Math.round(h));
  const ctx = c.getContext("2d")!;
  if (background) { ctx.fillStyle = background; ctx.fillRect(0, 0, c.width, c.height); }
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(src, 0, 0, c.width, c.height);
  return c;
}

/**
 * Encode `canvas` as JPEG/WebP no larger than `maxBytes`: binary-search the
 * quality, and if even the lowest sensible quality is too big, shrink the
 * pixels 15% at a time (unless allowShrink is false, e.g. an ID photo whose
 * pixel size is fixed). Returns the final canvas too (its size may change).
 */
export async function encodeUnder(canvas: HTMLCanvasElement, type: string, maxBytes: number, allowShrink = true):
  Promise<{ blob: Blob; quality: number; canvas: HTMLCanvasElement; fits: boolean }> {
  let c = canvas;
  for (let shrink = 0; shrink < (allowShrink ? 12 : 1); shrink++) {
    let lo = 0.05, hi = 0.95, best: { blob: Blob; q: number } | null = null;
    for (let i = 0; i < 7; i++) {
      const q = (lo + hi) / 2;
      const b = await canvasToBlob(c, type, q);
      if (b.size <= maxBytes) { best = { blob: b, q }; lo = q; } else hi = q;
    }
    if (!best) {
      const b = await canvasToBlob(c, type, 0.05);
      if (b.size <= maxBytes) best = { blob: b, q: 0.05 };
    }
    if (best) return { blob: best.blob, quality: best.q, canvas: c, fits: true };
    if (c.width < 32 || c.height < 32) break;
    c = drawToCanvas(c, c.width * 0.85, c.height * 0.85, type === "image/jpeg" ? "#fff" : undefined);
  }
  return { blob: await canvasToBlob(c, type, 0.05), quality: 0.05, canvas: c, fits: false };
}

export function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30_000);
}

export function status(el: HTMLElement, msg: string, kind: "info" | "error" | "ok" = "info") {
  el.textContent = msg;
  el.dataset.kind = kind;
}

/** A result row: optional thumbnail, a text line, and a Download button (no blob: <a> in the DOM). */
export function resultRow(opts: { text: string; blob: Blob; name: string; thumb?: Blob | null }): HTMLLIElement {
  const li = document.createElement("li");
  if (opts.thumb) {
    const img = document.createElement("img");
    const url = URL.createObjectURL(opts.thumb);
    img.src = url;
    img.alt = "";
    img.width = 56;
    img.height = 56;
    img.onload = () => URL.revokeObjectURL(url);
    li.append(img);
  }
  const span = document.createElement("span");
  span.className = "res-text";
  span.textContent = opts.text;
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "btn-ghost";
  btn.textContent = "Download";
  btn.setAttribute("aria-label", `Download ${opts.name}`);
  btn.addEventListener("click", () => download(opts.blob, opts.name));
  li.append(span, btn);
  return li;
}

/**
 * Wire a drop area + <input type=file>. `onFiles` gets the picked/dropped
 * files. Also picks up files handed over from the home "Drop anything" zone.
 */
export function filePicker(area: HTMLElement, input: HTMLInputElement, onFiles: (files: File[]) => void, slug: string) {
  input.addEventListener("change", () => {
    if (input.files?.length) onFiles([...input.files]);
    input.value = "";
  });
  area.addEventListener("dragover", (e) => { e.preventDefault(); area.classList.add("over"); });
  area.addEventListener("dragleave", () => area.classList.remove("over"));
  area.addEventListener("drop", (e) => {
    e.preventDefault();
    area.classList.remove("over");
    const files = [...(e.dataTransfer?.files ?? [])];
    if (files.length) onFiles(files);
  });
  takeHandoff(slug).then((files) => { if (files.length) onFiles(files); });
}

// ---- hand-off from the home drop zone (IndexedDB, this browser only) ------
const DB = "uh-handoff";
const STORE = "files";

function idb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function putHandoff(slug: string, files: File[]): Promise<void> {
  const db = await idb();
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).put({ slug, files, at: Date.now() }, "drop");
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}

export async function takeHandoff(slug: string): Promise<File[]> {
  try {
    const db = await idb();
    const rec = await new Promise<{ slug: string; files: File[]; at: number } | undefined>((resolve, reject) => {
      const tx = db.transaction(STORE, "readwrite");
      const st = tx.objectStore(STORE);
      const get = st.get("drop");
      get.onsuccess = () => { st.delete("drop"); resolve(get.result); };
      tx.onerror = () => reject(tx.error);
    });
    db.close();
    // Only a fresh hand-off meant for this tool (2 minutes covers a slow page load).
    if (rec && rec.slug === slug && Date.now() - rec.at < 120_000) return rec.files;
  } catch { /* IndexedDB unavailable (private mode): nothing to take */ }
  return [];
}

/** A synthetic sample photo drawn on a canvas (no network): gradient sky, sun, hills. */
export function samplePhoto(w = 1600, h = 1200): Promise<File> {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  const g = c.getContext("2d")!;
  const sky = g.createLinearGradient(0, 0, 0, h);
  sky.addColorStop(0, "#1e3a8a");
  sky.addColorStop(0.6, "#f59e0b");
  sky.addColorStop(1, "#fde68a");
  g.fillStyle = sky;
  g.fillRect(0, 0, w, h);
  g.fillStyle = "#fff7d6";
  g.beginPath();
  g.arc(w * 0.7, h * 0.45, h * 0.12, 0, Math.PI * 2);
  g.fill();
  g.fillStyle = "#14532d";
  g.beginPath();
  g.moveTo(0, h);
  for (let x = 0; x <= w; x += w / 16) g.lineTo(x, h * 0.72 + Math.sin(x / w * 9) * h * 0.06);
  g.lineTo(w, h);
  g.fill();
  return canvasToBlob(c, "image/jpeg", 0.92).then((b) => new File([b], "sample-photo.jpg", { type: "image/jpeg" }));
}
