#!/usr/bin/env python3
"""Prepare the background-remover model for ONNX Runtime Web's WebGL backend.

Input : u2netp.onnx (U^2-Net small, Apache-2.0, https://github.com/xuebinqin/U-2-Net; the ONNX export
        redistributed by rembg: https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx,
        sha256 309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8)
Output: public/models/u2netp-320.onnx

Why: the site runs the model with onnxruntime-web's WebGL backend, which is pure JavaScript (MIT). The
WebAssembly backend was rejected because its binary statically links MPL-2.0 code (Eigen), and the
project ships no copyleft code to browsers. The WebGL backend cannot run two things in the original
export, so this script rewrites them WITHOUT changing the maths:
  1. Fix the input to 1x3x320x320 and constant-fold the dynamic Shape/Gather/Slice/Concat chains
     that only compute Resize target sizes (ONNX Runtime "basic" optimisation = standard ONNX ops only).
  2. MaxPool ceil_mode=1 -> ceil_mode=0 with one extra end-pad where ceil and floor differ. MaxPool
     padding never wins a max, so the output is identical.
It then checks the rewritten model against the original on CPU (max |diff| must stay below 1e-4).

Dev-only tool (not part of the build). Needs: pip install onnx onnxruntime numpy
Usage: python3 scripts/make_bg_model.py path/to/u2netp.onnx
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnx import helper, shape_inference

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "models" / "u2netp-320.onnx"
SHA_IN = "309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8"
SIZE = 320


def main(src: str) -> int:
    raw = Path(src).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA_IN:
        print("input is not the expected u2netp.onnx (sha256 mismatch)")
        return 1
    m = onnx.load_from_string(raw)
    inp = m.graph.input[0]
    for d, v in zip(inp.type.tensor_type.shape.dim, (1, 3, SIZE, SIZE)):
        d.ClearField("dim_param")
        d.dim_value = v
    tmp = Path(tempfile.mkdtemp()) / "fixed.onnx"
    onnx.save(m, tmp)

    # 1. constant folding with standard ops only
    folded = tmp.with_name("folded.onnx")
    so = ort.SessionOptions()
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
    so.optimized_model_filepath = str(folded)
    ort.InferenceSession(str(tmp), so, providers=["CPUExecutionProvider"])
    m = shape_inference.infer_shapes(onnx.load(folded))
    dims = {vi.name: [d.dim_value for d in vi.type.tensor_type.shape.dim]
            for vi in list(m.graph.value_info) + list(m.graph.input) + list(m.graph.output)}

    # 2. MaxPool ceil_mode -> explicit end padding
    changed = 0
    for n in m.graph.node:
        if n.op_type != "MaxPool":
            continue
        at = {a.name: helper.get_attribute_value(a) for a in n.attribute}
        if not at.get("ceil_mode"):
            continue
        h, w = dims[n.input[0]][2:]
        k, s = at["kernel_shape"], at["strides"]
        pads = list(at.get("pads", [0, 0, 0, 0]))
        for i, size in enumerate((h, w)):
            span = size + pads[i] + pads[i + 2] - k[i]
            if span % s[i]:
                pads[i + 2] += s[i] - span % s[i]
        keep = [a for a in n.attribute if a.name not in ("ceil_mode", "pads")]
        del n.attribute[:]
        n.attribute.extend(keep + [helper.make_attribute("ceil_mode", 0), helper.make_attribute("pads", pads)])
        changed += 1
    ops = sorted({n.op_type for n in m.graph.node})
    print(f"MaxPool rewritten: {changed}; ops now: {', '.join(ops)}")
    onnx.checker.check_model(m)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(m, OUT)

    # 3. same output as the original
    a = ort.InferenceSession(raw, providers=["CPUExecutionProvider"])
    b = ort.InferenceSession(str(OUT), providers=["CPUExecutionProvider"])
    rng = np.random.default_rng(7)
    worst = 0.0
    for _ in range(3):
        x = rng.standard_normal((1, 3, SIZE, SIZE)).astype(np.float32)
        ya = a.run(None, {a.get_inputs()[0].name: x})[0]
        yb = b.run(None, {b.get_inputs()[0].name: x})[0]
        worst = max(worst, float(np.abs(ya - yb).max()))
    print(f"max |original - rewritten| over 3 random inputs: {worst:.2e}")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes, sha256 "
          f"{hashlib.sha256(OUT.read_bytes()).hexdigest()})")
    return 0 if worst < 1e-4 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "u2netp.onnx"))
