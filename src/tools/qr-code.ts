// QR code maker + scanner. qrcode-generator (MIT) and jsQR (Apache-2.0) are
// lazy-loaded; the camera stream and pictures are decoded in this tab only.
import { byId, decodeImage, drawToCanvas, canvasToBlob, status, download, takeHandoff, fetchSample } from "./common";

type QrFactory = typeof import("qrcode-generator").default;
type QrCode = ReturnType<QrFactory>;
type JsQr = typeof import("jsqr").default;

let qrP: Promise<QrFactory> | null = null;
const qrLib = () => (qrP ??= import("qrcode-generator").then((m) => {
  const f = m.default;
  // UTF-8 so ₹, Hindi and emoji encode correctly (the library default is Latin-1).
  f.stringToBytes = (s: string) => Array.from(new TextEncoder().encode(s));
  return f;
}));
let jsQrP: Promise<JsQr> | null = null;
const jsQr = () => (jsQrP ??= import("jsqr").then((m) => m.default));

// ---- tabs ----------------------------------------------------------------
const tabs = [byId<HTMLButtonElement>("qr-tab-make"), byId<HTMLButtonElement>("qr-tab-scan")];
function selectTab(i: number) {
  tabs.forEach((t, k) => {
    const on = k === i;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
    byId(t.getAttribute("aria-controls")!).hidden = !on;
  });
  if (i === 0) stopCamera();
}
tabs.forEach((t, i) => {
  t.addEventListener("click", () => selectTab(i));
  t.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); const j = (i + 1) % 2; selectTab(j); tabs[j].focus(); }
  });
});

// ---- make ------------------------------------------------------------------
const kind = byId<HTMLSelectElement>("qr-kind");
const ecc = byId<HTMLSelectElement>("qr-ecc");
const pxSel = byId<HTMLSelectElement>("qr-px");
const canvas = byId<HTMLCanvasElement>("qr-canvas");
const meta = byId("qr-meta");
const check = byId("qr-check");
const btnPng = byId<HTMLButtonElement>("qr-png");
const btnSvg = byId<HTMLButtonElement>("qr-svg");
const btnVerify = byId<HTMLButtonElement>("qr-verify");
const val = (id: string) => byId<HTMLInputElement>(id).value.trim();
let current: { qr: QrCode; text: string } | null = null;
const QUIET = 4;   // modules of white border, as the standard asks

