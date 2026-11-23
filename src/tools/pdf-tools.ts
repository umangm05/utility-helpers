// PDF tools: one ordered page list built from PDFs and photos, then
//   Make one PDF  |  Extract pages (range)  |  Split every page  |  Convert pages to JPG.
// pdf-lib (MIT) and pdf.js (Apache-2.0) load on first use, from this site only.
import { byId, fmtBytes, baseName, decodeImage, drawToCanvas, canvasToBlob, status, resultRow, filePicker }
  from "./common";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

type PdfLib = typeof import("pdf-lib");
type PdfJs = typeof import("pdfjs-dist");
type LibDoc = import("pdf-lib").PDFDocument;
type JsDoc = import("pdfjs-dist").PDFDocumentProxy;

let pdfLibP: Promise<PdfLib> | null = null;
const pdfLib = () => (pdfLibP ??= import("pdf-lib"));
let pdfJsP: Promise<PdfJs> | null = null;
const pdfJs = () => (pdfJsP ??= import("pdfjs-dist").then((m) => {
  m.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;
  return m;
}));

interface Source { name: string; bytes: Uint8Array; lib: LibDoc; js?: Promise<JsDoc> }
interface Page {
  id: number;
  file: number;          // which added file it came from (for the "N files" count)
  name: string;
  kind: "pdf" | "img";
  src?: Source; index: number;            // pdf page
  img?: Blob; w: number; h: number;       // photo (already orientation-corrected)
  rot: number;                            // extra clockwise rotation, degrees
}

const PAGE = { a4: [595.28, 841.89], letter: [612, 792] } as const;
const MAX_IMG_SIDE = 3508;               // A4 long side at 300 DPI

const listEl = byId<HTMLOListElement>("pdf-pages");
const summary = byId("pdf-summary");
const st = byId("pdf-status");
const out = byId<HTMLUListElement>("pdf-out");
const sizeSel = byId<HTMLSelectElement>("pdf-size");
const rangeIn = byId<HTMLInputElement>("pdf-range");
const dpiSel = byId<HTMLSelectElement>("pdf-dpi");
const buttons = ["pdf-build", "pdf-extract", "pdf-split", "pdf-jpg", "pdf-clear", "pdf-sample"]
  .map((id) => byId<HTMLButtonElement>(id));

let pages: Page[] = [];
let nextId = 1;
let fileCount = 0;
const thumbs = new Map<number, HTMLElement>();

const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;

// ---- adding files ----------------------------------------------------------
function isPdf(f: File) { return f.type === "application/pdf" || /\.pdf$/i.test(f.name); }

async function addFiles(files: File[]) {
  busy(true);
  status(st, "Reading…");
  const errors: string[] = [];
  for (const f of files) {
    try {
      if (isPdf(f)) await addPdf(f);
      else if (f.type.startsWith("image/") || /\.(jpe?g|png|webp|gif|bmp)$/i.test(f.name)) await addImage(f);
      else errors.push(`${f.name}: not a PDF or photo`);
    } catch (e) {
      const msg = (e as Error).message || "";
      errors.push(/encrypt/i.test(msg) ? `${f.name} is password-protected; remove the password first`
        : `${f.name} could not be opened`);
    }
  }
  render();
  status(st, errors.join(". "), errors.length ? "error" : "info");
  busy(false);
}

async function addPdf(f: File) {
  const { PDFDocument } = await pdfLib();
  const bytes = new Uint8Array(await f.arrayBuffer());
  const lib = await PDFDocument.load(bytes, { updateMetadata: false });
  const src: Source = { name: f.name, bytes, lib };
  const file = ++fileCount;
  for (let i = 0; i < lib.getPageCount(); i++) {
    pages.push({ id: nextId++, file, name: f.name, kind: "pdf", src, index: i, w: 0, h: 0, rot: 0 });
  }
}

async function addImage(f: File) {
  const bmp = await decodeImage(f);
  const k = Math.min(1, MAX_IMG_SIDE / Math.max(bmp.width, bmp.height));
  const png = f.type === "image/png";
  const c = drawToCanvas(bmp, bmp.width * k, bmp.height * k, png ? undefined : "#ffffff");
  bmp.close();
  const img = await canvasToBlob(c, png ? "image/png" : "image/jpeg", 0.9);
  pages.push({ id: nextId++, file: ++fileCount, name: f.name, kind: "img", index: 0, img, w: c.width, h: c.height, rot: 0 });
}

