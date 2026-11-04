// Guided tour and welcome card. The tour drives the lab through the steps in tours.js: it sets the state, plays a
// stretch when a step asks for it, rings the part of the screen the step talks about (dimming the rest), and shows
// the narration in a card above the timeline. The welcome card shows once (remembered in localStorage) and offers
// a tour of any of the three videos or the lab on its own.

import { TOURS } from "./tours.js";
import { plainName, likelihoodWords } from "./glossary.js";
import { sensitivities } from "./rail.js";
import { esc, variantLabel } from "./units.js";

let api = null, tour = null, k = 0, card = null, ring = null, dims = [], spotEl = null, raf = 0;
const store = { get: (key) => { try { return localStorage.getItem(key); } catch { return null; } },
  set: (key, v) => { try { localStorage.setItem(key, v); } catch { /* private window: the card just shows again */ } } };

export function initTours(a) {
  api = a;
  api.subscribe((s, ch) => {
    if (!tour) return;
    if (ch.has("data") || ch.has("dataRev") || ch.has("wT") || ch.has("hyp") || ch.has("overrides")) renderCard();
    if (ch.has("view") || ch.has("expert") || ch.has("data")) requestAnimationFrame(placeSpot);
  });
  window.addEventListener("resize", () => tour && placeSpot());
}

// Everything a step's text may use, from the data on screen (pure: tests/js/onboarding.test.mjs builds it from the
// exported files and checks every step's text).
function context() { return tourContext(api.getState(), api.currentScores() ?? [], api.currentVariant()); }

export function tourContext(s, rows, v) {
  const byPO = [...rows].filter((r) => Number.isFinite(r.physicsOnly)).sort((a, b) => b.physicsOnly - a.physicsOnly);
  const byTW = [...rows].filter((r) => Number.isFinite(r.testimonyWeighted)).sort((a, b) => b.testimonyWeighted - a.testimonyWeighted);
  const sens = v ? sensitivities(v) : [];
  const rf = s.data.readings?.fields?.range;
  const reads = rf && !rf.placeholder ? rf.value.map((x) => parseFloat(x)).filter(Number.isFinite) : [];
  return {
    s, esc, name: (id) => plainName(id),
    leadPO: byPO[0], secondPO: byPO[1], leadTW: byTW[0],
    tiedPO: byPO.slice(2).filter((r) => byPO[1] && Math.abs(r.physicsOnly - byPO[1].physicsOnly) < 0.05),
    size: s.data.predictions?.picture ? `${s.data.predictions.picture.frame_w} x ${s.data.predictions.picture.frame_h} pixels` : "a small copy",
    words: (r) => (r && byPO[0] ? likelihoodWords(r.physicsOnly - byPO[0].physicsOnly).replace(" less likely", " more likely") : ""),
    derived: (r) => r?.h.fits.find((f) => f.fit === r.testimonyFit)?.derived ?? null,
    claim: (id) => s.data.testimony?.claims?.find((c) => c.id === id) ?? null,
    rangeReads: reads.length ? [reads[0].toFixed(1), reads[reads.length - 1].toFixed(1)] : null,
    placeholder: rf?.placeholder ?? null,
    rotation: sens.find((x) => x.kind === "rotation" && x.side === "above") ?? null,
    sum: s.data.meta.summary, decisive: s.data.meta.summary?.decisive === true,
  };
}

export function isTouring() { return !!tour; }

export async function startTour(caseId) {
  closeWelcome();
  if (!TOURS[caseId]) return;
  if (api.getState().caseId !== caseId) await api.switchCase(caseId);
  tour = { id: caseId, ...TOURS[caseId] };
  k = 0;
  document.body.classList.add("touring");
  go(0);
}

export function stopTour() {
  if (!tour) return;
  tour = null;
  api.set({ playing: false });
  card?.remove(); card = null;
  clearSpot();
  document.body.classList.remove("touring");
}

function go(i) {
  const st = tour.steps[i];
  k = i;
  const s = api.getState();
  const patch = { playing: false };
  for (const key of ["view", "frame", "hyp", "range", "cmode"]) if (key in st) patch[key] = st[key];
  api.set(patch);
  renderCard();
  requestAnimationFrame(() => requestAnimationFrame(placeSpot));
  if (st.play !== undefined && st.play > (st.frame ?? s.frame)) playStep();
}

function playStep() {
  const st = tour.steps[k];
  api.set({ frame: st.frame ?? api.getState().frame, playing: false });
  api.player.playUntil(st.play);
  api.set({ playing: true });
}

function renderCard() {
  if (!tour) return;
  const st = tour.steps[k];
  if (!card) {
    card = document.createElement("div");
    card.className = "tour-card";
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-live", "polite");
    document.body.append(card);
    card.addEventListener("click", (e) => {
      const b = e.target.closest("button[data-t]");
      if (!b) return;
      const t = b.dataset.t;
      if (t === "next") { if (k < tour.steps.length - 1) go(k + 1); else finish(); }
      if (t === "back" && k > 0) go(k - 1);
      if (t === "exit") stopTour();
      if (t === "replay") playStep();
      if (t.startsWith("tour:")) startTour(t.slice(5));
    });
  }
  let text = "";
  try { text = st.text(context()); } catch { text = "Loading this step's data..."; }
  const last = k === tour.steps.length - 1;
  card.innerHTML = `<header><span class="tc-case">${esc(tour.title)}${api.getState().variant ? ` · ${esc(variantLabel(api.getState().variant))}` : ""}</span><span class="tc-n">${k + 1} of ${tour.steps.length}</span>
      <button type="button" class="x" data-t="exit" aria-label="Exit the tour">×</button></header>
    <h2>${esc(st.title)}</h2><p>${text}</p>
    <footer>${st.play !== undefined ? `<button type="button" class="reset" data-t="replay">Play again</button>` : ""}
      <span class="sp"></span>
      <button type="button" class="reset" data-t="back"${k === 0 ? " disabled" : ""}>Back</button>
      <button type="button" class="go" data-t="next">${last ? "Finish" : "Next"}</button></footer>`;
}

