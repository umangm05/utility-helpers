// Test helper for scripts/test_tools.py (file tools). Uses pdf-lib from node_modules.
//   node scripts/pdf_fixture.mjs make <dir>     -> <dir>/a.pdf (2 pages: 200pt, 300pt squares)
//                                                  <dir>/b.pdf (1 page: 400pt square)
//   node scripts/pdf_fixture.mjs inspect <file> -> {"pages": n, "sizes": [[w,h],...], "rotations": [...]}
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { PDFDocument, StandardFonts } from "pdf-lib";

const [cmd, arg] = process.argv.slice(2);

async function pdf(sizes, label) {
  const d = await PDFDocument.create();
  const font = await d.embedFont(StandardFonts.Helvetica);
  sizes.forEach((s, i) => d.addPage([s, s]).drawText(`${label}${i + 1}`, { x: 20, y: 20, size: 24, font }));
  return d.save();
}

if (cmd === "make") {
  writeFileSync(join(arg, "a.pdf"), await pdf([200, 300], "A"));
  writeFileSync(join(arg, "b.pdf"), await pdf([400], "B"));
  console.log(JSON.stringify({ ok: true }));
} else if (cmd === "inspect") {
  const d = await PDFDocument.load(readFileSync(arg));
  const pages = d.getPages();
  console.log(JSON.stringify({
    pages: pages.length,
    sizes: pages.map((p) => [Math.round(p.getWidth() * 100) / 100, Math.round(p.getHeight() * 100) / 100]),
    rotations: pages.map((p) => p.getRotation().angle),
  }));
} else {
  console.error("usage: pdf_fixture.mjs make <dir> | inspect <file>");
  process.exit(2);
}
