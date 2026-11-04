// Compare analyses (M4.6): prior work's published numbers beside the lab's reproduction of each
// (docs/reproductions/<case>.json, via compare.json), a pass or fail mark from the reproduction checks, the
// three solutions drawn over the clip in one frame (range and altitude against time: the lab's hypotheses
// per frame from predictions.json, prior work at the frames it states), and the lab's best fit per hypothesis
// at the live weight. Disagreements are explained in docs/prior-work/DISAGREEMENTS.md.

import { num, kt, ft, nmi, deg, variantLabel, hypColor, timecode, esc } from "../units.js";
import { fitPredictions, partState } from "../data.js";
import { ticks, NMI_M, FT_M, altitudeM } from "../geom.js";
import { plainName } from "../glossary.js";

let api, root;

const fmtUnit = (v, u) => {
  if (v === null || v === undefined) return "";
  if (Array.isArray(v)) return v.map((x) => fmtUnit(x, u)).join(" to ");
  return u === "kt" ? kt(v) : u === "ft" ? ft(v) : u === "nmi" ? nmi(v) : u === "deg" ? deg(v, 0) : num(v, 1);
};

const PRIOR_STYLE = { pvr_close: { color: "#d9d2c3", shape: "sq" }, pvr_far: { color: "#d9d2c3", shape: "tri" }, sitrec: { color: "#c3d1d9", shape: "ci" }, aaro: { color: "#d9c3c3", shape: "sq" } };

export function mount(el, a) {
  api = a;
  root = el;
  render();
  new ResizeObserver(() => drawCharts()).observe(el);
}

function render() {
  const s = api.getState();
  if (!s.data || !root) return;
  const c = s.data.compare;
  const v = api.currentVariant();
  let html = `<div class="stack">`;
  if (c) {
    html += `<div class="panel"><div class="panel-h"><h2>Prior work: published and reproduced</h2><span class="src">${esc(c.source)}</span></div>
      <div class="panel-b" style="overflow-x:auto"><table class="data cmp"><thead><tr><th>Quantity</th>
      ${c.sources.map((src) => `<th colspan="2" class="grp" title="${esc(src.note)}">${esc(src.label)}${src.check === true ? ' <span class="pass">reproduction checks pass</span>' : src.check === false ? ' <span class="fail">a reproduction check fails</span>' : ' <span class="note">no check</span>'}</th>`).join("")}</tr>
      <tr><th></th>${c.sources.map(() => `<th class="num">published</th><th class="num">lab reproduction</th>`).join("")}</tr></thead><tbody>
      ${c.rows.map((r) => `<tr><td>${esc(r.quantity)}</td>${c.sources.map((src) => {
        const x = r.values[src.id] || {};
        return `<td class="num">${esc(fmtUnit(x.published, r.unit)) || '<span class="note">not stated</span>'}</td><td class="num">${esc(fmtUnit(x.reproduced, r.unit)) || '<span class="note">n/a</span>'}</td>`;
      }).join("")}</tr>`).join("")}</tbody></table>
      <p class="note">Each source's own inputs were used for its reproduction. Where the lab and a source disagree, the reason is in docs/prior-work/DISAGREEMENTS.md. "Not stated": the source did not publish that number.</p></div></div>`;
  } else if (partState(s.data, "compare") === "loading") {
    html += `<div class="panel"><div class="panel-b"><div class="pending"><b>Loading the prior work...</b></div></div></div>`;
  } else if (partState(s.data, "compare") === "failed") {
    html += `<div class="panel"><div class="panel-b"><div class="pending"><b>The prior work did not load.</b> Reload the page to try again.</div></div></div>`;
  } else {
    html += `<div class="panel"><div class="panel-b"><div class="pending"><b>No reproduction of prior work for ${esc(s.data.meta.label)}.</b> Sitrec and the 2023 paper analyse GIMBAL (and Sitrec and AARO GOFAST); the lab's own fits are below.</div></div></div>`;
  }
  html += `<div class="cmp-charts">
      <div class="panel fill"><div class="panel-h"><h2>Range over the clip</h2><span class="src">nmi</span></div><div class="panel-b chart" id="cmp-range"></div></div>
      <div class="panel fill"><div class="panel-h"><h2>Altitude over the clip</h2><span class="src">ft above sea level</span></div><div class="panel-b chart" id="cmp-alt"></div></div>
    </div><div class="cmp-legend" id="cmp-legend"></div>`;
  const rows = api.currentScores();
  if (rows) {
    html += `<div class="panel"><div class="panel-h"><h2>The lab: best fit per hypothesis</h2><span class="src">${esc(v.variant ? variantLabel(v.variant) + " field of view, " : "")}fit at the live testimony weight</span></div>
      <div class="panel-b" style="overflow-x:auto"><table class="data"><thead><tr><th>Hypothesis</th><th class="num">Range</th><th class="num">Altitude</th><th class="num">Air speed</th><th class="num">Ground speed</th><th class="num">Vertical speed</th><th>Motion vs wind</th></tr></thead><tbody>
      ${rows.map((r, k) => {
        const f = r.h.fits.find((x) => x.fit === r.testimonyFit) || r.h.fits[0];
        const d = f.derived;
        return `<tr><td><span class="sw" style="background:${hypColor(r.h.id, k)}"></span><span class="hid">${esc(r.h.id)}</span> <span class="note">${esc(s.expert ? r.h.label : plainName(r.h.id, r.h.label))}</span></td><td class="num">${esc(nmi(d.range_nmi_mean))}</td><td class="num">${esc(ft(d.altitude_ft_mean))}</td><td class="num">${esc(kt(d.air_speed_kt))}</td><td class="num">${esc(kt(d.ground_speed_kt))}</td><td class="num">${esc(num(d.vertical_speed_fpm))} ft/min</td><td>${esc(d.motion_vs_wind ?? "")}</td></tr>`;
      }).join("")}</tbody></table></div></div>`;
  }
  html += `</div>`;
  root.innerHTML = html;
  drawCharts();
}

