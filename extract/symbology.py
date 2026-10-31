"""Per-frame reading of the ATFLIR on-screen symbology (GIMBAL, GOFAST).

Method (M1.3):
    1. Every text field is split into fixed character cells. Cell centers and glyph rows are
       stored per field in extract/layouts/<case>.yaml (`cells`), measured from clean frames;
       the font is fixed pitch (about 9.3 px), and the altitude thousands are drawn larger.
       Each cell patch is the white top-hat of the gray frame (bright strokes minus the local
       background), so the moving scene behind the glyphs is suppressed. Sensor and polarity
       are read as whole words.
    2. A glyph template library per video is built by clustering cell patches from many
       frames (k-means on normalized patches, cluster_stage). Clusters were labeled by eye from
       montage images; mixed clusters were split again (recluster_stage, position_stage) and
       labeled the same way. Every labeled cluster centroid is a template. Labels and templates
       live in extract/templates/<case>/ (cluster_labels.json, labels.json, t_*.png).
    3. Each cell is classified by normalized cross-correlation (cv2 TM_CCOEFF_NORMED,
       +-1 px shift search) against the templates allowed for that cell's role. Per character
       confidence = best label score minus second best label score, divided by the largest
       margin that template pair can give (1 - their correlation), so similar glyphs (8 and 9)
       and dissimilar ones share one 0..1 scale. Blank cells are decided first from stroke
       energy ("ink") relative to the frame's own symbology contrast. Per value confidence =
       min over its value-bearing characters. Low confidence: < LOW_CONF (0.30, see below).
    4. A temporal filter repairs short impossible runs (a run of 1 to 2 frames between equal
       neighbors that exceeds the field's maximum step, is a blank dropout, or is low
       confidence) and one-frame transition glitches (an interlaced frame mixing old and new
       digits). Repairs are recorded (method template+temporal), never silent.
    5. rapidocr (recognition only) is an optional second vote on low-confidence values; it is
       recorded in symbology_ocr.csv and never overwrites a value (so method "ocr" is unused).
    6. sitrec_crosscheck compares with Sitrec's independent tables (cross-check only).

CLI:  python -m extract.symbology <case> [--no-ocr] [--build-library]
Outputs: data/derived/<case>/symbology.csv (frame, field, value, raw, confidence, method)
         data/derived/<case>/symbology_summary.json (per field counts, cadence, change frames)
         data/derived/<case>/symbology_ocr.csv, symbology_sitrec_check.json
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass, field as dfield
from pathlib import Path

import cv2
import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
N_FRAMES_DEFAULT = 1031

# Cell patch geometry (pixels). Small glyphs are about 9 x 13, the altitude thousands 12 x 15.
SMALL = (15, 10)   # (h, w)
LARGE = (17, 13)
SHIFT = 1          # +- px shift search during matching
TOPHAT_K = 9

# Role -> allowed labels. "_" is blank.
ROLE_LABELS: dict[str, tuple[str, ...]] = {
    "d": tuple("0123456789"),
    "D": tuple("0123456789") + ("_",),
    "dL": tuple("0123456789"),
    "s": ("-", "_"),
    "dot": (".",),
    "deg": ("°",),
    "LR": ("L", "R"),
    "A": ("A", "_"),
}
CONSTANT_ROLES = {"dot", "deg"}           # structural cells: read, but not value-bearing
WORD_LABELS = {"sensor": ("IR", "TV"), "polarity": ("WHT", "BLK")}

# Low-confidence threshold on the per-value confidence (relative NCC margin, 0..1).
# Chosen from the data (both videos, raw reads before the temporal filter): a read is called
# inconsistent when it equals neither neighbor nor the majority of the +-4 frame window.
# Inconsistency rate by confidence bin: [0, .05) 39%, [.05, .1) 17%, [.1, .2) 9%,
# [.2, .3) 4%, [.3, .5) 0.6%, [.5, 1] 0.005%. Below 0.3 a read is wrong often enough to flag.
LOW_CONF = 0.30

# Temporal rules: maximum plausible change between two consecutive displayed values.
MAX_STEP = {
    "azimuth": 1, "elevation": 1, "range": 0.1, "closure": 10, "altitude": 10,
    "airspeed": 1, "mach": 0.01, "clock": 1, "zoom": 0.0,
}


# --------------------------------------------------------------------------- layout

@dataclass
class Cell:
    x: float
    y0: int
    y1: int
    role: str

    @property
    def large(self) -> bool:
        return self.role == "dL"

    @property
    def hw(self) -> tuple[int, int]:
        return LARGE if self.large else SMALL


@dataclass
class FieldSpec:
    name: str
    cells: list[Cell] = dfield(default_factory=list)
    word: tuple[int, int, int, int] | None = None


def load_layout(case: str) -> dict[str, FieldSpec]:
    lay = yaml.safe_load((ROOT / "extract" / "layouts" / f"{case}.yaml").read_text(encoding="utf-8"))
    out: dict[str, FieldSpec] = {}
    for name, f in lay["fields"].items():
        if f.get("kind") != "text":
            continue
        spec = FieldSpec(name)
        if "word" in f:
            spec.word = tuple(f["word"])
        else:
            c = f["cells"]
            for x, role in zip(c["x"], c["roles"]):
                y0, y1 = (c["big_y"] if role == "dL" else c["y"])
                spec.cells.append(Cell(float(x), int(y0), int(y1), role))
        out[name] = spec
    return out


# --------------------------------------------------------------------------- image features

def tophat(gray: np.ndarray) -> np.ndarray:
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (TOPHAT_K, TOPHAT_K))
    return cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, k).astype(np.float32)


def cell_window(th: np.ndarray, cell: Cell, margin: int = SHIFT) -> np.ndarray:
    """Patch of size hw + 2*margin around the cell (for shift search)."""
    h, w = cell.hw
    x0 = int(round(cell.x - w / 2.0)) - margin
    y0 = cell.y0 - 1 - margin
    return th[y0:y0 + h + 2 * margin, x0:x0 + w + 2 * margin]


def cell_patch(th: np.ndarray, cell: Cell) -> np.ndarray:
    return cell_window(th, cell, 0)


def word_window(th: np.ndarray, box, margin: int = 2) -> np.ndarray:
    x0, y0, x1, y1 = box
    return th[y0 - margin:y1 + margin, x0 - margin:x1 + margin]


def ink(patch: np.ndarray, k: int = 12) -> float:
    """Stroke energy: mean of the k brightest top-hat pixels."""
    v = np.sort(patch.ravel())
    return float(v[-k:].mean())


def norm_vec(p: np.ndarray) -> np.ndarray:
    v = p.astype(np.float32).ravel()
    v = v - v.mean()
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else v


def frame_path(case: str, i: int) -> Path:
    return ROOT / "data" / "frames" / case / f"f{i:06d}.png"


def n_frames(case: str) -> int:
    p = ROOT / "data" / "derived" / case / "frames.csv"
    if p.exists():
        with p.open() as fh:
            return sum(1 for _ in fh) - 1
    return N_FRAMES_DEFAULT


def read_tophat(case: str, i: int) -> np.ndarray:
    g = cv2.imread(str(frame_path(case, i)), cv2.IMREAD_GRAYSCALE)
    if g is None:
        raise FileNotFoundError(frame_path(case, i))
    return tophat(g)


# --------------------------------------------------------------------------- template library

@dataclass
class Library:
    """Templates per label and size class ('s' small, 'L' large, or a word field name)."""
    templates: dict[tuple[str, str], list[np.ndarray]] = dfield(default_factory=dict)

    def add(self, size: str, label: str, img: np.ndarray) -> None:
        self.templates.setdefault((size, label), []).append(img.astype(np.float32))

    def labels(self, size: str) -> list[str]:
        return sorted({lab for (s, lab) in self.templates if s == size})

    def get(self, size: str, label: str) -> list[np.ndarray]:
        return self.templates.get((size, label), [])

    def save(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("t_*.png"):
            old.unlink()
        entries = []
        for (size, label), imgs in sorted(self.templates.items()):
            for j, img in enumerate(imgs):
                name = f"t_{size}_{ord(label[0]):04x}_{len(label)}_{j:02d}.png" if len(label) == 1 else f"t_{size}_{label}_{j:02d}.png"
                scale = 255.0 / max(float(img.max()), 1e-6)
                cv2.imwrite(str(folder / name), np.clip(img * scale, 0, 255).astype(np.uint8))
                entries.append({"file": name, "size": size, "label": label})
        meta = {"note": "Glyph templates (white top-hat, scaled to 0..255). Built by k-means clustering "
                        "of character cells over the whole video, clusters labeled by eye from montages "
                        "in artifacts/tmp/m13/. See extract/symbology.py.",
                "templates": entries}
        (folder / "labels.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, folder: Path) -> "Library":
        meta = json.loads((folder / "labels.json").read_text(encoding="utf-8"))
        lib = cls()
        for e in meta["templates"]:
            img = cv2.imread(str(folder / e["file"]), cv2.IMREAD_GRAYSCALE)
            lib.add(e["size"], e["label"], img.astype(np.float32))
        return lib


def template_dir(case: str) -> Path:
    return ROOT / "extract" / "templates" / case


# --------------------------------------------------------------------------- classification

@dataclass
class CharRead:
    label: str
    score: float
    margin: float
    ink_ratio: float


def match_scores(window: np.ndarray, lib: Library, size: str, labels, with_templates: bool = False):
    """Best NCC per label over templates and +-SHIFT px offsets (optionally the winning template)."""
    out: dict[str, float] = {}
    best_t: dict[str, np.ndarray] = {}
    win = window.astype(np.float32)
    for lab in labels:
        best = -1.0
        for t in lib.get(size, lab):
            if win.shape[0] < t.shape[0] or win.shape[1] < t.shape[1]:
                continue
            r = cv2.matchTemplate(win, t, cv2.TM_CCOEFF_NORMED)
            v = float(r.max())
            if v > best:
                best, best_t[lab] = v, t
        if best > -1.0:
            out[lab] = best
    return (out, best_t) if with_templates else out


def relative_margin(margin: float, ta: np.ndarray, tb: np.ndarray) -> float:
    """NCC margin divided by the largest margin this template pair can produce.

    For unit-norm zero-mean templates with correlation rho, a patch identical to ta scores
    1 - rho more on ta than on tb; a patch midway scores 0. So margin / (1 - rho) is the
    best-minus-second-best margin on a 0..1 scale that is comparable between similar glyph
    pairs (8 vs 9, rho about 0.85) and dissimilar ones (1 vs 0)."""
    if ta.shape == tb.shape:
        pad = cv2.copyMakeBorder(ta.astype(np.float32), SHIFT, SHIFT, SHIFT, SHIFT, cv2.BORDER_CONSTANT, value=0)
        rho = float(cv2.matchTemplate(pad, tb.astype(np.float32), cv2.TM_CCOEFF_NORMED).max())
    else:
        rho = float(norm_vec(ta) @ norm_vec(tb))
    return float(np.clip(margin / max(1.0 - rho, 0.05), 0.0, 1.0))


BLANK_LO, BLANK_HI = 0.25, 0.45   # ink ratio: below LO surely blank, above HI surely ink


def classify_cell(window: np.ndarray, cell: Cell, lib: Library, ref_ink: float) -> CharRead:
    allowed = ROLE_LABELS[cell.role]
    h, w = cell.hw
    core = window[SHIFT:SHIFT + h, SHIFT:SHIFT + w]
    r = ink(core) / max(ref_ink, 1e-6)
    blank_ok = "_" in allowed
    mid = 0.5 * (BLANK_LO + BLANK_HI)
    if blank_ok and r < mid:
        conf = float(np.clip((mid - r) / (mid - BLANK_LO + 1e-9), 0, 1)) * 0.5 + 0.0
        return CharRead("_", 0.0, conf, r)
    size = "L" if cell.large else "s"
    labels = [lab for lab in allowed if lab != "_"]
    sc, bt = match_scores(window, lib, size, labels, with_templates=True)
    ranked = sorted(sc.items(), key=lambda kv: -kv[1])
    if not ranked:
        return CharRead("?", 0.0, 0.0, r)
    best_lab, best = ranked[0]
    if len(ranked) > 1:
        margin = relative_margin(best - ranked[1][1], bt[best_lab], bt[ranked[1][0]])
    else:
        margin = best   # single-label role (structural cell): the score itself
    if blank_ok:
        # an ink ratio close to the blank threshold also limits the confidence
        margin = min(margin, float(np.clip((r - mid) / (BLANK_HI - mid + 1e-9), 0, 1)) * 0.5)
    elif r < BLANK_LO:
        margin = 0.0   # a required glyph with no ink: not readable in this frame
    return CharRead(best_lab, best, float(margin), r)


def classify_word(window: np.ndarray, name: str, lib: Library) -> CharRead:
    labels = [lab for lab in WORD_LABELS[name] if lib.get(name, lab)]
    sc, bt = match_scores(window, lib, name, labels, with_templates=True)
    ranked = sorted(sc.items(), key=lambda kv: -kv[1])
    if not ranked:
        return CharRead("?", 0.0, 0.0, 1.0)
    if len(ranked) == 1:
        return CharRead(ranked[0][0], ranked[0][1], ranked[0][1], 1.0)
    m = relative_margin(ranked[0][1] - ranked[1][1], bt[ranked[0][0]], bt[ranked[1][0]])
    return CharRead(ranked[0][0], ranked[0][1], m, 1.0)


def reference_ink(th: np.ndarray, layout: dict[str, FieldSpec]) -> float:
    """The frame's symbology stroke contrast: median ink over cells that always hold a glyph."""
    vals = []
    for spec in layout.values():
        for c in spec.cells:
            if "_" not in ROLE_LABELS[c.role] and spec.name not in ("range", "closure"):
                vals.append(ink(cell_patch(th, c)))
    return float(np.median(vals)) if vals else 1.0


