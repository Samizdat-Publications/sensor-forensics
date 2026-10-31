"""M0 audit evidence: for each field in a layout, crops from N evenly spaced frames, enlarged.

One image per video: a row per field, a column per sampled frame, frame numbers on top.
Used to show (and let the verifier check) that a field is readable on screen.

Usage:
    python tools/field_strips.py extract/layouts/gofast.yaml data/frames/gofast artifacts/cp01/gofast_fields.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import yaml


def main(layout: str, frames_dir: str, out: str, n: int = 8, scale: int = 3) -> int:
    L = yaml.safe_load(Path(layout).read_text())
    frames = sorted(Path(frames_dir).glob("f*.png"))
    idx = np.linspace(0, len(frames) - 1, n).round().astype(int)
    imgs = {i: cv2.imread(str(frames[i])) for i in idx}
    rows = []
    label_w = 110
    for name, f in L["fields"].items():
        if f["kind"] != "text":
            continue
        x0, y0, x1, y1 = f["box"]
        cells = []
        for i in idx:
            c = cv2.resize(imgs[i][y0:y1, x0:x1], None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
            cells.append(cv2.copyMakeBorder(c, 2, 2, 2, 2, cv2.BORDER_CONSTANT, value=(0, 0, 160)))
        row = np.hstack(cells)
        lab = np.zeros((row.shape[0], label_w, 3), np.uint8)
        cv2.putText(lab, name, (4, row.shape[0] // 2 + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        rows.append(np.hstack([lab, row]))
    W = max(r.shape[1] for r in rows)
    rows = [cv2.copyMakeBorder(r, 0, 0, 0, W - r.shape[1], cv2.BORDER_CONSTANT) for r in rows]
    cell_w = (W - label_w) // n
    head = np.zeros((22, W, 3), np.uint8)
    for j, i in enumerate(idx):
        cv2.putText(head, f"f{i}", (label_w + j * cell_w + 4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.imwrite(out, np.vstack([head] + rows))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
