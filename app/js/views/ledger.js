// Evidence ledger (M4.7). Left: every on-screen reading with its source frame, value, confidence, read method
// and source file (a virtualized table: only the visible rows are in the DOM); clicking a row opens that frame in
// the cockpit view. A second tab lists every testimony claim with its source and how the scorer uses it.
// Right: one weight slider per criterion, the same for every hypothesis (criteria held at 0 by a data-quality
// rule say why, and can be added back); both totals for every hypothesis, as weighted now and with the
// exclusions added back; the selected hypothesis's per-criterion log-likelihoods for both fits; and anything
// else the scorer exported (sensitivity runs and the like) under "More from the scorer".

import { num, conf, LOW_CONF, FIELDS, FIELD_ORDER, signed, timecode, hypColor } from "../units.js";
import { esc } from "../rail.js";
import { fitPhysicsTotal, fitTestimony, scoreVariant } from "../scoring.js";

let api, root, tab = "read", rowsIdx = [], scroller, body, filt = { field: "all", low: false };
const ROW_H = 26;
const KNOWN_EXTRAS = new Set(["display_rounding", "criteria_n_eff", "data_sigmas"]);
const HYP_EXTRA_SKIP = new Set(["n_eff_total", "n_eval", "params_at_bound", "params_at_bound_physics_only_fit", "k_physics_only_fit",
  "rank_testimony_weighted", "rank_testimony_weighted_design_set", "rank_physics_only", "rank_physics_only_design_set"]);

export function mount(el, a) {
  api = a; root = el;
  el.innerHTML = `
    <div class="lg">
      <div class="panel fill">
        <div class="panel-h"><div class="seg" role="tablist" aria-label="Ledger" id="lg-tabs">
          <button data-t="read" aria-pressed="true" role="tab">Readings</button><button data-t="testi" aria-pressed="false" role="tab">Testimony claims</button></div>
          <span class="src" id="lg-src"></span></div>
        <div class="lg-filter" id="lg-filter">
          <label>Field <select id="lg-field"></select></label>
          <label><input type="checkbox" id="lg-low"> Only below ${LOW_CONF.toFixed(2)} confidence</label>
          <button class="reset" id="lg-goto">Go to frame</button>
          <span class="note" id="lg-count"></span>
        </div>
        <div class="lg-head" id="lg-head"><span class="c-f">Frame</span><span class="c-t">Time</span><span class="c-n">Field</span><span class="c-v">Value as read</span><span class="c-c">Confidence</span><span class="c-m">Method</span></div>
        <div class="panel-b lg-scroll" id="lg-scroll" tabindex="0" aria-label="Readings, one row per frame and field"><div id="lg-body" class="lg-body"></div></div>
      </div>
      <div class="lg-right" id="lg-right"></div>
    </div>`;
  scroller = el.querySelector("#lg-scroll");
  body = el.querySelector("#lg-body");
  scroller.addEventListener("scroll", paint);
  body.addEventListener("click", (e) => {
    const r = e.target.closest("[data-f]");
    if (r) api.set({ frame: +r.dataset.f, view: "cockpit", playing: false });
  });
  for (const b of el.querySelectorAll("#lg-tabs button")) b.addEventListener("click", () => { tab = b.dataset.t; left(true); });
  el.querySelector("#lg-field").addEventListener("change", (e) => { filt.field = e.target.value; build(); });
  el.querySelector("#lg-low").addEventListener("change", (e) => { filt.low = e.target.checked; build(); });
  el.querySelector("#lg-goto").addEventListener("click", () => scrollToFrame(api.getState().frame));
  el.querySelector("#lg-right").addEventListener("input", onWeight);
  el.querySelector("#lg-right").addEventListener("click", onClick);
  new ResizeObserver(paint).observe(scroller);
  left(true);
  right();
}

// ---------------------------------------------------------------- readings (virtualized)

function fieldsOf(s) { return FIELD_ORDER.filter((f) => s.data.readings?.fields?.[f]).concat(Object.keys(s.data.readings?.fields ?? {}).filter((f) => !FIELD_ORDER.includes(f))); }

