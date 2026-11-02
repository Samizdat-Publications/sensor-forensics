"""The 60-second GIMBAL recording for CP-05 (M4.8): the cockpit view, original frame beside the synthetic
re-render, captured frame by frame and assembled with ffmpeg.

Usage (from the repo root):
    .venv/Scripts/python tools/record_gimbal.py                   # capture every frame, then assemble
    .venv/Scripts/python tools/record_gimbal.py --assemble-only   # reuse the captured frames

Deterministic capture: the frame is set through the URL hash (the app's own router, no reload), and a
shot is taken only once the original image for exactly that frame has decoded and two animation frames
have passed, so the re-render and the original always show the same frame index. Playback timing comes
from ffmpeg, not from the browser.

Output: artifacts/movies/gimbal_framelock_60s.mp4
  part 1: all 1031 frames at the video's own 29.97 fps (34.4 s, real time);
  part 2: the last 384 frames (647 to 1030, where the object rotates) at half speed (25.6 s).
Frames: artifacts/movies/frames/gimbal/ (gitignored).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from screenshot_app import HOST, launch, route_files  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FRAMES = ROOT / "artifacts" / "movies" / "frames" / "gimbal"
OUT = ROOT / "artifacts" / "movies" / "gimbal_framelock_60s.mp4"
VIEWPORT = (1440, 900)
QUERY = "v=fov035&h=H-BAL"
FPS = 30000 / 1001
SLOW_FROM = 647            # half-speed part: frames SLOW_FROM .. n-1 (384 frames, 25.6 s)
FONT = "C\\:/Windows/Fonts/arial.ttf"


def capture() -> int:
    FRAMES.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    with sync_playwright() as p:
        b, mode = launch(p)
        page = b.new_page(viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]})
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        route_files(page, ROOT / "app")
        page.goto(f"{HOST}#/gimbal/cockpit?f=0&{QUERY}")
        page.wait_for_function("() => window.__app && (window.__app.ready || window.__app.error)", timeout=30000)
        if page.evaluate("() => window.__app.error || null"):
            raise SystemExit("app error: " + page.evaluate("() => window.__app.error"))
        n = page.evaluate("() => window.__app.state.data.meta.n_frames")
        for i in range(n):
            page.evaluate(f"() => {{ location.hash = '#/gimbal/cockpit?f={i}&{QUERY}'; }}")
            want = f"f{i:06d}.jpg"
            page.wait_for_function(
                """(want) => { const im = document.getElementById('ck-img');
                   return window.__app.state.frame === %d && im && im.src.endsWith(want) && im.complete && im.naturalWidth > 0; }""" % i,
                arg=want, timeout=20000)
            page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
            page.screenshot(path=str(FRAMES / f"{i:04d}.png"))
            if i % 100 == 0:
                print(f"  frame {i}/{n}", flush=True)
        b.close()
    if errors:
        raise SystemExit("console errors:\n" + "\n".join(errors[:20]))
    print(f"{mode}: {n} frames captured")
    return n


def assemble(n: int) -> None:
    src = str(FRAMES / "%04d.png")
    label = ("drawtext=fontfile='{f}':text='{t}':x=w-tw-24:y=h-th-20:fontsize=22:fontcolor=white:"
             "box=1:boxcolor=black@0.6:boxborderw=8")
    part1 = label.format(f=FONT, t="Real time (29.97 fps)")
    part2 = label.format(f=FONT, t=f"Half speed, frames {SLOW_FROM} to {n - 1}")
    fc = (f"[0:v]{part1},format=yuv420p[a];"
          f"[1:v]setpts=2*PTS,fps={FPS:.5f},{part2},format=yuv420p[b];"
          "[a][b]concat=n=2:v=1[v]")
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-framerate", "30000/1001", "-start_number", "0", "-i", src,
           "-framerate", "30000/1001", "-start_number", str(SLOW_FROM), "-i", src,
           "-filter_complex", fc, "-map", "[v]",
           "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-movflags", "+faststart", str(OUT)]
    subprocess.run(cmd, check=True)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=nb_frames,width,height",
                            "-of", "json", str(OUT)], capture_output=True, text=True, check=True)
    info = json.loads(probe.stdout)
    print(f"{OUT.relative_to(ROOT)}: {float(info['format']['duration']):.2f} s, "
          f"{info['streams'][0]['width']}x{info['streams'][0]['height']}, {OUT.stat().st_size / 1e6:.1f} MB")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assemble-only", action="store_true")
    a = ap.parse_args(argv)
    n = len(list(FRAMES.glob("*.png"))) if a.assemble_only else capture()
    assemble(n)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
