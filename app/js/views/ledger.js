// Evidence ledger (shell): every on-screen number near the current frame with its confidence and
// read method (click a row to go to that frame), and the per-criterion log-likelihoods behind the
// selected hypothesis's totals, with each criterion's weight.

import { num, conf, LOW_CONF, FIELDS, FIELD_ORDER, signed } from "../units.js";
import { esc } from "../rail.js";
import { fitPhysicsTotal, fitTestimony } from "../scoring.js";

let api, root;
const SPAN = 8;

export function mount(el, a) {
  api = a; root = el;
  el.innerHTML = `
    <div style="display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:14px;height:100%;min-height:420px">
      <div class="panel fill"><div class="panel-h"><h2>Readouts around this frame</h2><span class="src" id="lg-src"></span></div><div class="panel-b" id="lg-read" style="overflow:auto"></div></div>
      <div class="panel fill"><div class="panel-h"><h2 id="lg-ch">Criteria</h2><span class="src">scores.csv, results.json</span></div><div class="panel-b" id="lg-crit" style="overflow:auto"></div></div>
    </div>`;
  el.querySelector("#lg-read").addEventListener("click", (e) => {
    const tr = e.target.closest("tr[data-f]");
    if (tr) api.set({ frame: +tr.dataset.f, playing: false });
  });
  readings(); criteria();
}

function readings() {
  const s = api.getState();
  if (!s.data || !root) return;
  const fields = FIELD_ORDER.filter((f) => s.data.readings?.fields?.[f]);
  const n = s.data.meta.n_frames;
  const a = Math.max(0, s.frame - SPAN), b = Math.min(n - 1, s.frame + SPAN);
  root.querySelector("#lg-src").textContent = s.data.readings?.source ?? "";
  let h = `<table class="data"><thead><tr><th class="num">Frame</th>${fields.map((f) => `<th>${FIELDS[f].label}</th>`).join("")}</tr></thead><tbody>`;
  for (let i = a; i <= b; i++) {
    h += `<tr data-f="${i}" class="${i === s.frame ? "cur" : ""}" style="cursor:pointer"><td class="num">${i}</td>`;
    for (const f of fields) {
      const F = s.data.readings.fields[f];
      const v = F.value[i], c = F.confidence[i];
      const low = Number.isFinite(c) && c < LOW_CONF;
      h += `<td class="num${low ? " low" : ""}" title="confidence ${conf(c)}, ${esc(F.method[i])}">${v == null ? '<span class="note">blank</span>' : esc(v)}<span class="gap">${conf(c)}</span></td>`;
    }
    h += `</tr>`;
  }
  root.querySelector("#lg-read").innerHTML = h + `</tbody></table><p class="note">Raw readout text as read; small number under each is the read confidence (red below ${LOW_CONF}). Click a row to go to that frame.</p>`;
}

function criteria() {
  const s = api.getState();
  if (!root) return;
  const box = root.querySelector("#lg-crit");
  const rows = api.currentScores();
  if (!rows) { box.innerHTML = `<div class="empty"><div><b>Not scored yet.</b>There are no criteria to show for ${esc(s.data?.meta.label ?? "this case")}.</div></div>`; return; }
  const r = rows.find((x) => x.h.id === s.hyp) || rows[0];
  const v = api.currentVariant();
  const w = s.wT ?? v.weights.testimony;
  root.querySelector("#lg-ch").textContent = `Criteria for ${r.h.id}`;
  const fits = r.h.fits;
  const names = [...new Set(fits.flatMap((f) => f.criteria.map((c) => c.name)))];
  const get = (f, n) => f.criteria.find((c) => c.name === n);
  let h = `<p class="note" style="margin-top:0">${esc(r.h.label)}. Pick another hypothesis in the score table. Weighted = log-likelihood x weight; the testimony weight is the live slider (${w.toFixed(2)}).</p>
    <table class="data"><thead><tr><th>Criterion</th><th class="num">Weight</th>${fits.map((f) => `<th class="num">${f.fit === "physics_only" ? "Physics-only fit" : "Testimony-weighted fit"}</th>`).join("")}</tr></thead><tbody>`;
  for (const n of names) {
    const c0 = get(fits[0], n) || get(fits[1], n);
    const wt = c0.kind === "testimony" ? w : c0.weight;
    h += `<tr><td>${esc(n.replace(/_/g, " "))}${c0.kind !== "physics" && !n.includes(c0.kind) ? ` <span class="note">${esc(c0.kind)}</span>` : ""}</td><td class="num">${num(wt, 2)}</td>
      ${fits.map((f) => { const c = get(f, n); return `<td class="num${wt === 0 ? " note" : ""}">${c ? num(c.loglik, 2) : ""}</td>`; }).join("")}</tr>`;
  }
  h += `<tr><td><b>Physics total</b></td><td></td>${fits.map((f) => `<td class="num" style="color:var(--phys)">${num(fitPhysicsTotal(f), 2)}</td>`).join("")}</tr>
    <tr><td><b>Total with testimony</b></td><td class="num">${num(w, 2)}</td>${fits.map((f) => `<td class="num" style="color:var(--testi)">${num(fitPhysicsTotal(f) + w * fitTestimony(f), 2)}</td>`).join("")}</tr>
    </tbody></table>
    <p class="note">The rail shows the better of the two fits at the current weight.${Math.abs(w - v.weights.testimony) < 1e-9 && r.shortfall > 0.01 ? ` Here the physics-only fit beats the solver's testimony-weighted fit at its own weight by ${signed(r.shortfall, 2)} (an optimiser shortfall).` : ""}${r.shortfallPO > 0.01 ? ` The testimony-weighted fit has the better physics total, by ${signed(r.shortfallPO, 2)} (an optimiser shortfall).` : ""}</p>`;
  box.innerHTML = h;
}

export function update(s, ch) {
  if (!root) return;
  if (ch.has("frame") || ch.has("data")) readings();
  if (ch.has("data") || ch.has("variant") || ch.has("wT") || ch.has("hyp")) criteria();
}
