"""Testimony claims as likelihood terms (work item M3.3c; docs/design/scoring.md, Testimony row).

Inputs
------
- ``data/testimony/<case>.yaml``: the claims (one factual assertion each), validated by `load_claims`.
- ``data/testimony/scorable.yaml``: the hand-written mapping of every claim to what it constrains
  (a predicted quantity with an interval and uncertainty band, an on-screen readout, the environment,
  or context only), validated by `load_mapping`.

Interface for the scorer
------------------------
``testimony_loglik(case, predicted)`` takes a dict of predicted quantities (keys from the
vocabulary in scorable.yaml, the same keys for every model) and returns one row per scored term::

    {claim_id, quantity, predicted_value, interval, loglik, weight, firsthand, weighted_loglik}

The criterion's contribution is ``sum(weighted_loglik)`` (see `total`), multiplied by the
testimony weight from the scorer's settings (default 1.0; 0 gives the physics-only total).

This module never sees which model produced ``predicted``. It has no notion of model names:
unknown keys in ``predicted`` are rejected, so a label cannot be passed in by accident, and the
same numbers always give the same rows.

Likelihood
----------
Continuous quantities: a uniform density on the claim's interval [lo, hi] convolved with a
Gaussian edge of width sigma (the claim's uncertainty band)::

    p(x) = [Phi((hi - x) / sigma) - Phi((lo - x) / sigma)] / (hi - lo)     (lo < hi)
    p(x) = Normal(x; lo, sigma)                                            (lo == hi)

in the unit named by the quantity (log10 of it when the term says ``scale: log``). Flat inside
the interval, Gaussian tails outside it. Categorical quantities: probability 1 - e when the
prediction matches the claim and e when it does not (e = categorical_error_rate, one value for
all claims). Weight 1.0 for firsthand claims and 0.5 for relayed ones. A claim with several
terms contributes each; conflicting claims each contribute with their own interval.

``witness_consistency(case)`` compares claims about on-screen quantities (jet altitude and speed,
the range and closure fields, polarity, the object's contrast sign, the clip's duration) with the
lab's own readings. It tests memory against the record and never enters a hypothesis score.
"""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from scipy.special import log_ndtr

ROOT = Path(__file__).resolve().parents[1]
TESTIMONY_DIR = ROOT / "data" / "testimony"
DERIVED_DIR = ROOT / "data" / "derived"

CASES = {"gimbal": "G", "gofast": "F", "flir1": "T"}
EVENTS = {"GIMBAL", "GOFAST", "FLIR1"}

CLAIM_REQUIRED = {
    "id": str, "witness": str, "firsthand": bool, "firsthand_detail": str, "source": dict,
    "verification": str, "location_in_source": str, "claim": str, "quantity": str,
    "value": str, "uncertainty": str, "applies_to": list, "conflicts_with": list,
}
CLAIM_OPTIONAL = {"notes": str, "quote": str, "also_in": list}
SOURCE_KEYS = {"title", "outlet", "date", "url"}
ALSO_IN_KEYS = {"source", "url", "location_in_source", "verification", "note"}
USES = {"hypothesis", "witness_consistency", "environment", "context"}
KINDS = {"count", "class_statement", "other_event", "first_encounter", "outside_clip",
         "duplicate", "image_content", "location_or_time", "sensor_or_data", "role"}
REDUCERS = {"median", "mean", "min", "max", "first", "last"}


class TestimonyError(ValueError):
    """A claim file or the mapping table breaks the format."""


# ----------------------------------------------------------------------------- loading

def _case_key(case: str) -> str:
    key = case.lower()
    if key.startswith("flir1"):
        key = "flir1"
    if key not in CASES:
        raise TestimonyError(f"unknown case {case!r}; expected one of {sorted(CASES)}")
    return key