function finish() {
  const id = tour.id;
  const others = Object.keys(TOURS).filter((x) => x !== id);
  tour.steps = [...tour.steps];
  card.innerHTML = `<header><span class="tc-case">${esc(tour.title)}</span><span class="tc-n">done</span>
      <button type="button" class="x" data-t="exit" aria-label="Close">×</button></header>
    <h2>Now explore on your own</h2>
    <p>Switch videos at the top, step frame by frame with the arrow keys, and press <b>?</b> next to any number for what it means. Or take another tour:</p>
    <footer>${others.map((o) => `<button type="button" class="reset" data-t="tour:${o}">${esc(TOURS[o].title.split(",")[0])} tour</button>`).join("")}
      <span class="sp"></span><button type="button" class="go" data-t="exit">Explore</button></footer>`;
  clearSpot();
}

// ---- spotlight: a ring round the step's element and four dimming panels round the ring
function clearSpot() {
  cancelAnimationFrame(raf);
  ring?.remove(); ring = null;
  for (const d of dims) d.remove();
  dims = [];
  spotEl = null;
}

function placeSpot() {
  if (!tour) return;
  const st = tour.steps[k];
  const el = st.spot ? document.querySelector(st.spot) : null;
  if (!el || !el.getClientRects().length) { clearSpot(); return; }
  spotEl = el;
  el.scrollIntoView({ block: "nearest", inline: "nearest" });
  if (!ring) {
    ring = document.createElement("div");
    ring.className = "spot-ring";
    dims = [0, 1, 2, 3].map(() => { const d = document.createElement("div"); d.className = "spot-dim"; return d; });
    document.body.append(...dims, ring);
  }
  const follow = () => {
    if (!tour || !spotEl) return;
    const r = spotEl.getBoundingClientRect(), p = 4, W = window.innerWidth, H = window.innerHeight;
    const x0 = Math.max(0, r.left - p), y0 = Math.max(0, r.top - p), x1 = Math.min(W, r.right + p), y1 = Math.min(H, r.bottom + p);
    Object.assign(ring.style, { left: `${x0}px`, top: `${y0}px`, width: `${x1 - x0}px`, height: `${y1 - y0}px` });
    const set = (d, l, t, w, h) => Object.assign(d.style, { left: `${l}px`, top: `${t}px`, width: `${Math.max(0, w)}px`, height: `${Math.max(0, h)}px` });
    set(dims[0], 0, 0, W, y0);
    set(dims[1], 0, y1, W, H - y1);
    set(dims[2], 0, y0, x0, y1 - y0);
    set(dims[3], x1, y0, W - x1, y1 - y0);
    raf = requestAnimationFrame(follow);
  };
  cancelAnimationFrame(raf);
  follow();
}

// ---- welcome card (first visit)
let welcome = null;
export function closeWelcome() { welcome?.remove(); welcome = null; store.set("sfl.welcomed", "1"); }
export function welcomeSeen() { return store.get("sfl.welcomed") === "1"; }

export function showWelcome(index) {
  if (welcome) return;
  welcome = document.createElement("div");
  welcome.className = "welcome";
  welcome.setAttribute("role", "dialog");
  welcome.setAttribute("aria-modal", "true");
  welcome.setAttribute("aria-label", "Welcome to the Sensor Forensics Lab");
  const card = (c) => {
    const sm = c.summary;
    const lead = sm ? `On the video alone: ${esc(plainName(sm.leader_physics_only))}${sm.decisive ? "" : ", but not decisively"}.` : "";
    return `<article class="w-case">
      <img src="data/frames/${esc(c.case)}/f${String({ gimbal: 800, gofast: 600, flir1: 400 }[c.case] ?? 0).padStart(6, "0")}.jpg" alt="" loading="lazy">
      <div><h3>${esc(c.label)} <small>${esc(c.date)}</small></h3><p>${lead}${sm?.settle_title ? ` Would settle it: ${esc(sm.settle_title.toLowerCase())}.` : ""}</p>
      <button type="button" class="go" data-w="tour:${esc(c.case)}">Take the ${esc(c.label)} tour</button></div></article>`;
  };
  welcome.innerHTML = `<div class="w-box">
    <h2>Sensor Forensics Lab</h2>
    <p class="w-lead">Three Navy infrared videos of unidentified objects, rebuilt frame by frame. Six explanations, from a balloon to glare in the camera, are scored against the footage with the same geometry and the same math, and the lab says plainly where the public data cannot decide.</p>
    <div class="w-cases">${index.cases.map(card).join("")}</div>
    <footer><span class="note">Each tour takes about two minutes. You can restart it any time from the Tour button at the top.</span><button type="button" class="reset" data-w="explore">Explore on my own</button></footer>
  </div>`;
  welcome.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-w]");
    if (!b) return;
    if (b.dataset.w === "explore") closeWelcome();
    else startTour(b.dataset.w.slice(5));
  });
  document.body.append(welcome);
  welcome.querySelector("button.go")?.focus();
}
