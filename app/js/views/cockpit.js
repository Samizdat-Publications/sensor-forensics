// Cockpit view (M4.3): the original frame (image sequence keyed by frame index, never <video> seeking) beside a
// three.js re-render of the reconstructed geometry for the selected hypothesis. Both panels are cropped to the
// active picture. The re-render's camera sits at the jet, looks along the hypothesis's predicted line of sight
// with the frame's field of view and is rolled to the predicted image horizon (geom.js, the same camera model
// as tools/app_predictions.py). The object is drawn at its 3D position with its predicted size and rotation.
// Modes: Re-render, Difference (measured features solid grey, predicted dashed white, over the dimmed original),
// Blink. A strip reports the frame-lock error (median pixel error of horizon and object position).

import * as THREE from "three";
import { frameURL, cue, reading, variantPredictions, fitPredictions } from "../data.js";
import { num, deg, nmi, ft, hypColor } from "../units.js";
import { esc } from "../rail.js";
import { cameraBasis, framePose, focal, fovAt, frameLock, frameErrors, sub, norm, median, wrap90 } from "../geom.js";

let api, root, renderer, scene, camera, objMesh, levelLines, boxGL, svgR, svgL, imgL, imgR, tagEl, stripEl, infoEl;
let mode = "render", blinkTimer = 0, blinkOn = false;
const preload = new Map();
const lockCache = new Map();

const pic = () => api.getState().data?.predictions?.picture ?? null;

export function mount(el, a) {
  api = a;
  root = el;
  el.innerHTML = `
    <div class="ck">
      <div class="panel ck-strip" id="ck-strip" aria-live="off"></div>
      <div class="ck-panels">
        <div class="panel fill">
          <div class="panel-h"><h2>Original</h2><span class="src" id="ck-src"></span></div>
          <div class="panel-b"><div class="pic-box" id="ck-box-l"><div class="pic" id="ck-pic-l"><img id="ck-img" alt="Original video frame"><svg class="ovl" id="ck-svg-l" aria-hidden="true"></svg></div></div></div>
        </div>
        <div class="panel fill">
          <div class="panel-h"><h2>Re-render</h2>
            <div class="seg" role="group" aria-label="Re-render mode" id="ck-mode">
              <button data-m="render" aria-pressed="true">Re-render</button><button data-m="diff" aria-pressed="false">Difference</button><button data-m="blink" aria-pressed="false">Blink</button>
            </div><span class="src" id="ck-hsrc"></span></div>
          <div class="panel-b"><div class="pic-box" id="ck-box-r"><div class="pic" id="ck-pic-r">
            <img id="ck-img-r" alt="" aria-hidden="true"><div id="ck-gl" class="gl"></div><svg class="ovl" id="ck-svg-r" aria-hidden="true"></svg>
            <span class="overlay-tag" id="ck-tag"></span></div></div></div>
        </div>
      </div>
      <div class="panel"><div class="panel-b"><dl class="kv kv-row" id="ck-info"></dl></div></div>
    </div>`;
  imgL = el.querySelector("#ck-img");
  imgR = el.querySelector("#ck-img-r");
  svgL = el.querySelector("#ck-svg-l");
  svgR = el.querySelector("#ck-svg-r");
  tagEl = el.querySelector("#ck-tag");
  stripEl = el.querySelector("#ck-strip");
  infoEl = el.querySelector("#ck-info");
  boxGL = el.querySelector("#ck-gl");
  for (const b of el.querySelectorAll("#ck-mode button")) b.addEventListener("click", () => api.set({ cmode: b.dataset.m }));

  renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  renderer.domElement.setAttribute("aria-label", "Synthetic re-render from the reconstructed geometry");
  boxGL.append(renderer.domElement);
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera();
  camera.matrixAutoUpdate = false;
  objMesh = new THREE.Mesh(new THREE.CircleGeometry(1, 48), new THREE.MeshBasicMaterial({ color: 0xffffff }));
  objMesh.matrixAutoUpdate = false;
  scene.add(objMesh);
  levelLines = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: 0x8b96a3, transparent: true, opacity: 0.55 }));
  levelLines.frustumCulled = false;
  scene.add(levelLines);
  new ResizeObserver(layout).observe(el.querySelector("#ck-box-r"));
  new ResizeObserver(layout).observe(el.querySelector("#ck-box-l"));
  layout();
  setMode(api.getState().cmode || "render");
  update(api.getState(), new Set(["data", "frame"]));
}

