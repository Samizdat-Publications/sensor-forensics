"""Build the public landing site into site-dist/: the landing page (site/) at the root and the lab (app/) at /lab/.

Usage (from the repo root):
    .venv/Scripts/python tools/build_site.py            # build only
    .venv/Scripts/python tools/build_site.py --deploy   # build, then deploy to Cloudflare Pages

The lab's frame sequences (app/data/frames/, not in git) come from tools/build_app_data.py; the landing media from
tools/showcase_media.py. finish-site.mjs is the showcase kit's: it writes _headers and _routes.json, the byte-range
sizes for functions/media/, and fails on any file over Cloudflare's 25 MiB limit.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site-dist"
KIT = Path(r"C:\Users\stewa\Documents\Claude\Github Hub\kit")
PROJECT = "sensor-forensics"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--deploy", action="store_true")
    a = ap.parse_args(argv)
    frames = ROOT / "app" / "data" / "frames"
    for case in ("gimbal", "gofast", "flir1"):
        if not any((frames / case).glob("f*.jpg")):
            raise SystemExit(f"missing {frames / case}: run tools/build_app_data.py first")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "site", OUT)
    shutil.copytree(ROOT / "app", OUT / "lab", ignore=shutil.ignore_patterns("__pycache__", "*.map"))
    subprocess.run(["node", str(KIT / "tools" / "finish-site.mjs"), str(OUT), "--root", str(ROOT)], check=True)
    if a.deploy:
        subprocess.run(["npx", "--yes", "wrangler@4", "pages", "deploy", str(OUT), "--project-name", PROJECT,
                        "--branch", "main", "--commit-dirty=true"], check=True, shell=sys.platform == "win32")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
