// Loads the per-case exports written by tools/build_app_data.py. Cached per URL.

const cache = new Map();

async function getJSON(url) {
  if (!cache.has(url)) {
    cache.set(url, fetch(url).then((r) => {
      if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
      return r.json();
    }));
  }
  return cache.get(url);
}

const optional = (p) => p.catch(() => null);

export async function loadIndex() {
  return getJSON("data/index.json");
}

export async function loadCase(cid) {
  const meta = await getJSON(`data/${cid}/meta.json`);
  const has = (f) => meta.files.includes(f);
  const [results, readings, cues, rangeCurve, turnRate, compare, predictions, testimony, rangeCurves] = await Promise.all([
    has("results.json") ? getJSON(`data/${cid}/results.json`) : null,
    has("readings.json") ? getJSON(`data/${cid}/readings.json`) : null,
    has("cues.json") ? getJSON(`data/${cid}/cues.json`) : null,
    has("range_curve.json") ? optional(getJSON(`data/${cid}/range_curve.json`)) : null,
    has("turn_rate.json") ? optional(getJSON(`data/${cid}/turn_rate.json`)) : null,
    has("compare.json") ? optional(getJSON(`data/${cid}/compare.json`)) : null,
    has("predictions.json") ? optional(getJSON(`data/${cid}/predictions.json`)) : null,
    has("testimony.json") ? optional(getJSON(`data/${cid}/testimony.json`)) : null,
    has("range_curves.json") ? optional(getJSON(`data/${cid}/range_curves.json`)) : null,
  ]);
  return { meta, results, readings, cues, rangeCurve, turnRate, compare, predictions, testimony, rangeCurves };
}

export function frameURL(meta, i) {
  return `${meta.frames_path}f${String(i).padStart(6, "0")}.jpg`;
}

export function reading(data, field, i) {
  const f = data.readings?.fields?.[field];
  if (!f) return null;
  return { value: f.value[i], confidence: f.confidence[i], method: f.method[i] };
}

export function cue(data, col, i) {
  const c = data.cues?.columns?.[col];
  return c ? c[i] : null;
}

// Predictions for the current variant (predictions.json), or null.
export function variantPredictions(data, variant) {
  const p = data.predictions;
  if (!p) return null;
  return p.variants[variant ?? ""] ?? p.variants[Object.keys(p.variants)[0]] ?? null;
}

// The stored fit of one hypothesis that the live total uses (scoring.js envelope), as predictions.
export function fitPredictions(data, variant, hypId, fitName) {
  const v = variantPredictions(data, variant);
  const h = v?.hypotheses?.[hypId];
  if (!h) return null;
  const f = h[fitName] && h[fitName].valid !== false ? h[fitName] : h.testimony_weighted ?? h.physics_only;
  return f && f.valid !== false ? f : null;
}
