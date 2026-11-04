"""Build the public landing site into site-dist/: the landing page (site/) at the root and the lab (app/) at /lab/.

Usage (from the repo root):
    .venv/Scripts/python tools/build_site.py            # build only
    .venv/Scripts/python tools/build_site.py --deploy   # build, then deploy to Cloudflare Pages

The lab's frame sequences and playback videos (app/data/frames/, app/data/video/, not in git) come from
tools/build_app_data.py; the landing media from tools/showcase_media.py. finish-site.mjs is the showcase kit's: it
writes _headers and _routes.json, the byte-range sizes for functions/media/, and fails on any file over Cloudflare's
25 MiB limit. This script then adds the lab's own cache rules and sends the lab's videos through the same byte-range
function (functions/lab/data/video/), so Safari can play and seek them.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site-dist"
KIT = Path(r"C:\Users\stewa\Documents\Claude\Github Hub\kit")
PROJECT = "sensor-forensics"

# The lab's cache rules: frames, videos and three.js never change between builds; the JSON can, so it is
# revalidated after five minutes (served from cache meanwhile). Code (js, css, html) keeps Pages' default.
LAB_HEADERS = """
/lab/vendor/*
  Cache-Control: public, max-age=604800
/lab/data/frames/*
  Cache-Control: public, max-age=604800
/lab/data/video/*
  Cache-Control: public, max-age=604800
"""
JSON_RULE = "/lab/data/{case}/*\n  Cache-Control: public, max-age=300, stale-while-revalidate=86400\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--deploy", action="store_true")
    a = ap.parse_args(argv)
    data = ROOT / "app" / "data"
    cases = [c["case"] for c in json.loads((data / "index.json").read_text(encoding="utf-8"))["cases"]]
    for case in cases:
        if not any((data / "frames" / case).glob("f*.jpg")) or not (data / "video" / f"{case}.mp4").exists():
            raise SystemExit(f"missing frames or video for {case}: run tools/build_app_data.py first")
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(ROOT / "site", OUT)
    # predictions.json (every field of view, with test-only fields) stays out: the lab loads predictions_<variant>.json
    shutil.copytree(ROOT / "app", OUT / "lab", ignore=shutil.ignore_patterns("__pycache__", "*.map", "predictions.json"))
    subprocess.run(["node", str(KIT / "tools" / "finish-site.mjs"), str(OUT), "--root", str(ROOT)], check=True)

    with (OUT / "_headers").open("a", encoding="utf-8") as f:
        f.write(LAB_HEADERS + "".join(JSON_RULE.format(case=c) for c in cases))
    videos = sorted(f"/lab/data/video/{p.name}" for p in (OUT / "lab" / "data" / "video").glob("*.mp4"))
    routes_p = OUT / "_routes.json"
    routes = json.loads(routes_p.read_text(encoding="utf-8")) if routes_p.exists() else {"version": 1, "include": [], "exclude": []}
    routes["include"] = sorted(set(routes["include"]) | set(videos))
    routes_p.write_text(json.dumps(routes, indent=1), encoding="utf-8")
    sizes_p = ROOT / "functions" / "media" / "sizes.json"
    sizes = json.loads(sizes_p.read_text(encoding="utf-8")) if sizes_p.exists() else {}
    sizes.update({v: (OUT / v.lstrip("/")).stat().st_size for v in videos})
    sizes_p.write_text(json.dumps(sizes, indent=1) + "\n", encoding="utf-8")
    fn = ROOT / "functions" / "lab" / "data" / "video" / "[[path]].js"
    if not fn.exists():
        raise SystemExit(f"missing {fn}: the lab videos need the byte-range function")
    print(f"lab videos routed through the byte-range function: {', '.join(videos)}")

    if a.deploy:
        subprocess.run(["npx", "--yes", "wrangler@4", "pages", "deploy", str(OUT), "--project-name", PROJECT,
                        "--branch", "main", "--commit-dirty=true"], check=True, shell=sys.platform == "win32")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
