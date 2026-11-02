// Range explorer (M4.5): the object's air speed, altitude and peak acceleration as functions of assumed range,
// and the sight-line misfit against range, as SVG charts sharing the x axis. Curves:
// - the scorer's angles-only probe (results.json range_curve_angles_only: a constant-velocity object at each
//   fixed range, testimony weight 0), interpolated linearly between grid points (geom.interpCurve; parity test
//   tests/js/geom.test.mjs);
// - per-hypothesis curves from data/derived/<case>/range_curves.csv when the scorer has written them;
// - each hypothesis's own best fit (at the live weight) as a marker, with the band of ranges they occupy.
// Reference marks: balloon drift (near 0 kt air speed), birds 15 to 60 kt, airliners 400 to 500 kt, Mach 1 at
// the curve's altitude (ISA), 1 g and 9 g. One range slider drives a cursor through every chart.

import { num, kt, ft, nmi, hypColor, KT_TO_MPH } from "../units.js";
import { esc } from "../rail.js";
import { interpCurve, soundSpeedKt, ticks } from "../geom.js";
import { fitPredictions } from "../data.js";

export { interpCurve };

const BANDS = [
  { y0: 0, y1: 8, label: "balloon: drifts with the wind, air speed near 0" },
  { y0: 15, y1: 60, label: "birds, 15 to 60 kt" },
  { y0: 400, y1: 500, label: "airliners, 400 to 500 kt" },
];

let api, root;

export function mount(el, a) {
  api = a;
  root = el;
  el.innerHTML = `
    <div class="rg">
      <div class="panel rg-top"><div class="panel-b">
        <div class="range-ctl"><label for="rg-r">Assumed range</label><input id="rg-r" type="range" min="1" max="45" step="0.5" value="10"><output id="rg-out"></output></div>
        <div class="rg-legend" id="rg-legend"></div>
      </div></div>
      <div class="rg-charts">
        <div class="panel fill"><div class="panel-h"><h2>Air speed</h2><span class="src">kt, log scale (mph = kt x ${KT_TO_MPH.toFixed(3)}); dotted: Mach 1 at the probe's altitude</span></div><div class="panel-b chart" id="rg-speed"></div></div>
        <div class="panel fill"><div class="panel-h"><h2>Altitude</h2><span class="src">ft</span></div><div class="panel-b chart" id="rg-alt"></div></div>
        <div class="panel fill"><div class="panel-h"><h2>Peak acceleration</h2><span class="src">g, log scale</span></div><div class="panel-b chart" id="rg-acc"></div></div>
        <div class="panel fill"><div class="panel-h"><h2>Sight-line misfit</h2><span class="src">log-likelihood below the best, log scale</span></div><div class="panel-b chart" id="rg-mis"></div></div>
      </div>
      <div class="panel"><div class="panel-b" id="rg-read" style="overflow-x:auto"></div></div>
    </div>`;
  const sl = el.querySelector("#rg-r");
  sl.addEventListener("input", () => api.set({ range: +sl.value }));
  new ResizeObserver(() => render()).observe(el.querySelector("#rg-speed"));
  render();
}