const wifiEsc = (s: string) => s.replace(/([\\;,:"])/g, "\\$1");

/** The string the QR code will contain, or an error message to show instead. */
export function payload(): { text: string } | { error: string } | null {
  if (kind.value === "wifi") {
    const ssid = byId<HTMLInputElement>("qr-ssid").value;
    if (!ssid) return null;
    const sec = byId<HTMLSelectElement>("qr-sec").value;
    const pass = byId<HTMLInputElement>("qr-pass").value;
    return { text: `WIFI:T:${sec};S:${wifiEsc(ssid)};${sec === "nopass" ? "" : `P:${wifiEsc(pass)};`};` };
  }
  if (kind.value === "upi") {
    const vpa = val("qr-vpa");
    if (!vpa) return null;
    if (!/^[\w.-]{2,256}@[a-z][a-z0-9.-]{1,63}$/i.test(vpa)) return { error: "That does not look like a UPI ID (name@bank)." };
    // NPCI deep-link format. The UPI ID is validated above and kept literal (apps expect a raw "@").
    const parts = [`pa=${vpa}`];
    if (val("qr-payee")) parts.push(`pn=${encodeURIComponent(val("qr-payee"))}`);
    const amt = Number(val("qr-amt"));
    if (amt > 0) parts.push(`am=${amt.toFixed(2)}`);
    parts.push("cu=INR");
    if (val("qr-note")) parts.push(`tn=${encodeURIComponent(val("qr-note"))}`);
    return { text: `upi://pay?${parts.join("&")}` };
  }
  const t = byId<HTMLTextAreaElement>("qr-text").value;
  return t.trim() ? { text: t } : null;
}

function paint(qr: QrCode, target: HTMLCanvasElement, size: number) {
  const n = qr.getModuleCount();
  const total = n + QUIET * 2;
  const cell = size / total;
  target.width = size;
  target.height = size;
  const g = target.getContext("2d")!;
  g.fillStyle = "#fff";
  g.fillRect(0, 0, size, size);
  g.fillStyle = "#000";
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) {
    if (qr.isDark(r, c)) {
      // Snap to whole pixels so neighbouring modules never leave hairline gaps.
      const x0 = Math.round((c + QUIET) * cell), y0 = Math.round((r + QUIET) * cell);
      g.fillRect(x0, y0, Math.round((c + QUIET + 1) * cell) - x0, Math.round((r + QUIET + 1) * cell) - y0);
    }
  }
}

function svgOf(qr: QrCode): string {
  const n = qr.getModuleCount();
  const total = n + QUIET * 2;
  let d = "";
  for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (qr.isDark(r, c)) d += `M${c + QUIET} ${r + QUIET}h1v1h-1z`;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${total} ${total}" shape-rendering="crispEdges">`
    + `<rect width="${total}" height="${total}" fill="#fff"/><path d="${d}" fill="#000"/></svg>`;
}

async function make() {
  const p = payload();
  check.textContent = "";
  [btnPng, btnSvg, btnVerify].forEach((b) => { b.disabled = true; });
  current = null;
  if (!p || "error" in p) {
    canvas.getContext("2d")!.clearRect(0, 0, canvas.width, canvas.height);
    canvas.setAttribute("aria-label", "QR code preview (empty)");
    status(meta, p ? p.error : "Type something to make a code.", p ? "error" : "info");
    return;
  }
  const qrcode = await qrLib();
  const qr = qrcode(0, ecc.value as "L" | "M" | "Q" | "H");
  try {
    qr.addData(p.text, "Byte");
    qr.make();
  } catch {
    status(meta, "Too much text for one QR code. Shorten it or lower the error correction.", "error");
    return;
  }
  current = { qr, text: p.text };
  paint(qr, canvas, 232 * Math.min(2, window.devicePixelRatio || 1));
  canvas.setAttribute("aria-label", `QR code for ${p.text.slice(0, 80)}`);
  const n = qr.getModuleCount();
  status(meta, `Version ${(n - 17) / 4} · ${n} × ${n} modules · error correction ${ecc.value}`, "ok");
  [btnPng, btnSvg, btnVerify].forEach((b) => { b.disabled = false; });
}

let t: number | undefined;
const later = () => { clearTimeout(t); t = window.setTimeout(make, 120); };
document.querySelectorAll("#qr-make input, #qr-make textarea").forEach((el) => el.addEventListener("input", later));
document.querySelectorAll("#qr-make select").forEach((el) => el.addEventListener("change", make));
kind.addEventListener("change", () => {
  document.querySelectorAll<HTMLElement>(".qr-fields").forEach((f) => { f.hidden = f.dataset.kind !== kind.value; });
});

async function pngBlob(): Promise<Blob> {
  const c = document.createElement("canvas");
  paint(current!.qr, c, Number(pxSel.value) || 1024);
  return canvasToBlob(c, "image/png");
}
btnPng.addEventListener("click", async () => { if (current) download(await pngBlob(), "qr-code.png"); });
btnSvg.addEventListener("click", () => {
  if (current) download(new Blob([svgOf(current.qr)], { type: "image/svg+xml" }), "qr-code.svg");
});

// "Check it scans": decode our own PNG with the same reader the scanner uses.
btnVerify.addEventListener("click", async () => {
  if (!current) return;
  status(check, "Checking…");
  const c = document.createElement("canvas");
  paint(current.qr, c, 512);
  const got = await readCanvas(c);
  if (got === current.text) status(check, `Scans OK: ${got}`, "ok");
  else status(check, got === null ? "Could not read it back. Try a higher error correction." : `Reads as "${got}", not what you typed.`, "error");
});

// ---- scan ------------------------------------------------------------------
const video = byId<HTMLVideoElement>("qr-video");
const camBtn = byId<HTMLButtonElement>("qr-cam");
const scanSt = byId("qr-scan-status");
const resultBox = byId("qr-result-box");
const result = byId<HTMLTextAreaElement>("qr-result");
const resultActs = byId("qr-result-acts");
let stream: MediaStream | null = null;
let raf = 0;

async function readCanvas(c: HTMLCanvasElement, both = false): Promise<string | null> {
  const decode = await jsQr();
  const d = c.getContext("2d", { willReadFrequently: true })!.getImageData(0, 0, c.width, c.height);
  const hit = decode(d.data, d.width, d.height, { inversionAttempts: both ? "attemptBoth" : "dontInvert" });
  return hit ? hit.data : null;
}

function show(text: string) {
  resultBox.hidden = false;
  result.value = text;
  resultActs.replaceChildren();
  const copy = document.createElement("button");
  copy.type = "button";
  copy.textContent = "Copy";
  copy.addEventListener("click", () => navigator.clipboard?.writeText(text).then(() => status(scanSt, "Copied.", "ok")));
  resultActs.append(copy);
  if (/^(https?:|upi:|mailto:|tel:)/i.test(text.trim())) {
    const a = document.createElement("a");
    a.href = text.trim();
    a.rel = "noopener noreferrer nofollow";
    a.target = "_blank";
    a.className = "btn";
    a.textContent = /^upi:/i.test(text) ? "Pay with a UPI app" : "Open link";
    resultActs.append(a);
  }
  status(scanSt, "Found a QR code.", "ok");
}

function stopCamera() {
  cancelAnimationFrame(raf);
  stream?.getTracks().forEach((tr) => tr.stop());
  stream = null;
  video.hidden = true;
  camBtn.textContent = "Scan with camera";
}

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) { status(scanSt, "This browser has no camera access. Use Read from a picture.", "error"); return; }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
  } catch {
    status(scanSt, "Camera permission was blocked. Allow it in the browser settings, or use Read from a picture.", "error");
    return;
  }
  video.srcObject = stream;
  video.hidden = false;
  await video.play();
  camBtn.textContent = "Turn camera off";
  status(scanSt, "Looking for a QR code…");
  const c = document.createElement("canvas");
  const g = c.getContext("2d", { willReadFrequently: true })!;
  const decode = await jsQr();
  let last = 0;
  const tick = (now: number) => {
    if (!stream) return;
    raf = requestAnimationFrame(tick);
    if (now - last < 150 || video.readyState < 2) return;   // ~6 scans a second is plenty
    last = now;
    const k = Math.min(1, 720 / Math.max(video.videoWidth, video.videoHeight));
    c.width = Math.round(video.videoWidth * k);
    c.height = Math.round(video.videoHeight * k);
    g.drawImage(video, 0, 0, c.width, c.height);
    const d = g.getImageData(0, 0, c.width, c.height);
    const hit = decode(d.data, d.width, d.height, { inversionAttempts: "dontInvert" });
    if (hit?.data) { stopCamera(); show(hit.data); }
  };
  raf = requestAnimationFrame(tick);
}
camBtn.addEventListener("click", () => (stream ? stopCamera() : startCamera()));
addEventListener("pagehide", stopCamera);

