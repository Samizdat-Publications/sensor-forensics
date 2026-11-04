// God's-eye view (M4.4): the scene from above for the selected explanation: the jet's path, the pod's sight lines
// (every Nth frame), and where the explanation puts the object, from predictions.json (the scorer's forward model at
// the stored fits). The clip so far is drawn bright and the rest dim, with labelled markers for the jet and the
// object, so playback reads as motion. "Show every explanation" draws all six fits, each with its own jet.
// Each fit has its own heading, and the wind crabs each jet differently, so every fit is turned so its jet's NOSE
// points up the screen at the first frame (geom.alignToNose): the sight lines then sit where the pod pointed them,
// the same for every fit. A range slider draws a fixed-range path along the selected fit's sight lines and reads the
// curves over range there; the assumed range stays put while the clip plays.
// Scene units: nautical miles, three.js y up.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { variantPredictions, fitPredictions, partState } from "../data.js";
import { num, kt, ft, fpm, nmi, hypColor, esc } from "../units.js";
import { NMI_M, FT_M, alignToNose, pointAtRange, pathKinematics, interpCurve, ticks, altitudeM, rangeDomain } from "../geom.js";
import { plainName, q } from "../glossary.js";

let api, root, renderer, scene, camera, controls, box, scaleEl, labelsEl, groupStatic, groupLive, fixedLine, info, slider, out, picker;
let showAll = false, follow = false, built = "", dirty = false, sz = 10, lastJet = null;
const FAN_EVERY = 45;
const toScene = (p) => new THREE.Vector3(p[0] / NMI_M, p[2] / NMI_M, -p[1] / NMI_M);

export function parseAz(v) {
  const m = /^(\d+(?:\.\d+)?)([LR])$/.exec(v || "");
  return m ? (m[2] === "L" ? -1 : 1) * +m[1] : null;
}

export function mount(el, a) {
  api = a;
  root = el;
  el.innerHTML = `
    <div class="ge">
      <div class="panel fill">
        <div class="panel-h"><h2>Scene from above</h2><div class="seg" role="group" aria-label="Camera" id="ge-cam"><button data-c="overview" aria-pressed="true">Overview</button><button data-c="follow" aria-pressed="false">Follow the jet</button></div>
          <span class="src">drag to orbit, right-drag to pan, wheel to zoom</span></div>
        <div class="panel-b"><div class="frame-box" id="ge-gl" style="background:var(--ink-0)">
          <div class="ge-labels" id="ge-labels" aria-hidden="true"></div>
          <span class="overlay-tag" id="ge-tag"></span>
          <div class="scalebar" id="ge-scale"><span class="bar"></span><span class="lbl"></span></div>
          <ul class="ge-key" aria-label="Key"><li><i style="background:#e8ecf0"></i>Jet, clip so far</li><li><i style="background:#63758a"></i>Sight lines ${q("sightline")}</li><li><i class="dash"></i>Fixed-range path ${q("fixedrange")}</li></ul>
        </div></div>
      </div>
      <div class="stack ge-side">
        <div class="panel">
          <div class="panel-h"><h2>Explanation</h2><label class="src chk"><input type="checkbox" id="ge-all"> Show every explanation</label></div>
          <div class="panel-b"><ul class="ge-pick" id="ge-pick" role="listbox" aria-label="Explanation shown"></ul><p class="note" id="ge-pick-note"></p></div>
        </div>
        <div class="panel">
          <div class="panel-h"><h2>Assumed range ${q("assumedrange")}</h2><span class="src" id="ge-rsrc"></span></div>
          <div class="panel-b">
            <div class="range-ctl"><label for="ge-r">Range</label><input id="ge-r" type="range" min="1" max="45" step="0.5" value="10"><output id="ge-out"></output></div>
            <dl class="kv" id="ge-info" style="margin-top:10px"></dl>
          </div>
        </div>
      </div>
    </div>`;
  box = el.querySelector("#ge-gl");
  info = el.querySelector("#ge-info");
  slider = el.querySelector("#ge-r");
  out = el.querySelector("#ge-out");
  picker = el.querySelector("#ge-pick");
  scaleEl = el.querySelector("#ge-scale");
  labelsEl = el.querySelector("#ge-labels");
  slider.addEventListener("input", () => api.set({ range: +slider.value }));
  picker.addEventListener("click", (e) => { const b = e.target.closest("[data-h]"); if (b) api.set({ hyp: b.dataset.h }); });
  el.querySelector("#ge-all").addEventListener("change", (e) => { showAll = e.target.checked; built = ""; draw(); });
  for (const b of el.querySelectorAll("#ge-cam button")) b.addEventListener("click", () => {
    follow = b.dataset.c === "follow";
    for (const x of el.querySelectorAll("#ge-cam button")) x.setAttribute("aria-pressed", String(x === b));
    if (!follow) { built = ""; draw(); } else lastJet = null;
  });

  renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  renderer.domElement.classList.add("full");
  box.prepend(renderer.domElement);
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x10151b);
  camera = new THREE.PerspectiveCamera(40, 1.6, 0.05, 5000);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  scene.add(new THREE.GridHelper(200, 40, 0x445466, 0x222c36));
  groupStatic = new THREE.Group(); groupLive = new THREE.Group();
  scene.add(groupStatic, groupLive);
  fixedLine = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineDashedMaterial({ color: 0xf2b84b, dashSize: 0.25, gapSize: 0.18 }));
  fixedLine.frustumCulled = false;
  scene.add(fixedLine);
  new ResizeObserver(() => { if (visible()) { resize(); if (dirty) draw(); } }).observe(box);
  resize();
  const loop = () => {
    requestAnimationFrame(loop);
    if (!visible()) return;
    controls.update();
    renderer.render(scene, camera);
    placeLabels();
    scale();
  };
  loop();
  draw();
}

