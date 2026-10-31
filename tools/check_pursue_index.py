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
    return 1 if len(dups) else 0


if __name__ == "__main__":
    sys.exit(main())