const imgIn = byId<HTMLInputElement>("qr-img");
// Try a sample: read the bundled QR code picture (it opens this site's home page).
byId("qr-sample").addEventListener("click", async () => {
  status(scanSt, "Loading the sample…");
  try { await scanFile(await fetchSample("qr")); }
  catch (e) { status(scanSt, (e as Error).message, "error"); }
});
imgIn.addEventListener("change", async () => {
  const f = imgIn.files?.[0];
  imgIn.value = "";
  if (f) await scanFile(f);
});

export async function scanFile(f: File) {
  status(scanSt, "Reading the picture…");
  try {
    const bmp = await decodeImage(f);
    for (const side of [1600, 800, 400]) {
      const k = Math.min(1, side / Math.max(bmp.width, bmp.height));
      const got = await readCanvas(drawToCanvas(bmp, bmp.width * k, bmp.height * k), true);
      if (got !== null) { bmp.close(); show(got); return; }
    }
    bmp.close();
    status(scanSt, "No QR code found in that picture. Crop closer to the code and try again.", "error");
  } catch {
    status(scanSt, "That file is not a picture this browser can open.", "error");
  }
}

// Picture handed over from the home drop zone -> open the Scan tab with it.
takeHandoff("qr-code-generator").then((files) => {
  if (files[0]) { selectTab(1); scanFile(files[0]); }
});
// Text handed over from the home drop zone is filled into #qr-text by ui.ts.
if (byId<HTMLTextAreaElement>("qr-text").value.trim()) make();
