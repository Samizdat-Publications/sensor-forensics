// App shell: hash router, shared state, case switcher, field-of-view switch, rail, timeline, playback clock,
// staged loading, the welcome card and the tours.
// Route: #/<case>/<view>?f=<frame>&v=<variant>&w=<testimony weight>&h=<hypothesis>; #tour starts the GIMBAL tour.

import { loadIndex, loadCase, loadPredictions, retryFailed, onProgress } from "./data.js";
import { scoreVariant } from "./scoring.js";
import { renderRail } from "./rail.js";
import { createTape } from "./tape.js";
import { createPlayer } from "./player.js";
import { variantLabel, esc } from "./units.js";
import { mountGlossary, openGlossary, INTROS } from "./glossary.js";
import { initTours, startTour, stopTour, isTouring, showWelcome, welcomeSeen } from "./tour.js";
import * as cockpit from "./views/cockpit.js";
import * as godseye from "./views/godseye.js";
import * as rangeView from "./views/range.js";
import * as compare from "./views/compare.js";
import * as ledger from "./views/ledger.js";

const VIEWS = { cockpit, godseye, range: rangeView, compare, ledger };
const VIEW_KEYS = Object.keys(VIEWS);
const store = { get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* private window */ } } };

const state = {
  index: null, caseId: "gimbal", view: "cockpit", frame: 0, variant: null,
  wT: null, hyp: null, data: null, playing: false,
  range: null,        // assumed range (nmi) shared by the god's-eye view and the range explorer
  overrides: {},      // per-criterion weight changes from the ledger (same for every hypothesis)
  cmode: "render",    // cockpit re-render mode: render, diff, blink
  dataRev: 0,         // bumps as background files land (data.js stage 2)
  buffering: false,   // playback waiting on the network
  speed: 1,           // playback rate
  expert: store.get("sfl.expert") === "1", // "All numbers" instead of plain mode
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
  return v ? scoreVariant(v, state.wT ?? v.weights.testimony, state.overrides) : null;
}

// The hypothesis the views draw: the selected one, else the leader at the live weight.
export function currentHyp() {
  const rows = currentScores();
  if (!rows?.length) return null;
  return rows.find((r) => r.h.id === state.hyp) || rows[0];
}

export function set(patch, { route = true } = {}) {
  const changed = new Set();
  for (const [k, v] of Object.entries(patch)) if (state[k] !== v) { state[k] = v; changed.add(k); }
  if (!changed.size) return;
  if (route) writeHash();
  // a background file landing redraws like new data
  if (changed.has("dataRev")) changed.add("data");
  for (const fn of subs) fn(state, changed);
}

function parseHash() {
  const [path, q = ""] = location.hash.replace(/^#\/?/, "").split("?");
  const [c, v] = path.split("/");
  const p = new URLSearchParams(q);
  return {
    caseId: c && c !== "tour" ? c : null, view: VIEW_KEYS.includes(v) ? v : null,
    frame: p.has("f") ? +p.get("f") : null, variant: p.get("v"),
    wT: p.has("w") ? +p.get("w") : null, hyp: p.get("h"),
    range: p.has("r") ? +p.get("r") : null,
    cmode: ["render", "diff", "blink"].includes(p.get("m")) ? p.get("m") : null,
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
    if (state.range !== null) p.set("r", String(state.range));
    if (state.cmode !== "render") p.set("m", state.cmode);
    const h = `#/${state.caseId}/${state.view}?${p}`;
    if (location.hash !== h) history.replaceState(null, "", h);
  }, state.playing ? 400 : 60);
}

function onLate(data) {
  return () => { if (state.data === data) set({ dataRev: state.dataRev + 1 }, { route: false }); };
}

async function switchCase(cid, keep = {}) {
  let data, late = () => {}; // files already cached land before loadCase returns: nothing to announce then
  try {
    data = await loadCase(cid, () => late());
  } catch (err) {
    bootError(err);
    throw err;
  }
  late = onLate(data);
  const variants = data.meta.variants;
  const variant = keep.variant && variants.includes(keep.variant) ? keep.variant : (variants[0] ?? null);
  const v = data.results?.variants.find((x) => x.variant === variant);
  const frame = Math.min(Math.max(0, keep.frame ?? v?.reference_frame ?? 0), data.meta.n_frames - 1);
  loadPredictions(data, variant, late);
  player.load(data.meta);
  const patch = { data, caseId: cid, variant, frame, wT: keep.wT ?? v?.weights.testimony ?? null, hyp: keep.hyp ?? null, playing: false,
    range: keep.range ?? null, overrides: {} };
  if (keep.view) patch.view = keep.view;
  set(patch);
  document.title = `${data.meta.label}: Sensor Forensics Lab`;
  bootDone();
}

