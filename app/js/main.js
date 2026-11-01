// App shell: hash router, shared state, case switcher, field-of-view switch, rail, timeline.
// Route: #/<case>/<view>?f=<frame>&v=<variant>&w=<testimony weight>&h=<hypothesis>

import { loadIndex, loadCase } from "./data.js";
import { scoreVariant } from "./scoring.js";
import { renderRail } from "./rail.js";
import { createTape } from "./tape.js";
import { variantLabel } from "./units.js";
import * as cockpit from "./views/cockpit.js";
import * as godseye from "./views/godseye.js";
import * as rangeView from "./views/range.js";
import * as compare from "./views/compare.js";
import * as ledger from "./views/ledger.js";

const VIEWS = { cockpit, godseye, range: rangeView, compare, ledger };
const VIEW_KEYS = Object.keys(VIEWS);

const state = {
  index: null, caseId: "gimbal", view: "cockpit", frame: 0, variant: null,
  wT: null, hyp: null, data: null, playing: false,
};
const subs = new Set();
const $ = (s) => document.querySelector(s);
const mounted = {};

export function getState() { return state; }

// Current variant object, scored at the live testimony weight.
export function currentVariant() {
  const r = state.data?.results;
  if (!r) return null;
  return r.variants.find((v) => v.variant === state.variant) || r.variants[0];
}
export function currentScores() {
  const v = currentVariant();
  return v ? scoreVariant(v, state.wT ?? v.weights.testimony) : null;
}

export function set(patch, { route = true } = {}) {
  const changed = new Set();
  for (const [k, v] of Object.entries(patch)) if (state[k] !== v) { state[k] = v; changed.add(k); }
  if (!changed.size) return;
  if (route) writeHash();
  for (const fn of subs) fn(state, changed);
}