// ---- page list -------------------------------------------------------------
function move(i: number, j: number) {
  if (j < 0 || j >= pages.length) return;
  const [p] = pages.splice(i, 1);
  pages.splice(j, 0, p);
  render();
  (listEl.children[j]?.querySelector(`[data-act="${j > i ? "down" : "up"}"]`) as HTMLButtonElement | null)?.focus();
}

function actButton(act: string, label: string, text: string, on: () => void) {
  const b = document.createElement("button");
  b.type = "button";
  b.dataset.act = act;
  b.setAttribute("aria-label", label);
  b.title = label;
  b.textContent = text;
  b.addEventListener("click", on);
  return b;
}

function thumbFor(p: Page): HTMLElement {
  let t = thumbs.get(p.id);
  if (t) return t;
  t = document.createElement("div");
  t.className = "thumb";
  thumbs.set(p.id, t);
  if (p.kind === "img" && p.img) {
    const img = document.createElement("img");
    img.alt = "";
    img.src = URL.createObjectURL(p.img);
    t.append(img);
  } else {
    t.textContent = `Page ${p.index + 1}`;
    renderThumb(p, t);
  }
  return t;
}

function jsDoc(src: Source): Promise<JsDoc> {
  return (src.js ??= pdfJs().then((m) => m.getDocument({ data: src.bytes.slice(), useSystemFonts: true }).promise));
}

async function renderThumb(p: Page, holder: HTMLElement) {
  try {
    const doc = await jsDoc(p.src!);
    const pg = await doc.getPage(p.index + 1);
    const vp1 = pg.getViewport({ scale: 1 });
    const vp = pg.getViewport({ scale: Math.min(2, 272 / Math.max(vp1.width, vp1.height)) });
    const c = document.createElement("canvas");
    c.width = Math.ceil(vp.width);
    c.height = Math.ceil(vp.height);
    await pg.render({ canvas: c, viewport: vp }).promise;
    c.setAttribute("aria-hidden", "true");
    holder.replaceChildren(c);
    c.style.transform = `rotate(${p.rot}deg)`;
  } catch { /* keep the "Page N" placeholder */ }
}

function dropThumb(id: number) {
  const img = thumbs.get(id)?.querySelector("img");
  if (img?.src.startsWith("blob:")) URL.revokeObjectURL(img.src);
  thumbs.delete(id);
}

let dragFrom = -1;
function render() {
  const n = pages.length;
  listEl.replaceChildren(...pages.map((p, i) => {
    const li = document.createElement("li");
    li.draggable = true;
    const t = thumbFor(p);
    const visual = t.firstElementChild as HTMLElement | null;
    if (visual) visual.style.transform = `rotate(${p.rot}deg)`;
    const lab = document.createElement("span");
    lab.className = "lab";
    const b = document.createElement("b");
    b.textContent = `${i + 1}.`;
    lab.append(b, ` ${p.name}${p.kind === "pdf" ? ` · p${p.index + 1}` : ""}`);
    const acts = document.createElement("div");
    acts.className = "acts";
    acts.append(
      actButton("up", `Move page ${i + 1} up`, "↑", () => move(i, i - 1)),
      actButton("down", `Move page ${i + 1} down`, "↓", () => move(i, i + 1)),
      actButton("rot", `Rotate page ${i + 1}`, "⟳", () => { p.rot = (p.rot + 90) % 360; render(); }),
      actButton("del", `Remove page ${i + 1}`, "✕", () => { pages.splice(i, 1); dropThumb(p.id); render(); }),
    );
    li.append(t, lab, acts);
    li.addEventListener("dragstart", () => { dragFrom = i; li.classList.add("dragging"); });
    li.addEventListener("dragend", () => li.classList.remove("dragging"));
    li.addEventListener("dragover", (e) => e.preventDefault());
    li.addEventListener("drop", (e) => { e.preventDefault(); e.stopPropagation(); if (dragFrom >= 0) move(dragFrom, i); dragFrom = -1; });
    return li;
  }));
  const files = new Set(pages.map((p) => p.file)).size;
  status(summary, n ? `${plural(n, "page")} from ${plural(files, "file")}` : "No pages yet.");
}

