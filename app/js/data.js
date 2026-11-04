// Loads the per-case exports written by tools/build_app_data.py, in two stages so the lab appears quickly on a slow
// link: first what the rail, the timeline and the original footage need (meta, results, readings, cues), then the
// rest in the background (the predictions for the field of view on screen, curves over range, testimony, prior
// work, turn rate). A callback reports each background file as it lands, so the views fill in. Every request has
// a watchdog: one that stalls is aborted and tried again with a longer wait, so one slow file cannot hang the lab.

const cache = new Map();
const TIMEOUT_MS = 10000;
const TRIES = 3;
let progress = () => {};

export function onProgress(fn) { progress = fn; }

async function fetchJSON(url) {
  let last = null;
  for (let k = 1; k <= TRIES; k++) {
    const ctl = new AbortController();
    const wait = TIMEOUT_MS * k;
    const timer = setTimeout(() => ctl.abort(), wait);
    try {
      const r = await fetch(url, { signal: ctl.signal });
      if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
      return await r.json();
    } catch (e) {
      last = e.name === "AbortError" ? new Error(`${url}: no answer after ${wait / 1000} s`) : e;
    } finally {
      clearTimeout(timer);
    }
  }
  throw last;
}

function getJSON(url) {
  if (!cache.has(url)) {
    const p = fetchJSON(url);
    p.catch(() => cache.delete(url)); // a later retry fetches again
    cache.set(url, p);
  }
  return cache.get(url);
}

export async function loadIndex() {
  return getJSON("data/index.json");
}

// Files loaded after the lab is on screen: state key -> file.
const LATER = { rangeCurve: "range_curve.json", turnRate: "turn_rate.json", compare: "compare.json", testimony: "testimony.json", rangeCurves: "range_curves.json" };

// Stage 1 resolves with the case's data object; stage 2 fills it in and calls onLate(key) per file (also on failure,
// with the error in data.failed[key]). data.pending lists what is still on its way.
export async function loadCase(cid, onLate) {
  const meta = await getJSON(`data/${cid}/meta.json`);
  const has = (f) => meta.files.includes(f);
  const first = ["results.json", "readings.json", "cues.json"].filter(has);
  let done = 0;
  const tick = () => progress(`Loading ${meta.label}: ${++done} of ${first.length} files`);
  progress(`Loading ${meta.label}: 0 of ${first.length} files`);
  const [results, readings, cues] = await Promise.all(["results.json", "readings.json", "cues.json"].map((f) =>
    has(f) ? getJSON(`data/${cid}/${f}`).then((x) => (tick(), x)) : null));
  const data = { meta, results, readings, cues, predictions: null, pending: new Set(), failed: {} };
  for (const k of Object.keys(LATER)) data[k] = null;
  for (const [k, f] of Object.entries(LATER)) {
    if (!has(f)) continue;
    data.pending.add(k);
    getJSON(`data/${cid}/${f}`)
      .then((x) => { data[k] = x; delete data.failed[k]; }, (e) => { data.failed[k] = e.message; })
      .finally(() => { data.pending.delete(k); onLate?.(k); });
  }
  return data;
}

// The predictions for one field of view (predictions_<variant>.json), merged into data.predictions in the shape
// the views read: { picture, measured, method, variants: { <variant>: ... } }. Loads once per variant.
export function loadPredictions(data, variant, onLate) {
  const vn = variant ?? "";
  const name = data.meta.predictions_files?.[vn];
  const key = `predictions:${vn}`;
  if (!name || data.predictions?.variants?.[vn] || data.pending.has(key)) return;
  data.pending.add(key);
  getJSON(`data/${data.meta.case}/${name}`)
    .then((x) => {
      data.predictions ??= { picture: x.picture, measured: x.measured, method: x.method, variants: {} };
      data.predictions.variants[vn] = x.data;
      delete data.failed.predictions;
    }, (e) => { data.failed.predictions = e.message; })
    .finally(() => { data.pending.delete(key); onLate?.("predictions"); });
}

// Retry every background file that failed (the views' "Try again" buttons).
export function retryFailed(data, variant, onLate) {
  for (const [k, f] of Object.entries(LATER)) if (data.failed[k] && data.meta.files.includes(f) && !data.pending.has(k)) {
    data.pending.add(k);
    getJSON(`data/${data.meta.case}/${f}`)
      .then((x) => { data[k] = x; delete data.failed[k]; }, (e) => { data.failed[k] = e.message; })
      .finally(() => { data.pending.delete(k); onLate?.(k); });
  }
  if (data.failed.predictions) loadPredictions(data, variant, onLate);
}

// Is a background part still loading (or failed)? The views show a placeholder until it lands.
export function partState(data, key, variant) {
  if (!data) return "loading";
  if (key === "predictions") {
    if (data.predictions?.variants?.[variant ?? ""]) return "ready";
    if (data.pending.has(`predictions:${variant ?? ""}`)) return "loading";
    return data.failed.predictions ? "failed" : data.meta.predictions_files?.[variant ?? ""] ? "loading" : "none";
  }
  if (data[key]) return "ready";
  if (data.pending.has(key)) return "loading";
  return data.failed[key] ? "failed" : "none";
}

export function frameURL(meta, i) {
  return `${meta.frames_path}f${String(i).padStart(6, "0")}.jpg`;
}

export function reading(data, field, i) {
  const f = data.readings?.fields?.[field];
  if (!f) return null;
  return { value: f.value[i], confidence: f.confidence[i], method: f.method[i], placeholder: f.placeholder ?? null };
}

export function cue(data, col, i) {
  const c = data.cues?.columns?.[col];
  return c ? c[i] : null;
}

// Predictions for the current variant, or null (not loaded yet, or none).
export function variantPredictions(data, variant) {
  const p = data.predictions;
  if (!p) return null;
  return p.variants[variant ?? ""] ?? null;
}

// The stored fit of one hypothesis that the live total uses (scoring.js envelope), as predictions.
export function fitPredictions(data, variant, hypId, fitName) {
  const v = variantPredictions(data, variant);
  const h = v?.hypotheses?.[hypId];
  if (!h) return null;
  const f = h[fitName] && h[fitName].valid !== false ? h[fitName] : h.testimony_weighted ?? h.physics_only;
  return f && f.valid !== false ? f : null;
}