@dataclass
class FieldRead:
    value: str          # parsed value, or "blank"
    raw: str            # characters as read, "_" for blank cells
    confidence: float
    chars: list[CharRead]


def compose_value(name: str, raw: str) -> str:
    """Raw cell string to the displayed value (blank cells removed)."""
    if set(raw) <= {"_"}:
        return "blank"
    s = raw.replace("_", "")
    if name == "azimuth":
        return s.replace("°", "")          # e.g. "54L"
    if name == "elevation":
        return s.replace("°", "")          # e.g. "-2", "-22"
    return s


def read_field(th: np.ndarray, spec: FieldSpec, lib: Library, ref_ink: float) -> FieldRead:
    if spec.word is not None:
        cr = classify_word(word_window(th, spec.word), spec.name, lib)
        return FieldRead(cr.label, cr.label, round(cr.margin, 4), [cr])
    chars = [classify_cell(cell_window(th, c), c, lib, ref_ink) for c in spec.cells]
    raw = "".join(ch.label for ch in chars)
    # A field that can be wholly absent (range, closure in GOFAST before the laser comes on):
    # if no value cell has ink, the field is blank.
    if spec.name in ("range", "closure"):
        ratios = [ch.ink_ratio for ch in chars]
        mid = 0.5 * (BLANK_LO + BLANK_HI)
        if max(ratios) < mid:
            conf = float(np.clip((mid - max(ratios)) / (mid - BLANK_LO), 0, 1)) * 0.5
            return FieldRead("blank", "_" * len(chars), round(conf, 4), chars)
    value_conf = [ch.margin for ch, c in zip(chars, spec.cells) if c.role not in CONSTANT_ROLES]
    conf = min(value_conf) if value_conf else 0.0
    return FieldRead(compose_value(spec.name, raw), raw, round(float(conf), 4), chars)


