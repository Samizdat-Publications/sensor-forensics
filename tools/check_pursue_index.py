"""Sanity checks for data/pursue/index.csv: counts per release and agency, duplicate IDs."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    df = pd.read_csv(ROOT / "data" / "pursue" / "index.csv", dtype=str)
    print(f"total videos: {len(df)}")
    print("per release:", dict(sorted(Counter(df["release"]).items())))
    print("per agency:", dict(Counter(df["agency"])))
    dups = df[df.duplicated("clip_id", keep=False)]
    print("duplicate clip_id:", list(dups["clip_id"]) or "none")
    shared = df[df.duplicated("dvids_id", keep=False)]
    print("shared dvids_id:", list(shared["clip_id"]) or "none")
    bad = len(dups)
    triage_path = ROOT / "data" / "pursue" / "triage.csv"
    if triage_path.exists():
        tr = pd.read_csv(triage_path, dtype=str)
        counts = tr["clip_id"].value_counts()
        missing = sorted(set(df["clip_id"]) - set(tr["clip_id"]))
        extra = sorted(set(tr["clip_id"]) - set(df["clip_id"]))
        twice = sorted(counts[counts > 1].index)
        print(f"triage rows: {len(tr)}; missing {missing or 'none'}; not in index {extra or 'none'}; "
              f"duplicated {twice or 'none'}")
        print("tiers:", dict(Counter(tr["tier"])))
        bad += len(missing) + len(extra) + len(twice)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
