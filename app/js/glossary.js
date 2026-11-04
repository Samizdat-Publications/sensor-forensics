// Plain words for the lab: short names for the six explanations, a glossary behind every "?" button, the one-line
// introduction at the top of each view, and the wording of likelihood gaps. Presentation only: nothing here
// changes a score (D-021).

import { esc } from "./units.js";

// Short plain names; the scorer's own label (results.json) stays the long form.
export const PLAIN = {
  "H-BAL": "Balloon",
  "H-SLOW": "Bird or small drone",
  "H-AC": "Distant jet",
  "H-ART": "Glare in the pod",
  "H-CLOSE": "Close small object",
  "H-WIT": "Free path, no model",
};
export const plainName = (id, label) => PLAIN[id] ?? label ?? id;

export const TERMS = {
  "H-BAL": ["Balloon (H-BAL)", "A balloon or other object drifting with the wind, so its air speed is near zero. Its apparent motion comes from the jet's own movement and the wind."],
  "H-SLOW": ["Bird or small drone (H-SLOW)", "A slow flier: something moving through the air on its own at low speed, such as a bird or a small drone."],
  "H-AC": ["Distant jet (H-AC)", "A distant aircraft whose hot engine exhaust shows up in the infrared camera as a glare, so the glare's shape and rotation come from the camera, not the aircraft."],
  "H-ART": ["Glare in the pod (H-ART)", "A sensor artifact: glare in the targeting pod's own optics around a hot target of any kind. The shape you see turns with the camera, not with the object."],
  "H-CLOSE": ["Close small object (H-CLOSE)", "A small object close to the jet, for example within a couple of miles."],
  "H-WIT": ["Free path (H-WIT)", "An object on a smooth path with no physical model behind it: it may fly at any range and speed the footage allows. It is the most flexible explanation: it stands for an object none of the physical models describes."],
  likelihood: ["How likely, and log-likelihood", "Each explanation gets a score for how well it predicts everything measured in the footage. The lab adds these up as log-likelihoods: higher is better, and a gap of 2.3 means one explanation makes the data 10 times more likely than the other. Plain mode shows the gap as 'times less likely'."],
  physics: ["Video only (physics only)", "The score from the footage and physics alone, without counting what the aircrew said. It is always shown beside the score that counts testimony."],
  testimony: ["With aircrew accounts (testimony)", "The score after also counting sourced statements by the aircrew and others (range, speed, behaviour), each as a measurement with its own uncertainty. The slider sets how much they count: 0 ignores them, 1 is the default, 2 counts them double."],
  framelock: ["Frame lock", "How closely the lab's re-creation lines up with the real footage, in pixels. Horizon: how far the predicted horizon sits from the one measured from the cloud motion. Object offset: how far the blob sits from the centre of the picture (the same for every explanation)."],
  fov: ["Field of view", "How wide the camera's picture is, in degrees. GIMBAL was filmed in a narrow mode documented as 0.35 deg (with 2x zoom) or 0.7 deg; the lab runs both and never mixes them."],
  sightline: ["Sight line", "The direction from the jet to the object, from the pod's azimuth (left or right of the nose) and elevation (above or below level) read off the screen."],
  range: ["Range", "Distance from the jet to the object, in nautical miles (1 nmi = 1.15 miles = 1.85 km). Only GOFAST shows it on screen; for the others every answer depends on an assumed range."],
  assumedrange: ["Assumed range", "When the range is not on screen, the same picture fits a small thing close by or a big thing far away. Pick a range and the lab shows what the object would have to be doing at that distance."],
  fixedrange: ["Fixed-range path", "The path the object would follow if it stayed at the assumed range on every frame, along the sight lines."],
  probe: ["Angles-only fit", "The simplest possible object: one flying in a straight line at constant speed, fitted at each assumed range to the sight lines alone (no testimony)."],
  confidence: ["Read confidence", "How sure the lab's character reader is of a number read off the screen, from 0 to 1. Below 0.30 counts as low and is marked in red."],
  exclusions: ["Data-quality rules", "Two measurements (the blob's size and brightness) are held at weight 0 because the blob is unresolved or saturated. These rules were set after seeing results, so the lab always shows the ranking both with and without them."],
  rotationnoise: ["Rotation noise", "How precisely the shape's rotation can be measured from the video. Some rankings depend on it: FLIR1's leader changes if the rotation is measured a little less precisely, GIMBAL's if a little more. The lab measures it from the data and shows where it would flip the result."],
  nmi: ["nmi", "Nautical mile: 1.15 statute miles or 1.85 km. Air speeds are in knots (kt), nautical miles per hour."],
  nar: ["NAR, Z 2.0", "The pod's narrow field of view, with 2x digital zoom. GIMBAL and GOFAST were filmed in it."],
  window: ["Scored frames", "The part of the clip the scoring uses: frames where the sight line is read and the object is tracked."],
};