const visible = () => !!root && root.offsetParent !== null && box.clientWidth > 0 && box.clientHeight > 0;

function resize() {
  const r = box.getBoundingClientRect();
  if (!(r.width > 0 && r.height > 0)) return; // hidden: a zero aspect would put the camera at NaN
  renderer.setSize(r.width, r.height, false);
  renderer.domElement.style.width = "100%";
  renderer.domElement.style.height = "100%";
  camera.aspect = r.width / r.height;
  camera.updateProjectionMatrix();
}

let lastScale = "";
function scale() {
  const h = renderer.domElement.clientHeight || 1;
  const d = camera.position.distanceTo(controls.target);
  const pxPerNmi = h / (2 * d * Math.tan((camera.fov * Math.PI) / 360));
  if (!Number.isFinite(pxPerNmi) || pxPerNmi <= 0) return;
  const target = 120 / pxPerNmi;
  const p = Math.pow(10, Math.floor(Math.log10(target)));
  const len = [1, 2, 5, 10].map((k) => k * p).find((k) => k >= target * 0.6) ?? 10 * p;
  const key = `${len}|${Math.round(len * pxPerNmi)}`;
  if (key === lastScale) return;
  lastScale = key;
  scaleEl.querySelector(".bar").style.width = `${Math.round(len * pxPerNmi)}px`;
  scaleEl.querySelector(".lbl").textContent = `${num(len, len < 1 ? 1 : 0)} nmi (${num(len * 1.150779, 1)} mi) at the orbit centre`;
}

function material(color, opacity) { return new THREE.LineBasicMaterial({ color, transparent: opacity < 1, opacity }); }
function pathGeom(pts) { const g = new THREE.BufferGeometry().setFromPoints(pts); return g; }
function lineOf(g, color, opacity = 1) { const l = new THREE.Line(g, material(color, opacity)); l.frustumCulled = false; return l; }
function clear(g) { while (g.children.length) { const c = g.children.pop(); c.geometry?.dispose(); c.material?.dispose(); } }

function fitsFor(s) {
  const rows = api.currentScores() ?? [];
  const i0 = variantPredictions(s.data, s.variant)?.window_frames?.[0] ?? 0; // align at the first scored frame
  const out2 = [];
  rows.forEach((r, k) => {
    const f = fitPredictions(s.data, s.variant, r.h.id, r.testimonyFit);
    if (f) out2.push({ row: r, fit: f, color: hypColor(r.h.id, k), align: alignToNose(f, i0), derived: r.h.fits.find((x) => x.fit === r.testimonyFit)?.derived });
  });
  return out2;
}

let drawn = []; // per fit on screen: { x, jetGeom, objGeom, jetTrail, objTrail, jetMark, objMark, beam, jetPts, objPts }

