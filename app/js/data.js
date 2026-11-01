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
  const [results, readings, cues, rangeCurve, turnRate, compare] = await Promise.all([
    has("results.json") ? getJSON(`data/${cid}/results.json`) : null,
    has("readings.json") ? getJSON(`data/${cid}/readings.json`) : null,
    has("cues.json") ? getJSON(`data/${cid}/cues.json`) : null,
    has("range_curve.json") ? optional(getJSON(`data/${cid}/range_curve.json`)) : null,
    has("turn_rate.json") ? optional(getJSON(`data/${cid}/turn_rate.json`)) : null,
    has("compare.json") ? optional(getJSON(`data/${cid}/compare.json`)) : null,
  ]);
  return { meta, results, readings, cues, rangeCurve, turnRate, compare };
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