function renderHeader() {
  const cases = $("#cases");
  cases.innerHTML = "";
  for (const c of state.index.cases) {
    const b = document.createElement("button");
    b.className = "case-btn";
    b.dataset.case = c.case;
    b.innerHTML = `<b>${esc(c.label)}</b><small>${esc(c.date)}</small>`;
    b.title = `${c.label}, ${c.platform}${c.scored ? "" : " (not scored yet)"}`;
    b.addEventListener("click", () => { if (c.case !== state.caseId) { stopTour(); switchCase(c.case, {}); } });
    cases.append(b);
  }
  for (const a of document.querySelectorAll(".view-tab")) {
    a.addEventListener("click", (e) => { e.preventDefault(); set({ view: a.dataset.view }); });
  }
  $("#t-tour").addEventListener("click", () => (isTouring() ? stopTour() : startTour(state.caseId)));
  $("#t-gloss").addEventListener("click", openGlossary);
  $("#t-about").addEventListener("click", () => { const el = $(`#intro-${state.view}`); if (el) toggleIntro(state.view, el.hidden); });
  for (const b of document.querySelectorAll("#mode-seg button")) b.addEventListener("click", () => {
    const expert = b.dataset.m === "all";
    store.set("sfl.expert", expert ? "1" : "0");
    set({ expert }, { route: false });
  });
}