function build() {
  const s = api.getState();
  if (!s.data) return;
  const fields = fieldsOf(s);
  const n = s.data.meta.n_frames;
  rowsIdx = [];
  const fl = filt.field === "all" ? fields : fields.filter((f) => f === filt.field);
  const fi = fl.map((f) => fields.indexOf(f));
  for (let i = 0; i < n; i++) for (const k of fi) {
    const F = s.data.readings.fields[fields[k]];
    if (F.value[i] == null && F.confidence[i] == null) continue;
    if (filt.low && !(Number.isFinite(F.confidence[i]) && F.confidence[i] < LOW_CONF)) continue;
    rowsIdx.push(i * 64 + k);
  }
  body.style.height = `${rowsIdx.length * ROW_H}px`;
  root.querySelector("#lg-count").textContent = `${num(rowsIdx.length)} readings`;
  paint();
}

function paint() {
  const s = api.getState();
  if (!s.data || tab !== "read") return;
  const fields = fieldsOf(s);
  const top = scroller.scrollTop, h = scroller.clientHeight || 400;
  const a = Math.max(0, Math.floor(top / ROW_H) - 8), b = Math.min(rowsIdx.length, Math.ceil((top + h) / ROW_H) + 8);
  const t = s.data.meta.t_s;
  let html = "";
  for (let j = a; j < b; j++) {
    const code = rowsIdx[j], i = Math.floor(code / 64), f = fields[code % 64];
    const F = s.data.readings.fields[f];
    const v = F.value[i], c = F.confidence[i];
    const low = Number.isFinite(c) && c < LOW_CONF;
    const fmt = FIELDS[f]?.fmt;
    const shown = v == null ? '<span class="note">blank</span>' : esc(v) + (fmt && fmt(v) !== v ? ` <span class="note">${esc(fmt(v))}</span>` : "");
    html += `<div class="lg-row${i === s.frame ? " cur" : ""}" data-f="${i}" style="top:${j * ROW_H}px" title="Open frame ${i} in the cockpit view">
      <span class="c-f num">${i}</span><span class="c-t num">${timecode(t[i])}</span><span class="c-n">${esc(FIELDS[f]?.label ?? f)}</span>
      <span class="c-v num">${shown}</span><span class="c-c num${low ? " low" : ""}">${conf(c)}${low ? " low" : ""}</span><span class="c-m">${esc(F.method[i] ?? "")}</span></div>`;
  }
  body.innerHTML = html;
}

function scrollToFrame(fr) {
  const j = rowsIdx.findIndex((c) => Math.floor(c / 64) >= fr);
  if (j >= 0) scroller.scrollTop = Math.max(0, j * ROW_H - scroller.clientHeight / 3);
  paint();
}

function left(rebuild) {
  const s = api.getState();
  if (!s.data || !root) return;
  for (const b of root.querySelectorAll("#lg-tabs button")) b.setAttribute("aria-pressed", String(b.dataset.t === tab));
  const isRead = tab === "read";
  root.querySelector("#lg-filter").hidden = !isRead;
  root.querySelector("#lg-head").hidden = !isRead;
  if (isRead) {
    root.querySelector("#lg-src").textContent = s.data.readings?.source ?? "";
    const sel = root.querySelector("#lg-field");
    const fields = fieldsOf(s);
    sel.innerHTML = `<option value="all">All fields</option>` + fields.map((f) => `<option value="${f}"${f === filt.field ? " selected" : ""}>${esc(FIELDS[f]?.label ?? f)}</option>`).join("");
    if (!fields.includes(filt.field)) filt.field = "all";
    if (rebuild) { build(); scrollToFrame(s.frame); }
  } else {
    testimony();
  }
}

