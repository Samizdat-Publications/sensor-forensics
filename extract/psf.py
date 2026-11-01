"""Point-spread width per video (REVIEW-M3 item 4; D-016's resolved / unresolved test).

Three measurements per video, each a bound on the point-spread function (PSF) of the whole
chain (pod optics, detector, display and the recording / compression chain), as a full width at
half maximum (FWHM, display px):

1. Symbology line spread (LOWER bound on the recording chain alone). The display symbology is
   drawn after the optics, so the cross profile of its thin persistent strokes measures only the
   display and recording chain. Profiles are taken across long horizontal and vertical strokes of
   the persistent symbology (median white top-hat over the clip), background-subtracted, on 40
   frames; the median FWHM is reported. The scene PSF can only be wider than the chain's.
2. The tracked object's own minor axis (UPPER bound). The half-maximum minor axis of the blob
   (image_track.csv obj_hi_minor_px, the full axis of the uniform ellipse with the same second
   moments at half maximum, about 1.09 FWHM for a Gaussian), median over unsaturated scored
   frames (extract.frame_levels). A real object can only widen the PSF.
3. The same pod's unresolved point source in another video, carried over by the documented
   zoom (UPPER bound, GIMBAL only). GOFAST's target (NAR at 1.0x, a few px) bounds the PSF at
   the pod's optical field; GIMBAL at NAR 2.0 is a 2x DIGITAL zoom of the same optical field
   (Peings and von Rennenkampff 2023, p. 8; docs/prior-work/peings-vonrennenkampff-2023.md), so
   its PSF in display px is twice GOFAST's when the field is 0.35 deg, and equal to it if the
   field were 0.7 deg (no digital zoom), the other field-of-view variant.

The widest PSF consistent with the measurements is the smallest upper bound. D-016 compares the
blob's major axis in the size criterion's own metric (low-threshold, 25 percent of peak, uniform-
ellipse axis), so that bound is converted to the same metric by passing synthetic Gaussian point
sources of that FWHM through extract.image_cues.blob_moments with the same threshold rule.

Compact scene features (local maxima of the high-passed picture) were examined too: on GIMBAL the
only high-contrast compact features lie on a straight moving track (symbology, not scene), and on
GOFAST they cannot be told apart from compression noise, so neither is used as a bound.

CLI: python -m extract.psf   (writes data/derived/gimbal/psf.json and data/derived/gofast/psf.json)
     python -m extract.psf flir1   (writes data/derived/flir1_navy/psf.json; see run_flir1)
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
import pandas as pd

from .image_cues import CASES, blob_moments, load_gray, white_tophat

ROOT = Path(__file__).resolve().parents[1]
ZOOM_DIGITAL = {"fov035": 2.0, "fov070": 1.0}   # GIMBAL NAR 2.0 as a 2x digital zoom (0.35 deg) or none (0.7 deg)


def _fwhm(prof: np.ndarray) -> float:
    """FWHM of a single-peaked profile (background removed), by linear interpolation of the half-max crossings."""
    p = np.asarray(prof, float)
    c = int(np.argmax(p))
    pk = p[c]
    if pk <= 0:
        return float("nan")
    half = 0.5 * pk
    l = c
    while l > 0 and p[l] > half:
        l -= 1
    r = c
    while r < len(p) - 1 and p[r] > half:
        r += 1
    if p[l] > half or p[r] > half:
        return float("nan")
    xl = l + (half - p[l]) / (p[l + 1] - p[l])
    xr = (r - 1) + (p[r - 1] - half) / (p[r - 1] - p[r])
    return float(xr - xl)


def symbology_lsf(case: str, n_frames: int = 40, min_run: int = 12, half: int = 5) -> dict:
    """Median FWHM across thin persistent symbology strokes (recording-chain line spread)."""
    n = CASES[case].n_frames
    frames = list(range(0, n, max(n // n_frames, 1)))[:n_frames]
    med = np.median(np.array([white_tophat(load_gray(case, f), 7, 7) for f in frames]), 0)
    stroke = med > 25
    out = {}
    for orient in ("horizontal", "vertical"):
        m = stroke if orient == "horizontal" else stroke.T
        # Seed rows/cols: runs of at least min_run stroke pixels along the stroke direction.
        seeds = []
        for i in range(half + 1, m.shape[0] - half - 1):
            row = m[i]
            j = 0
            while j < len(row):
                if row[j]:
                    k = j
                    while k < len(row) and row[k]:
                        k += 1
                    if k - j >= min_run:
                        seeds.append((i, j + 2, k - 2))
                    j = k
                else:
                    j += 1
        widths = []
        for f in frames:
            g = load_gray(case, f).astype(float)
            G = g if orient == "horizontal" else g.T
            for i, j0, j1 in seeds:
                # Only stroke centres (local maximum of the median top-hat across the stroke).
                M = med if orient == "horizontal" else med.T
                if not (M[i, j0:j1].mean() >= M[i - 1, j0:j1].mean() and M[i, j0:j1].mean() >= M[i + 1, j0:j1].mean()):
                    continue
                prof = G[i - half:i + half + 1, j0:j1].mean(axis=1)
                bg = 0.5 * (prof[0] + prof[-1])
                w = _fwhm(prof - bg)
                if np.isfinite(w) and 0.5 < w < 8:
                    widths.append(w)
        out[orient] = {"n_profiles": len(widths), "fwhm_px_median": float(np.median(widths)) if widths else None,
                       "fwhm_px_p25_p75": [float(np.percentile(widths, 25)), float(np.percentile(widths, 75))] if widths else None,
                       "n_strokes": len(seeds)}
    return out


def object_minor_bound(case: str) -> dict:
    """Median half-maximum minor axis of the tracked blob over unsaturated frames of the scored window."""
    import yaml

    cfg = yaml.safe_load((ROOT / "solve" / "cases" / f"{case}.yaml").read_text(encoding="utf-8"))
    t = pd.read_csv(ROOT / "data" / "derived" / case / "image_track.csv").sort_values("frame").reset_index(drop=True)
    fl = pd.read_csv(ROOT / "data" / "derived" / case / "frame_levels.csv").sort_values("frame").reset_index(drop=True)
    sym = pd.read_csv(ROOT / cfg["files"]["symbology"], dtype=str)
    fld = cfg["readouts"][cfg["track_window"]["field"]]["field"]
    win = set(sym[(sym["field"] == fld) & sym["value"].notna() & (sym["value"] != "")]["frame"].astype(int))
    ok = t["frame"].isin(win) & (t["obj_found"] == 1) & ~fl["blob_saturated"].astype(bool)
    v = t.loc[ok, "obj_hi_minor_px"].to_numpy(float)
    return {"n_frames": int(ok.sum()), "hi_minor_px_median": float(np.median(v)),
            "fwhm_upper_px": float(np.median(v)),
            "note": "half-maximum minor axis of the unsaturated blob; a real object only widens the PSF"}


def lo_metric(fwhm_px: float, n: int = 64, seed: int = 20261031) -> float:
    """Low-threshold (25 percent of peak) major axis of a Gaussian point source of the given FWHM,
    measured with extract.image_cues.blob_moments (the size criterion's own metric), averaged over
    random sub-pixel positions."""
    rng = np.random.default_rng(seed)
    s = fwhm_px / (2.0 * math.sqrt(2.0 * math.log(2.0)))
    R = int(math.ceil(4 * s)) + 3
    yy, xx = np.mgrid[-R:R + 1, -R:R + 1].astype(float)
    vals = []
    for _ in range(n):
        dx, dy = rng.uniform(-0.5, 0.5, 2)
        img = np.exp(-((xx - dx) ** 2 + (yy - dy) ** 2) / (2 * s * s))
        c = cv2.GaussianBlur(img.astype(np.float32), (0, 0), 0.7)   # the tracker's own 0.7 px smoothing for the mask
        comp = c > 0.25 * c.max()
        _, lab = cv2.connectedComponents(comp.astype(np.uint8), connectivity=8)
        pk = np.unravel_index(int(np.argmax(c)), c.shape)
        comp = lab == lab[pk]
        vals.append(blob_moments(img, comp)["major_px"])
    return float(np.mean(vals))


def run() -> dict:
    res = {}
    for case in ("gofast", "gimbal"):
        res[case] = {"symbology_line_spread": symbology_lsf(case), "object_minor": object_minor_bound(case)}
    gof_upper = res["gofast"]["object_minor"]["fwhm_upper_px"]
    for case in ("gofast", "gimbal"):
        r = res[case]
        sym = r["symbology_line_spread"]
        lows = [v["fwhm_px_median"] for v in sym.values() if v["fwhm_px_median"]]
        r["chain_fwhm_lower_px"] = float(min(lows)) if lows else None
        variants = {"": 1.0} if case == "gofast" else ZOOM_DIGITAL
        r["variants"] = {}
        for vname, zoom in variants.items():
            uppers = {"own_object_minor": r["object_minor"]["fwhm_upper_px"]}
            if case == "gimbal":
                uppers["gofast_point_source_x_digital_zoom"] = gof_upper * zoom
            up = min(uppers.values())
            r["variants"][vname or "default"] = {
                "digital_zoom": zoom, "upper_bounds_fwhm_px": uppers, "psf_fwhm_upper_px": up,
                "psf_width_px_lo_metric": lo_metric(up), "chain_fwhm_lower_px": r["chain_fwhm_lower_px"]}
        p = ROOT / "data" / "derived" / case / "psf.json"
        p.write_text(json.dumps(r, indent=1) + "\n", encoding="utf-8")
    return res


def run_flir1() -> dict:
    """FLIR1 (REVIEW-M3 Rule P applied to the third video, 11/01/2026).

    The field of view changes on screen (NAR 1.0x / 2.0x, a brief MFOV / WFOV), so every width is expressed in
    px at the case's reference field (NAR 1.0x, 0.7 deg): native px x fov(frame) / 0.7, the same conversion the
    case loader applies to the size series. Bounds:
      - symbology line spread: LOWER bound (recording chain), native px (symbology is not zoomed);
      - the object's own half-maximum minor axis, median over the scored, unsaturated frames where it is found
        (UPPER bound; the same rule as GIMBAL and GOFAST), in reference px; also reported per sensor;
      - GOFAST's point source is NOT carried over: FLIR1 is a different recording chain (a 2004 tape, 352 x 264
        copy), whose blur can be wider than GOFAST's, so that number does not bound FLIR1's PSF from above.
    """
    import yaml

    from solve.case_data import fov_per_frame

    case_dir = ROOT / "data" / "derived" / "flir1_navy"
    cfg = yaml.safe_load((ROOT / "solve" / "cases" / "flir1.yaml").read_text(encoding="utf-8"))
    n = int(cfg["n_frames"])
    t = pd.read_csv(case_dir / "image_track.csv").sort_values("frame").reset_index(drop=True)
    fl = pd.read_csv(case_dir / "frame_levels.csv").sort_values("frame").reset_index(drop=True)
    sym = pd.read_csv(ROOT / cfg["files"]["symbology"], dtype=str)
    sym["frame"] = sym["frame"].astype(int)
    fov = fov_per_frame(cfg, sym, n)
    scale = fov / float(cfg["sensor"]["fov_deg"])
    ok = (t["obj_found"] == 1).to_numpy() & ~fl["blob_saturated"].astype(bool).to_numpy() & np.isfinite(scale)
    for a, b in cfg["image"].get("exclude_frames", []) or []:
        ok[int(a):int(b) + 1] = False
    minor_ref = t["obj_hi_minor_px"].to_numpy(float) * scale
    sensor = sym[sym["field"] == "sensor"].set_index("frame")["value"].reindex(range(n)).astype(str).to_numpy()
    per_sensor = {s: {"n_frames": int((ok & (sensor == s)).sum()),
                      "hi_minor_ref_px_median": float(np.median(minor_ref[ok & (sensor == s)]))
                      if (ok & (sensor == s)).any() else None}
                  for s in sorted(set(sensor))}
    up = float(np.median(minor_ref[ok]))
    lsf = symbology_lsf("flir1_navy")
    lows = [v["fwhm_px_median"] for v in lsf.values() if v["fwhm_px_median"]]
    r = {"symbology_line_spread": lsf,
         "object_minor": {"n_frames": int(ok.sum()), "hi_minor_ref_px_median": up, "fwhm_upper_px": up,
                          "per_sensor": per_sensor,
                          "note": "half-maximum minor axis of the unsaturated blob, px at NAR 1.0x (0.7 deg); a real "
                                  "object only widens the PSF"},
         "chain_fwhm_lower_px": float(min(lows)) if lows else None,
         "reference_field": "px at NAR 1.0x (0.7 deg); native px x fov(frame) / 0.7",
         "not_used": "GOFAST point source: different recording chain, not an upper bound for FLIR1",
         "variants": {"default": {"digital_zoom": None, "upper_bounds_fwhm_px": {"own_object_minor": up},
                                  "psf_fwhm_upper_px": up, "psf_width_px_lo_metric": lo_metric(up),
                                  "chain_fwhm_lower_px": float(min(lows)) if lows else None}}}
    (case_dir / "psf.json").write_text(json.dumps(r, indent=1) + "\n", encoding="utf-8")
    return r


def main() -> int:
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "flir1":
        r = run_flir1()
        print(json.dumps({k: r[k] for k in ("object_minor", "chain_fwhm_lower_px", "variants")}, indent=1))
        return 0
    res = run()
    for case, r in res.items():
        print(case, json.dumps(r["variants"], indent=1), "chain lower", r["chain_fwhm_lower_px"],
              json.dumps(r["symbology_line_spread"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