function setMode(m) {
  mode = m;
  for (const b of root.querySelectorAll("#ck-mode button")) b.setAttribute("aria-pressed", String(b.dataset.m === m));
  clearInterval(blinkTimer);
  blinkOn = false;
  if (m === "blink") blinkTimer = setInterval(() => { blinkOn = !blinkOn; draw(); }, 600);
  draw();
}

// Size the two picture boxes to the active picture's aspect, and crop the frame image to it.
function layout() {
  const p = pic();
  const s = api.getState();
  if (!p || !s.data) return;
  const W = p.width_px, H = p.frame_h;
  for (const id of ["l", "r"]) {
    const box = root.querySelector(`#ck-box-${id}`).getBoundingClientRect();
    const k = Math.max(0.1, Math.min(box.width / W, box.height / H));
    const el = root.querySelector(`#ck-pic-${id}`);
    el.style.width = `${Math.floor(W * k)}px`;
    el.style.height = `${Math.floor(H * k)}px`;
    for (const img of el.querySelectorAll("img")) {
      img.style.width = `${(p.frame_w / W) * 100}%`;
      img.style.left = `${(-(p.cx - W / 2 + 0.5) / W) * 100}%`;
    }
    el.querySelector("svg").setAttribute("viewBox", `${p.cx - W / 2 + 0.5} 0 ${W} ${H}`);
  }
  const r = root.querySelector("#ck-pic-r").getBoundingClientRect();
  renderer.setSize(Math.max(1, Math.round(r.width)), Math.max(1, Math.round(r.height)));
  draw();
}

function polarityAt(s) {
  const v = reading(s.data, "polarity", s.frame)?.value;
  return v === "BLK" ? "BLK" : "WHT";
}

function measuredAspect(d) {
  const ma = d.cues?.columns?.obj_hi_major_px, mi = d.cues?.columns?.obj_hi_minor_px;
  if (!ma || !mi) return 0.6;
  const r = ma.map((x, i) => (Number.isFinite(x) && x > 0 && Number.isFinite(mi[i]) ? mi[i] / x : NaN));
  return median(r) ?? 0.6;
}

function lockFor(s, v, fit, key) {
  if (!lockCache.has(key)) lockCache.set(key, frameLock(fit, v, s.data.predictions.picture, s.data.predictions.measured));
  return lockCache.get(key);
}

// Place the camera: world origin at the jet of this frame (ENU), basis from geom.cameraBasis, off-axis
// projection covering exactly the cropped picture (edge coordinates X0..X1, 0..H).
function placeCamera(p, b, fovDeg, aspect) {
  const { fx, fy } = focal(p, fovDeg, aspect);
  const near = 1, far = 1e9;
  const X0 = p.cx - p.width_px / 2 + 0.5, X1 = X0 + p.width_px, H = p.frame_h;
  const left = ((X0 - 0.5 - p.cx) / fx) * near, right = ((X1 - 0.5 - p.cx) / fx) * near;
  const top = ((p.cy + 0.5) / fy) * near, bottom = ((p.cy - (H - 0.5)) / fy) * near;
  camera.projectionMatrix.makePerspective(left, right, top, bottom, near, far);
  camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
  const m = new THREE.Matrix4().makeBasis(new THREE.Vector3(...b.r), new THREE.Vector3(...b.u), new THREE.Vector3(-b.f[0], -b.f[1], -b.f[2]));
  camera.matrixWorld.copy(m);
  camera.matrixWorldInverse.copy(m).invert();
  return { fx, fy };
}

function niceStep(x) {
  const p = Math.pow(10, Math.floor(Math.log10(x)));
  return [1, 2, 5, 10].map((k) => k * p).find((k) => k >= x);
}