function testimony() {
  const s = api.getState();
  const T = s.data.testimony;
  root.querySelector("#lg-src").textContent = T?.source ?? "";
  body.style.height = "auto";
  if (!T?.claims?.length) { body.innerHTML = `<div class="empty"><div><b>No testimony claims for ${esc(s.data.meta.label)}.</b></div></div>`; return; }
  const sel = api.currentHyp();
  const rowsBy = {};
  for (const r of sel?.h.testimony_rows ?? []) (rowsBy[r.claim_id] ??= []).push(r);
  const useLabel = (c) => (c.use ?? []).map((u) => ({ hypothesis: "scored for every hypothesis", witness_consistency: "memory vs the screen", environment: "environment check", context: "context, not scored" }[u] ?? u)).join(", ");
  body.innerHTML = `<p class="note" style="margin:0 0 8px">${num(T.claims.length)} claims. Scored claims enter the testimony total (the rail's lavender column) for every hypothesis alike; the log-likelihoods shown are for ${esc(sel?.h.id ?? "the selected hypothesis")}, testimony-weighted fit.</p>` +
    T.claims.map((c) => {
      const tr = rowsBy[c.id] ?? [];
      return `<article class="claim${c.scorable ? " scored" : ""}">
        <header><b class="hid">${esc(c.id)}</b> <span class="note">${esc(c.witness ?? "")}${c.firsthand === false ? ", relayed" : c.firsthand ? ", firsthand" : ""}</span><span class="use">${esc(useLabel(c))}</span></header>
        <p>${esc(c.claim ?? "")}${c.quote ? ` <q>${esc(c.quote)}</q>` : ""}</p>
        ${tr.length ? `<p class="num tr">${tr.map((r) => `${esc(r.quantity.replace(/_/g, " "))}: predicted ${esc(typeof r.predicted_value === "number" ? num(r.predicted_value, 1) : String(r.predicted_value))}, log-likelihood ${num(r.loglik, 2)}${r.weight !== 1 ? ` x ${num(r.weight, 1)}` : ""}`).join("; ")}</p>` : ""}
        <footer class="note">${esc([c.source_title, c.source_outlet, c.source_date].filter(Boolean).join(", "))}${c.location ? `; ${esc(c.location)}` : ""}${c.why ? `<br>Use: ${esc(c.why)}` : ""}</footer>
      </article>`;
    }).join("");
}

// ---------------------------------------------------------------- weights, both totals, criteria

function criteriaOf(v) {
  const seen = new Map();
  for (const h of v.hypotheses) for (const f of h.fits) for (const c of f.criteria) if (c.kind === "physics" && !seen.has(c.name)) seen.set(c.name, c.weight);
  return [...seen.entries()].map(([name, weight]) => ({ name, weight }));
}

function exclusionWhy(v, name) {
  const key = name.startsWith("size") ? /size/i : name.startsWith("brightness") ? /brightness/i : new RegExp(name.replace(/_/g, ".?"), "i");
  const f = v.flags.find((x) => key.test(x));
  return f ? f.split(":")[0] : "weight 0 by a ruling";
}

function onWeight(e) {
  const inp = e.target.closest("input[data-c]");
  if (!inp) return;
  const s = api.getState();
  const v = api.currentVariant();
  const c = criteriaOf(v).find((x) => x.name === inp.dataset.c);
  const ov = { ...s.overrides };
  const w = +inp.value;
  if (Math.abs(w - c.weight) < 1e-9) delete ov[c.name]; else ov[c.name] = w;
  api.set({ overrides: ov });
}

function onClick(e) {
  const b = e.target.closest("button[data-act]");
  if (!b) return;
  const s = api.getState();
  const v = api.currentVariant();
  if (b.dataset.act === "reset") api.set({ overrides: {} });
  if (b.dataset.act === "addback") {
    const ov = { ...s.overrides };
    for (const c of v.excluded_criteria ?? []) ov[c] = 1;
    api.set({ overrides: ov });
  }
  if (b.dataset.act === "exclude") {
    const ov = { ...s.overrides };
    for (const c of v.excluded_criteria ?? []) delete ov[c];
    api.set({ overrides: ov });
  }
  const tr = e.target.closest("tr[data-h]");
  if (tr) api.set({ hyp: tr.dataset.h });
}

