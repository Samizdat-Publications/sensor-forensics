"""Screenshot every view of the web app with Playwright (CP-05 evidence).

Usage (from the repo root):
    .venv/Scripts/python tools/screenshot_app.py                 # app views -> artifacts/cp05/shell_*.png
    .venv/Scripts/python tools/screenshot_app.py --mock          # design mockups -> docs/design/mock_*.png

Serves app/ (or the repo, for docs/design mockups) to the page straight from disk via Playwright routing. Tries headless Chromium first; if WebGL
is unavailable there, falls back to headed Chromium placed off-screen (the window never takes focus
on screen). Fails if any page logs a console error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SIZES = {"1440": (1440, 900), "1920": (1920, 1080)}
VIEWS = ["cockpit", "godseye", "range", "compare", "ledger"]


MIME = {".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
        ".json": "application/json", ".jpg": "image/jpeg", ".png": "image/png", ".svg": "image/svg+xml"}
HOST = "http://lab.localhost/"


def route_files(page, directory: Path) -> None:
    """Serve `directory` to the page straight from disk through Playwright's router: no socket at all.
    (A localhost HTTP server, in-process or not, intermittently timed out connections here.)"""
    root = directory.resolve()

    def handle(route):
        rel = route.request.url[len(HOST):].split("#")[0].split("?")[0] or "index.html"
        f = (root / rel).resolve()
        if root not in f.parents and f != root or not f.is_file():
            route.fulfill(status=404, body="not found")
            return
        route.fulfill(status=200, body=f.read_bytes(), headers={"Content-Type": MIME.get(f.suffix, "application/octet-stream")})

    page.route(HOST + "**", handle)


def launch(p):
    args = ["--use-angle=d3d11", "--ignore-gpu-blocklist", "--enable-webgl"]
    b = p.chromium.launch(headless=True, args=args)
    pg = b.new_page()
    ok = pg.evaluate("() => !!document.createElement('canvas').getContext('webgl2')")
    pg.close()
    if ok:
        return b, "headless"
    b.close()
    b = p.chromium.launch(headless=False, args=args + ["--window-position=-4000,0", "--window-size=1920,1080"])
    return b, "headed off-screen"


def shots(page, base: str, out: Path, prefix: str, plan: list[tuple[str, str, str]]) -> list[Path]:
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("requestfailed", lambda r: errors.append(f"request failed: {r.url} {r.failure}"))
    made = []
    for name, url, size in plan:
        w, h = SIZES[size]
        page.set_viewport_size({"width": w, "height": h})
        page.goto(f"{base}{url}")
        try:
            page.wait_for_function("() => window.__app && (window.__app.ready || window.__app.error)", timeout=20000)
        except Exception:
            raise SystemExit(f"{name} {size}: app did not report ready; " + " | ".join(errors[:20]))
        page.wait_for_timeout(900)
        path = out / f"{prefix}{name}_{size}.png"
        page.screenshot(path=str(path))
        made.append(path)
    if errors:
        raise SystemExit("console errors:\n" + "\n".join(errors[:20]))
    return made


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args(argv)
    if a.mock:
        served, base = ROOT, HOST + "docs/design/"
        out, prefix = ROOT / "docs" / "design", "mock_"
        plan = [(v, f"mockup.html#{v}", s) for v in ["cockpit", "range", "ledger"] for s in SIZES]
    else:
        served, base = ROOT / "app", HOST
        out, prefix = ROOT / "artifacts" / "cp05", "shell_"
        plan = [(f"gimbal_{v}", f"#/gimbal/{v}?f=719&v=fov035&w=1.00&h=H-BAL", s) for v in VIEWS for s in SIZES]
        plan += [("gofast_cockpit", "#/gofast/cockpit?f=701", "1440"), ("gofast_range", "#/gofast/range?f=701", "1440"),
                 ("flir1_cockpit", "#/flir1/cockpit?f=600", "1440"), ("gimbal_weight0", "#/gimbal/ledger?f=513&v=fov070&w=0.00&h=H-WIT", "1440")]
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b, mode = launch(p)
        page = b.new_page()
        route_files(page, served)
        made = shots(page, base, out, prefix, plan)
        b.close()
    print(f"{mode}: {len(made)} screenshots")
    for m in made:
        print(" ", m.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
