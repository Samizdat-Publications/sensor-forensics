"""Fetch the Navy videos from public sources, hash them, and write a manifest.

Each video has an ordered list of candidate sources. The first source that
returns a real video file wins; every attempt is logged in the manifest so the
provenance is auditable. Plain requests only: no header spoofing, no bot-check
workarounds. Files can also be dropped by hand into data/videos/inbox/ (for
example downloaded in a browser by Stewart); they are ingested and hashed the
same way, with provenance "manual drop".

Usage:
    python tools/fetch_videos.py            # try every missing video
    python tools/fetch_videos.py --ingest   # only ingest files in the inbox
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEOS = ROOT / "data" / "videos"
INBOX = VIDEOS / "inbox"
MANIFEST = VIDEOS / "MANIFEST.json"

NAVAIR = "https://www.navair.navy.mil/foia/sites/g/files/jejdrs566/files/2020-04/"
WAYBACK = "https://web.archive.org/web/2020id_/"

# name -> (local filename, ordered candidate sources, provenance label per source)
CATALOG: dict[str, dict] = {
    "gimbal_navy2020": {
        "file": "GIMBAL_navy2020.wmv",
        "video": "GIMBAL",
        "official": True,
        "sources": [
            ("NAVAIR FOIA 2020 release", NAVAIR + "2%20-%20GIMBAL.wmv"),
            ("Wayback copy of the NAVAIR file", WAYBACK + NAVAIR + "2%20-%20GIMBAL.wmv"),
        ],
        "inbox_names": ["2 - GIMBAL.wmv", "GIMBAL.wmv"],
    },
    "gofast_navy2020": {
        "file": "GOFAST_navy2020.wmv",
        "video": "GOFAST",
        "official": True,
        "sources": [
            ("NAVAIR FOIA 2020 release", NAVAIR + "3%20-%20GOFAST.wmv"),
            ("Wayback copy of the NAVAIR file", WAYBACK + NAVAIR + "3%20-%20GOFAST.wmv"),
        ],
        "inbox_names": ["3 - GOFAST.wmv", "GOFAST.wmv"],
    },
    "flir1_navy2020": {
        "file": "FLIR1_navy2020.mp4",
        "video": "FLIR1",
        "official": True,
        "sources": [
            ("NAVAIR FOIA 2020 release", NAVAIR + "1%20-%20FLIR.mp4"),
            ("Wayback copy of the NAVAIR file", WAYBACK + NAVAIR + "1%20-%20FLIR.mp4"),
        ],
        "inbox_names": ["1 - FLIR.mp4", "FLIR.mp4"],
    },
    "flir1_2007_f4": {
        "file": "FLIR1_2007_f4.mpg",
        "video": "FLIR1",
        "official": False,
        "sources": [
            ("2007 vision-unlimited.de copy via Wayback",
             "https://web.archive.org/web/20070209104330id_/http://www.vision-unlimited.de/extern/f4.mpg"),
        ],
        "inbox_names": ["f4.mpg", "F4.MPG"],
    },
}

VIDEO_MAGIC = (b"\x30\x26\xb2\x75", b"\x00\x00\x01\xba", b"\x00\x00\x01\xb3")  # ASF, MPEG-PS, MPEG-ES


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def looks_like_video(path: Path) -> bool:
    head = path.read_bytes()[:16]
    return head.startswith(VIDEO_MAGIC) or head[4:8] == b"ftyp"


def ffprobe(path: Path) -> dict:
    cmd = ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
           "-show_entries", "stream=codec_name,width,height,r_frame_rate,avg_frame_rate,nb_read_frames,duration",
           "-show_entries", "format=duration,size,format_name", "-of", "json", str(path)]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        return {"error": out.stderr.strip()[-500:]}
    return json.loads(out.stdout)


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"note": "Video files are gitignored; this manifest (hashes, sources, ffprobe) is committed.", "videos": {}}


def save_manifest(m: dict) -> None:
    MANIFEST.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")


def record(m: dict, key: str, spec: dict, path: Path, provenance: str, url: str | None, attempts: list) -> None:
    m["videos"][key] = {
        "video": spec["video"],
        "file": spec["file"],
        "official_copy": spec["official"],
        "provenance": provenance,
        "source_url": url,
        "retrieved": now(),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "ffprobe": ffprobe(path),
        "attempts": attempts,
    }


def try_download(url: str, dest: Path) -> tuple[bool, str]:
    tmp = dest.with_suffix(dest.suffix + ".part")
    cmd = ["curl", "-sSL", "--fail", "-m", "900", "-C", "-", "-o", str(tmp), url]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return False, f"curl exit {proc.returncode}: {proc.stderr.strip()[-200:]}"
    if not tmp.exists() or tmp.stat().st_size < 100_000 or not looks_like_video(tmp):
        size = tmp.stat().st_size if tmp.exists() else 0
        tmp.unlink(missing_ok=True)
        return False, f"not a video file ({size} bytes)"
    shutil.move(tmp, dest)
    return True, "ok"


def ingest_inbox(m: dict) -> None:
    if not INBOX.exists():
        return
    for key, spec in CATALOG.items():
        for name in spec["inbox_names"]:
            src = INBOX / name
            if src.exists():
                dest = VIDEOS / spec["file"]
                shutil.copy2(src, dest)
                record(m, key, spec, dest, f"manual drop ({name})", None,
                       [{"when": now(), "source": "inbox", "result": "ok"}])
                print(f"ingested {name} -> {spec['file']}")
                break


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ingest", action="store_true")
    args = ap.parse_args()
    VIDEOS.mkdir(parents=True, exist_ok=True)
    m = load_manifest()
    ingest_inbox(m)
    if not args.ingest:
        for key, spec in CATALOG.items():
            dest = VIDEOS / spec["file"]
            if key in m["videos"] and dest.exists():
                continue
            attempts = []
            for label, url in spec["sources"]:
                ok, msg = try_download(url, dest)
                attempts.append({"when": now(), "source": label, "url": url, "result": msg})
                print(f"{key}: {label}: {msg}")
                if ok:
                    record(m, key, spec, dest, label, url, attempts)
                    break
            else:
                m.setdefault("failed", {})[key] = attempts
    save_manifest(m)
    missing = [k for k, s in CATALOG.items() if k not in m["videos"]]
    print("missing:", missing or "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
