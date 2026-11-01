// Compare analyses (shell): prior work's published numbers beside the lab's reproduction of each
// (docs/reproductions/<case>.json), and the lab's own best fits under the current weights.

import { num, kt, ft, nmi, deg, variantLabel } from "../units.js";
import { esc } from "../rail.js";

let api, root;

const fmtUnit = (v, u) => {
  if (v === null || v === undefined) return "";
  if (Array.isArray(v)) return v.map((x) => fmtUnit(x, u)).join(" to ");
  return u === "kt" ? kt(v) : u === "ft" ? ft(v) : u === "nmi" ? nmi(v) : u === "deg" ? deg(v, 0) : num(v, 1);
};

export function mount(el, a) { api = a; root = el; render(); }

function render() {
  const s = api.getState();
  if (!s.data || !root) return;
  const c = s.data.compare;
  const v = api.currentVariant();
  let html = `<div class="stack">`;
  if (c) {
    html += `<div class="panel"><div class="panel-h"><h2>Prior work: published and reproduced</h2><span class="src">${esc(c.source)}</span></div>
      <div class="panel-b" style="overflow-x:auto"><table class="data"><thead><tr><th>Quantity</th>
      ${c.sources.map((src) => `<th colspan="2" title="${esc(src.note)}">${esc(src.label)}${src.check === true ? ' <span class="pass">checks pass</span>' : src.check === false ? ' <span class="fail">a check fails</span>' : ""}</th>`).join("")}</tr>
      <tr><th></th>${c.sources.map(() => `<th class="num">published</th><th class="num">lab reproduction</th>`).join("")}</tr></thead><tbody>
      ${c.rows.map((r) => `<tr><td>${esc(r.quantity)}</td>${c.sources.map((src) => {
        const x = r.values[src.id] || {};
        return `<td class="num">${esc(fmtUnit(x.published, r.unit)) || '<span class="note">not stated</span>'}</td><td class="num">${esc(fmtUnit(x.reproduced, r.unit)) || '<span class="note">n/a</span>'}</td>`;
      }).join("")}</tr>`).join("")}</tbody></table></div></div>`;
  } else {
    html += `<div class="panel"><div class="panel-b"><div class="pending"><b>No reproduction of prior work for ${esc(s.data.meta.label)} yet.</b></div></div></div>`;
  }
  const rows = api.currentScores();
  if (rows) {
    html += `<div class="panel"><div class="panel-h"><h2>The lab: best fit per hypothesis</h2><span class="src">${esc(v.variant ? variantLabel(v.variant) + " field of view, " : "")}fit at the live testimony weight</span></div>
      <div class="panel-b" style="overflow-x:auto"><table class="data"><thead><tr><th>Hypothesis</th><th class="num">Range</th><th class="num">Altitude</th><th class="num">Air speed</th><th class="num">Ground speed</th><th class="num">Vertical speed</th><th>Motion vs wind</th></tr></thead><tbody>
      ${rows.map((r) => {
        const f = r.h.fits.find((x) => x.fit === r.testimonyFit) || r.h.fits[0];
        const d = f.derived;
        return `<tr><td><span class="hid">${esc(r.h.id)}</span> <span class="note">${esc(r.h.label)}</span></td><td class="num">${esc(nmi(d.range_nmi_mean))}</td><td class="num">${esc(ft(d.altitude_ft_mean))}</td><td class="num">${esc(kt(d.air_speed_kt))}</td><td class="num">${esc(kt(d.ground_speed_kt))}</td><td class="num">${esc(num(d.vertical_speed_fpm))} ft/min</td><td>${esc(d.motion_vs_wind ?? "")}</td></tr>`;
      }).join("")}</tbody></table></div></div>`;
  }
  html += `<div class="pending"><b>Coming in M4.6:</b> Sitrec's solution, the 2023 paper's solution and the lab's drawn side by side in the same 3D frame, with each disagreement explained (docs/prior-work/DISAGREEMENTS.md).</div></div>`;
  root.innerHTML = html;
}

export function update(s, ch) { if (ch.has("data") || ch.has("variant") || ch.has("wT")) render(); }
