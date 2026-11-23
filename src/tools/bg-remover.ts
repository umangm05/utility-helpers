// Background remover. The model (U²-Net u2netp, Apache-2.0) and the runtime
// (onnxruntime-web WebGL backend: pure JavaScript, MIT) are loaded from THIS site the first time the user presses
// "Remove background"; the service worker keeps them for offline use. The photo
// is decoded, segmented and composited on canvases in this tab. Nothing is uploaded.
// Not the WebAssembly backend: its binary statically links MPL-2.0 (Eigen) code, and this
// site ships no copyleft code to browsers (SPEC; same rule as D-UH-NO-COPYLEFT-HEIC).
import { byId, baseName, decodeImage, canvasToBlob, download, status, filePicker } from "./common";
import { play, wireToggles } from "./sfx";
import type { InferenceSession } from "onnxruntime-web";

const MODEL_URL = "/models/u2netp-320.onnx";   // built by scripts/make_bg_model.py
const SIZE = 320;                       // u2netp input resolution
const MAX_SIDE = 4000;                  // cap the output so phones do not run out of memory
const MEAN = [0.485, 0.456, 0.406];
const STD = [0.229, 0.224, 0.225];

const fileIn = byId<HTMLInputElement>("bg-file");
const inInfo = byId("bg-in");
const st = byId("bg-status");
const go = byId<HTMLButtonElement>("bg-go");
const dl = byId<HTMLButtonElement>("bg-dl");
const fill = byId<HTMLSelectElement>("bg-fill");
const color = byId<HTMLInputElement>("bg-color");
const prog = byId("bg-prog");
const bar = byId("bg-bar");
const before = byId<HTMLCanvasElement>("bg-before");
const after = byId<HTMLCanvasElement>("bg-after");

let src: { name: string; bmp: ImageBitmap } | null = null;
let mask: HTMLCanvasElement | null = null;     // alpha mask at the output size
let session: Promise<InferenceSession> | null = null;

function progress(p: number | null) {
  prog.hidden = p === null;
  bar.style.width = `${Math.round((p ?? 0) * 100)}%`;
}

async function fetchModel(): Promise<Uint8Array> {
  const r = await fetch(MODEL_URL);
  if (!r.ok || !r.body) throw new Error(`model download failed (${r.status})`);
  const total = Number(r.headers.get("content-length")) || 4_561_450;
  const reader = r.body.getReader();
  const parts: Uint8Array[] = [];
  let got = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    parts.push(value);
    got += value.length;
    progress(Math.min(0.95, got / total));
    status(st, `Downloading the AI model… ${Math.round((got / 1024 / 1024) * 10) / 10} MB (first time only)`);
  }
  const buf = new Uint8Array(got);
  let o = 0;
  for (const p of parts) { buf.set(p, o); o += p.length; }
  return buf;
}

function loadSession(): Promise<InferenceSession> {
  session ??= (async () => {
    const ort = await import("onnxruntime-web/webgl");
    const model = await fetchModel();
    status(st, "Starting the AI model…");
    return ort.InferenceSession.create(model, { executionProviders: ["webgl"] });
  })().catch((e) => { session = null; throw e; });
  return session;
}

async function load(files: File[]) {
  const f = files.find((x) => x.type.startsWith("image/") || /\.(jpe?g|png|webp|avif|bmp)$/i.test(x.name));
  if (!f) { status(inInfo, "That is not an image this tool can open.", "error"); return; }
  try {
    const bmp = await decodeImage(f);
    src?.bmp.close();
    src = { name: f.name, bmp };
    mask = null;
    dl.disabled = true;
    go.disabled = false;
    const k = Math.min(1, MAX_SIDE / Math.max(bmp.width, bmp.height));
    paintBefore(Math.round(bmp.width * k), Math.round(bmp.height * k));
    byId("bg-views").hidden = false;
    after.width = 1; after.height = 1;
    status(inInfo, `${f.name} · ${bmp.width} × ${bmp.height}`);
    status(st, "");
  } catch {
    status(inInfo, `Could not open ${f.name}. iPhone HEIC photos: convert them with HEIC to JPG first.`, "error");
  }
}

