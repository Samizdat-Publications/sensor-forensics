"""The 2-minute highlight recording for CP-07 (M6): a captioned tour of the app's five views across GIMBAL,
GOFAST and FLIR1.

Usage (from the repo root):
    .venv/Scripts/python tools/record_highlights.py                   # capture, then assemble
    .venv/Scripts/python tools/record_highlights.py --assemble-only   # reuse the captured frames

Same deterministic capture as tools/record_gimbal.py: every state is set through the URL hash (the app's own
router), and a shot is taken only once the app reports that state (and, on the cockpit view, once the original
image for exactly that frame has decoded). A segment is either a sequence of states played at 15 fps or one
state held for a number of seconds. Each segment is encoded with its caption, then the segments are joined.

Output: artifacts/movies/highlights_2min.mp4. Frames: artifacts/movies/frames/highlights/ (gitignored).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from screenshot_app import HOST, launch, route_files  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FRAMES = ROOT / "artifacts" / "movies" / "frames" / "highlights"
OUT = ROOT / "artifacts" / "movies" / "highlights_2min.mp4"
VIEWPORT = (1440, 900)
FPS = 15
FONT = "C\\:/Windows/Fonts/arial.ttf"


def seq(case: str, view: str, frames, extra: str = "") -> list[str]:
    return [f"#/{case}/{view}?f={f}{extra}" for f in frames]


def sweep(case: str, view: str, frame: int, key: str, values, extra: str = "") -> list[str]:
    return [f"#/{case}/{view}?f={frame}&{key}={v:.2f}{extra}" for v in values]


def lin(a: float, b: float, n: int) -> list[float]:
    return [a + (b - a) * i / (n - 1) for i in range(n)]


G = "&v=fov035&h=H-BAL"
# (caption, states, hold seconds or None to play the states at FPS)
SEGMENTS = [
    ("Sensor Forensics Lab: GIMBAL, GOFAST and FLIR1 rebuilt from the public footage", [f"#/gimbal/cockpit?f=0{G}"], 6),
    ("GIMBAL: the original (left) beside the re-render of one hypothesis (right), locked frame by frame",
     seq("gimbal", "cockpit", range(600, 1031, 2), G), None),
    ("Difference view: what the re-render does not explain", [f"#/gimbal/cockpit?f=956{G}&m=diff"], 6),
    ("God's-eye: the jet's turn, the sight lines, and each hypothesis's path. Range is unknown, so it is swept",
     sweep("gimbal", "godseye", 719, "r", lin(5, 40, 120), G), None),
    ("Range explorer: the speed, altitude and g the object would need at each assumed range",
     sweep("gimbal", "range", 719, "r", lin(2, 40, 105), G), None),
    ("Every physical model needs about 12 nmi or more; the aircrew report 6 to 8. Radar range would settle it",
     [f"#/gimbal/range?f=719&r=7.00{G}"], 6),
    ("Evidence ledger: testimony weight swept from physics only (0) to double (2); both totals always shown",
     sweep("gimbal", "ledger", 719, "w", lin(0, 2, 105), G), None),
    ("Two data-quality rules decide GIMBAL's ranking; both ways are shown", [f"#/gimbal/ledger?f=719&w=1.00{G}"], 6),
    ("Prior work reproduced from its own inputs: Sitrec and Peings and von Rennenkampff 2023",
     [f"#/gimbal/compare?f=719{G}"], 9),
    ("GOFAST: range is on screen (4.4 down to 3.3 nmi), putting the object near 13,200 ft",
     seq("gofast", "cockpit", range(300, 700, 2)), None),
    ("A balloon, a slow flier and a glare on a slow target fit the same path; an independent wind would separate them",
     [f"#/gofast/range?f=701"], 8),
    ("FLIR1 (Tic Tac, 2004): a small 352 x 264 copy, no range on screen", seq("flir1", "cockpit", range(1000, 1600, 3)), None),
    ("FLIR1's leader depends on the rotation noise: free path at 11.9 deg, a glare above about 13 deg",
     [f"#/flir1/ledger?f=1300"], 8),
    ("Hypotheses tested, not confirmed. Full results: docs/results/", [f"#/gimbal/godseye?f=719&r=10.00{G}"], 8),
]


def wait_state(page, h: str) -> None:
    q = dict(p.split("=") for p in h.split("?", 1)[1].split("&"))
    cond = [f"s.frame === {int(q['f'])}"]
    if "r" in q:
        cond.append(f"Math.abs(s.range - {float(q['r'])}) < 1e-6")
    if "w" in q:
        cond.append(f"Math.abs(s.wT - {float(q['w'])}) < 1e-6")
    if "/cockpit" in h:
        cond.append("(() => { const im = document.getElementById('ck-img'); return im && im.src.endsWith('f%06d.jpg') "
                    "&& im.complete && im.naturalWidth > 0; })()" % int(q["f"]))
    page.wait_for_function("() => { const s = window.__app && window.__app.state; return !!s && " + " && ".join(cond) + "; }",
                           timeout=20000)
    page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def capture() -> None:
    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True)
    errors: list[str] = []
    with sync_playwright() as p:
        b, mode = launch(p)
        page = b.new_page(viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]})
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        route_files(page, ROOT / "app")
        case = None
        for k, (_, states, _) in enumerate(SEGMENTS):
            d = FRAMES / f"s{k:02d}"
            d.mkdir()
            for i, h in enumerate(states):
                c = h.split("/")[1]
                if c != case:
                    page.goto("about:blank")
                    page.goto(HOST + h)
                    page.wait_for_function("() => window.__app && (window.__app.ready || window.__app.error)", timeout=30000)
                    if page.evaluate("() => window.__app.error || null"):
                        raise SystemExit("app error: " + page.evaluate("() => window.__app.error"))
                    case = c
                else:
                    page.evaluate(f"() => {{ location.hash = {json.dumps(h)}; }}")
                wait_state(page, h)
                page.wait_for_timeout(60)
                page.screenshot(path=str(d / f"{i:04d}.png"))
            print(f"  segment {k}: {len(states)} frame(s)", flush=True)
        b.close()
    if errors:
        raise SystemExit("console errors:\n" + "\n".join(errors[:20]))
    print(f"{mode}: captured {len(SEGMENTS)} segments")


def assemble() -> None:
    parts = []
    for k, (cap, states, hold) in enumerate(SEGMENTS):
        d = FRAMES / f"s{k:02d}"
        txt = d / "caption.txt"
        txt.write_text(cap, encoding="utf-8")
        tf = str(txt).replace("\\", "/").replace(":", "\\:")
        draw = (f"drawtext=fontfile='{FONT}':textfile='{tf}':x=(w-tw)/2:y=h-th-34:fontsize=24:fontcolor=white:"
                f"box=1:boxcolor=black@0.7:boxborderw=12,format=yuv420p")
        part = d / "part.mp4"
        if hold:
            inp = ["-loop", "1", "-framerate", str(FPS), "-t", str(hold), "-i", str(d / "0000.png")]
        else:
            inp = ["-framerate", str(FPS), "-i", str(d / "%04d.png")]
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inp, "-vf", draw, "-r", str(FPS),
                        "-c:v", "libx264", "-preset", "slow", "-crf", "24", str(part)], check=True)
        parts.append(part)
    lst = FRAMES / "parts.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", "-movflags", "+faststart", str(OUT)], check=True)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(OUT)],
                           capture_output=True, text=True, check=True)
    dur = float(json.loads(probe.stdout)["format"]["duration"])
    print(f"{OUT.relative_to(ROOT)}: {dur:.1f} s, {OUT.stat().st_size / 1e6:.1f} MB")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assemble-only", action="store_true")
    a = ap.parse_args(argv)
    if not a.assemble_only:
        capture()
    assemble()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
