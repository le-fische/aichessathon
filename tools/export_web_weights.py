#!/usr/bin/env python3
"""
Export quantized NNUE v2 Silicon weights for Web / GitHub Pages.
Generates:
  - docs/weights.bin (raw binary)
  - docs/weights_data.js (self-contained base64 loader with zero CORS issues)
"""

import os
import base64
import numpy as np

def export_web_weights(weights_dir="weights", output_dir="docs"):
    os.makedirs(output_dir, exist_ok=True)
    print(f"Loading weights from {weights_dir}...")

    w_acc = np.load(os.path.join(weights_dir, "weights_acc.npy"))
    b_acc = np.load(os.path.join(weights_dir, "biases_acc.npy"))
    w_fc1 = np.load(os.path.join(weights_dir, "weights_fc1.npy"))
    b_fc1 = np.load(os.path.join(weights_dir, "biases_fc1.npy"))
    w_fc2 = np.load(os.path.join(weights_dir, "weights_fc2.npy"))
    b_fc2 = np.load(os.path.join(weights_dir, "biases_fc2.npy"))

    raw_bytes = (
        w_acc.tobytes() +
        b_acc.tobytes() +
        w_fc1.tobytes() +
        b_fc1.tobytes() +
        w_fc2.tobytes() +
        b_fc2.tobytes()
    )

    bin_path = os.path.join(output_dir, "weights.bin")
    with open(bin_path, "wb") as f:
        f.write(raw_bytes)
    print(f"  --> Saved {bin_path} ({len(raw_bytes):,} bytes)")

    b64 = base64.b64encode(raw_bytes).decode("ascii")
    js_code = f"""// Auto-generated NNUE v2 Silicon quantized weights
(function(global) {{
  const WEIGHTS_B64 = "{b64}";

  function unpackWeightsFromBinary(buffer) {{
    let offset = 0;
    const w_acc = new Int16Array(buffer, offset, 768 * 256);
    offset += 768 * 256 * 2;
    const b_acc = new Int16Array(buffer, offset, 256);
    offset += 256 * 2;
    const w_fc1 = new Int8Array(buffer, offset, 64 * 512);
    offset += 64 * 512 * 1;
    const b_fc1 = new Int32Array(buffer, offset, 64);
    offset += 64 * 4;
    const w_fc2 = new Int8Array(buffer, offset, 8 * 64);
    offset += 8 * 64 * 1;
    const b_fc2 = new Int32Array(buffer, offset, 8);
    offset += 8 * 4;
    return {{ w_acc, b_acc, w_fc1, b_fc1, w_fc2, b_fc2 }};
  }}

  function getEmbeddedWeights() {{
    const binaryString = atob(WEIGHTS_B64);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {{
      bytes[i] = binaryString.charCodeAt(i);
    }}
    return unpackWeightsFromBinary(bytes.buffer);
  }}

  global.NNUE_WEIGHTS = {{
    getEmbeddedWeights,
    unpackWeightsFromBinary
  }};
}})(typeof self !== 'undefined' ? self : this);
"""

    js_path = os.path.join(output_dir, "weights_data.js")
    with open(js_path, "w") as f:
        f.write(js_code)
    print(f"  --> Saved {js_path} ({len(js_code):,} bytes)")
    print("Export complete!")

if __name__ == "__main__":
    export_web_weights()
