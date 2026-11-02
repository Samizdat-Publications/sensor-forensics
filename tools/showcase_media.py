"""Landing-page and README media, cut from frames the app recordings already captured.

The frames come from tools/record_gimbal.py (artifacts/movies/frames/gimbal/, the Cockpit view at 1440 x 900, one
PNG per video frame) and tools/record_highlights.py (artifacts/movies/frames/highlights/sNN/, 15 fps). Run those
first if the folders are missing; this script only crops, scales and encodes.

Usage (from the repo root):
    .venv/Scripts/python tools/showcase_media.py

Writes site/media/*.mp4 + posters, site/media/og.jpg, docs/media/hero.gif and docs/media/*.jpg.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAMES = ROOT / "artifacts" / "movies" / "frames"
SITE = ROOT / "site" / "media"
DOCS = ROOT / "docs" / "media"

# Crops on the 1440 x 900 app capture. PANES: the original and re-render panes with the frame-lock strip (16:9).
# MAIN: the whole main panel without the scores rail (16:10). FULL: everything but the bottom timeline.
PANES = "crop=1044:588:0:56,scale=1280:720:flags=lanczos"
MAIN = "crop=1040:650:4:52,scale=1280:800:flags=lanczos"
FULL = "scale=1280:800:flags=lanczos"

# (name, source folder, fps, first frame, last frame (inclusive) or None, filter)
CLIPS = [
    ("hero", "gimbal", 30000 / 1001, 690, 1030, PANES),
    ("godseye", "highlights/s03", 15, 0, None, MAIN),
    ("range", "highlights/s04", 15, 0, None, MAIN),
    ("ledger", "highlights/s06", 15, 0, None, FULL),
    ("gofast", "highlights/s09", 15, 0, None, MAIN),
    ("flir1", "highlights/s11", 15, 0, None, MAIN),
]
# (name, source image, filter)
STILLS = [
    ("compare", "highlights/s08/0000.png", FULL),
    ("difference", "highlights/s02/0000.png", PANES),
    ("cockpit", "gimbal/0800.png", FULL),
]


def ff(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def clip(name: str, src: str, fps: float, first: int, last: int | None, vf: str) -> None:
    d = FRAMES / src
    n = len(list(d.glob("[0-9][0-9][0-9][0-9].png")))
    if n == 0:
        raise SystemExit(f"no frames in {d}: run the recording tool first")
    count = (last if last is not None else n - 1) - first + 1
    out = SITE / f"{name}.mp4"
    ff("-framerate", f"{fps:.5f}", "-start_number", str(first), "-i", str(d / "%04d.png"), "-frames:v", str(count),
       "-vf", f"{vf},format=yuv420p", "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "23",
       "-movflags", "+faststart", str(out))
    ff("-framerate", f"{fps:.5f}", "-start_number", str(first), "-i", str(d / "%04d.png"), "-frames:v", "1",
       "-vf", vf, "-q:v", "3", str(SITE / f"{name}.jpg"))
    print(f"{out.relative_to(ROOT)}: {count} frames, {out.stat().st_size / 1e6:.1f} MB")


def main() -> int:
    SITE.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)
    for c in CLIPS:
        clip(*c)
    for name, src, vf in STILLS:
        ff("-i", str(FRAMES / src), "-vf", vf, "-q:v", "3", str(SITE / f"{name}.jpg"))
    # social card: the panes from frame 800, letterboxed onto 1200 x 630
    ff("-i", str(FRAMES / "gimbal" / "0800.png"), "-vf",
       "crop=1044:588:0:56,scale=1118:630:flags=lanczos,pad=1200:630:41:0:color=0x10151b", "-q:v", "3",
       str(SITE / "og.jpg"))
    # README: hero GIF (640 px, 12 fps, frames 690 to 1030 of the GIMBAL lock) and stills
    with tempfile.TemporaryDirectory() as t:
        pal = Path(t) / "pal.png"
        src = ["-framerate", f"{30000 / 1001:.5f}", "-start_number", "690", "-i", str(FRAMES / "gimbal" / "%04d.png")]
        base = "trim=end_frame=341,crop=1044:588:0:56,fps=12,scale=640:-2:flags=lanczos"
        ff(*src, "-vf", f"{base},palettegen=max_colors=96", str(pal))
        ff(*src, "-i", str(pal), "-lavfi", f"[0:v]{base}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4",
           str(DOCS / "hero.gif"))
    print(f"docs/media/hero.gif: {(DOCS / 'hero.gif').stat().st_size / 1e6:.1f} MB")
    for name in ("cockpit", "godseye", "range", "ledger", "compare", "gofast"):
        ff("-i", str(SITE / f"{name}.jpg"), "-vf", "scale=1280:-2", "-q:v", "4", str(DOCS / f"{name}.jpg"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
