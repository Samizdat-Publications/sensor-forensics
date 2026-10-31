"""Contact sheets for video triage.

For each clip: a 4x4 grid of 16 evenly spaced frames (each labeled with its
frame number and time), plus 3 full-resolution frames at 10%, 50% and 90% of
the duration. Used for PURSUE triage and for the Navy video audit.

Usage:
    python tools/contact_sheet.py <video_or_dir> [--out data/pursue/sheets]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".wmv", ".mpg", ".mkv", ".webm"}


def probe(path: Path) -> tuple[float, float]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=r_frame_rate:format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True)
    d = json.loads(out.stdout)
    num, den = d["streams"][0]["r_frame_rate"].split("/")
    return float(d["format"]["duration"]), float(num) / float(den)


def grab(path: Path, t: float) -> np.ndarray | None:
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
         "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True)
    if out.returncode != 0 or not out.stdout:
        return None
    return cv2.imdecode(np.frombuffer(out.stdout, np.uint8), cv2.IMREAD_COLOR)


def sheet(path: Path, out_dir: Path, tile_w: int = 480) -> Path:
    duration, fps = probe(path)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    times = [duration * (i + 0.5) / 16 for i in range(16)]
    tiles = []
    for t in times:
        img = grab(path, t)
        if img is None:
            img = np.zeros((270, 480, 3), np.uint8)
        h, w = img.shape[:2]
        img = cv2.resize(img, (tile_w, int(h * tile_w / w)), interpolation=cv2.INTER_AREA)
        label = f"f{int(round(t * fps))}  t={t:.1f}s"
        cv2.rectangle(img, (0, 0), (len(label) * 11 + 8, 24), (0, 0, 0), -1)
        cv2.putText(img, label, (4, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1, cv2.LINE_AA)
        tiles.append(img)
    th = max(t.shape[0] for t in tiles)
    tiles = [cv2.copyMakeBorder(t, 0, th - t.shape[0], 0, 0, cv2.BORDER_CONSTANT) for t in tiles]
    rows = [np.hstack(tiles[r * 4:(r + 1) * 4]) for r in range(4)]
    grid = np.vstack(rows)
    sheet_path = out_dir / f"{stem}_sheet.jpg"
    cv2.imwrite(str(sheet_path), grid, [cv2.IMWRITE_JPEG_QUALITY, 85])
    for frac in (0.1, 0.5, 0.9):
        img = grab(path, duration * frac)
        if img is not None:
            cv2.imwrite(str(out_dir / f"{stem}_full_{int(frac * 100):02d}.png"), img)
    return sheet_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target", type=Path)
    ap.add_argument("--out", type=Path, default=Path("data/pursue/sheets"))
    a = ap.parse_args()
    paths = [a.target] if a.target.is_file() else sorted(
        p for p in a.target.rglob("*") if p.suffix.lower() in VIDEO_EXT)
    for p in paths:
        if (a.out / f"{p.stem}_sheet.jpg").exists():
            continue
        print(sheet(p, a.out), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
