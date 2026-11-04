// Right rail, present on every view: what the lab found for this case (the case file's verdict, and the one
// measurement that would settle it), both totals per hypothesis (D-011) with the live testimony weight, the flags,
// and the on-screen readouts at the current frame. Plain mode (the default) shows explanations by plain name and
// gaps as "times less likely"; "All numbers" shows the log-likelihoods. Both totals are always shown.

import { num, signed, conf, LOW_CONF, FIELDS, FIELD_ORDER, variantLabel, esc } from "./units.js";
import { reading } from "./data.js";
import { plainName, likelihoodWords, q } from "./glossary.js";

export { esc };

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
  const caseChanged = changed.has("data") || changed.has("caseId") || changed.has("variant") || changed.has("expert");
  if (!built || caseChanged) { build(el, api); built = true; }
  if (caseChanged || changed.has("wT") || changed.has("hyp") || changed.has("overrides")) { scores(el, api); verdict(el, api); }
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
  const plain = !s.expert;
  const flags = readFirst(v);
  el.innerHTML = `
    <section class="verdict" id="rail-verdict"></section>
    <section>
      <div class="sec-h"><h2>${plain ? "Which explanation fits best" : "Scores"}</h2><span class="src">${esc(meta.label)} ${esc(v.variant ? variantLabel(v.variant) : "")}${plain ? "" : " log-likelihood"}</span></div>
      <div class="weight">
        <div class="weight-row">
          <label for="wT">${plain ? "How much to count the aircrew's accounts" : "Testimony weight"} ${q("testimony")}</label>
          <span><output id="wT-out" for="wT">${(s.wT ?? w0).toFixed(2)}</output>
          <button class="reset" id="wT-reset" title="Back to the default (D-011)">Default ${w0.toFixed(1)}</button></span>
          <input id="wT" type="range" min="0" max="2" step="0.05" value="${s.wT ?? w0}" aria-describedby="wT-help">
          <div class="ticks" aria-hidden="true">${plain ? "<span>0 ignore them</span><span>1 default</span><span>2 double</span>" : "<span>0 physics only</span><span>1</span><span>2</span>"}</div>
        </div>
      </div>
      <div class="legend"><span class="p"><i></i>${plain ? "Video only" : "Physics only (fixed)"} ${q("physics")}</span><span class="t"><i></i>${plain ? "With aircrew accounts" : "Testimony weighted (live)"}</span></div>
      <table class="scores${plain ? " plain" : ""}" aria-describedby="wT-help">
        ${plain ? "" : `<thead><tr><th>Hypothesis</th><th class="r">Physics only</th><th class="r">With testimony</th></tr></thead>`}
        <tbody id="score-rows"></tbody>
      </table>
      <p class="note warn-note" id="ov-note" hidden style="padding:6px 16px 0;margin:0"></p>
      <p class="note" id="wT-help" style="padding:6px 16px 12px;margin:0">${plain
        ? `Top of the list fits the footage best. Click a row to show that explanation in every view. Scores compare explanations; they are not a verdict on what the object was. ${q("likelihood")}`
        : `Higher is better; a gap of 2.3 is a likelihood ratio of 10. Totals are recomputed here from each criterion's log-likelihood. Not a verdict on what the object was. ${q("likelihood")}`}</p>
    </section>
    ${plain ? "" : `<section>
      <div class="sec-h"><h2>Read first</h2><span class="src">${flags.length} flag${flags.length === 1 ? "" : "s"}</span></div>
      <ul class="flags">${flags.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>
    </section>`}
    <section id="rail-readouts"></section>`;
  const input = el.querySelector("#wT");
  input.addEventListener("input", () => api.set({ wT: +input.value }));
  el.querySelector("#wT-reset").addEventListener("click", () => api.set({ wT: w0 }));
  const tb = el.querySelector("#score-rows");
  tb.addEventListener("click", (e) => { const tr = e.target.closest("tr[data-h]"); if (tr) pick(api, tr.dataset.h); });
  tb.addEventListener("keydown", (e) => {
    const tr = e.target.closest("tr[data-h]");
    if (tr && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); pick(api, tr.dataset.h); }
  });
}

function pick(api, id) {
  const s = api.getState();
  api.set({ hyp: id === s.hyp ? null : id });
}

// The sensitivities that can change the leader (the same rule as tools/export_cases.py): a full refit without the
// post-hoc exclusions, and the nearest rotation-noise crossover on each side of the data-only value, within a
// factor of 2. Structured, so plain mode can word them.
export function sensitivities(v) {
  const out = [];
  const ne = v.extras?.no_exclusions;
  if (ne && !ne.identical && Array.isArray(ne.hypotheses)) {
    const ok = ne.hypotheses.filter((h) => h.valid !== false).sort((a, b) => b.total_physics_only - a.total_physics_only);
    const now = v.hypotheses.filter((h) => h.valid).map((h) => [h.id, h.python_totals.physics_only]).sort((a, b) => b[1] - a[1]);
    if (ok.length && now.length && ok[0].hypothesis !== now[0][0]) out.push({ kind: "exclusions", leader: ok[0].hypothesis, instead: now[0][0] });
  }
  const sw = v.extras?.rotation_sigma_sweep;
  const main = sw?.main_sigma_deg;
  const cs = (sw?.crossovers?.physics_only ?? []).filter((c) => c.sigma_deg >= 0.5 * main && c.sigma_deg <= 2 * main);
  const lo = cs.filter((c) => c.sigma_deg < main).sort((a, b) => b.sigma_deg - a.sigma_deg)[0];
  const hi = cs.filter((c) => c.sigma_deg >= main).sort((a, b) => a.sigma_deg - b.sigma_deg)[0];
  if (lo) out.push({ kind: "rotation", side: "below", sigma: lo.sigma_deg, main, leader: lo.leader_below });
  if (hi) out.push({ kind: "rotation", side: "above", sigma: hi.sigma_deg, main, leader: hi.leader_above });
  return out;
}

function readFirst(v) {
  return [...v.flags, ...sensitivities(v).map((x) => x.kind === "exclusions"
    ? `CP-04 Rule X: refitted without the post-hoc exclusions, ${x.leader} leads physics-only instead of ${x.instead}.`
    : `Rotation noise: ${x.side} ${x.sigma.toFixed(2)} deg (data-only value ${x.main.toFixed(2)} deg) ${x.leader} leads physics-only instead.`)];
}

function plainSensitivity(x, v) {
  const nm = (id) => `${plainName(id)} (${id})`;
  if (x.kind === "exclusions") return `Without the two data-quality rules ${q("exclusions")}, ${esc(nm(x.leader))} fits best instead.`;
  return `If the shape's rotation is measured ${x.side === "above" ? "a little less" : "a little more"} precisely (${x.side} ${x.sigma.toFixed(2)}° instead of ${x.main.toFixed(2)}° ${q("rotationnoise")}), ${esc(nm(x.leader))} fits best instead.`;
}

