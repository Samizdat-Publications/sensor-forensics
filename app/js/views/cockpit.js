// Cockpit view (shell): the original frame, keyed by frame index (no <video> seeking), beside a
// three.js panel. For now the panel re-draws the measured image cues (horizon bank and object
// blob from image_track.csv) in frame pixels; the geometric re-render replaces it in M4.3.

import * as THREE from "three";
import { frameURL, cue } from "../data.js";
import { num, deg } from "../units.js";
import { esc } from "../rail.js";

let api, img, renderer, scene, camera, horizon, blob, blobRing, tagEl, infoEl, box;
const W = 640, H = 480;
const preload = new Map();

export function mount(el, a) {
  api = a;
  el.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:14px;height:100%;min-height:460px">
    <div class="grid2" style="flex:1;height:auto;min-height:0">
      <div class="panel fill">
        <div class="panel-h"><h2>Original</h2><span class="src" id="ck-src"></span></div>
        <div class="panel-b"><div class="frame-box"><img id="ck-img" alt="Original video frame"></div></div>
      </div>
      <div class="panel fill">
        <div class="panel-h"><h2>Re-render</h2><span class="src">three.js</span></div>
        <div class="panel-b"><div class="frame-box" id="ck-gl"><span class="overlay-tag" id="ck-tag"></span></div></div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-b" style="display:flex;gap:28px;align-items:center;flex-wrap:wrap">
        <dl class="kv" id="ck-info" style="grid-template-columns:auto auto auto auto auto auto"></dl>
        <div class="pending" style="margin-left:auto;max-width:520px"><b>Coming in M4.3:</b> the re-render from the reconstructed geometry, frame-locked, with a difference overlay and a frame-lock error readout.</div>
      </div>
    </div>
    </div>`;
  img = el.querySelector("#ck-img");
  tagEl = el.querySelector("#ck-tag");
  infoEl = el.querySelector("#ck-info");
  box = el.querySelector("#ck-gl");

  renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(window.devicePixelRatio || 1);
  renderer.domElement.setAttribute("aria-label", "Image cues re-drawn in three.js");
  box.prepend(renderer.domElement);
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x05080b);
  camera = new THREE.OrthographicCamera(0, W, 0, -H, -10, 10); // frame pixels, y down
  const lineMat = new THREE.LineBasicMaterial({ color: 0x9aa6b2 });
  horizon = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-W, 0, 0), new THREE.Vector3(W, 0, 0)]), lineMat);
  scene.add(horizon);
  // frame border and reticle
  const border = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints([[0, 0], [W, 0], [W, -H], [0, -H]].map(([x, y]) => new THREE.Vector3(x, y, 0))), new THREE.LineBasicMaterial({ color: 0x2e3a47 }));
  scene.add(border);
  const ret = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints([
    [W / 2 - 24, -H / 2], [W / 2 - 8, -H / 2], [W / 2 + 8, -H / 2], [W / 2 + 24, -H / 2],
    [W / 2, -H / 2 + 24], [W / 2, -H / 2 + 8], [W / 2, -H / 2 - 8], [W / 2, -H / 2 - 24]].map(([x, y]) => new THREE.Vector3(x, y, 0))),
  new THREE.LineBasicMaterial({ color: 0x445466 }));
  scene.add(ret);
  blob = new THREE.Mesh(new THREE.CircleGeometry(1, 48), new THREE.MeshBasicMaterial({ color: 0xe8ecf0 }));
  scene.add(blob);
  blobRing = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(Array.from({ length: 64 }, (_, i) => new THREE.Vector3(Math.cos(i / 64 * Math.PI * 2), Math.sin(i / 64 * Math.PI * 2), 0))), new THREE.LineBasicMaterial({ color: 0xf2b84b }));
  scene.add(blobRing);
  new ResizeObserver(resize).observe(box);
  resize();
  update(api.getState(), new Set(["data", "frame"]));
}

function resize() {
  const r = box.getBoundingClientRect();
  const s = Math.min(r.width / W, r.height / H);
  renderer.setSize(Math.max(1, Math.floor(W * s)), Math.max(1, Math.floor(H * s)));
  draw();
}

function draw() {
  const s = api.getState();
  if (!s.data || !renderer) return;
  const d = s.data, i = s.frame;
  const bank = cue(d, "bank_deg", i);
  horizon.visible = Number.isFinite(bank);
  if (horizon.visible) { horizon.position.set(W / 2, -H / 2, 0); horizon.rotation.z = (bank * Math.PI) / 180; }
  const found = cue(d, "obj_found", i);
  const cx = cue(d, "obj_hi_cx", i), cy = cue(d, "obj_hi_cy", i);
  const ma = cue(d, "obj_hi_major_px", i), mi = cue(d, "obj_hi_minor_px", i), an = cue(d, "obj_hi_angle_deg", i);
  const ok = found && Number.isFinite(cx) && Number.isFinite(ma);
  blob.visible = blobRing.visible = !!ok;
  if (ok) {
    for (const m of [blob, blobRing]) {
      m.position.set(cx, -cy, 1);
      m.rotation.z = (an * Math.PI) / 180; // image_cues.py: CCW from +x, y up
    }
    blob.scale.set(Math.max(1, ma / 2), Math.max(1, (mi || ma) / 2), 1);
    blobRing.scale.set(Math.max(4, ma / 2) + 6, Math.max(4, (mi || ma) / 2) + 6, 1);
  }
  renderer.render(scene, camera);
  tagEl.textContent = "Measured cues only: artificial-horizon bank and object blob";
  infoEl.innerHTML = [
    ["Artificial-horizon bank", deg(bank)],
    ["Object", ok ? `${num(cx, 1)}, ${num(cy, 1)} px` : "not found"],
    ["Blob", ok ? `${num(ma, 1)} x ${num(mi, 1)} px at ${deg(an, 0)}` : "n/a"],
  ].map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("");
}

function showFrame(s) {
  const url = frameURL(s.data.meta, s.frame);
  img.src = url;
  img.alt = `${s.data.meta.label} original frame ${s.frame}`;
  // read ahead while playing so frames are decoded before they are needed
  if (s.playing) for (let k = 1; k <= 12; k++) {
    const j = s.frame + k;
    if (j >= s.data.meta.n_frames || preload.has(j + s.caseId)) continue;
    const p = new Image(); p.src = frameURL(s.data.meta, j); preload.set(j + s.caseId, p);
    if (preload.size > 300) preload.delete(preload.keys().next().value);
  }
}

export function update(s, ch) {
  if (!img || !s.data) return;
  if (ch.has("data")) document.getElementById("ck-src").textContent = `${s.data.meta.source_video.split("/").pop()}  frame ${s.frame}`;
  if (ch.has("frame") || ch.has("data")) {
    showFrame(s);
    document.getElementById("ck-src").textContent = `${s.data.meta.source_video.split("/").pop()}  frame ${s.frame}`;
    draw();
  }
}
