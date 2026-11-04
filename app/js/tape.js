// The evidence tape: transport controls and a frame scrubber whose tracks show, per frame,
// how well each on-screen readout was read and whether the object was found. One shared
// timeline for every view.

import { timecode, LOW_CONF, FIELDS } from "./units.js";

const ICON = {
  first: '<svg viewBox="0 0 16 16"><path d="M3 2h2v12H3zM14 2v12L6 8z"/></svg>',
  back: '<svg viewBox="0 0 16 16"><path d="M10 2v12L2 8zM14 2v12h-2V2z"/></svg>',
  play: '<svg viewBox="0 0 16 16"><path d="M4 2l10 6-10 6z"/></svg>',
  pause: '<svg viewBox="0 0 16 16"><path d="M3 2h4v12H3zM9 2h4v12H9z"/></svg>',
  fwd: '<svg viewBox="0 0 16 16"><path d="M6 2v12l8-6zM2 2v12h2V2z"/></svg>',
};

function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

export function createTape(root, api) {
  root.innerHTML = `
    <div class="transport">
      <div class="fr"><span id="fr-n">0</span> <small>/ <span id="fr-max">0</span></small></div>
      <div class="tc"><span id="fr-t">00:00.00</span> <span class="u2" id="fr-fps"></span></div>
      <div class="btns">
        <button id="t-first" aria-label="First frame (Home)" title="First frame (Home)">${ICON.first}</button>
        <button id="t-back" aria-label="Back one frame (Left arrow; Shift for 10)" title="Back one frame (Left; Shift for 10)">${ICON.back}</button>
        <button id="t-play" aria-label="Play (Space)" title="Play or pause (Space)">${ICON.play}</button>
        <button id="t-fwd" aria-label="Forward one frame (Right arrow; Shift for 10)" title="Forward one frame (Right; Shift for 10)">${ICON.fwd}</button>
      </div>
      <div class="spd"><span class="u2">Speed</span><div class="seg speed" role="group" aria-label="Playback speed" id="t-speed">${[0.25, 0.5, 1, 2].map((x) => `<button data-x="${x}" aria-pressed="${x === 1}" title="Play at ${x} times real time">${x === 0.25 ? "¼" : x === 0.5 ? "½" : x}×</button>`).join("")}</div><span class="buf" id="t-buf" hidden>Buffering</span></div>
    </div>
    <div class="tracks" id="tracks" tabindex="0" role="slider" aria-label="Frame" aria-valuemin="0">
      <div class="playhead" id="playhead"></div>
    </div>`;
  const tracks = root.querySelector("#tracks");
  const head = root.querySelector("#playhead");
  const s0 = () => api.getState();
  root.querySelector("#t-first").onclick = () => api.set({ frame: 0, playing: false });
  root.querySelector("#t-back").onclick = (e) => api.set({ frame: Math.max(0, s0().frame - (e.shiftKey ? 10 : 1)), playing: false });
  root.querySelector("#t-fwd").onclick = (e) => api.set({ frame: Math.min(s0().data.meta.n_frames - 1, s0().frame + (e.shiftKey ? 10 : 1)), playing: false });
  root.querySelector("#t-play").onclick = () => api.set({ playing: !s0().playing });
  for (const sb of root.querySelectorAll("#t-speed button")) sb.onclick = () => api.set({ speed: +sb.dataset.x }, { route: false });

  let lanes = [];
  const geom = () => {
    const first = tracks.querySelector(".track canvas");
    const r = (first || tracks).getBoundingClientRect();
    return { x0: r.left, w: r.width };
  };
  const seek = (clientX) => {
    const { x0, w } = geom();
    const n = s0().data.meta.n_frames;
    const f = Math.round(((clientX - x0) / w) * (n - 1));
    api.set({ frame: Math.max(0, Math.min(n - 1, f)), playing: false });
  };
  let drag = false;
  tracks.addEventListener("pointerdown", (e) => { drag = true; tracks.setPointerCapture(e.pointerId); seek(e.clientX); });
  tracks.addEventListener("pointermove", (e) => { if (drag) seek(e.clientX); });
  tracks.addEventListener("pointerup", () => { drag = false; });

  function buildLanes() {
    for (const l of lanes) l.el.remove();
    lanes = [];
    const s = s0();
    const d = s.data;
    const add = (label, draw, cls = "", title = "") => {
      const el = document.createElement("div");
      el.className = `track ${cls}`;
      el.innerHTML = `<span class="tl">${label}</span><canvas></canvas>`;
      if (title) el.title = title;
      tracks.insertBefore(el, head);
      lanes.push({ el, draw });
    };
    add("", drawRuler, "ruler");
    add("Scored", drawWindow, "", "Frames the scoring used; ticks mark the measured image-rotation steps");
    const fields = ["azimuth", "elevation", "range", "airspeed", "altitude"].filter((f) => d.readings?.fields?.[f]?.value.some((v) => v != null));
    for (const f of fields.slice(0, 4)) add(FIELDS[f].label.replace("Indicated air speed", "Air speed"), (c, w, h) => drawConf(c, w, h, f), "", `Read confidence of the ${FIELDS[f].label.toLowerCase()} readout; red ticks are below ${LOW_CONF}`);
    if (d.cues) add("Object", drawObject, "", "Object found in the frame (brightness = signal to noise)");
    redraw();
  }

  function canvasFor(l) {
    const c = l.el.querySelector("canvas");
    const dpr = window.devicePixelRatio || 1;
    const w = c.clientWidth, h = c.clientHeight;
    if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) { c.width = Math.round(w * dpr); c.height = Math.round(h * dpr); }
    const ctx = c.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    return [ctx, w, h];
  }
  function redraw() { for (const l of lanes) { const [ctx, w, h] = canvasFor(l); l.draw(ctx, w, h); } placeHead(); }

  const N = () => s0().data.meta.n_frames;
  const X = (i, w) => (i / Math.max(1, N() - 1)) * w;

  function drawRuler(ctx, w, h) {
    const d = s0().data;
    const fps = d.meta.fps || 29.97;
    const secs = (N() - 1) / fps;
    const stepS = secs > 60 ? 10 : 5;
    ctx.fillStyle = css("--text-3"); ctx.strokeStyle = css("--rule-strong");
    ctx.font = `11px ${css("--font-num")}`; ctx.textBaseline = "top";
    for (let t = 0; t <= secs + 1e-6; t += 1) {
      const x = Math.round((t * fps / (N() - 1)) * w) + 0.5;
      const major = t % stepS === 0;
      ctx.beginPath(); ctx.moveTo(x, h); ctx.lineTo(x, major ? h - 7 : h - 3); ctx.stroke();
      if (major && x < w - 30) ctx.fillText(`${t}s`, x + 3, 0);
    }
  }
  function drawWindow(ctx, w, h) {
    const s = s0();
    const v = s.data.results?.variants.find((x) => x.variant === s.variant) || s.data.results?.variants[0];
    ctx.fillStyle = css("--ink-2"); ctx.fillRect(0, 2, w, h - 4);
    if (v?.window_frames) {
      const [a, b] = v.window_frames;
      ctx.fillStyle = css("--rule-strong"); ctx.fillRect(X(a, w), 2, Math.max(1, X(b, w) - X(a, w)), h - 4);
      if (Number.isFinite(v.reference_frame)) { ctx.fillStyle = css("--text-2"); ctx.fillRect(Math.round(X(v.reference_frame, w)), 0, 1, h); }
    }
    ctx.fillStyle = css("--text");
    for (const f of s.data.meta.markers?.rotation_steps ?? []) ctx.fillRect(Math.round(X(f, w)) - 1, 0, 2, h);
  }
  function drawConf(ctx, w, h, field) {
    const f = s0().data.readings.fields[field];
    const n = N();
    const cw = Math.max(1, w / n);
    const warn = css("--warn");
    for (let i = 0; i < n; i++) {
      const c = f.confidence[i];
      if (f.value[i] == null || !Number.isFinite(c)) continue;
      const l = Math.round(28 + Math.min(1, c) * 62); // 28% to 90% lightness: low reads dark
      ctx.fillStyle = c < LOW_CONF ? warn : `hsl(205 12% ${l}%)`;
      ctx.fillRect(Math.floor(X(i, w)), c < LOW_CONF ? 0 : 1, Math.ceil(cw), c < LOW_CONF ? h : h - 2);
    }
  }
  function drawObject(ctx, w, h) {
    const c = s0().data.cues.columns;
    const n = N();
    const cw = Math.max(1, w / n);
    for (let i = 0; i < n; i++) {
      if (!c.obj_found[i]) { ctx.fillStyle = css("--warn"); ctx.fillRect(Math.floor(X(i, w)), 0, Math.ceil(cw), h); continue; }
      const snr = c.obj_snr[i] ?? 0;
      ctx.fillStyle = `hsl(205 12% ${Math.round(30 + Math.min(1, snr / 20) * 60)}%)`;
      ctx.fillRect(Math.floor(X(i, w)), 1, Math.ceil(cw), h - 2);
    }
  }
  function placeHead() {
    const s = s0();
    if (!lanes.length) return;
    const c = lanes[0].el.querySelector("canvas");
    const base = tracks.getBoundingClientRect().left;
    const r = c.getBoundingClientRect();
    head.style.left = `${r.left - base + X(s.frame, r.width)}px`;
  }

  new ResizeObserver(() => s0().data && redraw()).observe(tracks);

  return {
    update(s, ch) {
      if (ch.has("data") || ch.has("variant")) {
        root.querySelector("#fr-max").textContent = s.data.meta.n_frames - 1;
        root.querySelector("#fr-fps").textContent = `${(s.data.meta.fps || 0).toFixed(2)} fps`;
        tracks.setAttribute("aria-valuemax", s.data.meta.n_frames - 1);
        buildLanes();
      }
      if (ch.has("frame") || ch.has("data")) {
        root.querySelector("#fr-n").textContent = String(s.frame).padStart(4, "0");
        root.querySelector("#fr-t").textContent = timecode(s.data.meta.t_s[s.frame]);
        tracks.setAttribute("aria-valuenow", s.frame);
        tracks.setAttribute("aria-valuetext", `frame ${s.frame}, ${timecode(s.data.meta.t_s[s.frame])}`);
        placeHead();
      }
      if (ch.has("speed")) for (const sb of root.querySelectorAll("#t-speed button")) sb.setAttribute("aria-pressed", String(+sb.dataset.x === s.speed));
      if (ch.has("buffering") || ch.has("playing")) root.querySelector("#t-buf").hidden = !(s.buffering && s.playing);
      if (ch.has("playing")) {
        const b = root.querySelector("#t-play");
        b.innerHTML = s.playing ? ICON.pause : ICON.play;
        b.setAttribute("aria-label", s.playing ? "Pause (Space)" : "Play (Space)");
      }
    },
  };
}
