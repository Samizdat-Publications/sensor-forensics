"""M5 gate scan: find tracker-gate frames and measure the gate in pixels (D-013 clips).

Usage:  .venv/Scripts/python tools/pursue_m5_scan.py <clip_id> [--step N] [--montage]

Reads the official file's decoded frames (same order and indices as extract/frames.py), every
`step`th frame. Fixed
symbology (crosshair, frame corner ticks) is removed with a persistence mask: pixels of the
gate colour in at least 50 percent of the sampled frames. The gate is the largest roughly
square group of gate-colour pixels left (corners linked by a dilation); its SIZE is the
vertical extent (the label beside it never adds height). Output:
    data/derived/pursue/<clip>/gate_scan.csv   frame, t_s, x0, y0, x1, y1, h_px, w_px
and with --montage, review sheets (gate box drawn in red, label region enlarged) under
artifacts/tmp/pursue_m5/<clip>/ for reading the labels by eye.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extract.pursue_m5 import colour_mask  # noqa: E402

HUES = {  # OpenCV hue band of each clip's gate symbology (measured from hue histograms)
    "DOW-UAP-PR044": (65, 100),
    "DOW-UAP-PR059": (68, 102),
    "DOW-UAP-PR078": (95, 122),
    "DOW-UAP-PR089": (95, 122),
}


def frames_dir(clip: str) -> Path:
    return ROOT / "data" / "frames" / clip.lower()


def video_of(clip: str) -> Path:
    with (ROOT / "data" / "pursue" / "file_map.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["clip_id"] == clip:
                return ROOT / "data" / "pursue" / "raw" / r["file"]
    raise KeyError(clip)


def fps_of(clip: str) -> float:
    cap = cv2.VideoCapture(str(video_of(clip)))
    return float(cap.get(cv2.CAP_PROP_FPS))


def iter_frames(clip: str, step: int):
    """Decoded frames (index, image) every `step` frames, read from the official file in
    decode order (the same order extract/frames.py writes its PNGs)."""
    cap = cv2.VideoCapture(str(video_of(clip)))
    i = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % step == 0:
            ok, im = cap.retrieve()
            if ok:
                yield i, im
        i += 1


def read_frame(clip: str, f: int) -> np.ndarray:
    p = frames_dir(clip) / f"f{f:06d}.png"
    if p.exists():
        return cv2.imread(str(p))
    cap = cv2.VideoCapture(str(video_of(clip)))
    for _ in range(f):
        cap.grab()
    return cap.read()[1]


def find_gate(mask: np.ndarray, link: int = 31, min_h: int = 16):
    n, lab = cv2.connectedComponents(cv2.dilate(mask.astype(np.uint8), np.ones((link, link), np.uint8)))
    best = None
    for i in range(1, n):
        ys, xs = np.nonzero((lab == i) & mask)
        if len(ys) < 25:
            continue
        h = ys.max() - ys.min() + 1
        w = xs.max() - xs.min() + 1
        if h < min_h or w < 0.6 * h or w > 1.0 * h + 70:
            continue
        if best is None or h > best[3] - best[1] + 1:
            best = (xs.min(), ys.min(), xs.max(), ys.max())
    return best


def scan(clip: str, step: int) -> list[dict]:
    lo, hi = HUES[clip]
    n = int(cv2.VideoCapture(str(video_of(clip))).get(cv2.CAP_PROP_FRAME_COUNT))
    acc, k = None, 0
    for _, im in iter_frames(clip, max(1, n // 60)):
        m = colour_mask(im, lo, hi).astype(np.float32)
        acc = m if acc is None else acc + m
        k += 1
    fixed = cv2.dilate(((acc / k) >= 0.5).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    fps = fps_of(clip)
    rows = []
    for f, im in iter_frames(clip, step):
        m = colour_mask(im, lo, hi) & ~fixed
        g = find_gate(m)
        if g is None:
            continue
        x0, y0, x1, y1 = (int(v) for v in g)
        rows.append({"frame": f, "t_s": f"{f / fps:.3f}", "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                     "h_px": y1 - y0 + 1, "w_px": x1 - x0 + 1})
    return rows


def montage(clip: str, rows: list[dict], every_s: float = 1.0) -> list[Path]:
    out_dir = ROOT / "artifacts" / "tmp" / "pursue_m5" / clip.lower()
    out_dir.mkdir(parents=True, exist_ok=True)
    picked, last = [], -1e9
    for r in rows:
        if float(r["t_s"]) - last >= every_s:
            picked.append(r)
            last = float(r["t_s"])
    tiles = []
    want = {r["frame"] for r in picked}
    ims = {f: im for f, im in iter_frames(clip, 1) if f in want} if want else {}
    for r in picked:
        im = ims[r["frame"]]
        x0, y0, x1, y1 = r["x0"], r["y0"], r["x1"], r["y1"]
        h = y1 - y0
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        half = max(60, int(0.9 * h))
        xa, xb = max(0, cx - half), min(im.shape[1], cx + half + 60)
        ya, yb = max(0, cy - half), min(im.shape[0], cy + half)
        c = im[ya:yb, xa:xb].copy()
        cv2.rectangle(c, (x0 - xa, y0 - ya), (x1 - xa, y1 - ya), (0, 0, 255), 1)
        c = cv2.resize(c, (300, int(300 * c.shape[0] / c.shape[1])))
        c = cv2.resize(c, (300, 260)) if c.shape[0] != 260 else c
        c = cv2.copyMakeBorder(c, 18, 0, 0, 0, cv2.BORDER_CONSTANT, 0)
        cv2.putText(c, f"{r['frame']} h{r['h_px']}", (3, 14), 0, 0.45, (0, 255, 255), 1)
        tiles.append(c)
    paths = []
    per = 30
    for k in range(0, len(tiles), per):
        t = tiles[k:k + per]
        while len(t) % 6:
            t.append(np.zeros_like(tiles[0]))
        sheet = np.vstack([np.hstack(t[i:i + 6]) for i in range(0, len(t), 6)])
        p = out_dir / f"gates_{k // per:02d}.png"
        cv2.imwrite(str(p), sheet)
        paths.append(p)
    return paths


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("--step", type=int, default=5)
    ap.add_argument("--montage", action="store_true")
    ap.add_argument("--every", type=float, default=1.0)
    a = ap.parse_args()
    rows = scan(a.clip, a.step)
    out = ROOT / "data" / "derived" / "pursue" / a.clip.lower() / "gate_scan.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["frame", "t_s", "x0", "y0", "x1", "y1", "h_px", "w_px"])
        w.writeheader()
        w.writerows(rows)
    print(f"{a.clip}: {len(rows)} gate frames -> {out.relative_to(ROOT)}")
    if a.montage and rows:
        for p in montage(a.clip, rows, a.every):
            print(p.relative_to(ROOT))


if __name__ == "__main__":
    main()