def validate_claims(claims: Any, case: str) -> list[dict]:
    """Check a parsed claim file; return it unchanged or raise TestimonyError."""
    key = _case_key(case)
    if not isinstance(claims, list) or not claims:
        raise TestimonyError(f"{key}: the claim file must be a non-empty list")
    pattern = re.compile(rf"^{CASES[key]}-T\d{{2,3}}$")
    seen: set[str] = set()
    for i, c in enumerate(claims):
        where = f"{key} claim #{i + 1}"
        if not isinstance(c, dict):
            raise TestimonyError(f"{where}: not a mapping")
        cid = c.get("id")
        where = f"{key} {cid}"
        missing = set(CLAIM_REQUIRED) - set(c)
        if missing:
            raise TestimonyError(f"{where}: missing fields {sorted(missing)}")
        extra = set(c) - set(CLAIM_REQUIRED) - set(CLAIM_OPTIONAL)
        if extra:
            raise TestimonyError(f"{where}: unknown fields {sorted(extra)}")
        for f, t in {**CLAIM_REQUIRED, **CLAIM_OPTIONAL}.items():
            if f in c and not isinstance(c[f], t):
                raise TestimonyError(f"{where}: field {f!r} must be {t.__name__}")
        if not pattern.match(cid):
            raise TestimonyError(f"{where}: id must match {pattern.pattern}")
        if cid in seen:
            raise TestimonyError(f"{where}: duplicate id")
        seen.add(cid)
        for f in ("witness", "claim", "quantity", "value", "uncertainty", "verification"):
            if not c[f].strip():
                raise TestimonyError(f"{where}: field {f!r} is empty")
        if set(c["source"]) != SOURCE_KEYS:
            raise TestimonyError(f"{where}: source must have exactly {sorted(SOURCE_KEYS)}")
        if not c["applies_to"] or not set(c["applies_to"]) <= EVENTS:
            raise TestimonyError(f"{where}: applies_to must be a non-empty subset of {sorted(EVENTS)}")
        if "quote" in c and len(c["quote"].split()) >= 15:
            raise TestimonyError(f"{where}: quote must be under 15 words")
        for a in c.get("also_in") or []:
            if not isinstance(a, dict) or set(a) != ALSO_IN_KEYS:
                raise TestimonyError(f"{where}: also_in entries need exactly {sorted(ALSO_IN_KEYS)}")
    by_id = {c["id"]: c for c in claims}
    for c in claims:
        for other in c["conflicts_with"]:
            if other == c["id"]:
                raise TestimonyError(f"{key} {c['id']}: conflicts with itself")
            if other not in by_id:
                raise TestimonyError(f"{key} {c['id']}: conflicts_with names unknown id {other}")
            if c["id"] not in by_id[other]["conflicts_with"]:
                raise TestimonyError(f"{key} {c['id']}: conflict with {other} is not symmetric")
    return claims


