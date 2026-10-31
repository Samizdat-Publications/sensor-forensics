"""Frame extraction: every frame of a video to PNG, plus a frame index.

Outputs, under data/frames/<case>/ (gitignored) and data/derived/<case>/ (committed):
    data/frames/<case>/f000000.png ...         one PNG per decoded frame
    data/derived/<case>/frames.csv             frame, t_nominal_s, pts_s, sha256, dup_of
    data/derived/<case>/frames_meta.json       ffmpeg version, source sha256, counts, frame-set hash

Duplicate detection: a frame whose decoded pixels are identical to the
previous frame (same sha256) is marked dup_of=<previous index>. Telecine or
encoder duplicates matter because symbology update cadence (for example
GIMBAL azimuth every other frame) is measured in frames.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class FrameIndex:
    case: str
    n_frames: int
    n_dups: int
    fps: float
    frame_set_sha256: str


def ffmpeg_version() -> str:
    out = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
    return out.stdout.splitlines()[0] if out.returncode == 0 else "unknown"


def probe_fps(video: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=r_frame_rate", "-of", "default=nw=1:nk=1", str(video)],
        capture_output=True, text=True, check=True)
    num, den = out.stdout.strip().split("/")
    return float(num) / float(den)


def probe_pts(video: Path) -> list[float]:
    """Presentation timestamps of every decoded video frame, in seconds."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "frame=pts_time,best_effort_timestamp_time", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True)
    pts = []
    for line in out.stdout.splitlines():
        vals = [v for v in line.split(",") if v not in ("", "N/A")]
        pts.append(float(vals[0]) if vals else float("nan"))
    return pts


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract(video: Path, case: str, frames_root: Path | None = None,
            derived_root: Path | None = None) -> FrameIndex:
    frames_dir = (frames_root or ROOT / "data" / "frames") / case
    derived_dir = (derived_root or ROOT / "data" / "derived") / case
    frames_dir.mkdir(parents=True, exist_ok=True)
    derived_dir.mkdir(parents=True, exist_ok=True)
    for old in frames_dir.glob("f*.png"):
        old.unlink()

    # -vsync passthrough keeps exactly the decoded frames: no duplication or dropping by ffmpeg.
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-map", "0:v:0", "-fps_mode", "passthrough",
         "-start_number", "0", str(frames_dir / "f%06d.png")],
        check=True)

    fps = probe_fps(video)
    pts = probe_pts(video)
    pngs = sorted(frames_dir.glob("f*.png"))
    set_hash = hashlib.sha256()
    rows = []
    prev_hash = None
    prev_idx = None
    n_dups = 0
    for i, png in enumerate(pngs):
        # Hash decoded pixels, not PNG bytes, so encoder settings can't hide a duplicate.
        import cv2  # local import keeps module import cheap for tooling that only needs metadata
        img = cv2.imread(str(png), cv2.IMREAD_UNCHANGED)
        h = hashlib.sha256(img.tobytes()).hexdigest()
        set_hash.update(h.encode())
        dup_of = ""
        if h == prev_hash:
            dup_of = str(prev_idx)
            n_dups += 1
        else:
            prev_idx = i
        prev_hash = h
        rows.append({
            "frame": i,
            "t_nominal_s": f"{i / fps:.6f}",
            "pts_s": f"{pts[i]:.6f}" if i < len(pts) else "",
            "sha256": h,
            "dup_of": dup_of,
        })

    with (derived_dir / "frames.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["frame"])
        w.writeheader()
        w.writerows(rows)

    idx = FrameIndex(case=case, n_frames=len(pngs), n_dups=n_dups, fps=fps,
                     frame_set_sha256=set_hash.hexdigest())
    meta = {
        "case": case,
        "source_video": str(video.relative_to(ROOT)) if video.is_relative_to(ROOT) else str(video),
        "source_sha256": file_sha256(video),
        "ffmpeg": ffmpeg_version(),
        "fps_nominal": fps,
        "n_frames": idx.n_frames,
        "n_pts": len(pts),
        "n_exact_duplicates": n_dups,
        "frame_set_sha256": idx.frame_set_sha256,
    }
    (derived_dir / "frames_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return idx


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("video", type=Path)
    ap.add_argument("case")
    a = ap.parse_args()
    r = extract(a.video.resolve(), a.case)
    print(f"{r.case}: {r.n_frames} frames, {r.n_dups} exact duplicates, fps {r.fps:.4f}")
