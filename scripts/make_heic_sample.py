#!/usr/bin/env python3
"""Build public/samples/sample.heic: a tiny, self-made HEIC used by the HEIC -> JPG
tool's "Try a sample" button and by its known-answer test.

Why self-made: no licence questions about a third-party photo, and the known
answer (640 x 480) is fixed by construction.

How: ffmpeg + libx265 encode ONE frame of the lavfi `testsrc2` pattern into an
MP4, then this script lifts the HEVC config record (hvcC) and the frame out of
the MP4 and wraps them in a minimal HEIF container (ftyp / meta[hdlr pitm iinf
iprp iloc] / mdat) -- the same item layout a phone writes for a single image.

Usage:  python3 scripts/make_heic_sample.py [--out public/samples/sample.heic]
Needs:  ffmpeg built with libx265 (only to regenerate; the output is committed).
"""

from __future__ import annotations

import argparse
import struct
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W, H = 640, 480


def box(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + kind + payload


def fullbox(kind: bytes, version: int, flags: int, payload: bytes) -> bytes:
    return box(kind, struct.pack(">I", (version << 24) | flags) + payload)


def walk(buf: bytes, start: int, end: int):
    """Yield (type, payload_start, payload_end) for the boxes in buf[start:end]."""
    i = start
    while i + 8 <= end:
        size, kind = struct.unpack(">I4s", buf[i:i + 8])
        hdr = 8
        if size == 1:
            size = struct.unpack(">Q", buf[i + 8:i + 16])[0]
            hdr = 16
        elif size == 0:
            size = end - i
        yield kind, i + hdr, i + size
        i += size


def find(buf: bytes, path: list[bytes], start: int = 0, end: int | None = None):
    end = len(buf) if end is None else end
    for kind, s, e in walk(buf, start, end):
        if kind == path[0]:
            return (s, e) if len(path) == 1 else find(buf, path[1:], s, e)
    raise KeyError(b"/".join(path))


def extract_hevc(mp4: bytes) -> tuple[bytes, bytes]:
    stbl = find(mp4, [b"moov", b"trak", b"mdia", b"minf", b"stbl"])
    s, e = find(mp4, [b"stsd"], *stbl)
    # stsd: fullbox(4) + entry_count(4), then the hvc1 sample entry: 8 header + 78 visual fields
    entry_s = s + 8
    _, kind = struct.unpack(">I4s", mp4[entry_s:entry_s + 8])
    assert kind in (b"hvc1", b"hev1"), kind
    entry_size = struct.unpack(">I", mp4[entry_s:entry_s + 4])[0]
    hs, he = find(mp4, [b"hvcC"], entry_s + 8 + 78, entry_s + entry_size)
    hvcc = mp4[hs:he]
    zs, _ = find(mp4, [b"stsz"], *stbl)
    sample_size = struct.unpack(">I", mp4[zs + 4:zs + 8])[0] or struct.unpack(">I", mp4[zs + 12:zs + 16])[0]
    cs, _ = find(mp4, [b"stco"], *stbl)
    offset = struct.unpack(">I", mp4[cs + 8:cs + 12])[0]
    return hvcc, mp4[offset:offset + sample_size]


def heif(hvcc: bytes, data: bytes) -> bytes:
    ftyp = box(b"ftyp", b"heic" + struct.pack(">I", 0) + b"mif1heic")
    hdlr = fullbox(b"hdlr", 0, 0, struct.pack(">I", 0) + b"pict" + b"\0" * 12 + b"\0")
    pitm = fullbox(b"pitm", 0, 0, struct.pack(">H", 1))
    infe = fullbox(b"infe", 2, 0, struct.pack(">HH", 1, 0) + b"hvc1" + b"\0")
    iinf = fullbox(b"iinf", 0, 0, struct.pack(">H", 1) + infe)
    ispe = fullbox(b"ispe", 0, 0, struct.pack(">II", W, H))
    ipco = box(b"ipco", box(b"hvcC", hvcc) + ispe)
    # item 1 -> property 1 (hvcC, essential) and property 2 (ispe)
    ipma = fullbox(b"ipma", 0, 0, struct.pack(">IHB", 1, 1, 2) + bytes([0x81, 0x02]))
    iprp = box(b"iprp", ipco + ipma)

    def meta_with(offset: int) -> bytes:
        iloc = fullbox(b"iloc", 0, 0, bytes([0x44, 0x00]) + struct.pack(">HHHHII", 1, 1, 0, 1, offset, len(data)))
        return fullbox(b"meta", 0, 0, hdlr + pitm + iinf + iprp + iloc)

    offset = len(ftyp) + len(meta_with(0)) + 8   # +8 = mdat header
    return ftyp + meta_with(offset) + box(b"mdat", data)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "public" / "samples" / "sample.heic"))
    out = Path(ap.parse_args().out)
    with tempfile.TemporaryDirectory() as td:
        mp4 = Path(td) / "one.mp4"
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                        "-i", f"testsrc2=size={W}x{H}:rate=1", "-frames:v", "1", "-c:v", "libx265",
                        "-x265-params", "log-level=error:keyint=1", "-pix_fmt", "yuv420p",
                        "-tag:v", "hvc1", str(mp4)], check=True)
        hvcc, data = extract_hevc(mp4.read_bytes())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(heif(hvcc, data))
    print(f"wrote {out} ({out.stat().st_size} bytes, {W}x{H})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
