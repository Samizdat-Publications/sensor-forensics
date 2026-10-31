"""Download the official PURSUE video zips (war.gov/UFO), one at a time, with resume.

Then hash each zip, extract the clips into data/pursue/raw/<release>/, hash and
ffprobe every clip, record everything in data/pursue/downloads.json
(committed), and delete the zip once its hash and contents are recorded.

Slow or flaky network is expected: curl resumes partial files (-C -) and the
loop retries each zip until it succeeds or MAX_TRIES is hit. Safe to re-run.

Usage:
    python tools/pursue_fetch.py                 # all releases
    python tools/pursue_fetch.py --only R01 R05  # a subset
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "pursue" / "raw"
LOG = ROOT / "data" / "pursue" / "downloads.json"
CF = "https://d34w7g4gy10iej.cloudfront.net/"

# Official zip links from the war.gov/UFO page, as of 10/30/2026. Release 07 has no videos.
RELEASES = {
    "R05": CF + "release_05/uap_videos_080726.zip",      # 513 MB, smallest first
    "R01": CF + "uapvideos.zip",                         # 1.3 GB
    "R04": CF + "release_04/uap_release04_videos_071026.zip",  # 1.4 GB
    "R06": CF + "release_06/pursue_vids_091826.zip",     # 1.4 GB
    "R03": CF + "release_03/uap_videos_061226.zip",      # 4.6 GB
    "R02": CF + "uap052226.zip",                         # 5.6 GB
}
MAX_TRIES = 200
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".wmv", ".mpg", ".mkv", ".webm"}


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def remote_size(url: str) -> int | None:
    out = subprocess.run(["curl", "-sIL", "-m", "60", url], capture_output=True, text=True)
    size = None
    for line in out.stdout.splitlines():
        if line.lower().startswith("content-length:"):
            size = int(line.split(":", 1)[1].strip())
    return size


def ffprobe(path: Path) -> dict:
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
           "stream=codec_name,width,height,r_frame_rate,nb_frames,duration",
           "-show_entries", "format=duration,size", "-of", "json", str(path)]
    out = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(out.stdout) if out.returncode == 0 else {"error": out.stderr.strip()[-300:]}


def load_log() -> dict:
    return json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {"releases": {}}


def save_log(log: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")


def fetch(rel: str, url: str, log: dict) -> None:
    entry = log["releases"].get(rel, {})
    if entry.get("status") == "extracted":
        print(f"{rel}: already extracted")
        return
    RAW.mkdir(parents=True, exist_ok=True)
    zpath = RAW / f"{rel}.zip"
    expected = remote_size(url)
    for attempt in range(1, MAX_TRIES + 1):
        have = zpath.stat().st_size if zpath.exists() else 0
        if expected and have == expected:
            break
        print(f"{rel}: attempt {attempt}, have {have / 1e6:.0f} of {(expected or 0) / 1e6:.0f} MB", flush=True)
        subprocess.run(["curl", "-sSL", "--fail", "-C", "-", "--retry", "5", "--retry-delay", "10",
                        "--speed-limit", "1000", "--speed-time", "120", "-o", str(zpath), url])
        if expected is None:
            expected = remote_size(url)
        time.sleep(5)
    else:
        log["releases"][rel] = {"url": url, "status": "failed", "when": now()}
        save_log(log)
        return

    zhash = sha256(zpath)
    out_dir = RAW / rel
    out_dir.mkdir(exist_ok=True)
    clips = []
    with zipfile.ZipFile(zpath) as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError(f"{rel}: corrupt member {bad}")
        for info in z.infolist():
            if info.is_dir():
                continue
            name = Path(info.filename).name
            if Path(name).suffix.lower() not in VIDEO_EXT:
                continue
            dest = out_dir / name
            with z.open(info) as src, dest.open("wb") as dst:
                while chunk := src.read(1 << 20):
                    dst.write(chunk)
            clips.append({"member": info.filename, "file": f"{rel}/{name}", "sha256": sha256(dest),
                          "bytes": dest.stat().st_size, "ffprobe": ffprobe(dest)})
    log["releases"][rel] = {"url": url, "zip_bytes": zpath.stat().st_size, "zip_sha256": zhash,
                            "retrieved": now(), "status": "extracted", "n_clips": len(clips), "clips": clips}
    save_log(log)
    zpath.unlink()
    print(f"{rel}: extracted {len(clips)} clips, zip deleted (sha256 {zhash[:12]}...)", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    log = load_log()
    for rel, url in RELEASES.items():
        if args.only and rel not in args.only:
            continue
        fetch(rel, url, log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