function paintBefore(w: number, h: number) {
  before.width = w; before.height = h;
  before.getContext("2d")!.drawImage(src!.bmp, 0, 0, w, h);
}

/** RGB float tensor (1,3,320,320), normalised the way U²-Net was trained (rembg's preprocessing). */
function toTensorData(img: CanvasImageSource): Float32Array {
  const c = document.createElement("canvas");
  c.width = SIZE; c.height = SIZE;
  const g = c.getContext("2d", { willReadFrequently: true })!;
  g.imageSmoothingQuality = "high";
  g.drawImage(img, 0, 0, SIZE, SIZE);
  const px = g.getImageData(0, 0, SIZE, SIZE).data;
  let max = 1;
  for (let i = 0; i < px.length; i += 4) max = Math.max(max, px[i], px[i + 1], px[i + 2]);
  const out = new Float32Array(3 * SIZE * SIZE);
  const plane = SIZE * SIZE;
  for (let i = 0, p = 0; i < px.length; i += 4, p++) {
    for (let ch = 0; ch < 3; ch++) out[ch * plane + p] = (px[i + ch] / max - MEAN[ch]) / STD[ch];
  }
  return out;
}

/** 320x320 saliency map -> min-max normalised alpha mask scaled to w x h. */
function toMask(pred: Float32Array, w: number, h: number): HTMLCanvasElement {
  let lo = Infinity, hi = -Infinity;
  for (const v of pred) { if (v < lo) lo = v; if (v > hi) hi = v; }
  const span = hi - lo || 1;
  const small = document.createElement("canvas");
  small.width = SIZE; small.height = SIZE;
  const sg = small.getContext("2d")!;
  const id = sg.createImageData(SIZE, SIZE);
  for (let p = 0; p < SIZE * SIZE; p++) id.data[p * 4 + 3] = Math.round(((pred[p] - lo) / span) * 255);
  sg.putImageData(id, 0, 0);
  const big = document.createElement("canvas");
  big.width = w; big.height = h;
  const bg = big.getContext("2d")!;
  bg.imageSmoothingEnabled = true;
  bg.imageSmoothingQuality = "high";
  bg.drawImage(small, 0, 0, w, h);
  return big;
}

function composite() {
  if (!src || !mask) return;
  const w = before.width, h = before.height;
  after.width = w; after.height = h;
  const g = after.getContext("2d")!;
  g.clearRect(0, 0, w, h);
  g.drawImage(before, 0, 0);
  g.globalCompositeOperation = "destination-in";
  g.drawImage(mask, 0, 0);
  g.globalCompositeOperation = "destination-over";
  const bgc = fill.value === "custom" ? color.value : fill.value;
  if (bgc) { g.fillStyle = bgc; g.fillRect(0, 0, w, h); }
  g.globalCompositeOperation = "source-over";
  after.classList.toggle("checker", !bgc);
}

/** Alpha at the centre and the mean alpha of the four corners (used by the known-answer check). */
function measure() {
  const g = after.getContext("2d", { willReadFrequently: true })!;
  const a = (x: number, y: number) => g.getImageData(x, y, 1, 1).data[3];
  const w = after.width, h = after.height;
  const corners = [a(2, 2), a(w - 3, 2), a(2, h - 3), a(w - 3, h - 3)];
  after.dataset.centerAlpha = String(a(w >> 1, h >> 1));
  after.dataset.cornerAlpha = String(Math.round(corners.reduce((s, v) => s + v, 0) / 4));
}