function lineChart(box, o) {
  if (!box) return;
  const r = box.getBoundingClientRect();
  if (!r.width) return;
  const W = Math.max(260, r.width - 24), H = Math.max(170, r.height - 20);
  const m = { l: 66, r: 14, t: 10, b: 30 };
  const ys = [...o.series.flatMap((x) => x.pts.map((p) => p.y)), ...o.points.map((p) => p.y)].filter(Number.isFinite);
  if (!ys.length) { box.innerHTML = `<div class="empty"><div><b>${esc(o.empty ?? "Nothing to draw.")}</b></div></div>`; return; }
  let y0 = Math.min(...ys), y1 = Math.max(...ys);
  const pad = (y1 - y0) * 0.08 || Math.abs(y1) * 0.05 || 1;
  y0 -= pad; y1 += pad;
  if (o.zero && y0 > 0) y0 = 0;
  const [x0, x1] = o.xDomain;
  const X = (v) => m.l + ((v - x0) / (x1 - x0)) * (W - m.l - m.r);
  const Y = (v) => H - m.b - ((v - y0) / (y1 - y0)) * (H - m.t - m.b);
  const sym = (p) => {
    const x = X(p.x), y = Y(p.y), st = PRIOR_STYLE[p.src] ?? { color: "#d9d2c3", shape: "sq" };
    const fill = p.kind === "published" ? st.color : "none";
    const sh = st.shape === "ci" ? `<circle cx="${x}" cy="${y}" r="5"/>` : st.shape === "tri" ? `<path d="M${x},${y - 6}L${x + 6},${y + 5}L${x - 6},${y + 5}Z"/>` : `<rect x="${x - 5}" y="${y - 5}" width="10" height="10"/>`;
    return `<g class="pw" style="stroke:${st.color};fill:${fill}">${sh}<title>${esc(p.label)}: ${esc(o.fmt(p.y))} at frame ${p.frame} (${p.kind})</title></g>`;
  };
  box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.title)}">
    <g class="grid">${ticks(y0, y1, 5).map((v) => `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}"/>`).join("")}</g>
    <g class="axis">${ticks(y0, y1, 5).map((v) => `<text x="${m.l - 8}" y="${Y(v) + 4}" text-anchor="end">${num(v, o.dec ?? 0)}</text>`).join("")}
      ${ticks(x0, x1, 7).map((v) => `<text x="${X(v)}" y="${H - m.b + 15}" text-anchor="middle">${num(v)}</text>`).join("")}
      <text x="${W - m.r}" y="${H - 2}" text-anchor="end">time in the clip, s</text>
      <line x1="${m.l}" x2="${W - m.r}" y1="${H - m.b}" y2="${H - m.b}"/></g>
    ${o.series.map((x) => `<path class="curve" style="stroke:${x.color}${x.dash ? ";stroke-dasharray:4 3" : ""};stroke-width:${x.w ?? 1.6}" d="${x.pts.filter((p) => Number.isFinite(p.y)).map((p, i) => `${i ? "L" : "M"}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join("")}"><title>${esc(x.label)}</title></path>`).join("")}
    ${o.links.map((l) => `<line class="pwlink" x1="${X(l[0].x)}" y1="${Y(l[0].y)}" x2="${X(l[1].x)}" y2="${Y(l[1].y)}" style="stroke:${(PRIOR_STYLE[l[0].src] ?? {}).color ?? "#ccc"}"/>`).join("")}
    ${o.points.map(sym).join("")}
    ${Number.isFinite(o.cursor) ? `<line class="cursor" x1="${X(o.cursor)}" x2="${X(o.cursor)}" y1="${m.t}" y2="${H - m.b}"/>` : ""}
  </svg>`;
}

function drawCharts() {
  const s = api.getState();
  if (!s.data || !root) return;
  const fps = s.data.meta.fps || 29.97;
  const n = s.data.meta.n_frames;
  const xDomain = [0, (n - 1) / fps];
  const rows = api.currentScores() ?? [];
  const sR = [], sA = [];
  rows.forEach((r, k) => {
    const f = fitPredictions(s.data, s.variant, r.h.id, r.testimonyFit);
    if (!f) return;
    const step = Math.max(1, Math.floor(n / 400));
    const ptsR = [], ptsA = [];
    // altitude above sea level on the curved Earth, as the scorer and the table below report it
    for (let i = 0; i < n; i += step) { ptsR.push({ x: i / fps, y: f.range_m[i] / NMI_M }); ptsA.push({ x: i / fps, y: altitudeM(f.obj_e[i], f.obj_n[i], f.obj_u[i]) / FT_M }); }
    const sel = r.h.id === (api.currentHyp()?.h.id);
    sR.push({ label: `${r.h.id} (lab)`, color: hypColor(r.h.id, k), pts: ptsR, w: sel ? 2.4 : 1.4 });
    sA.push({ label: `${r.h.id} (lab)`, color: hypColor(r.h.id, k), pts: ptsA, w: sel ? 2.4 : 1.4 });
  });
  // the range readout on screen (GOFAST), where present; never a placeholder (FLIR1's constant 99.9)
  const rf0 = s.data.readings?.fields?.range;
  const rf = rf0 && !rf0.placeholder ? rf0 : null;
  if (rf) {
    const pts = [];
    for (let i = 0; i < n; i += 3) { const x = parseFloat(rf.value[i]); if (Number.isFinite(x)) pts.push({ x: i / fps, y: x }); }
    if (pts.length) sR.push({ label: "range readout on screen", color: "#e8ecf0", dash: true, pts, w: 1.2 });
  }
  const ptsOf = (q) => {
    const out = [], links = [];
    for (const src of s.data.compare?.sources ?? []) {
      const byKind = { published: [], reproduced: [] };
      for (const p of src.points ?? []) if (p.quantity === q) for (const kind of ["published", "reproduced"]) {
        const y = p[kind];
        if (Number.isFinite(y)) { const pt = { x: p.frame / fps, y, frame: p.frame, kind, src: src.id, label: src.label }; out.push(pt); byKind[kind].push(pt); }
      }
      for (const kind of ["published", "reproduced"]) if (byKind[kind].length === 2) links.push(byKind[kind]);
    }
    return { out, links };
  };
  const pr = ptsOf("range_nmi"), pa = ptsOf("altitude_ft");
  const cursor = s.frame / fps;
  const pst = partState(s.data, "predictions", s.variant);
  const emptyMsg = pst === "loading" ? "Loading the lab's fits..." : "Nothing to draw.";
  lineChart(root.querySelector("#cmp-range"), { title: "Range over the clip", series: sR, points: pr.out, links: pr.links, xDomain, fmt: (v) => nmi(v), dec: 0, zero: true, cursor, empty: emptyMsg });
  lineChart(root.querySelector("#cmp-alt"), { title: "Altitude over the clip", series: sA, points: pa.out, links: pa.links, xDomain, fmt: ft, cursor, empty: emptyMsg });
  const srcs = s.data.compare?.sources ?? [];
  root.querySelector("#cmp-legend").innerHTML = [
    ...rows.map((r, k) => `<span><i class="ln" style="background:${hypColor(r.h.id, k)}"></i>${esc(r.h.id)}</span>`),
    rf ? `<span><i class="ln dash"></i>range readout on screen</span>` : "",
    ...srcs.filter((x) => x.points?.length).map((x) => `<span><i class="pwk ${(PRIOR_STYLE[x.id] ?? {}).shape ?? "sq"}" style="border-color:${(PRIOR_STYLE[x.id] ?? {}).color}"></i>${esc(x.label)}</span>`),
    srcs.length ? `<span class="note">Filled mark: published; open mark: lab reproduction; thin line joins a source's start and end (only the frames it states, not its path).</span>` : `<span class="note">No prior-work points for this case.</span>`,
  ].join("");
}

export function show() { render(); }

export function update(s, ch) {
  if (ch.has("data") || ch.has("variant") || ch.has("wT") || ch.has("overrides") || ch.has("hyp") || ch.has("expert")) render();
  else if (ch.has("frame")) drawCharts();
}

export { timecode };