function draw() {
  const s = api.getState();
  if (!s.data || !renderer) return;
  const d = s.data, i = s.frame, p = pic();
  const v = variantPredictions(d, s.variant);
  const row = api.currentHyp();
  const fit = row ? fitPredictions(d, s.variant, row.h.id, row.testimonyFit) : null;
  const pol = polarityAt(s);
  const bg = pol === "BLK" ? 0x80868c : 0x15191d, fg = pol === "BLK" ? 0x0b0d10 : 0xf4f6f8;
  scene.background = new THREE.Color(bg);
  objMesh.material.color.setHex(fg);
  levelLines.material.color.setHex(pol === "BLK" ? 0x3a4148 : 0x8b96a3);
  const meas = d.predictions?.measured;
  root.querySelector("#ck-hsrc").textContent = row ? `${row.h.id}, ${row.testimonyFit === "physics_only" ? "physics-only" : "testimony-weighted"} fit` : "";

  let pose = fit ? framePose(fit, i) : null;
  let tag = "";
  const svgParts = [];
  const X0 = p ? p.cx - p.width_px / 2 + 0.5 : 0;
  if (p && v && pose) {
    const fov = (fovAt(v, i) || v.fov_deg);
    const rel = sub(pose.obj, pose.jet);
    const b = cameraBasis(rel, pose.theta);
    const { fx } = placeCamera(p, b, fov, v.pixel_aspect_x);
    const range = norm(rel);
    // object: a disc in the image plane at the object's position, predicted size and rotation
    const sizeRef = Number.isFinite(fit.size_px[i]) ? fit.size_px[i] : median(fit.size_px) ?? 6;
    const sizeFrame = sizeRef * (v.fov_deg / fov);
    const rotDeg = fit.rotation_deg[i];
    const asp = Number.isFinite(rotDeg) ? measuredAspect(d) : 1;
    const major = (Math.max(2, sizeFrame) * range) / fx / 2;
    const rot = new THREE.Matrix4().makeBasis(new THREE.Vector3(...b.r), new THREE.Vector3(...b.u), new THREE.Vector3(-b.f[0], -b.f[1], -b.f[2]));
    const m = new THREE.Matrix4().makeTranslation(...rel).multiply(rot)
      .multiply(new THREE.Matrix4().makeRotationZ(((Number.isFinite(rotDeg) ? rotDeg : 0) * Math.PI) / 180))
      .multiply(new THREE.Matrix4().makeScale(major, major * asp, 1));
    objMesh.matrix.copy(m);
    objMesh.matrixWorld.copy(m);
    objMesh.visible = true;
    // level lines: horizontal lines through the object and at fixed height steps, at the object's range
    const hFt = ((p.frame_h * v.pixel_aspect_x) / fx) * range / 0.3048;
    const step = niceStep(hFt / 7);
    const L = range * 0.05;
    const pts = [];
    for (let k = -8; k <= 8; k++) {
      const z = k * step * 0.3048;
      pts.push(rel[0] - L * b.r0[0], rel[1] - L * b.r0[1], rel[2] + z, rel[0] + L * b.r0[0], rel[1] + L * b.r0[1], rel[2] + z);
    }
    levelLines.geometry.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
    levelLines.visible = true;
    tag = `Level lines ${num(step)} ft apart at the object's range; ${pol === "BLK" ? "black hot" : "white hot"} as on screen`;
  } else {
    objMesh.visible = false;
    levelLines.visible = false;
    tag = fit ? "No prediction at this frame" : "No fitted hypothesis for this case";
  }
  renderer.render(scene, camera);

  // overlays (frame px, pixel centres at integers; the svg viewBox is in edge coordinates)
  const E = (x) => x + 0.5;
  const reticle = (cls) => p ? `<g class="${cls}"><circle cx="${E(p.cx)}" cy="${E(p.cy)}" r="7"/><line x1="${E(p.cx) - 20}" x2="${E(p.cx) - 10}" y1="${E(p.cy)}" y2="${E(p.cy)}"/><line x1="${E(p.cx) + 10}" x2="${E(p.cx) + 20}" y1="${E(p.cy)}" y2="${E(p.cy)}"/></g>` : "";
  const hline = (x, y, th, cls) => {
    const L = p.width_px, t = (th * Math.PI) / 180;
    return `<line class="${cls}" x1="${E(x - L * Math.cos(t))}" y1="${E(y + L * Math.sin(t))}" x2="${E(x + L * Math.cos(t))}" y2="${E(y - L * Math.sin(t))}"/>`;
  };
  const ell = (x, y, a, b2, th, cls) => `<ellipse class="${cls}" cx="${E(x)}" cy="${E(y)}" rx="${Math.max(1.5, a / 2)}" ry="${Math.max(1.5, b2 / 2)}" transform="rotate(${-th} ${E(x)} ${E(y)})"/>`;
  const mx = meas?.obj_cx?.[i], my = meas?.obj_cy?.[i], mth = meas?.horizon_deg?.[i];
  const err = fit && v && p ? frameErrors(fit, v, p, meas, i) : null;
  if (p && mode === "diff") {
    if (Number.isFinite(mth)) svgParts.push(hline(Number.isFinite(mx) ? mx : p.cx, Number.isFinite(my) ? my : p.cy, mth, "meas"));
    if (Number.isFinite(mx)) svgParts.push(ell(mx, my, cue(d, "obj_hi_major_px", i) || 4, cue(d, "obj_hi_minor_px", i) || 4, cue(d, "obj_hi_angle_deg", i) || 0, "meas"));
    if (err?.pred) {
      svgParts.push(hline(err.pred.x, err.pred.y, fit.horizon_deg[i], "pred"));
      const sz = (Number.isFinite(fit.size_px[i]) ? fit.size_px[i] : median(fit.size_px) ?? 6) * (v.fov_deg / (fovAt(v, i) || v.fov_deg));
      const asp = Number.isFinite(fit.rotation_deg[i]) ? measuredAspect(d) : 1;
      svgParts.push(ell(err.pred.x, err.pred.y, sz, sz * asp, Number.isFinite(fit.rotation_deg[i]) ? fit.rotation_deg[i] : 0, "pred"));
    }
    svgParts.push(`<g class="legend-svg"><rect x="${X0 + 8}" y="${p.frame_h - 34}" width="196" height="26" rx="2"/><line class="meas" x1="${X0 + 16}" x2="${X0 + 34}" y1="${p.frame_h - 21}" y2="${p.frame_h - 21}"/><text x="${X0 + 38}" y="${p.frame_h - 17}">measured</text><line class="pred" x1="${X0 + 102}" x2="${X0 + 120}" y1="${p.frame_h - 21}" y2="${p.frame_h - 21}"/><text x="${X0 + 124}" y="${p.frame_h - 17}">predicted</text></g>`);
  }
  svgR.innerHTML = reticle("ret") + svgParts.join("");
  svgL.innerHTML = "";
  const showImgR = mode === "diff" || (mode === "blink" && blinkOn);
  imgR.style.opacity = mode === "diff" ? "0.5" : showImgR ? "1" : "0";
  boxGL.style.opacity = mode === "blink" && blinkOn ? "0" : mode === "diff" ? "0" : "1";
  tagEl.textContent = mode === "diff" ? "Difference: measured solid grey, predicted dashed white, over the dimmed original" :
    mode === "blink" ? (blinkOn ? "Blink: original" : "Blink: re-render") : tag;

  // strip: frame-lock error
  if (fit && v && p) {
    const key = `${s.caseId}|${s.variant}|${row.h.id}|${row.testimonyFit}`;
    const lk = lockFor(s, v, fit, key);
    const hsrc = meas?.horizon_source ? "measured from the cloud-deck motion direction" : "no horizon reference in this footage";
    stripEl.innerHTML = `<span class="lbl">Frame lock</span>
      <span><span class="sw" style="background:${hypColor(row.h.id)}"></span><b class="hid">${esc(row.h.id)}</b> <span class="note">${esc(row.h.label)}</span></span>
      <span class="metric"><span class="note">Horizon, median</span> <b class="num">${lk.horizon_px_median == null ? "n/a" : num(lk.horizon_px_median, 1) + " px"}</b> <span class="note">${lk.horizon_n ? `${num(lk.horizon_n)} frames, ${hsrc}` : hsrc}</span></span>
      <span class="metric"><span class="note">Object position, median</span> <b class="num">${lk.object_px_median == null ? "n/a" : num(lk.object_px_median, 1) + " px"}</b> <span class="note">${num(lk.object_n)} frames</span></span>
      <span class="metric"><span class="note">This frame: horizon</span> <b class="num">${err?.horizon_px == null ? "n/a" : num(err.horizon_px, 1) + " px"}</b><span class="note">, object</span> <b class="num">${err?.object_px == null ? "n/a" : num(err.object_px, 1) + " px"}</b></span>`;
  } else {
    stripEl.innerHTML = `<span class="lbl">Frame lock</span><span class="note">No fitted hypothesis with predictions for ${esc(d.meta.label)}; the re-render needs a scored case.</span>`;
  }

  // info row
  const rows = [];
  if (fit && pose) {
    const rel = sub(pose.obj, pose.jet);
    rows.push(["Range", nmi(norm(rel) / 1852)], ["Object altitude", ft(pose.obj[2] / 0.3048)],
      ["Sight line (predicted)", `${num(Math.abs(fit.az_deg[i]), 2)}° ${fit.az_deg[i] < 0 ? "left" : "right"}, ${num(Math.abs(fit.el_deg[i]), 2)}° ${fit.el_deg[i] < 0 ? "below" : "above"} level`],
      ["Horizon", `${deg(fit.horizon_deg[i], 1)} predicted, ${Number.isFinite(mth) ? deg(mth, 1) + " measured" : "not measured"}`],
      ["Rotation", Number.isFinite(fit.rotation_deg[i]) ? `${deg(fit.rotation_deg[i], 1)} predicted, ${deg(wrap90(cue(d, "obj_hi_angle_deg", i) ?? NaN), 1)} measured (${fit.rotation_kind === "glare" ? "glare in the optics" : "own rotation, smooth"})` : "not scored for this case"],
      ["Size", `${num((Number.isFinite(fit.size_px[i]) ? fit.size_px[i] : NaN) * (v.fov_deg / (fovAt(v, i) || v.fov_deg)), 1)} px predicted, ${num(cue(d, "obj_lo_major_px", i), 1)} px measured`]);
  } else if (v) {
    rows.push(["Horizon from readouts", deg(v.readout_horizon_deg[i], 1)], ["Measured object", Number.isFinite(mx) ? `${num(mx, 1)}, ${num(my, 1)} px` : "not found"]);
  }
  infoEl.innerHTML = rows.map(([k, x]) => `<div><dt>${esc(k)}</dt><dd>${esc(x)}</dd></div>`).join("");
}