/** "none" (no WebGL), "software" (emulated on the CPU: works, but slowly) or "gpu". */
const gl = (() => {
  try {
    const c = document.createElement("canvas");
    const g = (c.getContext("webgl2") || c.getContext("webgl")) as WebGLRenderingContext | null;
    if (!g) return "none";
    const ext = g.getExtension("WEBGL_debug_renderer_info");
    const r = String(g.getParameter(ext ? ext.UNMASKED_RENDERER_WEBGL : g.RENDERER) || "");
    g.getExtension("WEBGL_lose_context")?.loseContext();
    return /swiftshader|llvmpipe|software|basic render/i.test(r) ? "software" : "gpu";
  } catch { return "none"; }
})();

async function run() {
  if (!src) { status(st, "Choose a photo first (or press Try a sample).", "error"); return; }
  if (gl === "none") {
    status(st, "This browser has graphics acceleration (WebGL) turned off, which the AI model needs. Try Chrome, Edge, Safari or Firefox with hardware acceleration on.", "error");
    return;
  }
  go.disabled = true;
  dl.disabled = true;
  const t0 = performance.now();
  try {
    progress(0.02);
    const sess = await loadSession();
    const ort = await import("onnxruntime-web/webgl");
    status(st, gl === "software"
      ? "Finding the subject… This device has no graphics acceleration, so this can take up to a minute."
      : "Finding the subject…");
    progress(0.97);
    await new Promise((r) => setTimeout(r, 30));   // let the status paint before the busy inference
    const input = new ort.Tensor("float32", toTensorData(before), [1, 3, SIZE, SIZE]);
    const res = await sess.run({ [sess.inputNames[0]]: input });
    const pred = res[sess.outputNames[0]].data as Float32Array;
    mask = toMask(pred, before.width, before.height);
    composite();
    measure();
    progress(null);
    const secs = ((performance.now() - t0) / 1000).toFixed(1);
    status(st, `Background removed · ${after.width} × ${after.height} · ${secs} s`, "ok");
    dl.disabled = false;
    play("success");
  } catch (e) {
    progress(null);
    status(st, `Could not remove the background: ${(e as Error).message}. Check your connection the first time (the model has to download once).`, "error");
    play("error");
  } finally {
    go.disabled = !src;
  }
}

go.addEventListener("click", run);
fill.addEventListener("change", () => { byId("bg-color-wrap").hidden = fill.value !== "custom"; composite(); });
color.addEventListener("input", composite);
dl.addEventListener("click", async () => {
  if (!src || !mask) return;
  const jpg = !!fill.value;
  const blob = await canvasToBlob(after, jpg ? "image/jpeg" : "image/png", 0.92);
  download(blob, `${baseName(src.name)}-no-bg.${jpg ? "jpg" : "png"}`);
});

/** Sample: an orange ball with a shadow on a light, textured studio backdrop (drawn locally). */
async function sample(): Promise<File> {
  const c = document.createElement("canvas");
  c.width = 1200; c.height = 900;
  const g = c.getContext("2d")!;
  const sky = g.createLinearGradient(0, 0, 0, 900);
  sky.addColorStop(0, "#e8eef5");
  sky.addColorStop(1, "#c9d3de");
  g.fillStyle = sky;
  g.fillRect(0, 0, 1200, 900);
  g.fillStyle = "rgba(0,0,0,.18)";
  g.beginPath(); g.ellipse(600, 760, 230, 40, 0, 0, Math.PI * 2); g.fill();
  const ball = g.createRadialGradient(540, 360, 40, 600, 450, 280);
  ball.addColorStop(0, "#ffd08a");
  ball.addColorStop(0.5, "#f97316");
  ball.addColorStop(1, "#9a3412");
  g.fillStyle = ball;
  g.beginPath(); g.arc(600, 450, 280, 0, Math.PI * 2); g.fill();
  const b = await canvasToBlob(c, "image/jpeg", 0.92);
  return new File([b], "sample-ball.jpg", { type: "image/jpeg" });
}
byId("bg-sample").addEventListener("click", async () => { status(inInfo, "Making a sample photo…"); await load([await sample()]); });
filePicker(byId("bg-drop"), fileIn, load, "background-remover");
wireToggles();