@lru_cache(maxsize=None)
def _load_claims_cached(path_str: str, key: str) -> tuple:
    with open(path_str, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return tuple(validate_claims(data, key))


def load_claims(case: str, path: Path | None = None) -> list[dict]:
    """Read and validate data/testimony/<case>.yaml (case: gimbal, gofast or flir1)."""
    key = _case_key(case)
    p = Path(path) if path is not None else TESTIMONY_DIR / f"{key}.yaml"
    return [dict(c) for c in _load_claims_cached(str(p), key)]


def _check_number(x, where: str, name: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise TestimonyError(f"{where}: {name} must be a finite number")
    return float(x)


def validate_mapping(mapping: Any, claims_by_case: dict[str, list[dict]]) -> dict:
    """Check scorable.yaml against the claim files; return it or raise TestimonyError."""
    if not isinstance(mapping, dict):
        raise TestimonyError("scorable.yaml must be a mapping")
    for f in ("weights", "categorical_error_rate", "quantities", "witness_quantities", "cases"):
        if f not in mapping:
            raise TestimonyError(f"scorable.yaml: missing {f!r}")
    w = mapping["weights"]
    if set(w) != {"firsthand", "relayed"}:
        raise TestimonyError("scorable.yaml: weights must have firsthand and relayed")
    eps = _check_number(mapping["categorical_error_rate"], "scorable.yaml", "categorical_error_rate")
    if not 0 < eps < 0.5:
        raise TestimonyError("scorable.yaml: categorical_error_rate must be in (0, 0.5)")
    vocab = mapping["quantities"]
    for q, spec in vocab.items():
        if spec.get("type") not in {"number", "bool", "category"}:
            raise TestimonyError(f"quantity {q}: type must be number, bool or category")
        if spec["type"] == "category" and not spec.get("values"):
            raise TestimonyError(f"quantity {q}: a category needs values")
    wvocab = mapping["witness_quantities"]
    env_vocab = set(mapping.get("environment_quantities", []))

    for key, claims in claims_by_case.items():
        if key not in mapping["cases"]:
            raise TestimonyError(f"scorable.yaml: no section for case {key}")
        entries = mapping["cases"][key].get("claims", {})
        ids = [c["id"] for c in claims]
        if set(entries) != set(ids):
            raise TestimonyError(
                f"scorable.yaml {key}: entries must match the claim ids exactly; "
                f"missing {sorted(set(ids) - set(entries))}, extra {sorted(set(entries) - set(ids))}")
        event = key.upper()
        by_id = {c["id"]: c for c in claims}
        for cid, e in entries.items():
            where = f"scorable.yaml {cid}"
            for f in ("firsthand", "scorable", "use", "why"):
                if f not in e:
                    raise TestimonyError(f"{where}: missing {f!r}")
            if e["firsthand"] is not by_id[cid]["firsthand"]:
                raise TestimonyError(f"{where}: firsthand differs from the claim file")
            use = set(e["use"])
            if not use or not use <= USES:
                raise TestimonyError(f"{where}: use must be a non-empty subset of {sorted(USES)}")
            if not str(e["why"]).strip():
                raise TestimonyError(f"{where}: why is empty")
            if bool(e["scorable"]) != ("hypothesis" in use):
                raise TestimonyError(f"{where}: scorable must be true exactly when use includes hypothesis")
            if ("terms" in e) != ("hypothesis" in use):
                raise TestimonyError(f"{where}: terms must be present exactly when scorable")
            if ("witness" in e) != ("witness_consistency" in use):
                raise TestimonyError(f"{where}: witness entries must be present exactly when use includes witness_consistency")
            if ("environment" in e) != ("environment" in use):
                raise TestimonyError(f"{where}: environment entries must be present exactly when use includes environment")
            if not e["scorable"] and e.get("kind") not in KINDS:
                raise TestimonyError(f"{where}: a claim that is not scored needs kind in {sorted(KINDS)}")
            if e["scorable"] and event not in by_id[cid]["applies_to"]:
                raise TestimonyError(f"{where}: scored for {event} but the claim does not apply to it")
            for t in e.get("terms", []):
                g = t.get("given")
                if g is not None:
                    if not isinstance(g, dict) or set(g) != {"quantity", "value"} or g["quantity"] not in vocab                             or vocab[g["quantity"]]["type"] != "bool" or not isinstance(g["value"], bool):
                        raise TestimonyError(f"{where}: given must be {{quantity: <bool quantity>, value: true|false}}")
                qs = t.get("quantity")
                qlist = qs if isinstance(qs, list) else [qs]
                if not qlist or any(q not in vocab for q in qlist):
                    raise TestimonyError(f"{where}: unknown quantity {qs!r}")
                types = {vocab[q]["type"] for q in qlist}
                if len(types) != 1:
                    raise TestimonyError(f"{where}: a mixture must use quantities of one type")
                qtype = types.pop()
                if qtype == "number":
                    lo = _check_number(t.get("lo"), where, "lo")
                    hi = _check_number(t.get("hi"), where, "hi")
                    sg = _check_number(t.get("sigma"), where, "sigma")
                    if lo > hi or sg <= 0:
                        raise TestimonyError(f"{where}: need lo <= hi and sigma > 0")
                    if t.get("scale", "linear") not in {"linear", "log"}:
                        raise TestimonyError(f"{where}: scale must be linear or log")
                    if t.get("scale") == "log" and lo <= 0:
                        raise TestimonyError(f"{where}: a log-scale interval needs lo > 0")
                    if t.get("reduce", "median") not in REDUCERS:
                        raise TestimonyError(f"{where}: reduce must be one of {sorted(REDUCERS)}")
                elif qtype == "bool":
                    if not isinstance(t.get("value"), bool):
                        raise TestimonyError(f"{where}: a bool term needs value true or false")
                else:
                    allowed = set(vocab[qlist[0]]["values"])
                    if t.get("value") not in allowed:
                        raise TestimonyError(f"{where}: value must be one of {sorted(allowed)}")
            for wt in e.get("witness", []):
                q = wt.get("quantity")
                if q not in wvocab:
                    raise TestimonyError(f"{where}: unknown witness quantity {q!r}")
                if "value" in wt:
                    continue
                lo = _check_number(wt.get("lo"), where, "lo")
                hi = _check_number(wt.get("hi"), where, "hi")
                tol = _check_number(wt.get("tol"), where, "tol")
                if lo > hi or tol < 0:
                    raise TestimonyError(f"{where}: witness needs lo <= hi and tol >= 0")
            for et in e.get("environment", []):
                if et.get("quantity") not in env_vocab:
                    raise TestimonyError(f"{where}: unknown environment quantity {et.get('quantity')!r}")
    return mapping


@lru_cache(maxsize=None)
def _load_mapping_cached(path_str: str) -> dict:
    with open(path_str, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    claims = {k: load_claims(k) for k in CASES}
    return validate_mapping(data, claims)


def load_mapping(path: Path | None = None) -> dict:
    """Read and validate data/testimony/scorable.yaml against all three claim files."""
    p = Path(path) if path is not None else TESTIMONY_DIR / "scorable.yaml"
    return _load_mapping_cached(str(p))


# ----------------------------------------------------------------------------- likelihood

# Lab decision D-015: floor on the Gaussian edge width for recalled quantities.
MEMORY_SIGMA_FLOOR = 0.25

def interval_logpdf(x: float, lo: float, hi: float, sigma: float) -> float:
    """Log density of a uniform on [lo, hi] convolved with Normal(0, sigma), at x.

    Stable far into the tails (uses log Phi). For lo == hi it is the Gaussian log density.
    """
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    if lo > hi:
        raise ValueError("need lo <= hi")
    x = float(x)
    if not math.isfinite(x):
        return -math.inf
    width = hi - lo
    if width <= 1e-12 * max(1.0, abs(lo), abs(hi)):
        z = (x - lo) / sigma
        return -0.5 * z * z - math.log(sigma) - 0.5 * math.log(2.0 * math.pi)
    a = (lo - x) / sigma
    b = (hi - x) / sigma
    # log(Phi(b) - Phi(a)), b > a; use the upper tail when both are positive.
    if a > 0:
        la, lb = log_ndtr(-b), log_ndtr(-a)   # Phi(-b) < Phi(-a)
    else:
        la, lb = log_ndtr(a), log_ndtr(b)
    diff = lb + math.log1p(-math.exp(la - lb)) if la < lb else -math.inf
    return float(diff - math.log(width))


def _reduce(value, how: str) -> float:
    arr = np.asarray(value, dtype=float).ravel()
    if arr.size == 0:
        raise TestimonyError("an empty prediction array cannot be reduced")
    if arr.size == 1:
        return float(arr[0])
    arr = arr[np.isfinite(arr)] if how not in {"first", "last"} else arr
    if arr.size == 0:
        return math.nan
    return float({"median": np.median, "mean": np.mean, "min": np.min, "max": np.max,
                  "first": lambda v: v[0], "last": lambda v: v[-1]}[how](arr))


def _categorical_loglik(pred, value, eps: float) -> float:
    if isinstance(value, bool):
        if isinstance(pred, (bool, np.bool_)):
            p_true = 1.0 if pred else 0.0
        else:
            p_true = float(pred)
            if not 0.0 <= p_true <= 1.0:
                raise TestimonyError("a bool prediction must be true, false or a probability")
        p_match = p_true if value else 1.0 - p_true
        return math.log(p_match * (1.0 - eps) + (1.0 - p_match) * eps)
    return math.log(1.0 - eps) if pred == value else math.log(eps)


def required_quantities(case: str) -> list[str]:
    """Quantities used by this case's scored claims: pass all of them for every model."""
    key = _case_key(case)
    entries = load_mapping()["cases"][key]["claims"]
    out: set[str] = set()
    for e in entries.values():
        for t in e.get("terms", []):
            q = t["quantity"]
            out.update(q if isinstance(q, list) else [q])
    return sorted(out)


def _check_predicted(predicted: dict, vocab: dict) -> None:
    if not isinstance(predicted, dict):
        raise TestimonyError("predicted must be a dict of quantity -> value")
    unknown = set(predicted) - set(vocab)
    if unknown:
        raise TestimonyError(
            f"predicted has keys outside the quantity vocabulary: {sorted(unknown)} "
            f"(allowed: {sorted(vocab)}); this module takes quantities only, never labels")


def testimony_loglik(case: str, predicted: dict, missing: str = "skip") -> list[dict]:
    """Likelihood rows for every scored claim term whose quantity is in ``predicted``.

    predicted: quantity -> scalar, per-frame array (reduced by the term's ``reduce``), bool or
    category, keys from scorable.yaml ``quantities``. missing: "skip" (default) leaves out terms
    whose quantity is absent; "raise" refuses, which is how a scorer guarantees that every model
    meets the same set of claims.
    """
    key = _case_key(case)
    mapping = load_mapping()
    vocab = mapping["quantities"]
    _check_predicted(predicted, vocab)
    if missing not in {"skip", "raise"}:
        raise ValueError("missing must be 'skip' or 'raise'")
    eps = float(mapping["categorical_error_rate"])
    weights = mapping["weights"]
    claims = {c["id"]: c for c in load_claims(key)}
    rows: list[dict] = []
    for cid, e in mapping["cases"][key]["claims"].items():
        if not e["scorable"]:
            continue
        firsthand = bool(claims[cid]["firsthand"])
        weight = float(weights["firsthand"] if firsthand else weights["relayed"])
        for t in e["terms"]:
            q = t["quantity"]
            qlist = q if isinstance(q, list) else [q]
            g = t.get("given")
            absent = [x for x in qlist + ([g["quantity"]] if g else []) if x not in predicted]
            if absent:
                if missing == "raise":
                    raise TestimonyError(f"{cid}: predicted lacks {absent}")
                continue
            # A conditional term (REVIEW-M3 Rule G): it scores its quantity only where the condition holds and
            # contributes 0 otherwise; with a probability p for the condition, log(p L + (1 - p)).
            p_given = 1.0
            if g:
                gv = predicted[g["quantity"]]
                p_true = (1.0 if gv else 0.0) if isinstance(gv, (bool, np.bool_)) else float(gv)
                p_given = p_true if g["value"] else 1.0 - p_true
                if p_given <= 0.0:
                    rows.append({"claim_id": cid, "quantity": "|".join(qlist), "predicted_value": None,
                                 "interval": {"lo": t.get("lo"), "hi": t.get("hi"), "given": dict(g),
                                              "applies": False},
                                 "loglik": 0.0, "weight": weight, "firsthand": firsthand, "weighted_loglik": 0.0})
                    continue
            qtype = vocab[qlist[0]]["type"]
            if qtype == "number":
                how = t.get("reduce", "median")
                log_scale = t.get("scale", "linear") == "log"
                lo, hi, sg_claim = float(t["lo"]), float(t["hi"]), float(t["sigma"])
                # Lab decision D-015: a recalled number is never treated as tighter than
                # MEMORY_SIGMA_FLOOR of its value (log scale: log10(1 + floor)).
                if log_scale:
                    sg = max(sg_claim, math.log10(1.0 + MEMORY_SIGMA_FLOOR))
                else:
                    sg = max(sg_claim, MEMORY_SIGMA_FLOOR * max(abs(lo), abs(hi)))
                vals, lls = [], []
                for x in qlist:
                    v = _reduce(predicted[x], how)
                    vals.append(v)
                    if log_scale:
                        ll = (interval_logpdf(math.log10(v), math.log10(lo), math.log10(hi), sg)
                              if v > 0 else -math.inf)
                    else:
                        ll = interval_logpdf(v, lo, hi, sg)
                    lls.append(ll)
                # equal mixture over the readings the claim allows
                m = max(lls)
                ll = m if not math.isfinite(m) else m + math.log(np.mean(np.exp(np.array(lls) - m)))
                interval = {"lo": lo, "hi": hi, "sigma": sg, "sigma_claimed": sg_claim,
                            "scale": "log10" if log_scale else "linear",
                            "reduce": how}
                pv = vals[0] if len(vals) == 1 else vals
            else:
                pv = predicted[qlist[0]]
                ll = _categorical_loglik(pv, t["value"], eps)
                interval = {"value": t["value"], "error_rate": eps}
            if g:
                interval = dict(interval, given=dict(g), applies=True)
                if p_given < 1.0:
                    ll = float(np.logaddexp(math.log(p_given) + ll, math.log(1.0 - p_given)))
            rows.append({
                "claim_id": cid,
                "quantity": "|".join(qlist),
                "predicted_value": pv,
                "interval": interval,
                "loglik": float(ll),
                "weight": weight,
                "firsthand": firsthand,
                "weighted_loglik": float(weight * ll),
            })
    return rows


def total(rows: list[dict]) -> float:
    """Sum of weighted log-likelihoods over the rows (the criterion's value before the testimony weight)."""
    return float(sum(r["weighted_loglik"] for r in rows))


# ----------------------------------------------------------------------------- witness consistency

def _derived_dir(key: str, mapping: dict, derived_root: Path) -> Path:
    return derived_root / mapping["cases"][key].get("derived_dir", key)


def _lab_reading(q: str, spec: dict, d: Path, fallback: dict, sym: pd.DataFrame | None,
                 track: pd.DataFrame | None, meta: dict | None) -> dict | None:
    """The lab's record for one witness quantity: numeric {lo, hi, text} or categorical {series}."""
    src = spec["source"]
    if src == "symbology" and sym is not None and spec["field"] in set(sym["field"]):
        vals = sym.loc[sym["field"] == spec["field"], "value"].astype(str)
        if q in ("polarity", "display_range_field"):
            return {"series": vals.to_numpy(), "source": f"{d.name}/symbology_final.csv"}
        num = pd.to_numeric(vals, errors="coerce").dropna()
        if num.empty:
            return None
        return {"lo": float(num.min()), "hi": float(num.max()), "n": int(num.size),
                "source": f"{d.name}/symbology_final.csv"}
    if src == "frames_meta" and meta is not None:
        dur = meta["n_frames"] / meta["fps_nominal"]
        return {"lo": dur, "hi": dur, "frame_s": 1.0 / meta["fps_nominal"],
                "source": f"{d.name}/frames_meta.json"}
    if src == "image_track" and track is not None:
        t = track[track["obj_found"] == 1]
        if t.empty:
            return None
        hot = ((t["polarity"] == "WHT") & (t["obj_sign"] > 0)) | ((t["polarity"] == "BLK") & (t["obj_sign"] < 0))
        return {"series": np.where(hot, "hotter", "colder"), "source": f"{d.name}/image_track.csv"}
    if q in fallback:
        fb = dict(fallback[q])
        fb["source"] = fallback.get("source", "fallback")
        return fb
    return None


def witness_consistency(case: str, derived_root: Path | None = None, mapping: dict | None = None,
                        claims: list[dict] | None = None) -> pd.DataFrame:
    """Claims about on-screen quantities against the lab's readings (memory vs the record).

    Numeric: agree when the gap between the recalled interval and the lab's range of values is
    within the rounding tolerance implied by the wording; ``difference`` is that gap, signed
    (recalled minus lab). Categorical: the fraction of frames showing the recalled value;
    agree at 90 percent or more, disagree at 10 percent or less, else partial. Reported
    separately: it does not change any hypothesis score.
    """
    key = _case_key(case)
    mapping = mapping if mapping is not None else load_mapping()
    claims = claims if claims is not None else load_claims(key)
    by_id = {c["id"]: c for c in claims}
    root = Path(derived_root) if derived_root is not None else DERIVED_DIR
    d = _derived_dir(key, mapping, root)
    sym = pd.read_csv(d / "symbology_final.csv", dtype=str, keep_default_na=False) \
        if (d / "symbology_final.csv").exists() else None
    track = pd.read_csv(d / "image_track.csv") if (d / "image_track.csv").exists() else None
    meta = json.loads((d / "frames_meta.json").read_text(encoding="utf-8")) \
        if (d / "frames_meta.json").exists() else None
    fallback = mapping["cases"][key].get("lab_fallback", {})
    wvocab = mapping["witness_quantities"]

    rows = []
    for cid, e in mapping["cases"][key]["claims"].items():
        for wt in e.get("witness", []):
            q = wt["quantity"]
            spec = wvocab[q]
            c = by_id[cid]
            row = {"claim_id": cid, "witness": c["witness"].split(" (")[0], "firsthand": c["firsthand"],
                   "quantity": q, "unit": spec.get("unit", ""), "recalled": wt.get("recalled", ""),
                   "lab": "", "lab_source": "", "difference": math.nan, "status": "no_lab_reading", "note": ""}
            lab = _lab_reading(q, spec, d, fallback, sym, track, meta)
            if lab is None:
                rows.append(row)
                continue
            row["lab_source"] = lab["source"]
            if "value" in wt:
                if "series" in lab:
                    s = np.asarray(lab["series"])
                    frac = float(np.mean(s == wt["value"]))
                    counts = pd.Series(s).value_counts()
                    row["lab"] = ", ".join(f"{k} {v} fr" for k, v in counts.items())
                    row["difference"] = round(1.0 - frac, 4)
                    row["status"] = "agree" if frac >= 0.9 else ("disagree" if frac <= 0.1 else "partial")
                    row["note"] = f"{frac:.0%} of frames show the recalled value"
                else:
                    row["lab"] = str(lab.get("value"))
                    same = str(lab.get("value")) == str(wt["value"])
                    row["difference"] = 0.0 if same else 1.0
                    row["status"] = "agree" if same else "disagree"
                    row["note"] = lab.get("note", "")
            else:
                rlo, rhi, tol = float(wt["lo"]), float(wt["hi"]), float(wt["tol"])
                llo, lhi = float(lab["lo"]), float(lab["hi"])
                tol_total = tol + lab.get("frame_s", 0.0)
                if rlo > lhi:
                    diff = rlo - lhi
                elif rhi < llo:
                    diff = rhi - llo
                else:
                    diff = 0.0
                row["lab"] = f"{llo:g}" if llo == lhi else f"{llo:g} to {lhi:g}"
                row["difference"] = round(diff, 4)
                row["status"] = "agree" if abs(diff) <= tol_total else "disagree"
                row["note"] = f"tolerance {tol:g} {spec.get('unit', '')}".strip()
            rows.append(row)
    cols = ["claim_id", "witness", "firsthand", "quantity", "unit", "recalled", "lab", "lab_source",
            "difference", "status", "note"]
    return pd.DataFrame(rows, columns=cols)


def environment_claims(case: str) -> pd.DataFrame:
    """Claims about wind, time of day, visibility and sea state (checked against ERA5 or ephemeris, not scored)."""
    key = _case_key(case)
    mapping = load_mapping()
    rows = []
    for cid, e in mapping["cases"][key]["claims"].items():
        for et in e.get("environment", []):
            rows.append({"claim_id": cid, "firsthand": e["firsthand"], **et})
    return pd.DataFrame(rows)