function syncHeader() {
  for (const b of document.querySelectorAll(".case-btn")) b.setAttribute("aria-pressed", String(b.dataset.case === state.caseId));
  for (const a of document.querySelectorAll(".view-tab")) {
    const on = a.dataset.view === state.view;
    a.href = `#/${state.caseId}/${a.dataset.view}`;
    if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
  for (const b of document.querySelectorAll("#mode-seg button")) b.setAttribute("aria-pressed", String((b.dataset.m === "all") === state.expert));
  $("#t-about").setAttribute("aria-pressed", String(store.get(`sfl.intro.${state.view}`) !== "0"));
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

// Each view gets an introduction line above it (open until dismissed, per view) and its body below.
function viewShell(k) {
  const el = $(`#view-${k}`);
  if (!el.querySelector(".vbody")) {
    const [what, tryIt] = INTROS[k];
    el.innerHTML = `<div class="intro" id="intro-${k}"${store.get(`sfl.intro.${k}`) === "0" ? " hidden" : ""}>
        <p><b>What you're looking at.</b> ${esc(what)} <span class="try"><b>Try:</b> ${esc(tryIt)}</span></p>
        <button type="button" class="x" aria-label="Hide this introduction">×</button></div>
      <div class="vbody"></div>`;
    el.querySelector(".intro .x").addEventListener("click", () => toggleIntro(k, false));
  }
  return el.querySelector(".vbody");
}
function toggleIntro(k, on) {
  store.set(`sfl.intro.${k}`, on ? "1" : "0");
  $(`#intro-${k}`).hidden = !on;
  $("#t-about").setAttribute("aria-pressed", String(on));
  window.dispatchEvent(new Event("resize"));
}

function showView() {
  for (const k of VIEW_KEYS) {
    const el = $(`#view-${k}`);
    const on = k === state.view;
    el.classList.toggle("active", on);
    if (on && !mounted[k]) { VIEWS[k].mount(viewShell(k), api); mounted[k] = true; }
    else if (on) VIEWS[k].show?.();
  }
  // the playback video lives in the cockpit's picture when the cockpit is on screen, else in a tiny holder so the
  // browser keeps decoding it (it is the clock for every view)
  if (state.view === "cockpit" && mounted.cockpit) cockpit.attachVideo(player.video);
  else if (player.video.parentElement !== $("#vid-holder")) $("#vid-holder").append(player.video);
}

const api = {
  getState, set, currentVariant, currentScores, currentHyp, subscribe: (fn) => subs.add(fn),
  switchCase: (cid) => switchCase(cid, {}),
  retry: () => state.data && retryFailed(state.data, state.variant, onLate(state.data)),
};
const player = createPlayer(api);
api.player = player;

function keyboard(e) {
  if (e.defaultPrevented) return;
  const t = e.target;
  if (t.closest("input, select, textarea, [contenteditable]") && !(t.type === "range" && /^[1-5]$/.test(e.key))) return;
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const n = state.data?.meta.n_frames ?? 1;
  if (e.key === "?") { openGlossary(); e.preventDefault(); return; }
  if (/^[1-5]$/.test(e.key)) { set({ view: VIEW_KEYS[+e.key - 1] }); e.preventDefault(); return; }
  if (t.closest("button, a, [role=button], tr[tabindex]") && (e.key === " " || e.key === "Enter")) return;
  const step = e.shiftKey ? 10 : 1;
  if (e.key === "ArrowRight" || e.key === ".") set({ frame: Math.min(n - 1, state.frame + step), playing: false });
  else if (e.key === "ArrowLeft" || e.key === ",") set({ frame: Math.max(0, state.frame - step), playing: false });
  else if (e.key === "Home") set({ frame: 0, playing: false });
  else if (e.key === "End") set({ frame: n - 1, playing: false });
  else if (e.key === " " || e.key === "k") set({ playing: !state.playing });
  else return;
  e.preventDefault();
}

// ---- boot screen (static in index.html, so it shows before any script runs)
function bootDone() { const b = $("#boot"); if (b) b.remove(); }
function bootError(err) {
  const b = $("#boot");
  const msg = `<b>The lab's data did not load.</b><span>${esc(String(err.message ?? err))}</span>
    <span>The connection may be slow or dropping. Try again, or come back later.</span><button type="button" class="go" id="boot-retry">Try again</button>`;
  if (b) {
    b.querySelector(".boot-msg").innerHTML = msg;
    b.classList.add("err");
    b.querySelector("#boot-retry").onclick = () => location.reload();
    window.__app = { error: String(err) };
    return;
  }
  // a later case switch: say so over the lab, which keeps the case it had
  const t = document.createElement("div");
  t.className = "toast";
  t.setAttribute("role", "alert");
  t.innerHTML = `${msg.replace('id="boot-retry"', 'data-retry')}<button type="button" class="x" aria-label="Close">×</button>`;
  t.querySelector("[data-retry]").onclick = () => location.reload();
  t.querySelector(".x").onclick = () => t.remove();
  document.body.append(t);
}

async function boot() {
  onProgress((msg) => { const m = $("#boot .boot-msg span"); if (m) m.textContent = msg; });
  mountGlossary();
  state.index = await loadIndex();
  renderHeader();
  const tape = createTape($("#tape"), api);
  subs.add((s, ch) => {
    if (ch.has("caseId") || ch.has("view") || ch.has("variant") || ch.has("data") || ch.has("expert")) { syncHeader(); showView(); }
    if (ch.has("variant") && s.data) loadPredictions(s.data, s.variant, onLate(s.data));
    if (ch.has("playing")) { if (s.playing) player.start(); else player.stop(); }
    if (ch.has("speed")) player.setSpeed(s.speed);
    renderRail($("#rail"), api, ch);
    tape.update(s, ch);
    for (const k of VIEW_KEYS) if (mounted[k]) VIEWS[k].update?.(s, ch);
  });
  initTours(api);
  document.addEventListener("keydown", keyboard);
  window.addEventListener("hashchange", () => {
    if (location.hash === "#tour") { startTour("gimbal"); return; }
    const h = parseHash();
    if (h.caseId && h.caseId !== state.caseId) switchCase(h.caseId, h);
    else set(Object.fromEntries(Object.entries(h).filter(([k, v]) => v !== null && k !== "caseId")), { route: false });
  });
  const wantTour = location.hash === "#tour";
  const h = parseHash();
  const cid = state.index.cases.some((c) => c.case === h.caseId) ? h.caseId : state.index.cases[0].case;
  if (h.view) state.view = h.view;
  if (h.cmode) state.cmode = h.cmode;
  await switchCase(cid, h);
  window.__app = { state, ready: true, api };
  if (wantTour) startTour(cid);
  else if (!welcomeSeen() && !h.caseId) showWelcome(state.index);
}

boot().catch((err) => { if (!window.__app?.error) bootError(err); });
