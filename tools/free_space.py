"""Free disk space taken by working files that the lab, the tests and the results no longer need. Every item is
gitignored and can be rebuilt (see "Bring back" below). A dry run by default: it lists what it would remove and how
much; pass --delete to remove it.

Usage (from the repo root):
    .venv/Scripts/python tools/free_space.py            # list only
    .venv/Scripts/python tools/free_space.py --delete   # remove

What goes, and what stays:
- data/frames/dow-uap-*/      PNG frames extracted from the PURSUE clips for the M5 analysis. The results are in
                              data/derived/pursue/ (committed); nothing reads these frames now.
- data/pursue/raw/ clips outside the Bounded tier   the 118 Not viable clips (and any copy not mapped to a clip):
                              triaged, never analyzed. The 16 Bounded clips stay (the 8 analyzed and the 8 deferred
                              under D-013), so the M5 work can be redone or extended without a download.
- data/pursue/sheets/         contact sheets for triage.
- artifacts/tmp/              scratch output.
Stays: the Navy frames (data/frames/gimbal, gofast, flir1_navy, flir1_f4: the app build and tests/test_app_video.py
use them), the Navy videos, the app's JPEGs and videos, the recording frames under artifacts/movies/frames (the landing
clips are cut from them), and everything in git.

Bring back:
- PURSUE clips: tools/pursue_fetch.py downloads the official release zips again (hashes in data/pursue/file_map.csv).
- PURSUE frames: .venv/Scripts/python -m extract.frames <clip.mp4> <dow-uap-prNNN>
- Contact sheets: tools/contact_sheet.py
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def size(p: Path) -> int:
    return p.stat().st_size if p.is_file() else sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def targets() -> list[Path]:
    out = sorted((ROOT / "data" / "frames").glob("dow-uap-*"))
    raw = ROOT / "data" / "pursue" / "raw"
    if raw.exists():
        tiers = {r["clip_id"]: r["tier"] for r in csv.DictReader(open(ROOT / "data" / "pursue" / "triage.csv", encoding="utf-8"))}
        fmap = {r["clip_id"]: r["file"] for r in csv.DictReader(open(ROOT / "data" / "pursue" / "file_map.csv", encoding="utf-8"))}
        keep = {(raw / fmap[c]).resolve() for c, t in tiers.items() if t == "Bounded" and c in fmap}
        missing = [p for p in keep if not p.exists()]
        if missing:
            raise SystemExit(f"a Bounded clip is missing ({missing[0]}); stopping so nothing it depends on is touched")
        out += sorted(p for p in raw.rglob("*") if p.is_file() and p.resolve() not in keep)
    for d in (ROOT / "data" / "pursue" / "sheets", ROOT / "artifacts" / "tmp"):
        if d.exists():
            out.append(d)
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--delete", action="store_true", help="remove the files (default: list only)")
    a = ap.parse_args(argv)
    ts = targets()
    total = 0
    groups: dict[str, list[int]] = {}
    for p in ts:
        s = size(p)
        total += s
        rel = p.relative_to(ROOT).as_posix()
        key = "data/pursue/raw (clips outside the Bounded tier)" if rel.startswith("data/pursue/raw/") else rel
        g = groups.setdefault(key, [0, 0])
        g[0] += 1
        g[1] += s
    for k, (n, s) in groups.items():
        print(f"{s / 2**30:7.2f} GiB  {k}{f'  ({n} files)' if n > 1 else ''}")
    print(f"{total / 2**30:7.2f} GiB  in all")
    if not a.delete:
        print("Dry run: nothing removed. Run again with --delete to remove these.")
        return 0
    for p in ts:
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
    for d in sorted((ROOT / "data" / "pursue" / "raw").glob("**/"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    print(f"Removed {total / 2**30:.2f} GiB.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