// What the lab found: the case file's verdict at the default settings, the live leader if the user's weights moved
// it, and the measurement that would settle it.
function verdict(el, api) {
  const box = el.querySelector("#rail-verdict");
  const s = api.getState();
  const sum = s.data.meta.summary;
  const v = api.currentVariant();
  if (!box || !v) return;
  const rows = api.currentScores() ?? [];
  const byPO = [...rows].filter((r) => Number.isFinite(r.physicsOnly)).sort((a, b) => b.physicsOnly - a.physicsOnly);
  const lead = byPO[0], second = byPO[1];
  const sens = sensitivities(v);
  const nm = (id) => `<b>${esc(plainName(id))}</b> <span class="hid-s">${esc(id)}</span>`;
  const words = lead && second ? likelihoodWords(second.physicsOnly - lead.physicsOnly) : "";
  const vs = !second ? "" : words === "about as likely" ? `, about as likely as ${nm(second.h.id)}`
    : `, ${esc(words.replace(" less likely", " more likely"))} than ${nm(second.h.id)}`;
  const decisive = sum?.decisive === true;
  box.innerHTML = `<div class="sec-h"><h2>What the lab found</h2><span class="src">${esc(s.data.meta.label)}${v.variant ? ` ${esc(variantLabel(v.variant))}` : ""}</span></div>
    <div class="v-body">
      <p class="v-head">${decisive ? "A clear leader" : "No clear winner"}</p>
      ${lead ? `<p>On the video alone, ${nm(lead.h.id)} fits best${vs}.${decisive ? "" : " That lead is not decisive:"}</p>` : ""}
      ${!decisive ? `<ul class="v-why">${sens.map((x) => `<li>${plainSensitivity(x, v)}</li>`).join("")}${
        /model-recovery/.test(sum?.verdict_text ?? "") ? "<li>Fed made-up footage from each explanation, the scorer could not always tell them apart, so this data cannot separate some of them even in principle.</li>" : ""}</ul>` : ""}
      ${sum?.settle_title ? `<p class="settle"><b>What would settle it</b>${esc(sum.settle_title)}.</p>` : ""}
      ${sum ? `<details><summary>The full verdict and technical notes</summary><p>${esc(sum.verdict_text)}</p>${sum.settle_text ? `<p>${esc(sum.settle_text)}</p>` : ""}
        <ul class="flags">${readFirst(v).map((f) => `<li>${esc(f)}</li>`).join("")}</ul><p class="note">Source: ${esc(sum.source)}</p></details>` : ""}
    </div>`;
}