function right() {
  const s = api.getState();
  const box = root?.querySelector("#lg-right");
  if (!box || !s.data) return;
  const v = api.currentVariant();
  if (!v) { box.innerHTML = `<div class="panel"><div class="panel-b"><div class="empty"><div><b>Not scored yet.</b>There are no criteria or totals for ${esc(s.data.meta.label)}.</div></div></div></div>`; return; }
  const w = s.wT ?? v.weights.testimony;
  const crit = criteriaOf(v);
  const excl = v.excluded_criteria ?? [];
  const ov = s.overrides ?? {};
  const addedBack = excl.length && excl.every((c) => ov[c] === 1);
  let h = `<div class="panel"><div class="panel-h"><h2>Weights</h2><span class="src">the same for every hypothesis</span></div><div class="panel-b">
    <div class="wgrid">${crit.map((c) => {
      const val = ov[c.name] ?? c.weight;
      const isEx = excl.includes(c.name);
      return `<label for="w-${c.name}">${esc(c.name.replace(/_/g, " "))}${isEx ? ` <span class="exw">${esc(exclusionWhy(v, c.name))}</span>` : ""}</label>
        <input type="range" id="w-${c.name}" data-c="${esc(c.name)}" min="0" max="2" step="0.05" value="${val}"><output class="num${val !== c.weight ? " chg" : ""}">${num(val, 2)}</output>`;
    }).join("")}
    <label>testimony <span class="note">rail slider</span></label><span class="note">same as the rail</span><output class="num" style="color:var(--testi)">${num(w, 2)}</output></div>
    <div class="btnrow">${excl.length ? (addedBack ? `<button class="reset" data-act="exclude">Apply the data-quality exclusions</button>` : `<button class="reset" data-act="addback">Add excluded criteria back at weight 1</button>`) : ""}
      <button class="reset" data-act="reset"${Object.keys(ov).length ? "" : " disabled"}>Reset weights</button></div>
    <p class="note">${excl.length ? `Held at 0 by a data-quality rule: ${excl.map((x) => esc(x.replace(/_/g, " "))).join(", ")}. These rules were not decided blind (CP-04 review), so both ways are shown below.` : "No criterion is held at 0 by a data-quality rule on this case."} Changing a weight here re-scores the stored fits; it does not refit.</p>
  </div></div>`;
  // both totals, both ways
  const now = scoreVariant(v, w, ov);
  const back = scoreVariant(v, w, { ...ov, ...Object.fromEntries(excl.map((c) => [c, 1])) });
  const cell = (r, k) => `${num(r[k], 1)} <span class="gap">${r[k === "physicsOnly" ? "gapPO" : "gapTW"] === 0 ? "best" : signed(r[k === "physicsOnly" ? "gapPO" : "gapTW"], 1)}</span>`;
  h += `<div class="panel"><div class="panel-h"><h2>Both totals</h2><span class="src">testimony weight ${num(w, 2)}</span></div><div class="panel-b" style="overflow-x:auto">
    <table class="data tot2"><thead><tr><th rowspan="2">Hypothesis</th><th colspan="2" class="grp">As weighted now</th>${excl.length ? `<th colspan="2" class="grp">Exclusions added back</th>` : ""}</tr>
    <tr><th class="num p">Physics only</th><th class="num t">With testimony</th>${excl.length ? `<th class="num p">Physics only</th><th class="num t">With testimony</th>` : ""}</tr></thead><tbody>
    ${now.map((r, k) => { const b2 = back.find((x) => x.h.id === r.h.id); return `<tr data-h="${esc(r.h.id)}" class="${r.h.id === (api.currentHyp()?.h.id) ? "cur" : ""}" style="cursor:pointer">
      <td><span class="sw" style="background:${hypColor(r.h.id, k)}"></span><span class="hid">${esc(r.h.id)}</span></td>
      <td class="num p">${cell(r, "physicsOnly")}</td><td class="num t">${cell(r, "testimonyWeighted")}</td>
      ${excl.length ? `<td class="num p">${cell(b2, "physicsOnly")}</td><td class="num t">${cell(b2, "testimonyWeighted")}</td>` : ""}</tr>`; }).join("")}
    </tbody></table>
    <p class="note">${excl.length ? `"Added back" puts each excluded criterion in at weight 1 on the stored fits (no refit, so a refit could only raise those totals). ` : ""}Click a row to select a hypothesis.</p></div></div>`;
  // per-criterion breakdown of the selected hypothesis
  const r = api.currentHyp();
  if (r) {
    const fits = r.h.fits;
    const names = [...new Set(fits.flatMap((f) => f.criteria.map((c) => c.name)))];
    const get = (f, n) => f.criteria.find((c) => c.name === n);
    h += `<div class="panel"><div class="panel-h"><h2>Criteria for ${esc(r.h.id)}</h2><span class="src">scores.csv, results.json</span></div><div class="panel-b" style="overflow-x:auto">
      <table class="data"><thead><tr><th>Criterion</th><th class="num">Weight</th>${fits.map((f) => `<th class="num">${f.fit === "physics_only" ? "Physics-only fit" : "Testimony-weighted fit"}</th>`).join("")}</tr></thead><tbody>`;
    for (const n of names) {
      const c0 = get(fits[0], n) || get(fits[1], n);
      const wt = c0.kind === "testimony" ? w : (ov[n] ?? c0.weight);
      h += `<tr><td>${esc(n.replace(/_/g, " "))}${c0.kind !== "physics" && !n.includes(c0.kind) ? ` <span class="note">${esc(c0.kind)}</span>` : ""}</td><td class="num">${num(wt, 2)}</td>
        ${fits.map((f) => { const c = get(f, n); return `<td class="num${wt === 0 ? " note" : ""}">${c ? num(c.loglik, 2) : ""}</td>`; }).join("")}</tr>`;
    }
    h += `<tr><td><b>Physics total</b></td><td></td>${fits.map((f) => `<td class="num" style="color:var(--phys)">${num(fitPhysicsTotal(f, ov), 2)}</td>`).join("")}</tr>
      <tr><td><b>Total with testimony</b></td><td class="num">${num(w, 2)}</td>${fits.map((f) => `<td class="num" style="color:var(--testi)">${num(fitPhysicsTotal(f, ov) + w * fitTestimony(f), 2)}</td>`).join("")}</tr>
      </tbody></table><p class="note">Weighted = log-likelihood x weight. The rail and the table above use the better of the two fits at the current weights.</p></div></div>`;
  }
  // anything else the scorer exported
  const ex = Object.entries(v.extras ?? {}).filter(([k]) => !KNOWN_EXTRAS.has(k));
  const hx = r ? Object.entries(r.h.extras ?? {}).filter(([k]) => !HYP_EXTRA_SKIP.has(k)) : [];
  if (ex.length || hx.length) {
    h += `<div class="panel"><div class="panel-h"><h2>More from the scorer</h2><span class="src">results.json, passed through</span></div><div class="panel-b">
      ${ex.map(([k, x]) => `<details><summary>${esc(k.replace(/_/g, " "))}</summary>${kvTable(x)}</details>`).join("")}
      ${hx.map(([k, x]) => `<details><summary>${esc(r.h.id)}: ${esc(k.replace(/_/g, " "))}</summary>${kvTable(x)}</details>`).join("")}</div></div>`;
  }
  box.innerHTML = h;
}