function draw() {
  const s = api.getState();
  if (!s.data || !renderer) return;
  if (!visible()) { dirty = true; return; }
  dirty = false;
  const v = variantPredictions(s.data, s.variant);
  const sel = api.currentHyp();
  const fits = v ? fitsFor(s) : [];
  const cur = fits.find((x) => x.row.h.id === sel?.h.id) ?? fits[0];
  const tag = root.querySelector("#ge-tag");
  const plain = !s.expert;
  pickerList(s, fits, cur);
  if (!cur) {
    clear(groupStatic); clear(groupLive); drawn = []; fixedLine.visible = false; labelsEl.innerHTML = "";
    const ps = partState(s.data, "predictions", s.variant);
    tag.textContent = ps === "loading" ? "Loading the scene..." : ps === "failed" ? "The scene did not load; use Try again in the cockpit strip" : "No fitted explanation with predictions for this case";
    info.innerHTML = "";
    return;
  }
  const n = cur.fit.jet_e.length;
  const fps = s.data.meta.fps || 29.97;
  const shown = showAll ? fits : [cur];
  // static geometry: rebuild when the case, variant, selection, fits or "show every explanation" change
  const key = `${s.caseId}|${s.variant}|${cur.row.h.id}|${fits.map((x) => x.row.h.id + x.row.testimonyFit).join(",")}|${showAll}`;
  if (key !== built) {
    built = key;
    clear(groupStatic); clear(groupLive);
    drawn = shown.map((x) => {
      const jetPts = [], objPts = [];
      for (let i = 0; i < n; i++) {
        jetPts.push(toScene(x.align(x.fit.jet_e[i], x.fit.jet_n[i], x.fit.jet_u[i])));
        objPts.push(toScene(x.align(x.fit.obj_e[i], x.fit.obj_n[i], x.fit.obj_u[i])));
      }
      const isCur = x === cur;
      const jetColor = showAll ? x.color : 0xe8ecf0;
      const jetGeom = pathGeom(jetPts), objGeom = pathGeom(objPts);
      groupStatic.add(lineOf(jetGeom, jetColor, 0.22), lineOf(objGeom, x.color, 0.22));
      const jetTrail = lineOf(jetGeom.clone(), jetColor, isCur || !showAll ? 1 : 0.8);
      const objTrail = lineOf(objGeom.clone(), x.color, 1);
      groupStatic.add(jetTrail, objTrail);
      return { x, jetPts, objPts, jetTrail, objTrail };
    });
    // sight-line fan for the selected fit, every FAN_EVERY frames, reaching past the farthest object shown
    const pos = [];
    const reach = Math.max(...shown.map((x) => Math.max(...x.fit.range_m.filter(Number.isFinite)))) * 1.05;
    for (let i = 0; i < n; i += FAN_EVERY) {
      const j = toScene(cur.align(cur.fit.jet_e[i], cur.fit.jet_n[i], cur.fit.jet_u[i]));
      const pa = pointAtRange(cur.fit, i, reach);
      if (!pa) continue;
      const o = toScene(cur.align(...pa));
      pos.push(j.x, j.y, j.z, o.x, o.y, o.z);
    }
    const fan = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)),
      new THREE.LineBasicMaterial({ color: 0x63758a, transparent: true, opacity: 0.18 }));
    fan.frustumCulled = false;
    groupStatic.add(fan);
    frameCamera(cur, shown, n);
    lastJet = null;
    const dom = rangeDomain(s.data, s.variant, fits.map((x) => x.derived?.range_nmi_mean));
    slider.min = String(dom[0]); slider.max = String(dom[1]);
  }

  // this frame: trails up to now, markers, the sight line to the object
  const i = s.frame;
  clear(groupLive);
  labels = [];
  const mk = (p, color, r) => { const m = new THREE.Mesh(new THREE.SphereGeometry(r, 16, 12), new THREE.MeshBasicMaterial({ color })); m.position.copy(p); groupLive.add(m); return m; };
  for (const d of drawn) {
    d.jetTrail.geometry.setDrawRange(0, i + 1);
    d.objTrail.geometry.setDrawRange(0, i + 1);
    const j = d.jetPts[i], o = d.objPts[i];
    const isCur = d.x.row.h.id === cur.row.h.id;
    // the jet: a cone pointing along its motion
    const ahead = d.jetPts[Math.min(n - 1, i + 3)], behind = d.jetPts[Math.max(0, i - 3)];
    const dir = new THREE.Vector3().subVectors(ahead, behind).normalize();
    if (isCur || showAll) {
      const cone = new THREE.Mesh(new THREE.ConeGeometry(sz / 75, sz / 26, 14), new THREE.MeshBasicMaterial({ color: showAll ? d.x.color : 0xe8ecf0 }));
      cone.position.copy(j);
      if (dir.lengthSq() > 0) cone.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
      groupLive.add(cone);
    }
    mk(o, d.x.color, sz / (isCur ? 85 : 110));
    const beam = new THREE.Line(new THREE.BufferGeometry().setFromPoints([j, o]), material(d.x.color, isCur ? 0.95 : 0.6));
    beam.frustumCulled = false;
    groupLive.add(beam);
    if (isCur) groupLive.add(lineOf(new THREE.BufferGeometry().setFromPoints([o, new THREE.Vector3(o.x, 0, o.z)]), 0x6b7886, 0.8));
    labels.push({ p: o, text: showAll && !isCur ? d.x.row.h.id : `${plainName(d.x.row.h.id)}${showAll ? ` (${d.x.row.h.id})` : ""}`, color: d.x.color });
    if (isCur || !showAll) labels.push({ p: j, text: "Jet", color: "#e8ecf0" });
  }
  if (follow) {
    const j = drawn.find((d) => d.x.row.h.id === cur.row.h.id)?.jetPts[i];
    if (j) { if (lastJet) { const dv = new THREE.Vector3().subVectors(j, lastJet); camera.position.add(dv); controls.target.add(dv); } else controls.target.copy(j); lastJet = j.clone(); }
  }

  // the assumed range: chosen on the slider, else the selected fit's mean range over the scored frames; it does not
  // follow the frame, so nothing jumps while the clip plays
  const rDef = Number.isFinite(cur.derived?.range_nmi_mean) ? Math.round(cur.derived.range_nmi_mean * 2) / 2 : 10;
  const r = s.range ?? rDef;
  if (+slider.value !== r) slider.value = String(r);
  out.textContent = nmi(r);
  const fixed = [], fixedM = [];
  for (let k = 0; k < n; k++) { const qq = pointAtRange(cur.fit, k, r * NMI_M); if (qq) { fixedM.push(qq); fixed.push(toScene(cur.align(...qq))); } }
  fixedLine.geometry.dispose();
  fixedLine.geometry = new THREE.BufferGeometry().setFromPoints(fixed);
  fixedLine.computeLineDistances();
  fixedLine.visible = true;
  const prM = pointAtRange(cur.fit, i, r * NMI_M);
  if (prM) mk(toScene(cur.align(...prM)), 0xf2b84b, sz / 120);
  tag.textContent = showAll
    ? "Every explanation, each with its own jet: each fits its own wind and heading, so each has its own idea of where the jet flew. All are turned so the jet's nose points up the screen at the first scored frame."
    : `${plainName(cur.row.h.id)} (${cur.row.h.id}). Turned so the jet's nose points up the screen at the first scored frame. Grid: sea level, 5 nmi squares.`;

  // readout
  const t = Array.from({ length: fixedM.length }, (_, k) => k / fps);
  const kin = fixedM.length > 60 ? pathKinematics(t, fixedM, 31) : null;
  const alts = fixedM.map((p) => altitudeM(...p) / FT_M);
  const curve = curveFor(s);
  const at = curve ? interpCurve(curve, r) : null;
  root.querySelector("#ge-rsrc").textContent = s.data.rangeCurves ? "range_curves.json" : s.data.rangeCurve ? "range_curve.json" : "";
  const rows = [["", `<b>If the object stayed ${esc(nmi(r))} away</b> <span class="note">on ${esc(plainName(cur.row.h.id))}'s sight lines</span>`],
    [plain ? "Height now" : "Altitude now", prM ? ft(altitudeM(...prM) / FT_M) : "n/a"]];
  if (kin) rows.push([plain ? "Speed over the ground" : "Ground speed, mean", kt(kin.mean_ground_speed_kt)], [plain ? "Height range" : "Altitude span", `${ft(Math.min(...alts))} to ${ft(Math.max(...alts))}`], [plain ? "Hardest turn or push" : "Peak acceleration", `${num(kin.max_accel_g, 1)} g (1 s smoothing)`]);
  rows.push(["", `<b>Straight-line object at this range</b> ${q("probe")}`]);
  if (at) {
    rows.push(["Air speed", kt(at.air_speed_kt)]);
    if (!plain) rows.push(["Ground speed", kt(at.ground_speed_kt)]);
    rows.push([plain ? "Height, average" : "Altitude, mean", ft(at.altitude_ft_mean)]);
    if (!plain) rows.push(["Vertical speed", fpm(at.vertical_speed_fpm)], ["Sight-line fit", `${num(at.line_of_sight_loglik, 1)} log-lik.`]);
  } else rows.push(["", partState(s.data, "rangeCurve") === "loading" ? "loading the curves over range..." : "outside the range grid"]);
  const perH = s.data.rangeCurves?.variants?.[s.variant ?? ""] ?? null;
  if (perH && !plain) for (const x of fits) {
    const c = perH[x.row.h.id];
    const p = c ? interpCurve(c, r) : null;
    if (p) rows.push([x.row.h.id, esc(`${kt(p.air_speed_kt)}, ${ft(p.altitude_ft_mean)}`)]);
  }
  info.innerHTML = rows.map(([k, val]) => k === "" ? `<dt class="sub" style="grid-column:1/-1">${val}</dt>` : `<dt>${esc(k)}</dt><dd>${val.startsWith("<") ? val : esc(val)}</dd>`).join("") +
    (plain ? "" : `<dt></dt><dd class="note" style="font-family:var(--font-ui)">The fixed-range path puts the object at this slant range on every frame of the selected fit's sight lines. The angles-only fit is the scorer's whole-clip constant-velocity probe at this range (testimony weight 0), linear between grid points.</dd>`);
}