function scores(el, api) {
  const s = api.getState();
  const rows = api.currentScores();
  const tb = el.querySelector("#score-rows");
  if (!rows || !tb) return;
  const v = api.currentVariant();
  const w = s.wT ?? v.weights.testimony;
  const plain = !s.expert;
  el.querySelector("#wT-out").textContent = w.toFixed(2);
  const ov = Object.entries(s.overrides || {});
  const on = el.querySelector("#ov-note");
  on.hidden = !ov.length;
  on.innerHTML = ov.length ? `Criterion weights changed in the evidence ledger: ${ov.map(([k, x]) => `${esc(k.replace(/_/g, " "))} ${num(x, 2)}`).join(", ")}. Both totals below use them.` : "";
  const input = el.querySelector("#wT");
  if (+input.value !== w) input.value = w;
  const focused = document.activeElement?.closest?.("#score-rows tr[data-h]")?.dataset.h;
  tb.innerHTML = rows.map((r) => {
    // Flag only where the solver itself fitted (the default weight, and the physics-only total): there a stored
    // fit beating the solver's fit is an optimiser shortfall. At other weights picking the other fit is expected.
    const atFit = Math.abs(w - v.weights.testimony) < 1e-9;
    const sf = atFit && r.shortfall > 0.01 ? `<span class="flag-dot" title="The physics-only fit beats the solver's testimony-weighted fit at its own weight by ${num(r.shortfall, 2)}; shown at the better fit.">*</span>` : "";
    const sfPO = r.shortfallPO > 0.01 ? `<span class="flag-dot" title="The testimony-weighted fit has a better physics total than the solver's physics-only fit, by ${num(r.shortfallPO, 2)}; shown at the better fit.">*</span>` : "";
    if (plain) {
      const line = (lbl, gap, rank, cls, mark) => `<div class="pline ${cls}"><span class="plbl">${lbl}</span><span class="rank">#${rank}</span><span class="pw">${esc(likelihoodWords(gap))}${mark}</span>
          <div class="bar ${cls}"><span style="width:${(barFrac(gap) * 100).toFixed(1)}%"></span></div></div>`;
      return `<tr data-h="${esc(r.h.id)}" aria-selected="${r.h.id === s.hyp}" tabindex="0" title="Show ${esc(r.h.id)} in every view"><td colspan="3">
        <div class="prow"><span class="pname">${esc(plainName(r.h.id, r.h.label))}</span><span class="hlabel">${esc(r.h.id)}</span>${q(r.h.id)}</div>
        ${line("Video only", r.gapPO, r.rankPO, "p", sfPO)}${line("With accounts", r.gapTW, r.rankTW, "t", sf)}</td></tr>`;
    }
    const name = `<td><span class="hid">${esc(r.h.id)}</span><span class="hlabel">${esc(r.h.label)}</span></td>`;
    const cell = (tot, gap, rank, cls, mark) => `<td class="r"><span class="tot ${cls}">${num(tot, 1)}${mark}</span><span class="gap">${gap === 0 ? "best" : signed(gap, 1)} <span class="rank">#${rank}</span></span>
          <div class="bar ${cls}"><span style="width:${(barFrac(gap) * 100).toFixed(1)}%"></span></div></td>`;
    return `<tr data-h="${esc(r.h.id)}" aria-selected="${r.h.id === s.hyp}" tabindex="0" title="Show ${esc(r.h.id)} in every view">
      ${name}${cell(r.physicsOnly, r.gapPO, r.rankPO, "p", sfPO)}${cell(r.testimonyWeighted, r.gapTW, r.rankTW, "t", sf)}
    </tr>`;
  }).join("");
  if (focused) tb.querySelector(`tr[data-h="${CSS.escape(focused)}"]`)?.focus();
}

function readouts(el, api) {
  const s = api.getState();
  const box = el.querySelector("#rail-readouts");
  if (!box) return;
  const fields = FIELD_ORDER.filter((f) => s.data.readings?.fields?.[f]);
  box.innerHTML = `
    <div class="sec-h"><h2>On screen at frame ${s.frame}</h2><span class="src">read confidence ${q("confidence")}</span></div>
    <dl class="readouts">${fields.map((f) => {
      const r = reading(s.data, f, s.frame);
      const ph = r?.placeholder && r.value === r.placeholder.value;
      const val = r?.value == null ? "blank" : ph ? `${r.value} (${r.placeholder.note})` : FIELDS[f].fmt(r.value);
      const low = Number.isFinite(r?.confidence) && r.confidence < LOW_CONF;
      return `<dt>${FIELDS[f].label}</dt><dd${ph ? ' class="ph"' : ""}>${esc(val)}</dd><dd class="conf${low ? " low" : ""}" title="${esc(r?.method)}">${conf(r?.confidence)}</dd>`;
    }).join("")}</dl>`;
}