def read_frame(th: np.ndarray, layout: dict[str, FieldSpec], lib: Library) -> dict[str, FieldRead]:
    ref = reference_ink(th, layout)
    return {name: read_field(th, spec, lib, ref) for name, spec in layout.items()}


# --------------------------------------------------------------------------- value parsing

def numeric(name: str, value: str) -> float | None:
    """Numeric form of a value for temporal checks (azimuth: L negative, R positive; clock: s)."""
    if value in ("blank", "") or "?" in value:
        return None
    try:
        if name == "azimuth":
            side = value[-1]
            v = float(value[:-1])
            return -v if side == "L" else v
        if name == "clock":
            d = "".join(ch for ch in value if ch.isdigit())
            if len(d) != 4:
                return None
            return int(d[:2]) * 60 + int(d[2:])
        if name in ("sensor", "polarity"):
            return None
        return float(value)
    except ValueError:
        return None


# --------------------------------------------------------------------------- temporal filter

@dataclass
class Series:
    values: list[str]
    conf: list[float]
    method: list[str]


def run_is_impossible(name: str, left: str, run: list[str]) -> bool:
    """Whether a short run between two equal values cannot be a real display change."""
    if left == "blank" or any(v == "blank" for v in run):
        return True                       # a value flashing inside a blank stretch, or a dropout
    if name in ("sensor", "polarity"):
        return True                       # a mode switched for 1 or 2 frames and back
    step = MAX_STEP.get(name)
    a = numeric(name, left)
    if step is None or a is None:
        return False
    for v in run:
        b = numeric(name, v)
        if b is None or abs(b - a) > step + 1e-9:
            return True
    return False


