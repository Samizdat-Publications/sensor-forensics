// Right rail: both totals per hypothesis (D-011), the live testimony weight, flags, and the
// on-screen readouts at the current frame. Present on every view.

import { num, signed, conf, LOW_CONF, FIELDS, FIELD_ORDER, variantLabel } from "./units.js";
import { reading } from "./data.js";

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// Bar length for a gap below the best total (log units, 0 = best). Log scale so a gap of
// thousands still reads as "far" without flattening the gaps of a few units.
export function barFrac(gap) {
  if (!Number.isFinite(gap)) return 0;
  return Math.max(0.02, 1 - Math.log10(1 + Math.abs(gap)) / 4);
}

let built = false;

export function renderRail(el, api, changed) {
  const s = api.getState();
  if (!s.data) return;
  const caseChanged = changed.has("data") || changed.has("caseId") || changed.has("variant");
  if (!built || caseChanged) { build(el, api); built = true; }
  if (caseChanged || changed.has("wT") || changed.has("hyp")) scores(el, api);
  if (caseChanged || changed.has("frame")) readouts(el, api);
}

function build(el, api) {
  const s = api.getState();
  const v = api.currentVariant();
  const meta = s.data.meta;
  if (!v) {
    el.innerHTML = `
      <section><div class="sec-h"><h2>Scores</h2><span class="src">${esc(meta.label)}</span></div>
        <div class="panel-b"><div class="pending"><b>Not scored yet.</b> ${esc(meta.label)} has on-screen readouts and image cues for all
        ${num(meta.n_frames)} frames; hypothesis scoring for this case is planned but has not run, so there are no totals to show.</div></div>
      </section>
      <section id="rail-readouts"></section>`;
    return;
  }
  const w0 = v.weights.testimony;
  el.innerHTML = `
    <section>
      <div class="sec-h"><h2>Scores</h2><span class="src">${esc(meta.label)} ${esc(v.variant ? variantLabel(v.variant) : "")} log-likelihood</span></div>
      <div class="weight">
        <div class="weight-row">
          <label for="wT">Testimony weight</label>
          <span><output id="wT-out" for="wT">${(s.wT ?? w0).toFixed(2)}</output>
          <button class="reset" id="wT-reset" title="Back to the default (D-011)">Default ${w0.toFixed(1)}</button></span>
          <input id="wT" type="range" min="0" max="2" step="0.05" value="${s.wT ?? w0}" aria-describedby="wT-help">
          <div class="ticks" aria-hidden="true"><span>0 physics only</span><span>1</span><span>2</span></div>
        </div>
      </div>
      <div class="legend"><span class="p"><i></i>Physics only (fixed)</span><span class="t"><i></i>Testimony weighted (live)</span></div>
      <table class="scores" aria-describedby="wT-help">
        <thead><tr><th>Hypothesis</th><th class="r">Physics only</th><th class="r">With testimony</th></tr></thead>
        <tbody id="score-rows"></tbody>
      </table>
      <p class="note" id="wT-help" style="padding:6px 16px 12px;margin:0">Higher is better; a gap of 2.3 is a likelihood ratio of 10.
      Totals are recomputed here from each criterion's log-likelihood. Not a verdict on what the object was.</p>
    </section>
    <section>
      <div class="sec-h"><h2>Read first</h2><span class="src">${v.flags.length} flags</span></div>
      <ul class="flags">${v.flags.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>
    </section>
    <section id="rail-readouts"></section>`;
  const input = el.querySelector("#wT");
  input.addEventListener("input", () => api.set({ wT: +input.value }));
  el.querySelector("#wT-reset").addEventListener("click", () => api.set({ wT: w0 }));
}

function scores(el, api) {
  const s = api.getState();
  const rows = api.currentScores();
  const tb = el.querySelector("#score-rows");
  if (!rows || !tb) return;
  const v = api.currentVariant();
  const w = s.wT ?? v.weights.testimony;
  el.querySelector("#wT-out").textContent = w.toFixed(2);
  const input = el.querySelector("#wT");
  if (+input.value !== w) input.value = w;
  tb.innerHTML = rows.map((r) => {
    // Flag only where the solver itself fitted (the default weight, and the physics-only total): there a stored
    // fit beating the solver's fit is an optimiser shortfall. At other weights picking the other fit is expected.
    const atFit = Math.abs(w - v.weights.testimony) < 1e-9;
    const sf = atFit && r.shortfall > 0.01 ? `<span class="flag-dot" title="The physics-only fit beats the solver's testimony-weighted fit at its own weight by ${num(r.shortfall, 2)}; shown at the better fit.">*</span>` : "";
    const sfPO = r.shortfallPO > 0.01 ? `<span class="flag-dot" title="The testimony-weighted fit has a better physics total than the solver's physics-only fit, by ${num(r.shortfallPO, 2)}; shown at the better fit.">*</span>` : "";
    return `<tr data-h="${esc(r.h.id)}" aria-selected="${r.h.id === s.hyp}" tabindex="0">
      <td><span class="hid">${esc(r.h.id)}</span><span class="hlabel">${esc(r.h.label)}</span></td>
      <td class="r"><span class="tot p">${num(r.physicsOnly, 1)}${sfPO}</span><span class="gap">${r.gapPO === 0 ? "best" : signed(r.gapPO, 1)} <span class="rank">#${r.rankPO}</span></span>
        <div class="bar p"><span style="width:${(barFrac(r.gapPO) * 100).toFixed(1)}%"></span></div></td>
      <td class="r"><span class="tot t">${num(r.testimonyWeighted, 1)}${sf}</span><span class="gap">${r.gapTW === 0 ? "best" : signed(r.gapTW, 1)} <span class="rank">#${r.rankTW}</span></span>
        <div class="bar t"><span style="width:${(barFrac(r.gapTW) * 100).toFixed(1)}%"></span></div></td>
    </tr>`;
  }).join("");
  for (const tr of tb.querySelectorAll("tr")) {
    const pick = () => api.set({ hyp: tr.dataset.h === s.hyp ? null : tr.dataset.h });
    tr.addEventListener("click", pick);
    tr.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } });
  }
}

function readouts(el, api) {
  const s = api.getState();
  const box = el.querySelector("#rail-readouts");
  if (!box) return;
  const fields = FIELD_ORDER.filter((f) => s.data.readings?.fields?.[f]);
  box.innerHTML = `
    <div class="sec-h"><h2>On screen at frame ${s.frame}</h2><span class="src">confidence</span></div>
    <dl class="readouts">${fields.map((f) => {
      const r = reading(s.data, f, s.frame);
      const val = r?.value == null ? "blank" : FIELDS[f].fmt(r.value);
      const low = Number.isFinite(r?.confidence) && r.confidence < LOW_CONF;
      return `<dt>${FIELDS[f].label}</dt><dd>${esc(val)}</dd><dd class="conf${low ? " low" : ""}" title="${esc(r?.method)}">${conf(r?.confidence)}</dd>`;
    }).join("")}</dl>`;
}
