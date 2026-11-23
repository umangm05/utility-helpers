u2netp-320.onnx — background-remover model for /background-remover/

Model:    U^2-Net, small variant "u2netp" (Qin, Zhang, Huang, Dehghan, Zaiane, Jagersand, 2020)
Source:   https://github.com/xuebinqin/U-2-Net
Licence:  Apache License 2.0 (https://www.apache.org/licenses/LICENSE-2.0)
ONNX export taken from rembg (MIT): https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx
          sha256 309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8

Modified by Utility Helpers (Apache-2.0 section 4(b) notice): scripts/make_bg_model.py fixes the input
to 1x3x320x320, constant-folds the shape-computation subgraphs, and rewrites MaxPool ceil_mode=1 as
ceil_mode=0 with explicit end padding, so ONNX Runtime Web's WebGL backend can run it. The weights are
unchanged and the output is identical to the original (max |difference| 0.0 on CPU, checked by the script).

The model runs in the visitor's browser. Photos are never uploaded.