def temporal_filter(name: str, values: list[str], conf: list[float], max_run: int = 2,
                    low_conf: float = LOW_CONF) -> Series:
    """Repair isolated impossible jumps.

    A run of 1..max_run frames whose value differs from equal values on both sides is
    replaced by the neighbor value when (a) the run is impossible for the field (a jump larger
    than MAX_STEP, an unparseable value, a blank dropout or a 1 to 2 frame mode switch), or
    (b) the run is low confidence. Confident, plausible one-frame flickers are kept (a real
    display can dither between adjacent values). Every repair is marked in `method`
    ("template+temporal"), and its confidence is the lower of the two neighbors'.
    """
    vals = list(values)
    cf = [float(c) for c in conf]
    meth = ["blank" if v == "blank" else "template" for v in vals]
    n = len(vals)
    i = 1
    while i < n:
        if vals[i] == vals[i - 1]:
            i += 1
            continue
        left = vals[i - 1]
        for L in range(1, max_run + 1):
            j = i + L
            if j >= n:
                break
            if vals[j] == left:
                run = vals[i:j]
                if any(v == left for v in run):
                    break
                if run_is_impossible(name, left, run) or min(cf[i:j]) < low_conf:
                    c_new = min(cf[i - 1], cf[j])
                    for k in range(i, j):
                        vals[k] = left
                        meth[k] = "blank" if left == "blank" else "template+temporal"
                        cf[k] = c_new
                break
        i += 1
    # Transition glitches: one frame between two different, mutually plausible values that is
    # impossible relative to both (an interlaced frame mixing old and new digits, e.g. 59L
    # between 50L and 49L). It is set to the new value: the frame already holds a field of it.
    step = MAX_STEP.get(name)
    if step is not None:
        for i in range(1, n - 1):
            a, x, b = vals[i - 1], vals[i], vals[i + 1]
            if a == b or x in (a, b) or "blank" in (a, x, b):
                continue
            na, nx, nb = numeric(name, a), numeric(name, x), numeric(name, b)
            if na is None or nb is None or abs(nb - na) > step + 1e-9:
                continue
            if nx is None or (abs(nx - na) > step + 1e-9 and abs(nx - nb) > step + 1e-9) or cf[i] < low_conf:
                vals[i] = b
                meth[i] = "template+temporal"
                cf[i] = 0.5 * min(cf[i - 1], cf[i + 1])
    return Series(vals, cf, meth)


# --------------------------------------------------------------------------- library building

def collect_patches(case: str, frames, layout=None):
    """Cell patches (top-hat) for the given frames. Returns dict size -> (patches, meta)."""
    layout = layout or load_layout(case)
    out: dict[str, list] = {}
    meta: dict[str, list] = {}
    for i in frames:
        th = read_tophat(case, i)
        ref = reference_ink(th, layout)
        for name, spec in layout.items():
            if spec.word is not None:
                p = word_window(th, spec.word, 0)
                out.setdefault(name, []).append(p)
                meta.setdefault(name, []).append((i, name, -1, 1.0))
                continue
            for ci, c in enumerate(spec.cells):
                p = cell_patch(th, c)
                r = ink(p) / max(ref, 1e-6)
                size = "L" if c.large else "s"
                out.setdefault(size, []).append(p)
                meta.setdefault(size, []).append((i, name, ci, r))
    return {k: (np.array(v, dtype=np.float32), meta[k]) for k, v in out.items()}