function showFrame(s) {
  const url = frameURL(s.data.meta, s.frame);
  imgL.src = url;
  imgR.src = url;
  imgL.alt = `${s.data.meta.label} original frame ${s.frame}`;
  if (s.playing) for (let k = 1; k <= 12; k++) {
    const j = s.frame + k;
    if (j >= s.data.meta.n_frames || preload.has(j + s.caseId)) continue;
    const im = new Image(); im.src = frameURL(s.data.meta, j); preload.set(j + s.caseId, im);
    if (preload.size > 300) preload.delete(preload.keys().next().value);
  }
}

export function update(s, ch) {
  if (!imgL || !s.data) return;
  if (ch.has("cmode") && s.cmode !== mode) setMode(s.cmode);
  if (ch.has("data")) layout();
  if (ch.has("frame") || ch.has("data")) {
    showFrame(s);
    root.querySelector("#ck-src").textContent = `${s.data.meta.source_video.split("/").pop()}, frame ${s.frame}`;
  }
  if (ch.has("frame") || ch.has("data") || ch.has("variant") || ch.has("hyp") || ch.has("wT") || ch.has("overrides")) draw();
}

// For the screenshot tool and the CP-05 report: frame-lock numbers of every fit the app can show.
export function frameLockTable(s) {
  const out = [];
  const pv = s.data?.predictions;
  if (!pv) return out;
  for (const [vn, v] of Object.entries(pv.variants)) for (const [h, fits] of Object.entries(v.hypotheses))
    for (const [fn, f] of Object.entries(fits)) if (f.valid !== false) out.push({ variant: vn, hypothesis: h, fit: fn, ...frameLock(f, v, pv.picture, pv.measured) });
  return out;
}
