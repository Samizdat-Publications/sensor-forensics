// Playback clock. While playing, the case's video (tools/build_app_data.py export_video: the same frames as the
// JPEGs, frame i shown at i / fps) drives the frame number: the frame the browser actually shows is read back with
// requestVideoFrameCallback (its mediaTime), or from currentTime where that callback is missing or not firing, and
// every view follows it. So the re-render can never run ahead of the footage, and a stall in the download pauses
// both (state.buffering). Paused, stepping and scrubbing still show the exact JPEG of each frame.
// If the video cannot play, playback falls back to the JPEGs, advancing only when the next frame has loaded.

import { frameURL } from "./data.js";

export function createPlayer(api) {
  const video = document.createElement("video");
  video.muted = true;
  video.playsInline = true;
  video.preload = "metadata";
  video.className = "frm vid";
  video.setAttribute("aria-hidden", "true");
  video.disablePictureInPicture = true;

  let meta = null, fps = 29.97, n = 1, running = false, failed = false, stopAt = null;
  let vfc = 0, raf = 0, lastVfc = 0;
  const hasVfc = "requestVideoFrameCallback" in HTMLVideoElement.prototype;
  const clamp = (f) => Math.max(0, Math.min(n - 1, f));

  function push(f) {
    if (!running) return;
    f = clamp(f);
    if (stopAt !== null && f >= stopAt) { stop(); api.set({ frame: stopAt, playing: false }); return; }
    if (f !== api.getState().frame) api.set({ frame: f });
  }

  function onVideoFrame(_now, md) {
    if (!running) return;
    lastVfc = performance.now();
    push(Math.round(md.mediaTime * fps));
    vfc = video.requestVideoFrameCallback(onVideoFrame);
  }

  // currentTime lies between frames: frame i covers [i / fps, (i + 1) / fps)
  function poll() {
    if (!running) return;
    if (!hasVfc || performance.now() - lastVfc > 150) push(Math.floor(video.currentTime * fps + 1e-3));
    raf = requestAnimationFrame(poll);
  }

  video.addEventListener("waiting", () => running && api.set({ buffering: true }, { route: false }));
  video.addEventListener("playing", () => api.set({ buffering: false }, { route: false }));
  video.addEventListener("ended", () => { if (running) { stop(); api.set({ frame: n - 1, playing: false }); } });
  video.addEventListener("error", () => {
    failed = true;
    if (running) { cancel(); startImages(); }
  });

  function cancel() {
    if (vfc && hasVfc) video.cancelVideoFrameCallback(vfc);
    cancelAnimationFrame(raf);
    clearTimeout(imgTimer);
    vfc = raf = 0;
  }

  async function start() {
    if (!meta) return;
    const s = api.getState();
    if (s.frame >= n - 1) api.set({ frame: 0 }, { route: false });
    running = true;
    if (failed || !meta.video) { startImages(); return; }
    video.playbackRate = s.speed || 1;
    if (video.readyState < 1) {
      // a new case's video is still loading: wait for its metadata (up to 20 s, then use the images)
      const ok = await new Promise((res) => {
        const t = setTimeout(() => res(false), 20000);
        video.addEventListener("loadedmetadata", () => { clearTimeout(t); res(true); }, { once: true });
      });
      if (!running) return;
      if (!ok) { failed = true; startImages(); return; }
    }
    const target = (api.getState().frame + 0.5) / fps;
    if (Math.abs(video.currentTime - target) > 0.5 / fps) video.currentTime = target;
    try {
      await video.play().catch((e) => (e.name === "AbortError" && running ? video.play() : Promise.reject(e)));
    } catch (e) {
      if (!running) return;
      if (e.name === "NotAllowedError") { running = false; api.set({ playing: false }); return; }
      failed = true;
      startImages();
      return;
    }
    if (!running) { video.pause(); return; }
    lastVfc = 0;
    if (hasVfc) vfc = video.requestVideoFrameCallback(onVideoFrame);
    raf = requestAnimationFrame(poll);
  }

  function stop() {
    if (!running) return;
    running = false;
    stopAt = null;
    cancel();
    video.pause();
    api.set({ buffering: false }, { route: false });
  }

  // ---- fallback: JPEGs, advancing only when the next one has loaded
  const ahead = new Map();
  let imgTimer = 0;
  function want(i) {
    if (i >= n || ahead.has(i)) return;
    const im = new Image();
    im.src = frameURL(meta, i);
    ahead.set(i, im);
    if (ahead.size > 240) ahead.delete(ahead.keys().next().value);
  }
  function startImages() {
    const step = () => {
      if (!running) return;
      const s = api.getState();
      const next = s.frame + 1;
      for (let k = 1; k <= 45; k++) want(s.frame + k);
      const im = ahead.get(next);
      if (next >= n) { stop(); api.set({ playing: false }); return; }
      if (im && im.complete && im.naturalWidth) {
        if (s.buffering) api.set({ buffering: false }, { route: false });
        push(next);
      } else if (!s.buffering) api.set({ buffering: true }, { route: false });
      imgTimer = setTimeout(step, 1000 / (fps * (s.speed || 1)));
    };
    step();
  }

  return {
    video,
    get usingVideo() { return running && !failed && !!meta?.video; },
    get failed() { return failed; },
    load(m) {
      stop();
      meta = m;
      fps = m.fps || 29.97;
      n = m.n_frames;
      failed = !m.video;
      ahead.clear();
      if (m.video) { video.src = m.video; video.load(); }
      else video.removeAttribute("src");
    },
    setSpeed(x) { video.playbackRate = x; },
    // play from the current frame and stop at frame b (the tours use it); null plays to the end
    playUntil(b) { stopAt = b; },
    start, stop,
  };
}