let labels = [];
function placeLabels() {
  if (!labels.length) { labelsEl.innerHTML = ""; return; }
  const w = box.clientWidth, h = box.clientHeight;
  const html = labels.map((l) => {
    const p = l.p.clone().project(camera);
    if (p.z > 1) return "";
    const x = (p.x * 0.5 + 0.5) * w, y = (-p.y * 0.5 + 0.5) * h;
    return `<span style="left:${x.toFixed(0)}px;top:${y.toFixed(0)}px;border-color:${l.color}">${esc(l.text)}</span>`;
  }).join("");
  if (labelsEl.innerHTML !== html) labelsEl.innerHTML = html;
}

function frameCamera(cur, shown, n) {
  const bb = new THREE.Box3();
  for (let i = 0; i < n; i += 10) {
    bb.expandByPoint(toScene(cur.align(cur.fit.jet_e[i], cur.fit.jet_n[i], cur.fit.jet_u[i])));
    for (const x of shown) bb.expandByPoint(toScene(x.align(x.fit.obj_e[i], x.fit.obj_n[i], x.fit.obj_u[i])));
  }
  bb.expandByPoint(new THREE.Vector3(bb.min.x, 0, bb.min.z)); // the sea-level footprint, so height reads against the grid
  const c = bb.getCenter(new THREE.Vector3());
  sz = Math.max(4, bb.getSize(new THREE.Vector3()).length());
  controls.target.copy(c);
  const dist = (sz * 0.62) / Math.tan((camera.fov * Math.PI) / 360) / Math.min(1, Math.max(0.2, camera.aspect));
  camera.position.set(c.x + dist * 0.18, c.y + dist * 0.72, c.z + dist * 0.67);
  controls.update();
}