def kmeans_clusters(patches: np.ndarray, k: int, seed: int = 0):
    X = np.array([norm_vec(p) for p in patches], dtype=np.float32)
    k = min(k, len(X))
    cv2.setRNGSeed(seed)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-4)
    _, lab, _ = cv2.kmeans(X, k, None, crit, 5, cv2.KMEANS_PP_CENTERS)
    return lab.ravel()


def montage(groups: list[tuple[str, list[np.ndarray]]], path: Path, per_row: int = 24, scale: int = 4) -> None:
    rows = []
    for title, imgs in groups:
        imgs = imgs[:per_row]
        h = max(im.shape[0] for im in imgs)
        w = max(im.shape[1] for im in imgs)
        tiles = []
        for im in imgs:
            t = np.zeros((h, w), np.float32)
            t[:im.shape[0], :im.shape[1]] = im / max(float(im.max()), 1e-6)
            tiles.append(np.pad(t, ((1, 1), (1, 1)), constant_values=0.3))
        row = np.hstack(tiles)
        row = cv2.resize((row * 255).astype(np.uint8), None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
        lab = np.zeros((row.shape[0], 110), np.uint8)
        cv2.putText(lab, title, (2, row.shape[0] // 2 + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.55, 255, 1)
        rows.append(np.hstack([lab, row]))
    W = max(r.shape[1] for r in rows)
    img = np.vstack([np.pad(r, ((0, 2), (0, W - r.shape[1]))) for r in rows])
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)


def cluster_stage(case: str, k_small: int = 72, k_large: int = 12, k_word: int = 4, step: int = 3,
                  out_dir: Path | None = None) -> Path:
    """Stage 1 of the library: cluster cells and write montages for labeling by eye."""
    out_dir = out_dir or ROOT / "artifacts" / "tmp" / "m13" / f"lib_{case}"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = collect_patches(case, range(0, n_frames(case), step))
    store = {}
    for size, (P, meta) in data.items():
        inked = np.array([m[3] >= BLANK_HI for m in meta]) if size in ("s", "L") else np.ones(len(P), bool)
        P2 = P[inked]
        meta2 = [m for m, ok in zip(meta, inked) if ok]
        k = {"s": k_small, "L": k_large}.get(size, k_word)
        lab = kmeans_clusters(P2, k)
        rng = np.random.default_rng(0)
        groups = []
        for c in range(lab.max() + 1):
            idx = np.where(lab == c)[0]
            if len(idx) == 0:
                continue
            pick = rng.choice(idx, size=min(23, len(idx)), replace=False)
            mean = P2[idx].mean(0)
            groups.append((f"{c} n={len(idx)}", [mean] + [P2[j] for j in pick]))
        # montage files of 24 clusters each
        for g0 in range(0, len(groups), 24):
            montage(groups[g0:g0 + 24], out_dir / f"montage_{size}_{g0 // 24}.png")
        store[size] = (P2, lab, meta2)
        np.savez_compressed(out_dir / f"clusters_{size}.npz", P=P2, lab=lab,
                            meta=np.array([(m[0], m[2]) for m in meta2]),
                            fields=np.array([m[1] for m in meta2]))
    return out_dir


def recluster_stage(case: str, size: str, cluster_ids: list[int], k: int = 12, out_dir: Path | None = None,
                    tag: str = "m", field_cell: tuple[str, int] | None = None) -> Path:
    """Second labeling pass: split ambiguous clusters (mixed glyphs) into k sub-clusters.

    Sub-cluster s of this pass is addressed as "<tag>/<s>" in the label map. `field_cell`
    restricts the pass to members from one cell position (glyph rendering depends on the
    sub-pixel phase of the position)."""
    out_dir = out_dir or ROOT / "artifacts" / "tmp" / "m13" / f"lib_{case}"
    z = np.load(out_dir / f"clusters_{size}.npz")
    P, lab = z["P"], z["lab"]
    sel = np.isin(lab, cluster_ids)
    if field_cell is not None:
        sel &= (z["fields"] == field_cell[0]) & (z["meta"][:, 1] == field_cell[1])
    idx = np.where(sel)[0]
    sub = kmeans_clusters(P[idx], k, seed=2)
    rng = np.random.default_rng(0)
    groups = []
    for s in range(sub.max() + 1):
        m = idx[sub == s]
        if len(m) == 0:
            continue
        pick = rng.choice(m, size=min(23, len(m)), replace=False)
        groups.append((f"{tag}/{s} n={len(m)}", [P[m].mean(0)] + [P[j] for j in pick]))
    suffix = "" if tag == "m" else f"_{tag}"
    montage(groups, out_dir / f"montage_{size}_recluster{suffix}.png")
    np.savez_compressed(out_dir / f"recluster_{size}{suffix}.npz", idx=idx, sub=sub)
    return out_dir


def position_stage(case: str, field_name: str, cell_index: int, k: int = 8, frames=None,
                   tag: str = "p", out_dir: Path | None = None) -> Path:
    """Extra labeling pass at full frame rate for one cell position (rare glyphs there)."""
    out_dir = out_dir or ROOT / "artifacts" / "tmp" / "m13" / f"lib_{case}"
    layout = load_layout(case)
    cell = layout[field_name].cells[cell_index]
    frames = list(frames if frames is not None else range(n_frames(case)))
    P = np.array([cell_patch(read_tophat(case, i), cell) for i in frames], dtype=np.float32)
    sub = kmeans_clusters(P, k, seed=3)
    groups = []
    for s_ in range(sub.max() + 1):
        m = np.where(sub == s_)[0]
        if len(m) == 0:
            continue
        fr = [frames[j] for j in m]
        groups.append((f"{tag}/{s_} n={len(m)}", [P[m].mean(0)] + [P[j] for j in m[:: max(1, len(m) // 23)][:23]]))
        print(f"{tag}/{s_}: n={len(m)} frames {min(fr)}..{max(fr)}")
    montage(groups, out_dir / f"montage_position_{tag}.png")
    np.savez_compressed(out_dir / f"position_{tag}.npz", P=P, sub=sub, frames=np.array(frames))
    return out_dir


def library_from_labels(case: str, cluster_labels: dict[str, dict[str, str]], out_dir: Path | None = None,
                        min_members: int = 3) -> Library:
    """Stage 2: cluster labels (by eye) -> template library.

    Every labeled cluster centroid (mean top-hat image of its members) becomes one template,
    so variants of a glyph (dark or bright background, interlaced, sub-pixel phase of the
    cell position) stay separate. '?' (mixed) clusters are dropped. Label keys: "<n>" for
    first-pass clusters, "m/<n>" and "<tag>/<n>" for re-clustered ambiguous members, and
    "<tag>/<n>" with a position_<tag>.npz file for full-rate single-position passes.
    (Averaging all members of a label into a few sub-templates, and self-training on
    confident reads, were tried first and misread more often.)
    """
    out_dir = out_dir or ROOT / "artifacts" / "tmp" / "m13" / f"lib_{case}"
    lib = Library()
    for size, labmap in cluster_labels.items():
        z = np.load(out_dir / f"clusters_{size}.npz")
        P, lab = z["P"], z["lab"]

        def members_of(c: str) -> np.ndarray:
            if "/" in c:
                tag, n = c.split("/")
                pos = out_dir / f"position_{tag}.npz"
                if pos.exists():
                    pz = np.load(pos)
                    return pz["P"][pz["sub"] == int(n)]
                rz = np.load(out_dir / (f"recluster_{size}.npz" if tag == "m" else f"recluster_{size}_{tag}.npz"))
                return P[rz["idx"][rz["sub"] == int(n)]]
            return P[lab == int(c)]

        for c, name in labmap.items():
            if name in ("?", "_"):
                continue
            members = members_of(str(c))
            if len(members) >= min_members:
                lib.add(size, name, members.mean(0))
    return lib


def build_library(case: str) -> Library:
    """Labels (extract/templates/<case>/cluster_labels.json) -> templates, saved."""
    labels = json.loads((template_dir(case) / "cluster_labels.json").read_text(encoding="utf-8"))["labels"]
    lib = library_from_labels(case, labels)
    lib.save(template_dir(case))
    return lib


# --------------------------------------------------------------------------- OCR second vote

_OCR = None


def ocr_engine():
    global _OCR
    if _OCR is None:
        from rapidocr import RapidOCR  # optional dependency
        _OCR = RapidOCR()
    return _OCR


def ocr_crop(th: np.ndarray, spec: FieldSpec) -> np.ndarray:
    """Field text span (cells or word box), top-hat, contrast-stretched, inverted, 3x."""
    if spec.word is not None:
        x0, y0, x1, y1 = spec.word
    else:
        x0 = int(min(c.x for c in spec.cells)) - 7
        x1 = int(max(c.x for c in spec.cells)) + 7
        y0 = min(c.y0 for c in spec.cells) - 2
        y1 = max(c.y1 for c in spec.cells) + 3
    c = th[y0:y1, x0:x1]
    c = np.clip(c / max(float(np.percentile(c, 99)), 1.0) * 255, 0, 255).astype(np.uint8)
    c = 255 - cv2.resize(c, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    return cv2.copyMakeBorder(c, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)


def ocr_field(th: np.ndarray, spec: FieldSpec) -> str:
    """rapidocr recognition only (its text detector finds nothing on crops this small)."""
    res = ocr_engine()(cv2.cvtColor(ocr_crop(th, spec), cv2.COLOR_GRAY2BGR),
                       use_det=False, use_cls=False, use_rec=True)
    txts = getattr(res, "txts", None)
    return " ".join(txts) if txts else ""


def ocr_normalize(name: str, text: str) -> str:
    """OCR text to the same value format as compose_value."""
    t = text.upper().replace(" ", "").replace("O", "0")
    digits = "".join(ch for ch in t if ch.isdigit())
    if name == "azimuth":
        side = "L" if "L" in t else ("R" if "R" in t else "")
        return (digits.lstrip("0") or "0") + side if digits else ""
    if name == "elevation":
        return ("-" if "-" in t else "") + digits
    if name == "mach":
        k = t.find(".")
        return "0." + "".join(ch for ch in t[k + 1:] if ch.isdigit())[:2] if k >= 0 else ""
    if name in ("range", "zoom"):
        k = t.find(".")
        if k < 1:
            return ""
        return t[k - 1] + "." + t[k + 1:k + 2]
    if name == "clock":
        return digits[:4] + ("A" if "A" in t[4:] or t.endswith("A") else "")
    if name in ("sensor", "polarity"):
        return t
    return digits


# --------------------------------------------------------------------------- full run

def read_case(case: str, lib: Library | None = None, frames=None, progress: bool = False):
    layout = load_layout(case)
    lib = lib or Library.load(template_dir(case))
    frames = list(frames if frames is not None else range(n_frames(case)))
    reads: dict[str, list[FieldRead]] = {name: [] for name in layout}
    for i in frames:
        th = read_tophat(case, i)
        fr = read_frame(th, layout, lib)
        for name in layout:
            reads[name].append(fr[name])
        if progress and i % 200 == 0:
            print(f"  {case} f{i}")
    return frames, reads


def run_case(case: str, use_ocr: bool = True, progress: bool = True) -> dict:
    layout = load_layout(case)
    frames, reads = read_case(case, progress=progress)
    out_dir = ROOT / "data" / "derived" / case
    rows = []
    summary: dict = {"case": case, "n_frames": len(frames), "low_conf_threshold": LOW_CONF,
                     "low_conf_threshold_note": (
                         "Confidence = best minus second-best NCC score (min over the value's "
                         "characters), divided by the largest margin that template pair can give "
                         "(1 - their correlation), so 1 means the cell matches its template as well as "
                         "the template itself and 0 means midway between two glyphs. Blank cells: ink "
                         "ratio distance from the blank threshold, at most 0.5. Threshold 0.30: over "
                         "both videos, raw reads that disagree with both neighbors and the +-4 frame "
                         "majority occur at 39% (conf < .05), 17% (.05-.1), 9% (.1-.2), 4% (.2-.3), "
                         "0.6% (.3-.5) and 0.005% (>= .5)."),
                     "update_note": (
                         "update_gap_frames: frames between successive value changes (a value-change "
                         "cadence, set by how fast the quantity moves). change_frame_phase: residues "
                         "mod 6 of the frames where a clean (non-repaired) change happens; a dominant "
                         "residue means the display refreshes that field on a fixed frame grid."),
                     "fields": {}}
    ocr_rows = []
    for name in layout:
        fr = reads[name]
        vals = [r.value for r in fr]
        conf = [r.confidence for r in fr]
        ser = temporal_filter(name, vals, conf)
        # OCR second vote on low-confidence values (recorded, never used to overwrite)
        if use_ocr:
            for k, i in enumerate(frames):
                if ser.conf[k] < LOW_CONF and ser.values[k] != "blank":
                    try:
                        txt = ocr_field(read_tophat(case, i), layout[name])
                    except Exception as e:  # OCR is optional
                        txt = f"ERR {type(e).__name__}"
                    norm = ocr_normalize(name, txt)
                    ocr_rows.append({"frame": i, "field": name, "template_value": ser.values[k],
                                     "template_conf": f"{ser.conf[k]:.4f}", "ocr_text": txt,
                                     "ocr_value": norm, "agree": int(norm == ser.values[k])})
        changes = []
        for k in range(1, len(frames)):
            if ser.values[k] != ser.values[k - 1]:
                changes.append({"frame": frames[k], "from": ser.values[k - 1], "to": ser.values[k]})
        for k, i in enumerate(frames):
            rows.append({"frame": i, "field": name, "value": ser.values[k], "raw": fr[k].raw,
                         "confidence": f"{ser.conf[k]:.4f}", "method": ser.method[k]})
        nonblank = [k for k in range(len(frames)) if ser.values[k] != "blank"]
        low = [k for k in nonblank if ser.conf[k] < LOW_CONF]
        gaps = np.diff([c["frame"] for c in changes if c["from"] != "blank" and c["to"] != "blank"])
        clean = [frames[k] for k in range(1, len(frames))
                 if ser.values[k] != ser.values[k - 1] and ser.method[k] == "template"
                 and ser.method[k - 1] == "template" and "blank" not in (ser.values[k], ser.values[k - 1])]
        phase = None
        if len(clean) >= 4:
            res = np.bincount(np.array(clean) % 6, minlength=6)
            phase = {"modulus": 6, "counts_by_residue": res.tolist(), "dominant_residue": int(res.argmax()),
                     "dominant_fraction": round(float(res.max() / res.sum()), 3)}
        summary["fields"][name] = {
            "frames": len(frames),
            "blank": len(frames) - len(nonblank),
            "low_confidence": len(low),
            "low_confidence_frac": round(len(low) / max(len(nonblank), 1), 4),
            "repaired_temporal": sum(1 for m in ser.method if m == "template+temporal"),
            "first_value": ser.values[0], "last_value": ser.values[-1],
            "n_changes": len(changes),
            "update_gap_frames": ({"min": int(gaps.min()), "median": float(np.median(gaps)),
                                   "max": int(gaps.max())} if len(gaps) else None),
            "change_frame_phase": phase,
            "changes": changes,
        }
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "symbology.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["frame", "field", "value", "raw", "confidence", "method"])
        w.writeheader()
        rows.sort(key=lambda r: (r["frame"], list(layout).index(r["field"])))
        w.writerows(rows)
    if use_ocr:
        with (out_dir / "symbology_ocr.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=["frame", "field", "template_value", "template_conf", "ocr_text", "ocr_value", "agree"])
            w.writeheader()
            w.writerows(ocr_rows)
        summary["ocr_second_vote"] = {
            "n_low_conf_values_checked": len(ocr_rows),
            "n_agree": sum(r["agree"] for r in ocr_rows),
            "agree_by_field": {f: [sum(r["agree"] for r in ocr_rows if r["field"] == f),
                                   sum(1 for r in ocr_rows if r["field"] == f)]
                               for f in sorted({r["field"] for r in ocr_rows})},
            "note": "rapidocr (recognition only) on the top-hat, 3x upscaled text span, only for "
                    "values below the threshold; a vote, never used to overwrite (symbology_ocr.csv).",
        }
    (out_dir / "symbology_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    return summary


def sitrec_crosscheck(case: str, max_offset: int = 8) -> dict | None:
    """Compare our readings with Sitrec's independent tables (cross-check only, never labels).

    Offset convention: Sitrec frame = our frame + offset. GIMBAL: per-frame azimuth column of
    GimbalData.csv (left positive). GOFAST: keyframe tables (value from that frame on; left and
    down negative), expanded to per-frame step functions; frames where we read a blank are
    excluded."""
    ref = ROOT / "data" / "reference" / "sitrec" / "data" / case
    sym = ROOT / "data" / "derived" / case / "symbology.csv"
    if not ref.exists() or not sym.exists():
        return None
    import pandas as pd
    d = pd.read_csv(sym, dtype={"value": str})
    ours: dict[str, dict[int, float]] = {}
    for name in ("azimuth", "elevation", "range"):
        g = d[d.field == name]
        ours[name] = {int(r.frame): numeric(name, r.value) for r in g.itertuples() if r.value != "blank"}
    series: dict[str, tuple[str, dict[int, float]]] = {}
    if case == "gimbal":
        s = pd.read_csv(ref / "GimbalData.csv", encoding="utf-8-sig")
        # Sitrec: left positive; ours: left negative
        series["azimuth"] = ("GimbalData.csv '4 azimuth'", {int(f): -float(a) for f, a in zip(s["Frame"], s["4 azimuth"])})
    elif case == "gofast":
        nf = n_frames(case)
        for name, fn, col, sign in (("azimuth", "Go Fast AZ.csv", "Az", 1.0), ("elevation", "Go Fast El.csv", "El", 1.0),
                                     ("range", "Go Fast RNG.csv", "RNG", 1.0)):
            p = ref / fn
            if not p.exists():
                continue
            k = pd.read_csv(p, encoding="utf-8-sig")
            kf = [(int(f), float(v) * sign) for f, v in zip(k["Frame"], k[col])]
            per = {}
            for j, (f0, v) in enumerate(kf):
                f1 = kf[j + 1][0] if j + 1 < len(kf) else nf + max_offset
                for f in range(f0, f1):
                    per[f] = v
            series[name] = (f"{fn} keyframes", per)
    out = {"case": case, "offset_convention": "sitrec_frame = our_frame + offset", "fields": {}}
    for name, (src, ref_per) in series.items():
        best = None
        for off in range(-max_offset, max_offset + 1):
            pairs = [(v, ref_per[f + off]) for f, v in ours[name].items() if v is not None and (f + off) in ref_per]
            if not pairs:
                continue
            agree = sum(1 for a, b in pairs if abs(a - b) < 1e-6)
            if best is None or agree / len(pairs) > best[1]:
                best = (off, agree / len(pairs), len(pairs), [(a, b) for a, b in pairs if abs(a - b) >= 1e-6])
        off, frac, n, dis = best
        entry = {"source": src, "best_offset": off, "frames_compared": n, "agreement": round(frac, 4),
                 "disagreements": len(dis),
                 "max_abs_difference": round(max((abs(a - b) for a, b in dis), default=0.0), 3)}
        if case == "gofast":
            # keyframe timing: Sitrec keyframe frame minus our change frame to the same value
            k = sorted({f for f in ref_per if f - 1 not in ref_per or ref_per[f - 1] != ref_per[f]})
            ourf = sorted(ours[name])
            diffs = []
            for f in k:
                v = ref_per[f]
                hit = [g for g in ourf if abs(ours[name][g] - v) < 1e-6
                       and (g - 1 not in ours[name] or abs(ours[name][g - 1] - v) >= 1e-6)]
                if hit and f > 0:
                    g = min(hit, key=lambda x: abs(x - f))
                    diffs.append({"value": v, "sitrec_frame": f, "our_change_frame": g, "diff": f - g})
            entry["keyframe_timing"] = diffs
        out["fields"][name] = entry
    (ROOT / "data" / "derived" / case / "symbology_sitrec_check.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("case")
    ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--build-library", action="store_true",
                    help="rebuild templates from cluster_labels.json (needs the cluster files in artifacts/tmp/m13)")
    a = ap.parse_args(argv)
    if a.build_library:
        build_library(a.case)
    s = run_case(a.case, use_ocr=not a.no_ocr)
    for name, f in s["fields"].items():
        print(f"{name:10s} blank {f['blank']:4d} low {f['low_confidence']:4d} ({f['low_confidence_frac']:.3f}) "
              f"repaired {f['repaired_temporal']:3d} changes {f['n_changes']:3d} {f['first_value']} -> {f['last_value']}")
    chk = sitrec_crosscheck(a.case)
    if chk:
        for name, e in chk["fields"].items():
            print(f"sitrec {name}: offset {e['best_offset']:+d}, agreement {e['agreement']:.4f} over {e['frames_compared']} frames")


if __name__ == "__main__":
    main()