function parseHash() {
  const [path, q = ""] = location.hash.replace(/^#\/?/, "").split("?");
  const [c, v] = path.split("/");
  const p = new URLSearchParams(q);
  return {
    caseId: c || null, view: VIEW_KEYS.includes(v) ? v : null,
    frame: p.has("f") ? +p.get("f") : null, variant: p.get("v"),
    wT: p.has("w") ? +p.get("w") : null, hyp: p.get("h"),
  };
}

let hashTimer = 0;
function writeHash() {
  clearTimeout(hashTimer);
  hashTimer = setTimeout(() => {
    const p = new URLSearchParams();
    p.set("f", state.frame);
    if (state.variant) p.set("v", state.variant);
    if (state.wT !== null) p.set("w", state.wT.toFixed(2));
    if (state.hyp) p.set("h", state.hyp);
    const h = `#/${state.caseId}/${state.view}?${p}`;
    if (location.hash !== h) history.replaceState(null, "", h);
  }, state.playing ? 400 : 60);
}

async function switchCase(cid, keep = {}) {
  const data = await loadCase(cid);
  const variants = data.meta.variants;
  const variant = keep.variant && variants.includes(keep.variant) ? keep.variant : (variants[0] ?? null);
  const v = data.results?.variants.find((x) => x.variant === variant);
  const frame = Math.min(Math.max(0, keep.frame ?? v?.reference_frame ?? 0), data.meta.n_frames - 1);
  const patch = { data, caseId: cid, variant, frame, wT: keep.wT ?? v?.weights.testimony ?? null, hyp: keep.hyp ?? null, playing: false };
  if (keep.view) patch.view = keep.view;
  set(patch);
  document.title = `${data.meta.label}: Sensor Forensics Lab`;
}

function renderHeader() {
  const cases = $("#cases");
  cases.innerHTML = "";
  for (const c of state.index.cases) {
    const b = document.createElement("button");
    b.className = "case-btn";
    b.dataset.case = c.case;
    b.innerHTML = `<b>${c.label}</b><small>${c.date}</small>`;
    b.title = `${c.label}, ${c.platform}${c.scored ? "" : " (not scored yet)"}`;
    b.addEventListener("click", () => { if (c.case !== state.caseId) switchCase(c.case, {}); });
    cases.append(b);
  }
  for (const a of document.querySelectorAll(".view-tab")) {
    a.addEventListener("click", (e) => { e.preventDefault(); set({ view: a.dataset.view }); });
  }
}

function syncHeader() {
  for (const b of document.querySelectorAll(".case-btn")) b.setAttribute("aria-pressed", String(b.dataset.case === state.caseId));
  for (const a of document.querySelectorAll(".view-tab")) {
    const on = a.dataset.view === state.view;
    a.href = `#/${state.caseId}/${a.dataset.view}`;
    if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
  const vs = state.data?.meta.variants ?? [];
  const box = $("#variant");
  box.hidden = vs.length < 2;
  const seg = $("#variant-seg");
  seg.innerHTML = "";
  for (const v of vs) {
    const b = document.createElement("button");
    b.textContent = variantLabel(v);
    b.setAttribute("aria-pressed", String(v === state.variant));
    b.title = "Field of view is a sensor setting; both runs are reported, never mixed";
    b.addEventListener("click", () => set({ variant: v }));
    seg.append(b);
  }
}

function showView() {
  for (const k of VIEW_KEYS) {
    const el = $(`#view-${k}`);
    const on = k === state.view;
    el.classList.toggle("active", on);
    if (on && !mounted[k]) { VIEWS[k].mount(el, api); mounted[k] = true; }
  }
}

const api = { getState, set, currentVariant, currentScores, subscribe: (fn) => subs.add(fn) };

function keyboard(e) {
  const t = e.target;
  if (t.closest("input, select, textarea, [contenteditable]") && !(t.type === "range" && /^[1-5]$/.test(e.key))) return;
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const n = state.data?.meta.n_frames ?? 1;
  if (/^[1-5]$/.test(e.key)) { set({ view: VIEW_KEYS[+e.key - 1] }); e.preventDefault(); return; }
  if (t.closest("button, a") && (e.key === " " || e.key === "Enter")) return;
  const step = e.shiftKey ? 10 : 1;
  if (e.key === "ArrowRight" || e.key === ".") set({ frame: Math.min(n - 1, state.frame + step), playing: false });
  else if (e.key === "ArrowLeft" || e.key === ",") set({ frame: Math.max(0, state.frame - step), playing: false });
  else if (e.key === "Home") set({ frame: 0, playing: false });
  else if (e.key === "End") set({ frame: n - 1, playing: false });
  else if (e.key === " " || e.key === "k") set({ playing: !state.playing });
  else return;
  e.preventDefault();
}

let raf = 0, last = 0, acc = 0;
function playLoop(ts) {
  if (!state.playing) { raf = 0; return; }
  const fps = state.data?.meta.fps || 29.97;
  acc += last ? (ts - last) / 1000 : 0;
  last = ts;
  const adv = Math.floor(acc * fps);
  if (adv > 0) {
    acc -= adv / fps;
    const n = state.data.meta.n_frames;
    const f = state.frame + adv;
    set(f >= n - 1 ? { frame: n - 1, playing: false } : { frame: f });
  }
  raf = requestAnimationFrame(playLoop);
}

async function boot() {
  state.index = await loadIndex();
  renderHeader();
  const tape = createTape($("#tape"), api);
  subs.add((s, ch) => {
    if (ch.has("caseId") || ch.has("view") || ch.has("variant") || ch.has("data")) { syncHeader(); showView(); }
    if (ch.has("playing") && s.playing && !raf) { last = 0; acc = 0; raf = requestAnimationFrame(playLoop); }
    renderRail($("#rail"), api, ch);
    tape.update(s, ch);
    for (const k of VIEW_KEYS) if (mounted[k]) VIEWS[k].update?.(s, ch);
  });
  document.addEventListener("keydown", keyboard);
  window.addEventListener("hashchange", () => {
    const h = parseHash();
    if (h.caseId && h.caseId !== state.caseId) switchCase(h.caseId, h);
    else set(Object.fromEntries(Object.entries(h).filter(([k, v]) => v !== null && k !== "caseId")), { route: false });
  });
  const h = parseHash();
  const cid = state.index.cases.some((c) => c.case === h.caseId) ? h.caseId : state.index.cases[0].case;
  if (h.view) state.view = h.view;
  await switchCase(cid, h);
  window.__app = { state, ready: true };
}

boot().catch((err) => {
  document.getElementById("main").innerHTML =
    `<div class="empty"><div><b>The app data did not load.</b>${String(err.message)}<br>Run <code>.venv/Scripts/python tools/build_app_data.py</code>, then reload.</div></div>`;
  window.__app = { error: String(err) };
});