// ---- building ---------------------------------------------------------------
function pageSize(w: number, h: number): [number, number] {
  if (sizeSel.value === "fit") return [w * 0.75, h * 0.75];   // CSS px -> pt
  const [a, b] = PAGE[sizeSel.value as "a4" | "letter"];
  return w > h ? [b, a] : [a, b];
}

async function buildPdf(sel: Page[]): Promise<Uint8Array> {
  const { PDFDocument, degrees } = await pdfLib();
  const doc = await PDFDocument.create();
  // Copy each source's pages in one call so shared fonts/images are copied once.
  const copied = new Map<Page, import("pdf-lib").PDFPage>();
  const bySrc = new Map<Source, Page[]>();
  for (const p of sel) if (p.kind === "pdf") bySrc.set(p.src!, [...(bySrc.get(p.src!) ?? []), p]);
  for (const [src, ps] of bySrc) {
    const got = await doc.copyPages(src.lib, ps.map((p) => p.index));
    ps.forEach((p, k) => copied.set(p, got[k]));
  }
  for (const p of sel) {
    if (p.kind === "pdf") {
      const page = doc.addPage(copied.get(p)!);
      if (p.rot) page.setRotation(degrees((page.getRotation().angle + p.rot) % 360));
    } else {
      const bytes = new Uint8Array(await p.img!.arrayBuffer());
      const emb = p.img!.type === "image/png" ? await doc.embedPng(bytes) : await doc.embedJpg(bytes);
      const [pw, ph] = pageSize(p.w, p.h);
      const page = doc.addPage([pw, ph]);
      const m = sizeSel.value === "fit" ? 0 : 24;
      const s = Math.min((pw - 2 * m) / p.w, (ph - 2 * m) / p.h);
      page.drawImage(emb, { x: (pw - p.w * s) / 2, y: (ph - p.h * s) / 2, width: p.w * s, height: p.h * s });
      if (p.rot) page.setRotation(degrees(p.rot));
    }
  }
  doc.setProducer("Utility Helpers PDF tools (made in the browser)");
  doc.setCreator("utility-helpers.netlify.app");
  return doc.save({ useObjectStreams: false });
}

/** "1-3, 5, 8-" -> zero-based indices, or an error message. */
export function parseRange(text: string, n: number): number[] | string {
  const idx: number[] = [];
  const parts = text.replace(/\s*[-–]\s*/g, "-").split(/[,\s]+/).filter(Boolean);
  for (const part of parts) {
    const m = part.match(/^(\d+)?(?:(-)(\d+)?)?$/);
    if (!m || (!m[1] && !m[3])) return `"${part}" is not a page number or range`;
    const a = m[1] ? Number(m[1]) : 1;
    const b = m[2] ? (m[3] ? Number(m[3]) : n) : a;
    if (a < 1 || b > n || a > b) return `${part} is outside pages 1-${n}`;
    for (let i = a; i <= b; i++) idx.push(i - 1);
  }
  return idx.length ? idx : "Type the pages you want, for example 1-3, 5";
}

const stem = () => baseName(pages[0]?.name ?? "document");

function pdfRow(bytes: Uint8Array, name: string, n: number) {
  const blob = new Blob([bytes as BlobPart], { type: "application/pdf" });
  out.append(resultRow({ text: `${name} · ${plural(n, "page")} · ${fmtBytes(blob.size)}`, blob, name }));
}

function busy(on: boolean) { buttons.forEach((b) => { b.disabled = on; }); }

async function task(label: string, fn: () => Promise<void>) {
  if (!pages.length) { status(st, "Add a PDF or a photo first (or press Try a sample).", "error"); return; }
  busy(true);
  out.replaceChildren();
  status(st, `${label}…`);
  try { await fn(); }
  catch (e) { status(st, `Something went wrong: ${(e as Error).message}`, "error"); }
  finally { busy(false); }
}

byId("pdf-build").addEventListener("click", () => task("Making the PDF", async () => {
  const multi = new Set(pages.map((p) => p.file)).size > 1;
  const name = `${stem()}${multi ? "-combined" : "-edited"}.pdf`;
  pdfRow(await buildPdf(pages), name, pages.length);
  status(st, "Your PDF is ready.", "ok");
}));

byId("pdf-extract").addEventListener("click", () => task("Extracting", async () => {
  const r = parseRange(rangeIn.value, pages.length);
  if (typeof r === "string") { status(st, r, "error"); return; }
  const label = rangeIn.value.replace(/\s+/g, "").replace(/,/g, "_");
  pdfRow(await buildPdf(r.map((i) => pages[i])), `${stem()}-pages-${label}.pdf`, r.length);
  status(st, "Extracted.", "ok");
}));