let pickKey = "";
function pickerList(s, fits, cur) {
  const plain = !s.expert;
  const k = `${plain}|${cur?.row.h.id}|${fits.map((x) => x.row.h.id + (x.derived?.range_nmi_mean ?? "")).join(",")}`;
  if (k === pickKey) return;
  pickKey = k;
  const had = document.activeElement?.closest?.("#ge-pick [data-h]")?.dataset.h;
  picker.innerHTML = fits.map((x) => `<li><button type="button" data-h="${esc(x.row.h.id)}" role="option" aria-selected="${x === cur}" class="${x === cur ? "cur" : ""}">
      <span class="sw" style="background:${x.color}"></span><span class="nm">${esc(plain ? plainName(x.row.h.id) : x.row.h.id)}${plain ? ` <span class="note">${esc(x.row.h.id)}</span>` : ""}</span>
      <span class="note">${esc(nmi(x.derived?.range_nmi_mean))}</span></button></li>`).join("");
  root.querySelector("#ge-pick-note").textContent = fits.length ? "Average distance over the scored frames. Click to show an explanation in every view." : "";
  if (had) picker.querySelector(`[data-h="${CSS.escape(had)}"]`)?.focus();
}

function curveFor(s) {
  const v = api.currentVariant();
  return s.data.rangeCurve?.variants?.[v?.variant ?? ""] ?? null;
}

export function show() { resize(); if (dirty) draw(); }

export function update(s, ch) {
  if (!renderer) return;
  if (["frame", "data", "variant", "hyp", "wT", "range", "overrides", "expert"].some((k) => ch.has(k))) draw();
}

export { ticks };
