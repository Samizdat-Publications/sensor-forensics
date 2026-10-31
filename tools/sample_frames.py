"""Blind-check sheets for CP-02: random frames, raw crops only, no extracted values.

Picks N frames per case with a fixed seed, and renders review sheets of 10 frames
each: one row per frame (labeled with its frame number only), one column per text
field (labeled with the field name), each cell the raw field crop enlarged 4x. The
verifier types what they read into a CSV (frame, field, value); score_blind.py
compares that with symbology_final.csv. The sheets never show our readings.

Usage:
    python tools/sample_frames.py --seed 2026 --n 100 gimbal gofast
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "artifacts" / "cp02"


def sheets(case: str, seed: int, n: int, per_sheet: int = 10, scale: int = 4, tag: str = "blind") -> dict:
    layout = yaml.safe_load((ROOT / "extract" / "layouts" / f"{case}.yaml").read_text())
    fields = [k for k, v in layout["fields"].items() if v["kind"] == "text" and k != "sensor"]
    frames = sorted((ROOT / "data" / "frames" / case).glob("f*.png"))
    rng = np.random.default_rng(seed)
    picks = sorted(rng.choice(len(frames), size=n, replace=False).tolist())
    out_dir = OUT_ROOT / tag / case
    out_dir.mkdir(parents=True, exist_ok=True)
    cell_w = max((v["box"][2] - v["box"][0]) for k, v in layout["fields"].items() if k in fields) * scale + 8
    cell_h = max((v["box"][3] - v["box"][1]) for k, v in layout["fields"].items() if k in fields) * scale + 8
    label_w = 90
    files = []
    for s in range(0, n, per_sheet):
        chunk = picks[s:s + per_sheet]
        sheet = np.full((28 + cell_h * len(chunk), label_w + cell_w * len(fields), 3), 24, np.uint8)
        for j, f in enumerate(fields):
            cv2.putText(sheet, f, (label_w + j * cell_w + 4, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)
        for i, fr in enumerate(chunk):
            img = cv2.imread(str(frames[fr]))
            y = 28 + i * cell_h
            cv2.putText(sheet, f"f{fr}", (6, y + cell_h // 2 + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            for j, f in enumerate(fields):
                x0, y0, x1, y1 = layout["fields"][f]["box"]
                c = cv2.resize(img[y0:y1, x0:x1], None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
                x = label_w + j * cell_w + 4
                sheet[y + 4:y + 4 + c.shape[0], x:x + c.shape[1]] = c
        p = out_dir / f"sheet_{s // per_sheet:02d}.png"
        cv2.imwrite(str(p), sheet)
        files.append(str(p.relative_to(ROOT)).replace("\\", "/"))
    meta = {"case": case, "seed": seed, "n": n, "frames": picks, "fields": fields, "sheets": files,
            "instructions": "Type exactly what each crop shows (digits, sign, letters such as L/R/A/B, "
                            "BLK/WHT); write 'blank' if the crop is empty and '?' if unreadable."}
    (out_dir / "sample.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cases", nargs="+")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--tag", default="blind", help="output folder under artifacts/cp02 (one per sampling round)")
    a = ap.parse_args()
    for c in a.cases:
        m = sheets(c, a.seed, a.n, tag=a.tag)
        print(c, len(m["sheets"]), "sheets, fields:", ", ".join(m["fields"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
