// Sensor Forensics Lab landing page: clips play while on screen and pause when they leave; the top bar turns solid
// past the hero. The page works without this script (posters show, clips get controls).
(function () {
  "use strict";
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  // Data saver: skip autoplay only on a real slow link or when the visitor asked to save data (a "3g" label is
  // common on fine connections, so it does not count).
  const conn = navigator.connection || {};
  const saver = Boolean(conn.saveData) || conn.effectiveType === "2g" || conn.effectiveType === "slow-2g";
  const still = reduced || saver;

  const bar = document.querySelector(".bar");
  const hero = document.querySelector(".hero");
  const onBar = () => bar.classList.toggle("solid", window.scrollY > hero.offsetHeight * 0.5);
  window.addEventListener("scroll", onBar, { passive: true });
  onBar();

  const heroVideo = document.querySelector(".hero-video");
  if (still && heroVideo) {
    heroVideo.removeAttribute("autoplay");
    heroVideo.pause();
  }

  const clips = [...document.querySelectorAll("video[data-inview]")];
  if (still) {
    for (const v of clips) v.setAttribute("controls", "");
    return;
  }
  const play = (v) => {
    const p = v.play();
    if (p && p.catch) p.catch(() => {});
  };
  if (!("IntersectionObserver" in window)) {
    for (const v of clips) v.setAttribute("controls", "");
    return;
  }
  // start loading a little before a clip scrolls in
  const near = new IntersectionObserver(
    (entries) => {
      for (const e of entries)
        if (e.isIntersecting) {
          e.target.preload = "auto";
          near.unobserve(e.target);
        }
    },
    { rootMargin: "600px 0px" },
  );
  const seen = new IntersectionObserver(
    (entries) => {
      for (const e of entries) (e.isIntersecting ? play : (v) => v.pause())(e.target);
    },
    { threshold: 0.35 },
  );
  for (const v of clips) {
    near.observe(v);
    seen.observe(v);
  }
})();
