"""PR113: find a small dark object crossing the frame quickly (Haqq-Misra and Kopparapu's
four-frame transit). For every frame, the residual min(prev, next) - cur (dark movers) at
half resolution, blurred; the top three peaks per frame are written to
data/derived/pursue/dow-uap-pr113/dark_movers.csv. Usage: python tools/pursue_m5_darkscan.py"""
from __future__ import annotations
import csv
from pathlib import Path
import cv2
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "frames" / "dow-uap-pr113"

def g(f):
    im = cv2.imread(str(D / f"f{f:06d}.png"), cv2.IMREAD_GRAYSCALE)
    return cv2.resize(im, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA).astype(np.float32)

def main():
    n = len(list(D.glob("f*.png")))
    rows = []
    a, b = g(0), g(1)
    for f in range(1, n - 1):
        c = g(f + 1)
        d = cv2.GaussianBlur(np.minimum(a, c) - b, (5, 5), 0)
        d[:, :15] = 0; d[:, -15:] = 0; d[-20:] = 0
        for k in range(3):
            y, x = np.unravel_index(int(np.argmax(d)), d.shape)
            rows.append({"frame": f, "rank": k, "x": 2 * x, "y": 2 * y, "score": f"{d[y, x]:.1f}"})
            d[max(0, y - 20):y + 21, max(0, x - 20):x + 21] = 0
        a, b = b, c
    out = ROOT / "data" / "derived" / "pursue" / "dow-uap-pr113" / "dark_movers.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(len(rows))

if __name__ == "__main__":
    main()
