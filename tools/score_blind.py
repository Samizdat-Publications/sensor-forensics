"""Score the verifier's blind transcription against our per-frame readings (CP-02).

Input: artifacts/cp02/blind/<case>/verifier.csv with columns frame, field, value
(as typed from the raw-crop sheets made by sample_frames.py). Our side:
data/derived/<case>/symbology_final.csv. Both are normalized the same way
(degree signs, spaces, the Mach prefix, units, letter case) before comparing.
Rows the verifier marked '?' (unreadable to a person) are counted separately
and excluded from the error rate.

Output: artifacts/cp02/blind/<case>/score.json and a printed table:
per field, n compared, n errors, error rate, and the disagreeing frames.

Usage:
    python tools/score_blind.py gimbal gofast
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def norm(field: str, v: object) -> str:
    s = "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
    s = s.strip().upper().replace("°", "").replace(" ", "")
    if s in ("", "BLANK", "NAN", "NONE", "-"):
        return "blank"
    if field == "mach":
        s = re.sub(r"^[MW]", "", s)
    if field == "zoom":
        s = re.sub(r"^Z", "", s)
    if field == "range":
        s = s.replace("RNG", "")
    if field == "closure":
        s = re.sub(r"V[C]?$", "", s)
    if field == "altitude":
        s = re.sub(r"B$", "", s)
    if field == "azimuth":
        m = re.match(r"^(\d+)([LR])$", s)
        if m:
            s = f"{int(m.group(1))}{m.group(2)}"
    if field == "elevation":
        m = re.match(r"^(-?)0*(\d+)$", s)
        if m:
            s = f"{m.group(1)}{int(m.group(2))}"
    return s


def score(case: str, tag: str = "blind") -> dict:
    d = ROOT / "artifacts" / "cp02" / tag / case
    ver = pd.read_csv(d / "verifier.csv", dtype=str)
    ours = pd.read_csv(ROOT / "data" / "derived" / case / "symbology_final.csv", dtype=str)
    ours["frame"] = ours["frame"].astype(int)
    lookup = {(r.frame, r.field): r.value for r in ours.itertuples()}
    res: dict = {"case": case, "fields": {}, "unreadable_to_person": 0}
    for field, g in ver.groupby("field"):
        n = err = unread = 0
        bad = []
        for r in g.itertuples():
            v = str(r.value).strip()
            if v == "?":
                unread += 1
                continue
            a, b = norm(field, v), norm(field, lookup.get((int(r.frame), field)))
            n += 1
            if a != b:
                err += 1
                bad.append({"frame": int(r.frame), "verifier": a, "lab": b})
        res["fields"][field] = {"n": n, "errors": err, "error_rate": round(err / n, 4) if n else None,
                                "unreadable_to_person": unread, "disagreements": bad}
        res["unreadable_to_person"] += unread
    tot_n = sum(f["n"] for f in res["fields"].values())
    tot_e = sum(f["errors"] for f in res["fields"].values())
    res["overall"] = {"n": tot_n, "errors": tot_e, "error_rate": round(tot_e / tot_n, 4) if tot_n else None}
    (d / "score.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    return res


def main() -> int:
    args = sys.argv[1:]
    tag = "blind"
    if args and args[0].startswith("--tag="):
        tag = args.pop(0).split("=", 1)[1]
    for case in args:
        r = score(case, tag)
        print(f"{case}: overall {r['overall']['errors']}/{r['overall']['n']} = {r['overall']['error_rate']}"
              f" (unreadable to a person: {r['unreadable_to_person']})")
        for f, v in r["fields"].items():
            print(f"  {f:10s} {v['errors']:3d}/{v['n']:3d}  {v['error_rate']}  {[x['frame'] for x in v['disagreements']][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
