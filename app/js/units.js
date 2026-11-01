// Display formatting. Internal data stays in the units of the export (SI or the source's own);
// everything a person reads goes through here: feet, knots and mph, dates MM/DD/YYYY.

export const KT_TO_MPH = 1.150779;
export const NMI_TO_MI = 1.150779;
export const M_TO_FT = 3.280839895;

const nf = (d) => new Intl.NumberFormat("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const F0 = nf(0), F1 = nf(1), F2 = nf(2);

export function num(v, d = 0) {
  if (v === null || v === undefined || !Number.isFinite(v)) return "n/a";
  // true minus sign reads better in monospace columns
  return (d === 0 ? F0 : d === 1 ? F1 : d === 2 ? F2 : nf(d)).format(v).replace("-", "−");
}

export function signed(v, d = 1) {
  if (!Number.isFinite(v)) return "n/a";
  if (Math.abs(v) < 0.5 * 10 ** -d) return num(0, d);
  return (v > 0 ? "+" : "") + num(v, d);
}

export const kt = (v) => (Number.isFinite(v) ? `${num(v)} kt (${num(v * KT_TO_MPH)} mph)` : "n/a");
export const ktShort = (v) => (Number.isFinite(v) ? `${num(v)} kt` : "n/a");
export const ft = (v) => (Number.isFinite(v) ? `${num(v)} ft` : "n/a");
export const fpm = (v) => (Number.isFinite(v) ? `${signed(v, 0)} ft/min` : "n/a");
export const nmi = (v, d = 1) => (Number.isFinite(v) ? `${num(v, d)} nmi (${num(v * NMI_TO_MI, d)} mi)` : "n/a");
export const deg = (v, d = 1) => (Number.isFinite(v) ? `${num(v, d)}°` : "n/a");
export const meters = (v) => (Number.isFinite(v) ? `${num(v * M_TO_FT)} ft` : "n/a");

export function timecode(s) {
  if (!Number.isFinite(s)) return "n/a";
  const m = Math.floor(s / 60);
  const r = s - m * 60;
  return `${String(m).padStart(2, "0")}:${r.toFixed(2).padStart(5, "0")}`;
}

// Confidence (0 to 1) with the project's low-confidence threshold (symbology_summary.json: 0.30).
export const LOW_CONF = 0.3;
export const conf = (c) => (Number.isFinite(c) ? c.toFixed(2) : "n/a");

// On-screen readout fields: label and how to show the raw value.
export const FIELDS = {
  azimuth: { label: "Azimuth", fmt: (v) => v.replace(/^(\d+)([LR])$/, "$1° $2") },
  elevation: { label: "Elevation", fmt: (v) => `${v}°` },
  range: { label: "Range", fmt: (v) => (isFinite(+v) ? nmi(+v) : v) },
  closure: { label: "Closure", fmt: (v) => (isFinite(+v) ? kt(+v) : v) },
  airspeed: { label: "Indicated air speed", fmt: (v) => (isFinite(+v) ? kt(+v) : v) },
  altitude: { label: "Altitude", fmt: (v) => (isFinite(+v) ? ft(+v) : v) },
  mach: { label: "Mach", fmt: (v) => v },
  fov: { label: "Field of view", fmt: (v) => v },
  zoom: { label: "Zoom", fmt: (v) => v },
  sensor: { label: "Sensor mode", fmt: (v) => v },
  polarity: { label: "Polarity", fmt: (v) => ({ WHT: "white hot", BLK: "black hot" }[v] || v) },
  clock: { label: "Clock", fmt: (v) => v },
};
export const FIELD_ORDER = ["azimuth", "elevation", "range", "closure", "airspeed", "altitude", "mach", "fov", "zoom", "sensor", "polarity", "clock"];

export function variantLabel(v) {
  if (!v) return "single run";
  const m = /^fov(\d+)$/.exec(v); // fov035 = 0.35 deg, fov070 = 0.70 deg (hundredths of a degree)
  return m ? `${(+m[1] / 100).toFixed(2)}°` : v;
}

// One color per hypothesis for paths and curves (never the two total colors, the cue amber or warn red).
const HYP_COLORS = { "H-AC": "#e89f6b", "H-ART": "#9aa6b2", "H-BAL": "#6fcfb5", "H-CLOSE": "#e57fae", "H-SLOW": "#b9cc6a", "H-WIT": "#7f9cf5" };
const SPARE = ["#d6c38f", "#a98fd6", "#8fc7d6", "#d68f8f"];
export function hypColor(id, i = 0) { return HYP_COLORS[id] ?? SPARE[i % SPARE.length]; }

export const mi = (vNmi) => vNmi * NMI_TO_MI;
export const mph = (vKt) => vKt * KT_TO_MPH;
