"""FLIR1 symbology reading with the 2007 copy as a cross-check (M1, FLIR1).

    python -m extract.flir1_read            # align copies, read both, write outputs
    python -m extract.flir1_read --skip-f4  # official copy only

The official NAVAIR copy (flir1_navy, 352x264, H.264) is read with extract/symbology.py and
its FLIR1 templates (extract/templates/flir1_navy/, cells upsampled 4x). The 2007 copy
(flir1_f4, 352x240, MPEG-1, an independent encode of the same footage) is used only to
resolve readings that stay low confidence in the official copy:

1. Geometry: the 2007 copy is the same picture squeezed vertically (y_f4 = 0.9091 y_navy,
   ECC affine fit on frame pairs 300/299, 1300/1298, 2000/1997, residual shear < 3e-4), so each
   of its frames is resized to 352x264 (bicubic) and read with the same cells and templates.
2. Frame alignment: the copies drift by up to 4 frames (different duplicate/drop patterns).
   Every official frame i is matched to a 2007 frame j(i) by dynamic programming over offsets
   -8..+4 (monotone, offset changes cost a penalty) on a per-frame signature: the white
   top-hat of the symbology rows (digit changes are sharp, frame-exact events) plus a coarse
   scene thumbnail. Output: copy_alignment.csv (frame, f4_frame, cost, second_best_cost).
3. Resolution: after the temporal filter, an official value with confidence < LOW_CONF is
   replaced by the 2007 copy's value at j(i) when that read is confident (>= LOW_CONF) and
   plausible next to the nearest confident official values (within the field's MAX_STEP of
   the previous or the next one). Method "template+f4copy"; confidence = the 2007 read's.
   Every 2007 read is kept in symbology_f4.csv with the agreement per field.

Outputs (data/derived/flir1_navy/): symbology.csv, symbology_summary.json (with an
"f4_crosscheck" block), symbology_f4.csv, copy_alignment.csv, symbology_sitrec_check.json.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np

from extract import symbology as sym

ROOT = Path(__file__).resolve().parents[1]
CASE = "flir1_navy"
COPY = "flir1_f4"
OUT = ROOT / "data" / "derived" / CASE
OFF_LO, OFF_HI = -8, 4
SWITCH_PENALTY = 0.15   # in units of the median per-frame signature cost


def f4_gray(j: int) -> np.ndarray:
    g = cv2.imread(str(sym.frame_path(COPY, j)), cv2.IMREAD_GRAYSCALE)
    if g is None:
        raise FileNotFoundError(sym.frame_path(COPY, j))
    return cv2.resize(g, (352, 264), interpolation=cv2.INTER_CUBIC)


sym.FRAME_LOADERS[COPY] = f4_gray


def n_copy_frames() -> int:
    return len(list((ROOT / "data" / "frames" / COPY).glob("f*.png")))


# Rows holding readouts (native official coordinates): top line, azimuth, zoom, elevation, bottom lines.
SIG_BANDS = [(16, 35), (75, 85), (121, 131), (226, 251)]


def signature(gray: np.ndarray) -> np.ndarray:
    th = sym.tophat(gray, 7)
    parts = [th[y0:y1, 60:300] for y0, y1 in SIG_BANDS]
    sym_part = np.concatenate([p.ravel() for p in parts]).astype(np.float32)
    scene = cv2.resize(gray[40:220, 60:290].astype(np.float32), (46, 36), interpolation=cv2.INTER_AREA)
    scene = (scene - scene.mean()).ravel()
    return np.concatenate([sym_part / max(float(sym_part.std()), 1.0), scene / max(float(scene.std()), 1.0)])


def align_copies(progress: bool = True) -> np.ndarray:
    n = sym.n_frames(CASE)
    m = n_copy_frames()
    A = np.array([signature(sym.read_gray(CASE, i)) for i in range(n)])
    B = np.array([signature(f4_gray(j)) for j in range(m)])
    K = OFF_HI - OFF_LO + 1
    C = np.full((n, K), np.inf)
    for k, o in enumerate(range(OFF_LO, OFF_HI + 1)):
        i = np.arange(n)
        j = i + o
        ok = (j >= 0) & (j < m)
        C[i[ok], k] = np.abs(A[i[ok]] - B[j[ok]]).mean(1)
    pen = SWITCH_PENALTY * float(np.median(np.min(C, 1)))
    D = np.full_like(C, np.inf)
    P = np.zeros(C.shape, int)
    D[0] = C[0]
    for i in range(1, n):
        for k in range(K):
            best, arg = np.inf, k
            for kk in (k - 1, k, k + 1):
                if 0 <= kk < K:
                    v = D[i - 1, kk] + (pen if kk != k else 0.0)
                    if v < best:
                        best, arg = v, kk
            D[i, k] = best + C[i, k]
            P[i, k] = arg
    k = int(np.argmin(D[-1]))
    path = [k]
    for i in range(n - 1, 0, -1):
        k = P[i, k]
        path.append(k)
    path = np.array(path[::-1])
    jmap = np.arange(n) + path + OFF_LO
    own = C[np.arange(n), path]
    second = np.sort(C, 1)
    with (OUT / "copy_alignment.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["frame", "f4_frame", "cost", "best_cost", "second_best_cost"])
        for i in range(n):
            w.writerow([i, int(jmap[i]), f"{own[i]:.4f}", f"{second[i, 0]:.4f}", f"{second[i, 1]:.4f}"])
    return jmap


def load_alignment() -> np.ndarray:
    with (OUT / "copy_alignment.csv").open(encoding="utf-8") as fh:
        return np.array([int(r["f4_frame"]) for r in csv.DictReader(fh)])


def plausible(name: str, v: str, ref: str | None, max_step: dict) -> bool:
    if ref is None:
        return True
    if name in ("sensor", "polarity", "fov"):
        return v == ref
    step = max_step.get(name, sym.MAX_STEP.get(name))
    a, b = sym.numeric(name, v), sym.numeric(name, ref)
    if step is None or a is None or b is None:
        return v == ref
    return abs(a - b) <= step + 1e-9


def make_resolver(f4_reads: dict[str, list], stats: dict):
    max_step = {**sym.MAX_STEP, **sym.MAX_STEP_CASE.get(CASE, {})}

    def resolve(name: str, frames: list[int], ser: sym.Series) -> sym.Series:
        fr4 = f4_reads[name]
        n = len(frames)
        conf_ok = [ser.conf[k] >= sym.LOW_CONF and ser.values[k] != "blank" for k in range(n)]
        prev_ok: list[str | None] = [None] * n
        last = None
        for k in range(n):
            prev_ok[k] = last
            if conf_ok[k]:
                last = ser.values[k]
        next_ok: list[str | None] = [None] * n
        last = None
        for k in range(n - 1, -1, -1):
            next_ok[k] = last
            if conf_ok[k]:
                last = ser.values[k]
        st = {"low_before": 0, "resolved": 0, "agree_all": 0, "compared_all": 0, "agree_confident_both": 0,
              "compared_confident_both": 0}
        for k in range(n):
            r4 = fr4[k]
            if ser.values[k] != "blank" and r4.value != "blank":
                st["compared_all"] += 1
                st["agree_all"] += int(r4.value == ser.values[k])
                if conf_ok[k] and r4.confidence >= sym.LOW_CONF:
                    st["compared_confident_both"] += 1
                    st["agree_confident_both"] += int(r4.value == ser.values[k])
            if ser.values[k] == "blank" or conf_ok[k]:
                continue
            st["low_before"] += 1
            if r4.confidence >= sym.LOW_CONF and r4.value not in ("blank", "?") and "?" not in r4.value:
                if plausible(name, r4.value, prev_ok[k], max_step) or plausible(name, r4.value, next_ok[k], max_step):
                    ser.values[k] = r4.value
                    ser.conf[k] = float(r4.confidence)
                    ser.method[k] = "template+f4copy"
                    st["resolved"] += 1
        stats[name] = st
        return ser

    return resolve


def run(skip_f4: bool = False, realign: bool = True) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    resolver = None
    stats: dict = {}
    f4_rows = []
    if not skip_f4:
        jmap = align_copies() if realign or not (OUT / "copy_alignment.csv").exists() else load_alignment()
        lib = sym.Library.load(sym.template_dir(CASE))
        layout = sym.load_layout(CASE)
        _, reads4 = sym.read_case(COPY, lib=lib, frames=[int(j) for j in jmap])
        for name in layout:
            for i, (j, r) in enumerate(zip(jmap, reads4[name])):
                f4_rows.append({"frame": i, "f4_frame": int(j), "field": name, "value": r.value, "raw": r.raw,
                                "confidence": f"{r.confidence:.4f}"})
        resolver = make_resolver(reads4, stats)
        with (OUT / "symbology_f4.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["frame", "f4_frame", "field", "value", "raw", "confidence"],
                               lineterminator="\n")
            w.writeheader()
            w.writerows(sorted(f4_rows, key=lambda r: (r["frame"], list(layout).index(r["field"]))))
    summary = sym.run_case(CASE, use_ocr=False, progress=True, resolver=resolver)
    if not skip_f4:
        summary["f4_crosscheck"] = {
            "note": ("2007 copy (flir1_f4) resized to 352x264, frame-aligned by DP (copy_alignment.csv), read with "
                     "the same cells and templates. low_before: official values below LOW_CONF after the temporal "
                     "filter; resolved: replaced by a confident, plausible 2007 read (method template+f4copy). "
                     "agree_*: official vs 2007 values on all non-blank frames, and on frames where both are confident."),
            "fields": stats,
        }
        (OUT / "symbology_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    return summary


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--skip-f4", action="store_true")
    ap.add_argument("--keep-alignment", action="store_true", help="reuse copy_alignment.csv")
    a = ap.parse_args(argv)
    s = run(skip_f4=a.skip_f4, realign=not a.keep_alignment)
    for name, f in s["fields"].items():
        print(f"{name:10s} blank {f['blank']:4d} low {f['low_confidence']:4d} ({f['low_confidence_frac']:.3f}) "
              f"repaired {f['repaired_temporal']:3d} f4 {f.get('resolved_f4copy', 0):3d} changes {f['n_changes']:3d} "
              f"{f['first_value']} -> {f['last_value']}")
    chk = sym.sitrec_crosscheck(CASE)
    if chk:
        for name, e in chk["fields"].items():
            print(f"sitrec {name}: offset {e['best_offset']:+d}, agreement {e['agreement']:.4f} over {e['frames_compared']} frames")


if __name__ == "__main__":
    main()
