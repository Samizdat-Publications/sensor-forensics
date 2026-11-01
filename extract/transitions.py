"""Flag interlaced transition frames in the symbology readings.

The video is interlaced: a frame's even and odd rows come from two fields about
1/60 s apart. When an on-screen readout changes between those fields, the frame
shows the old digits on one set of rows and the new digits on the other, so it
genuinely carries two values (CP-02 adjudication found 5 such frames in a 200-frame
blind sample). Picking one value there is a coin toss; this step flags them.

Method: for every frame within one frame of a change in a field's reading, compare
the field crop's even rows and odd rows separately with the previous and next frames
(on the union of bright glyph pixels). A transition frame matches one neighbor on its
even rows and the other neighbor on its odd rows, so the best split match is much
better than the best whole-frame match. split_ratio = whole / split; above THRESH
marks a transition, with the readings before and after.

Output: data/derived/<case>/transitions.csv with columns
frame, field, comb_ratio (the split ratio), transition (0/1), value_before, value_after.
The solver treats a flagged frame as "either value", i.e. the readout interval
spans both.

Usage:
    python -m extract.transitions gimbal
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
THRESH = 1.3


def _gray(crop: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(float)


def split_ratio(prev: np.ndarray, cur: np.ndarray, nxt: np.ndarray) -> float:
    p, c, n = _gray(prev), _gray(cur), _gray(nxt)
    mask = np.maximum(np.maximum(p, c), n) > np.percentile(np.stack([p, c, n]), 85)
    if not mask.any():
        return 1.0

    def d(a: np.ndarray, b: np.ndarray, rows: slice) -> float:
        m = mask[rows]
        return float(np.abs(a[rows] - b[rows])[m].mean()) if m.any() else 0.0

    ev, od = slice(0, None, 2), slice(1, None, 2)
    whole = min(d(c, p, ev) + d(c, p, od), d(c, n, ev) + d(c, n, od))
    split = min(d(c, p, ev) + d(c, n, od), d(c, n, ev) + d(c, p, od))
    return whole / max(split, 1e-6)


def flag(case: str, frames_dir: Path | None = None, derived: Path | None = None,
         layout_path: Path | None = None) -> pd.DataFrame:
    frames_dir = frames_dir or ROOT / "data" / "frames" / case
    derived = derived or ROOT / "data" / "derived" / case
    if layout_path is None:
        from extract.symbology import layout_path as _layout_path  # resolves FLIR1 copies to flir1.yaml
        layout_path = _layout_path(case)
    layout = yaml.safe_load(layout_path.read_text(encoding="utf-8"))
    sym = pd.read_csv(derived / "symbology_final.csv", dtype=str)
    sym["frame"] = sym["frame"].astype(int)
    rows = []
    cache: dict[int, np.ndarray] = {}

    def img(f: int) -> np.ndarray:
        if f not in cache:
            cache[f] = cv2.imread(str(frames_dir / f"f{f:06d}.png"))
        return cache[f]

    for field, g in sym.groupby("field"):
        if field not in layout["fields"] or layout["fields"][field]["kind"] != "text":
            continue
        g = g.sort_values("frame")
        vals = g["value"].tolist()
        fr = g["frame"].tolist()
        near = set()
        for i in range(1, len(vals)):
            if vals[i] != vals[i - 1]:
                near.update({i - 1, i})
        if not near:
            continue
        x0, y0, x1, y1 = layout["fields"][field]["box"]
        for i in sorted(near):
            if i == 0 or i + 1 >= len(vals):
                continue
            crop = lambda k: img(fr[k])[y0:y1, x0:x1]
            ratio = split_ratio(crop(i - 1), crop(i), crop(i + 1))
            rows.append({"frame": fr[i], "field": field, "comb_ratio": round(ratio, 3),
                         "transition": int(ratio > THRESH and vals[i - 1] != vals[i + 1]),
                         "value_before": vals[i - 1], "value_after": vals[i + 1]})
    out = pd.DataFrame(rows, columns=["frame", "field", "comb_ratio", "transition", "value_before", "value_after"])
    out = out.sort_values(["field", "frame"])
    out.to_csv(derived / "transitions.csv", index=False, lineterminator="\n")
    return out


def main(argv: list[str]) -> int:
    for case in argv:
        t = flag(case)
        print(f"{case}: {len(t)} frames near a change, {int(t['transition'].sum())} flagged as transitions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