function kvTable(x, depth = 0) {
  if (x === null || typeof x !== "object") return `<span class="num">${esc(typeof x === "number" ? num(x, Math.abs(x) < 10 ? 3 : 1) : String(x))}</span>`;
  if (Array.isArray(x)) {
    if (x.length > 12 || depth > 1) return `<pre class="kvpre">${esc(JSON.stringify(x).slice(0, 600))}${JSON.stringify(x).length > 600 ? " ..." : ""}</pre>`;
    return `<ol class="kvl">${x.map((y) => `<li>${kvTable(y, depth + 1)}</li>`).join("")}</ol>`;
  }
  return `<table class="data kvt"><tbody>${Object.entries(x).map(([k, y]) => `<tr><td>${esc(k.replace(/_/g, " "))}</td><td>${kvTable(y, depth + 1)}</td></tr>`).join("")}</tbody></table>`;
}

export function update(s, ch) {
  if (!root) return;
  if (ch.has("data")) left(true);
  else if (ch.has("frame") && tab === "read") {
    // follow the playhead: keep the current frame's rows in view
    const j = rowsIdx.findIndex((c) => Math.floor(c / 64) >= s.frame);
    const y = j * ROW_H;
    if (j >= 0 && (y < scroller.scrollTop || y > scroller.scrollTop + scroller.clientHeight - 3 * ROW_H)) scrollToFrame(s.frame);
    else paint();
  }
  if (tab === "testi" && (ch.has("hyp") || ch.has("wT"))) testimony();
  if (["data", "variant", "wT", "hyp", "overrides"].some((k) => ch.has(k))) right();
}