// One chart. x: assumed range (nmi). opts: series [{pts:[{x,y}], color, dash, label}], markers [{x,y,color,label}],
// bands [{y0,y1,label}], lines [{y,label}], refCurve {pts, label}, log (bool), xDomain, cursor, fmt, xBand.
function chart(box, o) {
  const r = box.getBoundingClientRect();
  const W = Math.max(220, r.width - 24), H = Math.max(150, r.height - 20);
  const m = { l: 62, r: 14, t: 10, b: 30 };
  const ys = [...o.series.flatMap((s) => s.pts.map((p) => p.y)), ...o.markers.map((p) => p.y), ...(o.refCurve?.pts.map((p) => p.y) ?? []),
    ...o.lines.map((l) => l.y), ...o.bands.flatMap((b) => [b.y1])].filter((y) => Number.isFinite(y) && (!o.log || y > 0));
  if (!ys.length) { box.innerHTML = `<div class="empty"><div><b>No data.</b>${esc(o.empty || "")}</div></div>`; return; }
  const [x0, x1] = o.xDomain;
  let y0 = o.log ? Math.max(o.yMin ?? 1e-4, Math.min(...ys) / 2) : Math.min(0, ...ys);
  let y1 = o.log ? Math.max(...ys) * 2 : Math.max(...ys) * 1.08;
  if (o.yMax) y1 = Math.min(y1, o.yMax);
  if (!(y1 > y0)) y1 = y0 + 1;
  const ty = (v) => (o.log ? Math.log10(v) : v);
  const X = (v) => m.l + ((v - x0) / (x1 - x0)) * (W - m.l - m.r);
  const Y = (v) => H - m.b - ((ty(Math.min(Math.max(v, y0), y1)) - ty(y0)) / (ty(y1) - ty(y0))) * (H - m.t - m.b);
  const yt = o.yTicks ? o.yTicks.filter((v) => v >= y0 && v <= y1) : o.log ? logTicks(y0, y1) : ticks(y0, y1, 5);
  const path = (pts) => pts.filter((p) => Number.isFinite(p.y) && (!o.log || p.y > 0)).map((p, i) => `${i ? "L" : "M"}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join("");
  const inX = (p) => p.x >= x0 && p.x <= x1;
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.title)} against assumed range">
    ${o.xBand ? `<rect class="hband" x="${X(Math.max(x0, o.xBand[0]))}" y="${m.t}" width="${Math.max(2, X(Math.min(x1, o.xBand[1])) - X(Math.max(x0, o.xBand[0])))}" height="${H - m.t - m.b}"><title>Range interval of the hypotheses' best fits</title></rect>` : ""}
    <g class="grid">${yt.map((v) => `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}"/>`).join("")}</g>
    <g class="bands">${o.bands.filter((b) => b.y0 < y1).map((b) => { const ya = Y(Math.min(b.y1, y1)), yb = Y(Math.max(b.y0, y0)); return `<rect x="${m.l}" width="${W - m.l - m.r}" y="${ya}" height="${Math.max(1, yb - ya)}"/><text x="${W - m.r - 4}" y="${(ya + yb) / 2 + 4}" text-anchor="end">${esc(b.label)}</text>`; }).join("")}</g>
    <g class="axis">${yt.map((v) => `<text x="${m.l - 8}" y="${Y(v) + 4}" text-anchor="end">${o.fmtTick ? o.fmtTick(v) : num(v)}</text>`).join("")}
      ${ticks(x0, x1, 8).map((v) => `<text x="${X(v)}" y="${H - m.b + 15}" text-anchor="middle">${num(v)}</text>`).join("")}
      <text x="${W - m.r}" y="${H - 2}" text-anchor="end">assumed range, nmi</text>
      <line x1="${m.l}" x2="${W - m.r}" y1="${H - m.b}" y2="${H - m.b}"/></g>
    <g class="thr">${o.lines.filter((l) => l.y >= y0 && l.y <= y1).map((l) => `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(l.y)}" y2="${Y(l.y)}"/><text x="${W - m.r - 4}" y="${Y(l.y) - 4}" text-anchor="end">${esc(l.label)}</text>`).join("")}
      ${o.refCurve ? `<path class="ref" d="${path(o.refCurve.pts.filter(inX))}"/>${(() => { const ps = o.refCurve.pts.filter(inX); const q = ps[Math.floor(ps.length * 0.12)]; return q ? `<text x="${X(q.x)}" y="${Y(q.y) + 13}">${esc(o.refCurve.label)}</text>` : ""; })()}` : ""}</g>
    ${o.series.map((s) => `<path class="curve" style="stroke:${s.color}${s.dash ? ";stroke-dasharray:5 4" : ""}" d="${path(s.pts.filter(inX))}"/>
      ${s.pts.filter(inX).map((p) => Number.isFinite(p.y) && (!o.log || p.y > 0) ? `<circle cx="${X(p.x)}" cy="${Y(p.y)}" r="2.4" fill="${s.color}"><title>${esc(s.label)}, ${esc(nmi(p.x))}: ${esc(o.fmt(p.y))}</title></circle>` : "").join("")}`).join("")}
    ${o.markers.filter((p) => inX(p) && Number.isFinite(p.y) && (!o.log || p.y > 0)).map((p) => `<g class="mk"><rect x="${X(p.x) - 5}" y="${Y(p.y) - 5}" width="10" height="10" transform="rotate(45 ${X(p.x)} ${Y(p.y)})" fill="${p.color}"/><title>${esc(p.label)}: ${esc(nmi(p.x))}, ${esc(o.fmt(p.y))}</title></g>`).join("")}
    ${Number.isFinite(o.cursor) && o.cursor >= x0 && o.cursor <= x1 ? `<line class="cursor" x1="${X(o.cursor)}" x2="${X(o.cursor)}" y1="${m.t}" y2="${H - m.b}"/>` : ""}
  </svg>`;
}

function logTicks(a, b) {
  const out = [];
  for (let e = Math.floor(Math.log10(a)); e <= Math.ceil(Math.log10(b)); e++) {
    const v = Math.pow(10, e);
    if (v >= a && v <= b) out.push(v);
  }
  return out.length ? out : [a, b];
}

const fmtG = (v) => (v >= 1 ? num(v, v < 10 ? 1 : 0) : v >= 0.01 ? num(v, 2) : v.toExponential(0).replace("-", "−"));

const FLOOR_TOTAL = -5e5; // the scorer's "outside the constraint" label threshold (results pages)

function curves(s) {
  const v = api.currentVariant();
  const probe = (s.data.rangeCurve?.variants?.[v?.variant ?? ""] ?? []).filter((p) => p.valid !== false && Number.isFinite(p.range_nmi))
    .sort((a, b) => a.range_nmi - b.range_nmi);
  // Per-hypothesis grid points the scorer marked invalid, or whose total sits at the likelihood floor (outside a
  // hypothesis's own constraint, for example below sea level), are not drawn: they are not solutions.
  const raw = s.data.rangeCurves?.variants?.[v?.variant ?? ""] ?? null;
  const ok = (p) => p.valid !== false && p.valid_physics_only !== false && Number.isFinite(p.range_nmi)
    && Number.isFinite(p.total_physics_only) && p.total_physics_only > FLOOR_TOTAL;
  const perH = raw ? Object.fromEntries(Object.entries(raw).map(([h, c]) => [h, c.filter(ok)]).filter(([, c]) => c.length)) : null;
  return { probe, perH: perH && Object.keys(perH).length ? perH : null };
}

function render() {
  const s = api.getState();
  if (!s.data || !root) return;
  const { probe, perH } = curves(s);
  const rows = api.currentScores() ?? [];
  const charts = ["#rg-speed", "#rg-alt", "#rg-acc", "#rg-mis"].map((q) => root.querySelector(q));
  const read = root.querySelector("#rg-read");
  if (!probe.length && !perH) {
    for (const c of charts) c.innerHTML = `<div class="empty"><div><b>No range grid for ${esc(s.data.meta.label)}.</b>The scoring run did not write curves over range for this case.</div></div>`;
    read.innerHTML = "";
    return;
  }
  // markers: each hypothesis's own best fit at the live weight
  const markers = rows.map((r, k) => {
    const f = r.h.fits.find((x) => x.fit === r.testimonyFit) || r.h.fits[0];
    const pf = fitPredictions(s.data, s.variant, r.h.id, r.testimonyFit);
    return { id: r.h.id, color: hypColor(r.h.id, k), x: f.derived.range_nmi_mean, speed: f.derived.air_speed_kt, alt: f.derived.altitude_ft_mean, acc: pf?.max_accel_g ?? null, label: `${r.h.id} best fit` };
  }).filter((p) => Number.isFinite(p.x));
  const xs = [...probe.map((p) => p.range_nmi), ...markers.map((p) => p.x), ...Object.values(perH ?? {}).flat().map((p) => p.range_nmi)].filter(Number.isFinite);
  const xDomain = [0, Math.max(...xs) * 1.04];
  const sl = root.querySelector("#rg-r");
  sl.min = "1"; sl.max = String(Math.ceil(xDomain[1]));
  const cur = s.range ?? Math.round((markers[0]?.x ?? 10) * 2) / 2;
  if (+sl.value !== cur) sl.value = String(cur);
  root.querySelector("#rg-out").textContent = nmi(cur);
  const xBand = markers.length ? [Math.min(...markers.map((p) => p.x)), Math.max(...markers.map((p) => p.x))] : null;

  const ser = (key, scale = 1) => {
    const out = [];
    if (probe.length && probe.some((p) => Number.isFinite(p[key]))) out.push({ label: "angles-only probe", color: "#e8ecf0", pts: probe.map((p) => ({ x: p.range_nmi, y: Number.isFinite(p[key]) ? p[key] * scale : NaN })) });
    if (perH) rows.forEach((r, k) => { const c = perH[r.h.id]; if (c && c.some((p) => Number.isFinite(p[key]))) out.push({ label: r.h.id, color: hypColor(r.h.id, k), dash: true, pts: c.map((p) => ({ x: p.range_nmi, y: Number.isFinite(p[key]) ? p[key] * scale : NaN })) }); });
    return out;
  };
  const mach = probe.length ? { label: "Mach 1", pts: probe.map((p) => ({ x: p.range_nmi, y: soundSpeedKt(p.altitude_ft_mean) })) } : null;
  const common = { xDomain, cursor: cur, xBand };
  const clamp1 = (v) => (Number.isFinite(v) ? Math.max(1, v) : v);
  chart(charts[0], { ...common, title: "Air speed", series: ser("air_speed_kt").map((x) => ({ ...x, pts: x.pts.map((p) => ({ ...p, y: clamp1(p.y) })) })),
    markers: markers.map((p) => ({ x: p.x, y: clamp1(p.speed), color: p.color, label: `${p.label} (${kt(p.speed)})` })), bands: BANDS.map((b) => ({ ...b, y0: Math.max(1, b.y0) })),
    lines: [], refCurve: mach, fmt: kt, log: true, yMin: 1, yTicks: [1, 3, 10, 30, 100, 300, 1000, 3000, 10000] });
  chart(charts[1], { ...common, title: "Altitude", series: ser("altitude_ft_mean"), markers: markers.map((p) => ({ x: p.x, y: p.alt, color: p.color, label: p.label })), bands: [], lines: [{ y: 0, label: "sea level" }], fmt: ft });
  const accSer = ser("max_accel_g");
  chart(charts[2], { ...common, title: "Peak acceleration", series: accSer, markers: markers.filter((p) => p.acc > 0).map((p) => ({ x: p.x, y: p.acc, color: p.color, label: p.label })), bands: [], lines: [{ y: 1, label: "1 g" }, { y: 9, label: "9 g, fighter limit" }], log: true, fmt: (v) => `${fmtG(v)} g`, fmtTick: fmtG });
  // misfit: probe sight-line log-likelihood below its best (log scale on 1 + gap)
  const misSer = [];
  if (probe.length && probe.some((p) => Number.isFinite(p.line_of_sight_loglik))) {
    const best = Math.max(...probe.map((p) => p.line_of_sight_loglik).filter(Number.isFinite));
    misSer.push({ label: "angles-only probe", color: "#e8ecf0", pts: probe.map((p) => ({ x: p.range_nmi, y: 1 + best - p.line_of_sight_loglik })) });
  }
  if (perH) for (const key of ["total_physics_only", "line_of_sight_loglik"]) {
    const any = rows.some((r) => perH[r.h.id]?.some((p) => Number.isFinite(p[key])));
    if (!any) continue;
    const best = Math.max(...rows.flatMap((r) => (perH[r.h.id] ?? []).map((p) => p[key])).filter(Number.isFinite));
    rows.forEach((r, k) => { const c = perH[r.h.id]; if (c) misSer.push({ label: `${r.h.id} (${key.replace(/_/g, " ")})`, color: hypColor(r.h.id, k), dash: true, pts: c.map((p) => ({ x: p.range_nmi, y: 1 + best - p[key] })) }); });
    break;
  }
  chart(charts[3], { ...common, title: "Sight-line misfit", series: misSer, markers: [], bands: [], lines: [{ y: 3.3, label: "2.3 below the best: likelihood ratio 10" }], log: true, yMin: 1, yTicks: [1, 11, 101, 1001, 10001, 100001],
    fmt: (v) => `${num(v - 1, 1)} below the best`, fmtTick: (v) => num(v - 1) });

  // legend
  root.querySelector("#rg-legend").innerHTML = [
    probe.length ? `<span><i class="ln" style="background:#e8ecf0"></i>Angles-only probe (constant velocity, testimony weight 0)</span>` : "",
    perH ? `<span><i class="ln dash"></i>Per-hypothesis curves (range_curves.csv)</span>` : `<span class="note">No per-hypothesis curves over range yet (range_curves.csv not written by the scorer).</span>`,
    ...markers.map((p) => `<span><i class="dm" style="background:${p.color}"></i>${esc(p.id)}</span>`),
    `<span><i class="bd"></i>Best-fit range band</span>`,
  ].join("");

  // readout at the cursor
  const at = probe.length ? interpCurve(probe, cur) : null;
  const tr = [];
  if (at) tr.push(["Angles-only probe", at.air_speed_kt, at.ground_speed_kt, at.altitude_ft_mean, null, at.line_of_sight_loglik]);
  else if (probe.length) tr.push(["Angles-only probe", null, null, null, null, null, "outside the grid"]);
  if (perH) rows.forEach((r) => { const c = perH[r.h.id]; const p = c ? interpCurve(c, cur) : null; if (p) tr.push([r.h.id, p.air_speed_kt, p.ground_speed_kt, p.altitude_ft_mean, p.max_accel_g, p.line_of_sight_loglik]); });
  read.innerHTML = `<table class="data"><thead><tr><th>At ${esc(nmi(cur))}</th><th class="num">Air speed</th><th class="num">Ground speed</th><th class="num">Altitude</th><th class="num">Peak acceleration</th><th class="num">Sight-line log-likelihood</th></tr></thead><tbody>
    ${tr.map((x) => `<tr><td>${esc(x[0])}</td>${x[6] ? `<td colspan="5" class="note">${esc(x[6])}</td>` : `<td class="num">${esc(kt(x[1]))}</td><td class="num">${esc(kt(x[2]))}</td><td class="num">${esc(ft(x[3]))}</td><td class="num">${x[4] == null ? '<span class="note">n/a</span>' : esc(fmtG(x[4]) + " g")}</td><td class="num">${esc(num(x[5], 1))}</td>`}</tr>`).join("")}
    </tbody></table>
    <p class="note">Probe values are linear between the scorer's grid points. The probe flies a constant velocity, so its acceleration is zero by construction; the acceleration chart shows each hypothesis's own best fit (and per-hypothesis curves when the scorer writes them). Markers sit at each hypothesis's mean range at the live testimony weight.</p>`;
}

export function update(s, ch) {
  if (["data", "variant", "range", "wT", "hyp", "overrides"].some((k) => ch.has(k))) render();
}