byId("pdf-split").addEventListener("click", () => task("Splitting", async () => {
  for (const [i, p] of pages.entries()) {
    status(st, `Splitting… ${i + 1} of ${pages.length}`);
    pdfRow(await buildPdf([p]), `${stem()}-page-${i + 1}.pdf`, 1);
  }
  status(st, `Split into ${plural(pages.length, "file")}.`, "ok");
}));

async function pageToCanvas(p: Page, dpi: number): Promise<HTMLCanvasElement> {
  if (p.kind === "img") {
    const bmp = await createImageBitmap(p.img!);
    const swap = p.rot % 180 !== 0;
    const c = document.createElement("canvas");
    c.width = swap ? bmp.height : bmp.width;
    c.height = swap ? bmp.width : bmp.height;
    const g = c.getContext("2d")!;
    g.fillStyle = "#fff";
    g.fillRect(0, 0, c.width, c.height);
    g.translate(c.width / 2, c.height / 2);
    g.rotate((p.rot * Math.PI) / 180);
    g.drawImage(bmp, -bmp.width / 2, -bmp.height / 2);
    bmp.close();
    return c;
  }
  const doc = await jsDoc(p.src!);
  const pg = await doc.getPage(p.index + 1);
  const vp = pg.getViewport({ scale: dpi / 72, rotation: (pg.rotate + p.rot) % 360 });
  const c = document.createElement("canvas");
  c.width = Math.round(vp.width);
  c.height = Math.round(vp.height);
  await pg.render({ canvas: c, viewport: vp }).promise;
  return c;
}

byId("pdf-jpg").addEventListener("click", () => task("Converting to JPG", async () => {
  let idx = pages.map((_, i) => i);
  if (rangeIn.value.trim()) {
    const r = parseRange(rangeIn.value, pages.length);
    if (typeof r === "string") { status(st, r, "error"); return; }
    idx = r;
  }
  const dpi = Number(dpiSel.value) || 150;
  for (const [k, i] of idx.entries()) {
    status(st, `Converting… ${k + 1} of ${idx.length}`);
    const c = await pageToCanvas(pages[i], dpi);
    const blob = await canvasToBlob(c, "image/jpeg", 0.9);
    const name = `${stem()}-page-${i + 1}.jpg`;
    out.append(resultRow({ text: `${name} · ${c.width} × ${c.height} · ${fmtBytes(blob.size)}`, blob, name, thumb: blob }));
  }
  status(st, `${plural(idx.length, "image")} ready.`, "ok");
}));

byId("pdf-clear").addEventListener("click", () => {
  pages = [];
  [...thumbs.keys()].forEach(dropThumb);
  fileCount = 0;
  out.replaceChildren();
  status(st, "");
  render();
});

// ---- sample: two small PDFs made right here with pdf-lib ----------------------
async function samplePdf(name: string, labels: string[], landscape: boolean): Promise<File> {
  const { PDFDocument, StandardFonts, rgb } = await pdfLib();
  const d = await PDFDocument.create();
  const font = await d.embedFont(StandardFonts.HelveticaBold);
  for (const label of labels) {
    const [w, h] = landscape ? [PAGE.a4[1], PAGE.a4[0]] : [PAGE.a4[0], PAGE.a4[1]];
    const page = d.addPage([w, h]);
    page.drawRectangle({ x: 0, y: h - 90, width: w, height: 90, color: rgb(0.96, 0.62, 0.04) });
    page.drawText(label, { x: 48, y: h / 2, size: 44, font, color: rgb(0.1, 0.1, 0.12) });
  }
  return new File([(await d.save()) as BlobPart], name, { type: "application/pdf" });
}

byId("pdf-sample").addEventListener("click", async () => {
  busy(true);
  try {
    const files = [await samplePdf("sample-a.pdf", ["Sample A, page 1", "Sample A, page 2"], false),
      await samplePdf("sample-b.pdf", ["Sample B, page 1"], true)];
    busy(false);
    await addFiles(files);
  } finally { busy(false); }
});

filePicker(byId("pdf-drop"), byId<HTMLInputElement>("pdf-file"), addFiles, "pdf-tools");
render();
