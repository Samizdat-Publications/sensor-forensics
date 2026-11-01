// God's-eye view (M4.4): the jet path, the line-of-sight fan (every Nth frame) and each hypothesis's object path
// in its own color, from predictions.json (the scorer's forward model at the stored fits). A range slider redraws
// a fixed-range path along the selected hypothesis's sight lines and reads the curves over range at that range.
// Scene units: nautical miles, three.js y up; each hypothesis is drawn in its own jet frame, rotated so the jet
// starts heading up the screen (the true heading is a fitted nuisance, different for each fit).

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { variantPredictions, fitPredictions } from "../data.js";
import { num, kt, ft, fpm, nmi, hypColor } from "../units.js";
import { esc } from "../rail.js";
import { NMI_M, alignToJet, pointAtRange, pathKinematics, interpCurve, ticks } from "../geom.js";

let api, root, renderer, scene, camera, controls, box, scaleEl, groupPaths, groupFan, groupCur, fixedLine, info, slider, out, legend;
const hidden = new Set();
const FAN_EVERY = 30;
let built = "", dotScale = 0.15;

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
        <div class="panel-h"><h2>Scene</h2><span class="src">drag to orbit, right-drag to pan, wheel to zoom</span></div>
        <div class="panel-b"><div class="frame-box" id="ge-gl" style="background:var(--ink-0)">
          <span class="overlay-tag" id="ge-tag"></span>
          <div class="scalebar" id="ge-scale"><span class="bar"></span><span class="lbl"></span></div>
        </div></div>
      </div>
      <div class="stack ge-side">
        <div class="panel">
          <div class="panel-h"><h2>Assumed range</h2><span class="src" id="ge-rsrc"></span></div>
          <div class="panel-b">
            <div class="range-ctl"><label for="ge-r">Range</label><input id="ge-r" type="range" min="1" max="45" step="0.5" value="10"><output id="ge-out"></output></div>
            <dl class="kv" id="ge-info" style="margin-top:10px"></dl>
          </div>
        </div>
        <div class="panel">
          <div class="panel-h"><h2>Object paths</h2><span class="src">click to show or hide</span></div>
          <div class="panel-b"><ul class="hyp-legend" id="ge-legend"></ul></div>
        </div>
      </div>
    </div>`;
  box = el.querySelector("#ge-gl");
  info = el.querySelector("#ge-info");
  slider = el.querySelector("#ge-r");
  out = el.querySelector("#ge-out");
  legend = el.querySelector("#ge-legend");
  scaleEl = el.querySelector("#ge-scale");
  slider.addEventListener("input", () => api.set({ range: +slider.value }));
  legend.addEventListener("click", (e) => {
    const li = e.target.closest("li[data-h]");
    if (!li) return;
    const h = li.dataset.h;
    if (hidden.has(h)) hidden.delete(h); else hidden.add(h);
    built = "";
    draw();
  });

  renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  renderer.domElement.classList.add("full");
  box.prepend(renderer.domElement);
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x10151b);
  camera = new THREE.PerspectiveCamera(40, 1, 0.05, 5000);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  const grid = new THREE.GridHelper(200, 40, 0x445466, 0x222c36);
  scene.add(grid);
  groupPaths = new THREE.Group(); groupFan = new THREE.Group(); groupCur = new THREE.Group();
  scene.add(groupPaths, groupFan, groupCur);
  fixedLine = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineDashedMaterial({ color: 0xf2b84b, dashSize: 0.25, gapSize: 0.18 }));
  fixedLine.frustumCulled = false;
  scene.add(fixedLine);
  new ResizeObserver(resize).observe(box);
  resize();
  const loop = () => { controls.update(); renderer.render(scene, camera); scale(); requestAnimationFrame(loop); };
  loop();
  draw();
}

function resize() {
  const r = box.getBoundingClientRect();
  renderer.setSize(Math.max(1, r.width), Math.max(1, r.height), false);
  renderer.domElement.style.width = "100%";
  renderer.domElement.style.height = "100%";
  camera.aspect = r.width / Math.max(1, r.height);
  camera.updateProjectionMatrix();
}

let lastScale = "";
function scale() {
  const h = renderer.domElement.clientHeight || 1;
  const d = camera.position.distanceTo(controls.target);
  const pxPerNmi = h / (2 * d * Math.tan((camera.fov * Math.PI) / 360));
  const target = 120 / pxPerNmi;
  const p = Math.pow(10, Math.floor(Math.log10(target)));
  const len = [1, 2, 5, 10].map((k) => k * p).find((k) => k >= target * 0.6) ?? 10 * p;
  const key = `${len}|${Math.round(len * pxPerNmi)}`;
  if (key === lastScale) return;
  lastScale = key;
  scaleEl.querySelector(".bar").style.width = `${Math.round(len * pxPerNmi)}px`;
  scaleEl.querySelector(".lbl").textContent = `${num(len, len < 1 ? 1 : 0)} nmi (${num(len * 1.150779, len < 1 ? 1 : 1)} mi) at the orbit centre`;
}

function lineOf(pts, color, width = 1, opacity = 1) {
  const g = new THREE.BufferGeometry().setFromPoints(pts);
  const m = new THREE.LineBasicMaterial({ color, transparent: opacity < 1, opacity, linewidth: width });
  const l = new THREE.Line(g, m);
  l.frustumCulled = false;
  return l;
}

function clear(g) { while (g.children.length) { const c = g.children.pop(); c.geometry?.dispose(); c.material?.dispose(); } }

function fitsFor(s) {
  const rows = api.currentScores() ?? [];
  const out = [];
  rows.forEach((r, k) => {
    const f = fitPredictions(s.data, s.variant, r.h.id, r.testimonyFit);
    if (f) out.push({ row: r, fit: f, color: hypColor(r.h.id, k), align: alignToJet(f) });
  });
  return out;
}

function draw() {
  const s = api.getState();
  if (!s.data || !renderer) return;
  const v = variantPredictions(s.data, s.variant);
  const sel = api.currentHyp();
  const fits = v ? fitsFor(s) : [];
  const cur = fits.find((x) => x.row.h.id === sel?.h.id) ?? fits[0];
  const tag = root.querySelector("#ge-tag");
  if (!cur) {
    clear(groupPaths); clear(groupFan); clear(groupCur); fixedLine.visible = false;
    tag.textContent = "No fitted hypothesis with predictions for this case";
    legend.innerHTML = "";
    info.innerHTML = "";
    return;
  }
  const n = cur.fit.jet_e.length;
  const fps = s.data.meta.fps || 29.97;
  const t = Array.from({ length: n }, (_, k) => k / fps);
  // static geometry: rebuild when the case, variant, selection, weight (fit choice) or visibility changes
  const key = `${s.caseId}|${s.variant}|${cur.row.h.id}|${fits.map((x) => x.row.h.id + x.row.testimonyFit).join(",")}|${[...hidden].join(",")}`;
  if (key !== built) {
    built = key;
    clear(groupPaths); clear(groupFan);
    for (const x of fits) {
      const jet = [], obj = [];
      for (let i = 0; i < n; i++) {
        jet.push(toScene(x.align(x.fit.jet_e[i], x.fit.jet_n[i], x.fit.jet_u[i])));
        obj.push(toScene(x.align(x.fit.obj_e[i], x.fit.obj_n[i], x.fit.obj_u[i])));
      }
      const isCur = x === cur;
      if (isCur) groupPaths.add(lineOf(jet, 0xe8ecf0, 2));
      if (!hidden.has(x.row.h.id)) groupPaths.add(lineOf(obj, x.color, 2, isCur ? 1 : 0.75));
    }
    // line-of-sight fan for the selected hypothesis, every FAN_EVERY frames
    // the fan reaches past the farthest shown object (every model's object lies near the same sight lines)
    const pos = [];
    const reach = Math.max(...fits.filter((x) => x === cur || !hidden.has(x.row.h.id)).map((x) => Math.max(...x.fit.range_m))) * 1.05;
    for (let i = 0; i < n; i += FAN_EVERY) {
      const j = toScene(cur.align(cur.fit.jet_e[i], cur.fit.jet_n[i], cur.fit.jet_u[i]));
      const o = toScene(cur.align(...pointAtRange(cur.fit, i, reach)));
      pos.push(j.x, j.y, j.z, o.x, o.y, o.z);
    }
    const fan = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)),
      new THREE.LineBasicMaterial({ color: 0x63758a, transparent: true, opacity: 0.4 }));
    fan.frustumCulled = false;
    groupFan.add(fan);
    // frame the scene on the selected hypothesis's jet and object paths
    const bb = new THREE.Box3();
    for (let i = 0; i < n; i += 10) {
      bb.expandByPoint(toScene(cur.align(cur.fit.jet_e[i], cur.fit.jet_n[i], cur.fit.jet_u[i])));
      for (const x of fits) if (x === cur || !hidden.has(x.row.h.id)) bb.expandByPoint(toScene(x.align(x.fit.obj_e[i], x.fit.obj_n[i], x.fit.obj_u[i])));
    }
    // include the sea-level footprint so altitude reads against the grid
    bb.expandByPoint(new THREE.Vector3(bb.min.x, 0, bb.min.z));
    const c = bb.getCenter(new THREE.Vector3()), sz = Math.max(4, bb.getSize(new THREE.Vector3()).length());
    controls.target.copy(c);
    dotScale = sz / 90;
    const dist = (sz * 0.62) / Math.tan((camera.fov * Math.PI) / 360) / Math.min(1, camera.aspect);
    camera.position.set(c.x + dist * 0.18, c.y + dist * 0.72, c.z + dist * 0.67);
    controls.update();
    // the range slider spans the curves over range (or 1 to 45 nmi)
    const curve = curveFor(s);
    const rmax = Math.max(45, ...(curve?.map((p) => p.range_nmi) ?? []));
    slider.max = String(rmax);
    legend.innerHTML = fits.map((x) => `<li data-h="${esc(x.row.h.id)}" class="${hidden.has(x.row.h.id) ? "off" : ""}${x === cur ? " cur" : ""}" tabindex="0">
      <span class="sw" style="background:${x.color}"></span><b class="hid">${esc(x.row.h.id)}</b>
      <span class="note">${esc(nmi(x.fit.range_m.reduce((a, b) => a + b, 0) / n / NMI_M))} mean range</span></li>`).join("") +
      `<li class="static"><span class="sw" style="background:#e8ecf0"></span>Jet (selected fit)</li><li class="static"><span class="sw" style="background:#63758a"></span>Sight lines, every ${FAN_EVERY} frames</li><li class="static"><span class="sw" style="background:#f2b84b"></span>Fixed-range path</li>`;
  }
  // current frame: sight line, jet and object markers
  clear(groupCur);
  const i = s.frame;
  const j = toScene(cur.align(cur.fit.jet_e[i], cur.fit.jet_n[i], cur.fit.jet_u[i]));
  const r = s.range ?? Math.round((cur.fit.range_m[i] / NMI_M) * 2) / 2;
  if (+slider.value !== r) slider.value = String(r);
  out.textContent = nmi(r);
  const far = pointAtRange(cur.fit, i, Math.max(r, cur.fit.range_m[i] / NMI_M) * NMI_M * 1.08);
  groupCur.add(lineOf([j, toScene(cur.align(...far))], 0xf2b84b, 1, 0.9));
  const dot = (p, color, rad) => { const m = new THREE.Mesh(new THREE.SphereGeometry(rad * dotScale / 0.12, 14, 10), new THREE.MeshBasicMaterial({ color })); m.position.copy(p); groupCur.add(m); };
  dot(j, 0xe8ecf0, 0.12);
  for (const x of fits) {
    if (hidden.has(x.row.h.id)) continue;
    const o = toScene(x.align(x.fit.obj_e[i], x.fit.obj_n[i], x.fit.obj_u[i]));
    dot(o, x.color, x === cur ? 0.14 : 0.1);
    if (x === cur) groupCur.add(lineOf([o, new THREE.Vector3(o.x, 0, o.z)], 0x6b7886, 1, 0.8));
  }
  // fixed-range path along the selected fit's sight lines
  const fixed = [], fixedM = [];
  for (let k = 0; k < n; k++) { const q = pointAtRange(cur.fit, k, r * NMI_M); if (q) { fixedM.push(q); fixed.push(toScene(cur.align(...q))); } }
  fixedLine.geometry.dispose();
  fixedLine.geometry = new THREE.BufferGeometry().setFromPoints(fixed);
  fixedLine.computeLineDistances();
  fixedLine.visible = true;
  const pr = toScene(cur.align(...pointAtRange(cur.fit, i, r * NMI_M)));
  dot(pr, 0xf2b84b, 0.12);
  tag.textContent = `Selected: ${cur.row.h.id}. Aligned so the jet starts heading up the screen (the true heading is fitted). Altitude to scale; the grid is sea level, 5 nmi squares.`;

  // readout
  const kin = fixedM.length > 60 ? pathKinematics(t.slice(0, fixedM.length), fixedM, 31) : null;
  const rows = [["", `<b>Fixed-range path</b> <span class="note">${esc(cur.row.h.id)} sight lines</span>`], ["Altitude now", ft(pr.y * NMI_M / 0.3048)]];
  if (kin) rows.push(["Ground speed, mean", kt(kin.mean_ground_speed_kt)], ["Altitude span", `${ft(kin.alt_min_ft)} to ${ft(kin.alt_max_ft)}`], ["Peak acceleration", `${num(kin.max_accel_g, 1)} g (1 s smoothing)`]);
  const curve = curveFor(s);
  const at = curve ? interpCurve(curve, r) : null;
  root.querySelector("#ge-rsrc").textContent = s.data.rangeCurves ? "range_curves.json" : "range_curve.json";
  rows.push(["", `<b>Angles-only fit</b> <span class="note">constant velocity</span>`]);
  if (at) rows.push(["Air speed", kt(at.air_speed_kt)], ["Ground speed", kt(at.ground_speed_kt)], ["Altitude, mean", ft(at.altitude_ft_mean)],
    ["Vertical speed", fpm(at.vertical_speed_fpm)], ["Sight-line fit", `${num(at.line_of_sight_loglik, 1)} log-lik.`]);
  else rows.push(["", "outside the range grid"]);
  const perH = s.data.rangeCurves?.variants?.[s.variant ?? ""] ?? null;
  if (perH) for (const x of fits) {
    const c = perH[x.row.h.id];
    const p = c ? interpCurve(c, r) : null;
    if (p) rows.push([x.row.h.id, esc(`${kt(p.air_speed_kt)}, ${ft(p.altitude_ft_mean)}`)]);
  }
  info.innerHTML = rows.map(([k, val]) => k === "" ? `<dt class="sub" style="grid-column:1/-1">${val}</dt>` : `<dt>${esc(k)}</dt><dd>${val.startsWith("<") ? val : esc(val)}</dd>`).join("") +
    `<dt></dt><dd class="note" style="font-family:var(--font-ui)">The fixed-range path puts the object at this slant range on every frame of the selected fit's sight lines. The angles-only fit is the scorer's whole-clip constant-velocity probe at this range (testimony weight 0), linear between grid points.</dd>`;
}

function curveFor(s) {
  const v = api.currentVariant();
  return s.data.rangeCurve?.variants?.[v?.variant ?? ""] ?? null;
}

export function update(s, ch) {
  if (!renderer) return;
  if (["frame", "data", "variant", "hyp", "wT", "range", "overrides"].some((k) => ch.has(k))) draw();
}

export { ticks };