// A "?" button that opens one glossary entry.
export function q(key) {
  const t = TERMS[key];
  return t ? `<button type="button" class="q" data-g="${key}" aria-label="What is ${esc(t[0])}?" title="What is this?">?</button>` : "";
}

// What each view shows, and one thing to try. Plain words, no numbers (the numbers are in the view).
export const INTROS = {
  cockpit: ["The real Navy footage on the left; on the right, what the camera would have seen if the selected explanation were true.",
    "Press Play to watch both together, or switch the right panel to Difference to see where they disagree."],
  godseye: ["The scene from above: the jet's path, the pod's sight lines, and where the selected explanation puts the object.",
    "Press Play and watch the jet turn while its sight line sweeps; pick another explanation in the list on the right."],
  range: ["When the distance is not on screen, the same picture fits a small thing close by or a big thing far away. These charts show what the object would have to be doing at each distance.",
    "Drag the assumed range and read where each explanation crosses the shaded bands (balloon, birds, airliners)."],
  compare: ["Earlier analyses of the same video, each rerun from its own inputs, beside the lab's own fits.",
    "Hover a mark to see the published number and the lab's reproduction of it."],
  ledger: ["Every number the lab read off the screen, every witness statement, and the weight each measurement gets.",
    "Drag a weight and watch the scores on the right recompute; click a reading to open its frame."],
};

// Words for a gap below the best total (natural-log units: 2.3 is a factor of 10).
export function likelihoodWords(gap) {
  if (!Number.isFinite(gap)) return "not scored";
  const g = -gap;
  if (g < 0.005) return "best fit";
  const r = Math.exp(g);
  if (r < 1.5) return "about as likely";
  if (r < 10) return `about ${r.toFixed(1)} times less likely`;
  if (r < 100) return `about ${Math.round(r)} times less likely`;
  if (r < 1e6) {
    const p = Math.pow(10, Math.floor(Math.log10(r)) - 1);
    return `about ${(Math.round(r / p) * p).toLocaleString("en-US")} times less likely`;
  }
  return "over a million times less likely";
}

let pop = null;
function closePop() { pop?.remove(); pop = null; }

export function openGlossary() {
  closePop();
  const el = document.createElement("div");
  el.className = "gloss-panel";
  el.setAttribute("role", "dialog");
  el.setAttribute("aria-label", "Glossary");
  el.innerHTML = `<header><h2>Glossary</h2><button type="button" class="x" aria-label="Close">×</button></header>
    <dl>${Object.values(TERMS).map(([t, d]) => `<dt>${esc(t)}</dt><dd>${esc(d)}</dd>`).join("")}</dl>`;
  el.querySelector(".x").addEventListener("click", closePop);
  document.body.append(el);
  pop = el;
  el.querySelector(".x").focus();
}

// One delegated handler for every "?" button in the app.
export function mountGlossary() {
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-g]");
    if (!b) { if (pop && !e.target.closest(".gloss-pop, .gloss-panel")) closePop(); return; }
    e.preventDefault();
    e.stopPropagation();
    const t = TERMS[b.dataset.g];
    if (!t) return;
    const wasMine = pop?.dataset.for === b.dataset.g;
    closePop();
    if (wasMine) return;
    const el = document.createElement("div");
    el.className = "gloss-pop";
    el.dataset.for = b.dataset.g;
    el.setAttribute("role", "tooltip");
    el.innerHTML = `<b>${esc(t[0])}</b><p>${esc(t[1])}</p>`;
    document.body.append(el);
    const r = b.getBoundingClientRect(), w = Math.min(320, window.innerWidth - 24);
    el.style.width = `${w}px`;
    el.style.left = `${Math.max(12, Math.min(window.innerWidth - w - 12, r.left - w / 2))}px`;
    const h = el.offsetHeight;
    el.style.top = `${r.bottom + 8 + h > window.innerHeight ? Math.max(8, r.top - h - 8) : r.bottom + 8}px`;
    pop = el;
  }, true);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePop(); });
}
