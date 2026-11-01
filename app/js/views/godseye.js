// God's-eye view (shell): a three.js scene with orbit controls. Shows the jet at the origin and
// the line of sight at the current frame from the on-screen azimuth and elevation (relative to
// the jet's nose; the jet path and hypothesis paths arrive in M4.4). The range slider places a
// point on the sight line and reads the angles-only fit at that range from the Python range grid.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { reading } from "../data.js";
import { num, kt, ft, fpm, nmi, signed } from "../units.js";
import { esc } from "../rail.js";
import { interpCurve } from "./range.js";

let api, renderer, scene, camera, controls, losLine, pt, box, info, slider, out;
const NMI = 1; // scene unit: 1 nautical mile

export function parseAz(v) {
  const m = /^(\d+(?:\.\d+)?)([LR])$/.exec(v || "");
  return m ? (m[2] === "L" ? -1 : 1) * +m[1] : null;
}

export function mount(el, a) {
  api = a;
  el.innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 340px;gap:14px;height:100%;min-height:420px">
      <div class="panel fill">
        <div class="panel-h"><h2>Scene</h2><span class="src">drag to orbit, wheel to zoom</span></div>
        <div class="panel-b"><div class="frame-box" id="ge-gl" style="background:var(--ink-0)"><span class="overlay-tag">Grid squares are 5 nmi. North is up only if the jet's nose is; the heading is not on screen.</span></div></div>
      </div>
      <div class="stack">
        <div class="panel">
          <div class="panel-h"><h2>Assumed range</h2><span class="src">range_curve.json</span></div>
          <div class="panel-b">
            <div class="range-ctl"><label for="ge-r">Range</label><input id="ge-r" type="range" min="1" max="60" step="0.5" value="10"><output id="ge-out"></output></div>
            <dl class="kv" id="ge-info" style="margin-top:12px"></dl>
          </div>
        </div>
        <div class="pending"><b>Coming in M4.4:</b> the reconstructed jet path, the line-of-sight fan over the whole clip, and each hypothesis's object path.</div>
      </div>
    </div>`;
  box = el.querySelector("#ge-gl");
  info = el.querySelector("#ge-info");
  slider = el.querySelector("#ge-r");
  out = el.querySelector("#ge-out");
  slider.addEventListener("input", () => draw());

  renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  box.prepend(renderer.domElement);
  renderer.domElement.classList.add("full");
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x10151b);
  camera = new THREE.PerspectiveCamera(45, 1, 0.1, 2000);
  camera.position.set(-30, 26, 38);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0, -8);
  controls.enableDamping = true;
  const grid = new THREE.GridHelper(120 * NMI, 24, 0x445466, 0x26313c);
  scene.add(grid);
  // jet: a small arrow pointing along -z (the nose)
  const jet = new THREE.Mesh(new THREE.ConeGeometry(0.5, 1.8, 3), new THREE.MeshBasicMaterial({ color: 0xe8ecf0 }));
  jet.rotation.x = -Math.PI / 2;
  scene.add(jet);
  losLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(0, 0, -60)]), new THREE.LineBasicMaterial({ color: 0x63b6d9 }));
  scene.add(losLine);
  pt = new THREE.Mesh(new THREE.SphereGeometry(0.45, 16, 12), new THREE.MeshBasicMaterial({ color: 0xf2b84b }));
  scene.add(pt);
  const drop = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]), new THREE.LineDashedMaterial({ color: 0x75828f, dashSize: 0.6, gapSize: 0.5 }));
  drop.name = "drop";
  scene.add(drop);
  new ResizeObserver(resize).observe(box);
  resize();
  const loop = () => { controls.update(); renderer.render(scene, camera); requestAnimationFrame(loop); };
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

function draw() {
  const s = api.getState();
  if (!s.data || !renderer) return;
  const az = parseAz(reading(s.data, "azimuth", s.frame)?.value);
  const el = +reading(s.data, "elevation", s.frame)?.value;
  const r = +slider.value;
  out.textContent = nmi(r);
  const ok = Number.isFinite(az) && Number.isFinite(el);
  losLine.visible = pt.visible = ok;
  const drop = scene.getObjectByName("drop");
  drop.visible = ok;
  let rows = [["Line of sight", "no azimuth or elevation readout"]];
  if (ok) {
    const a = (az * Math.PI) / 180, e = (el * Math.PI) / 180;
    const dir = new THREE.Vector3(Math.sin(a) * Math.cos(e), Math.sin(e), -Math.cos(a) * Math.cos(e));
    losLine.geometry.setFromPoints([new THREE.Vector3(), dir.clone().multiplyScalar(60 * NMI)]);
    const p = dir.clone().multiplyScalar(r * NMI);
    pt.position.copy(p);
    drop.geometry.setFromPoints([p, new THREE.Vector3(p.x, 0, p.z)]);
    drop.computeLineDistances();
    rows = [["Line of sight", `${signed(az, 0)}° az, ${signed(el, 0)}° el (frame ${s.frame})`],
      ["Height vs jet", ft(r * 6076.12 * Math.sin(e))]];
  }
  const v = api.currentVariant();
  const curve = s.data.rangeCurve?.variants?.[v?.variant ?? ""] ?? null;
  const at = curve ? interpCurve(curve, r) : null;
  if (at) rows.push(
    ["Air speed", kt(at.air_speed_kt)], ["Ground speed", kt(at.ground_speed_kt)],
    ["Altitude", ft(at.altitude_ft_mean)], ["Vertical speed", fpm(at.vertical_speed_fpm)],
    ["Sight-line fit", `${num(at.line_of_sight_loglik, 1)} log-likelihood`],
  );
  else rows.push(["Range grid", "not available for this case yet"]);
  info.innerHTML = rows.map(([k, val]) => `<dt>${k}</dt><dd>${esc(val)}</dd>`).join("") +
    (at ? `<dt></dt><dd class="note" style="font-family:var(--font-ui)">Whole-clip angles-only fit with range held at this value; linear between grid points.</dd>` : "");
}

export function update(s, ch) {
  if (!renderer) return;
  if (ch.has("frame") || ch.has("data") || ch.has("variant")) draw();
}
