// Range explorer (shell): the object's speed and altitude as functions of assumed range, from the
// Python range grid (angles-only fit, testimony weight 0), with physically notable speeds marked.
// Full version (M4.5) adds acceleration and a node parity test on the interpolation.

import { num, kt, ft, nmi, KT_TO_MPH } from "../units.js";
import { esc } from "../rail.js";

// Linear interpolation on the valid grid points. Returns null outside the grid.
export function interpCurve(curve, r) {
  const pts = curve.filter((p) => p.valid !== false && Number.isFinite(p.range_nmi)).sort((a, b) => a.range_nmi - b.range_nmi);
  if (!pts.length || r < pts[0].range_nmi || r > pts[pts.length - 1].range_nmi) return null;
  let j = pts.findIndex((p) => p.range_nmi >= r);
  if (pts[j].range_nmi === r) return { ...pts[j] };
  const a = pts[j - 1], b = pts[j], t = (r - a.range_nmi) / (b.range_nmi - a.range_nmi);
  const out = { range_nmi: r };
  for (const k of Object.keys(a)) if (typeof a[k] === "number" && typeof b[k] === "number") out[k] = a[k] + t * (b[k] - a[k]);
  return out;
}

// Reference speeds (air speed, kt). Approximate and labelled as such.
const THRESHOLDS = [
  { kt: 0, label: "balloon: drifts with the wind (0 kt air speed)" },
  { kt: 45, label: "fast birds, about 45 kt" },
  { kt: 450, label: "airliner cruise, about 450 kt" },
  { kt: 602, label: "speed of sound at 25,000 ft (ISA), 602 kt" },
];

let api, root;

export function mount(el, a) {
  api = a;
  root = el;
  el.innerHTML = `
    <div class="grid2" style="grid-template-rows:1fr auto">
      <div class="panel fill"><div class="panel-h"><h2>Air speed vs assumed range</h2><span class="src" id="rg-src"></span></div><div class="panel-b chart" id="rg-speed"></div></div>
      <div class="panel fill"><div class="panel-h"><h2>Altitude vs assumed range</h2><span class="src">ft</span></div><div class="panel-b chart" id="rg-alt"></div></div>
      <div class="panel" style="grid-column:1/-1"><div class="panel-b" id="rg-note"></div></div>
    </div>`;
  new ResizeObserver(() => render()).observe(el.querySelector("#rg-speed"));
  render();
}

function chart(box, pts, key, { thresholds = [], yLabel, fmt }) {
  const r = box.getBoundingClientRect();
  const W = Math.max(200, r.width - 24), H = Math.max(160, r.height - 20);
  const m = { l: 62, r: 16, t: 12, b: 34 };
  const xs = pts.map((p) => p.range_nmi), ys = pts.map((p) => p[key]).concat(thresholds.map((t) => t.kt));
  const x0 = 0, x1 = Math.max(...xs) * 1.04;
  const y0 = Math.min(0, ...ys), y1 = Math.max(...ys) * 1.08;
  const X = (v) => m.l + ((v - x0) / (x1 - x0)) * (W - m.l - m.r);
  const Y = (v) => H - m.b - ((v - y0) / (y1 - y0)) * (H - m.t - m.b);
  const ticks = (a, b, n) => { const st = Math.pow(10, Math.floor(Math.log10((b - a) / n))); const s = [1, 2, 5, 10].map((k) => k * st).find((k) => (b - a) / k <= n); const o = []; for (let v = Math.ceil(a / s) * s; v <= b; v += s) o.push(v); return o; };
  const path = pts.map((p, i) => `${i ? "L" : "M"}${X(p.range_nmi).toFixed(1)},${Y(p[key]).toFixed(1)}`).join("");
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(yLabel)} against assumed range">
    <g class="grid">${ticks(y0, y1, 6).map((v) => `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}"/>`).join("")}</g>
    <g class="axis">${ticks(y0, y1, 6).map((v) => `<text x="${m.l - 8}" y="${Y(v) + 4}" text-anchor="end">${num(v)}</text>`).join("")}
      ${ticks(x0, x1, 8).map((v) => `<text x="${X(v)}" y="${H - m.b + 16}" text-anchor="middle">${num(v)}</text>`).join("")}
      <text x="${W - m.r}" y="${H - 4}" text-anchor="end">assumed range, nmi</text>
      <line x1="${m.l}" x2="${W - m.r}" y1="${H - m.b}" y2="${H - m.b}"/></g>
    <g class="thr">${thresholds.map((t) => `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(t.kt)}" y2="${Y(t.kt)}"/><text x="${m.l + 6}" y="${Y(t.kt) - 4}">${esc(t.label)}</text>`).join("")}</g>
    <path class="curve" d="${path}"/>
    ${pts.map((p) => `<circle cx="${X(p.range_nmi)}" cy="${Y(p[key])}" r="2.6" fill="var(--text)"><title>${esc(nmi(p.range_nmi))}: ${esc(fmt(p[key]))}</title></circle>`).join("")}
  </svg>`;
}

function render() {
  const s = api.getState();
  if (!s.data || !root) return;
  const v = api.currentVariant();
  const curve = s.data.rangeCurve?.variants?.[v?.variant ?? ""];
  const sp = root.querySelector("#rg-speed"), al = root.querySelector("#rg-alt"), note = root.querySelector("#rg-note");
  if (!curve?.length) {
    sp.innerHTML = al.innerHTML = `<div class="empty"><div><b>No range grid for ${esc(s.data.meta.label)} yet.</b>The range grid comes from the scoring run, which has not run for this case.</div></div>`;
    note.innerHTML = "";
    note.parentElement.hidden = true;
    root.querySelector("#rg-src").textContent = "";
    return;
  }
  note.parentElement.hidden = false;
  const pts = curve.filter((p) => p.valid !== false).sort((a, b) => a.range_nmi - b.range_nmi);
  root.querySelector("#rg-src").textContent = `kt; ${pts.length} grid points`;
  chart(sp, pts, "air_speed_kt", { thresholds: THRESHOLDS, yLabel: "Air speed, kt", fmt: kt });
  chart(al, pts, "altitude_ft_mean", { yLabel: "Altitude, ft", fmt: ft });
  const best = pts.reduce((a, b) => (b.line_of_sight_loglik > a.line_of_sight_loglik ? b : a));
  note.innerHTML = `<span class="note">Each point is a whole-clip fit of a smooth path to the sight-line readouts with range held fixed (testimony weight 0). Best sight-line fit on this grid:
    <span class="num" style="color:var(--text)">${esc(nmi(best.range_nmi))}</span>, air speed <span class="num" style="color:var(--text)">${esc(kt(best.air_speed_kt))}</span>.
    Speeds in mph: multiply knots by ${KT_TO_MPH.toFixed(3)}. Acceleration and the parity test on this interpolation come in M4.5.</span>`;
}

export function update(s, ch) {
  if (ch.has("data") || ch.has("variant")) render();
}
