"""Apply manual corrections to the per-frame symbology readings (M1.5).

    python -m extract.merge <case>

Reads data/derived/<case>/symbology.csv and data/derived/<case>/corrections.json (optional) and
writes data/derived/<case>/symbology_final.csv. The solver reads only symbology_final.csv.

Rules:
  * a correction wins over the machine reading for its (frame, field);
  * corrected rows get method "manual" and confidence 1.0;
  * the machine value and confidence stay in previous_value and previous_confidence
    (both empty for rows that were never corrected);
  * a correction for a (frame, field) that has no machine row adds a row (previous_value empty).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

BASE_COLUMNS = ["frame", "field", "value", "raw", "confidence", "method"]
FINAL_COLUMNS = BASE_COLUMNS + ["previous_value", "previous_confidence"]


def derived_dir(case: str, data_root: Path | None = None) -> Path:
    return Path(data_root if data_root is not None else ROOT / "data") / "derived" / case


def read_corrections(path: Path) -> list[dict]:
    """The corrections list, or [] when the file does not exist yet."""
    path = Path(path)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON list of corrections")
    return data


def read_symbology(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    df["frame"] = df["frame"].astype(int)
    df["confidence"] = df["confidence"].astype(float)
    return df


def merge(case: str, derived: Path | None = None) -> pd.DataFrame:
    """Symbology with corrections applied. `derived` overrides data/derived/<case>."""
    d = Path(derived) if derived is not None else derived_dir(case)
    df = read_symbology(d / "symbology.csv")
    df["previous_value"] = ""
    df["previous_confidence"] = ""
    corrections = read_corrections(d / "corrections.json")

    index = {(int(f), str(n)): i for i, (f, n) in enumerate(zip(df["frame"], df["field"]))}
    extra = []
    for c in corrections:
        key = (int(c["frame"]), str(c["field"]))
        value = str(c["value"])
        if key in index:
            i = index[key]
            df.at[df.index[i], "previous_value"] = df.at[df.index[i], "value"]
            df.at[df.index[i], "previous_confidence"] = f"{df.at[df.index[i], 'confidence']:.4f}"
            df.at[df.index[i], "value"] = value
            df.at[df.index[i], "confidence"] = 1.0
            df.at[df.index[i], "method"] = "manual"
        else:
            extra.append({"frame": key[0], "field": key[1], "value": value, "raw": "",
                          "confidence": 1.0, "method": "manual",
                          "previous_value": "", "previous_confidence": ""})
    if extra:
        df = pd.concat([df, pd.DataFrame(extra)], ignore_index=True)
        df = df.sort_values("frame", kind="mergesort").reset_index(drop=True)
    return df[FINAL_COLUMNS]


def write_final(case: str, derived: Path | None = None) -> Path:
    d = Path(derived) if derived is not None else derived_dir(case)
    df = merge(case, d)
    out = d / "symbology_final.csv"
    df.to_csv(out, index=False, float_format="%.4f", encoding="utf-8")
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("case")
    ap.add_argument("--data-root", type=Path, default=None, help="default: <repo>/data")
    a = ap.parse_args(argv)
    d = derived_dir(a.case, a.data_root)
    out = write_final(a.case, d)
    df = merge(a.case, d)
    n_manual = int((df["method"] == "manual").sum())
    print(f"{a.case}: {len(df)} rows, {n_manual} manual -> {out}")


if __name__ == "__main__":
    main()
