// Client-side geometry for the cockpit re-render and the god's-eye view. Pure functions, no DOM, no three.js:
// shared by the views and tests/js/geom.test.mjs (parity with tools/app_predictions.py).
//
// Camera model (tools/app_predictions.py docstring): the camera sits at the jet and looks along the predicted
// line of sight f (ENU); r0 = unit(f x up), u0 = r0 x f; rolled to the image horizon angle theta (deg, CCW, image
// y up): r = r0 cos(theta) - u0 sin(theta), u = r0 sin(theta) + u0 cos(theta). Pinhole projection onto the frame:
// x = cx + fx (d.r)/(d.f), y = cy - fy (d.u)/(d.f), fx = (picture width / 2) / tan(fov / 2), fy = fx / pixel aspect.

export const NMI_M = 1852;
export const FT_M = 0.3048;
export const KT_MS = 1852 / 3600;
export const G0 = 9.80665;

const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = (a) => Math.hypot(a[0], a[1], a[2]);
const unit = (a) => { const n = norm(a); return [a[0] / n, a[1] / n, a[2] / n]; };
export { dot, sub, cross, norm, unit };

export function wrap90(a) { return ((((a + 90) % 180) + 180) % 180) - 90; }
export function wrap180(a) { return ((((a + 180) % 360) + 360) % 360) - 180; }

// Image right and up unit vectors for forward f (ENU) rolled to horizon angle thetaDeg.
export function cameraBasis(f, thetaDeg) {
  const fu = unit(f);
  const r0 = unit(cross(fu, [0, 0, 1]));
  const u0 = cross(r0, fu);
  const t = (thetaDeg * Math.PI) / 180, c = Math.cos(t), s = Math.sin(t);
  return {
    f: fu,
    r: [r0[0] * c - u0[0] * s, r0[1] * c - u0[1] * s, r0[2] * c - u0[2] * s],
    u: [r0[0] * s + u0[0] * c, r0[1] * s + u0[1] * c, r0[2] * s + u0[2] * c],
    r0, u0,
  };
}

export function focal(pic, fovDeg, pixelAspect = 1) {
  const fx = pic.width_px / 2 / Math.tan((fovDeg * Math.PI) / 360);
  return { fx, fy: fx / pixelAspect };
}

// Frame px of world point p seen from cam with basis b. Returns null behind the camera.
export function project(cam, b, p, pic, fovDeg, pixelAspect = 1) {
  const d = sub(p, cam);
  const z = dot(d, b.f);
  if (!(z > 0)) return null;
  const { fx, fy } = focal(pic, fovDeg, pixelAspect);
  return { x: pic.cx + (fx * dot(d, b.r)) / z, y: pic.cy - (fy * dot(d, b.u)) / z };
}

// Angle (deg, CCW, image y up) at which the world-horizontal direction perpendicular to the sight line
// appears in the image. Equals thetaDeg by construction; computed from the basis so the test checks it.
export function horizonAngleInImage(b) {
  return (Math.atan2(dot(b.r0, b.u), dot(b.r0, b.r)) * 180) / Math.PI;
}

// Per-frame inputs from predictions.json for one fit.
export function framePose(fit, i) {
  const jet = [fit.jet_e[i], fit.jet_n[i], fit.jet_u[i]];
  const obj = [fit.obj_e[i], fit.obj_n[i], fit.obj_u[i]];
  if (![...jet, ...obj].every(Number.isFinite) || !Number.isFinite(fit.horizon_deg[i])) return null;
  return { jet, obj, theta: fit.horizon_deg[i] };
}

// Field of view at frame i: per frame where the case reads it off the screen (FLIR1; NaN where unread), else fixed.
export function fovAt(v, i) {
  if (v.fov_by_frame) { const f = v.fov_by_frame[i]; return Number.isFinite(f) ? f : NaN; }
  return v.fov_deg;
}

// Predicted image position of the object at frame i (frame px).
export function predictedImage(fit, v, pic, i) {
  const p = framePose(fit, i);
  if (!p) return null;
  const fov = fovAt(v, i);
  if (!Number.isFinite(fov)) return null;
  const b = cameraBasis(sub(p.obj, p.jet), p.theta);
  return project(p.jet, b, p.obj, pic, fov, v.pixel_aspect_x);
}

function median(xs) {
  const a = xs.filter(Number.isFinite).sort((x, y) => x - y);
  if (!a.length) return null;
  const m = a.length >> 1;
  return a.length % 2 ? a[m] : 0.5 * (a[m - 1] + a[m]);
}
export { median };

// Frame-lock errors over the clip: same definitions as tools/app_predictions.frame_lock.
export function frameLock(fit, v, pic, meas) {
  const n = fit.horizon_deg.length;
  const eo = [], eh = [];
  for (let i = 0; i < n; i++) {
    const p = predictedImage(fit, v, pic, i);
    const mx = meas.obj_cx[i], my = meas.obj_cy[i];
    if (p && Number.isFinite(mx) && Number.isFinite(my)) eo.push(Math.hypot(p.x - mx, p.y - my));
    const th = fit.horizon_deg[i], tm = meas.horizon_deg?.[i];
    if (Number.isFinite(th) && Number.isFinite(tm)) eh.push((pic.width_px / 2) * Math.abs(Math.sin((wrap90(th - tm) * Math.PI) / 180)));
  }
  return { object_px_median: median(eo), object_n: eo.length, horizon_px_median: median(eh), horizon_n: eh.length };
}

// Per-frame errors at one frame (for the strip under the panels).
export function frameErrors(fit, v, pic, meas, i) {
  const p = predictedImage(fit, v, pic, i);
  const mx = meas.obj_cx[i], my = meas.obj_cy[i];
  const th = fit.horizon_deg[i], tm = meas.horizon_deg?.[i];
  return {
    pred: p,
    object_px: p && Number.isFinite(mx) && Number.isFinite(my) ? Math.hypot(p.x - mx, p.y - my) : null,
    horizon_px: Number.isFinite(th) && Number.isFinite(tm) ? (pic.width_px / 2) * Math.abs(Math.sin((wrap90(th - tm) * Math.PI) / 180)) : null,
    horizon_deg: Number.isFinite(th) && Number.isFinite(tm) ? wrap90(th - tm) : null,
  };
}

// Point at slant range rM along the predicted sight line of frame i (the fixed-range path).
export function pointAtRange(fit, i, rM) {
  const p = framePose(fit, i);
  if (!p) return null;
  const u = unit(sub(p.obj, p.jet));
  return [p.jet[0] + rM * u[0], p.jet[1] + rM * u[1], p.jet[2] + rM * u[2]];
}

// Speed of sound (kt) in the ISA at a pressure altitude in ft (troposphere; isothermal above 36,089 ft).
export function soundSpeedKt(altFt) {
  const h = Math.min(Math.max(altFt, -2000), 36089) * FT_M;
  const T = 288.15 - 0.0065 * h;
  return Math.sqrt(1.4 * 287.05287 * T) / KT_MS;
}

// Linear interpolation of a curve (array of {range_nmi, ...}) at r over valid points; null outside.
export function interpCurve(curve, r) {
  const pts = curve.filter((p) => p.valid !== false && Number.isFinite(p.range_nmi)).sort((a, b) => a.range_nmi - b.range_nmi);
  if (!pts.length || r < pts[0].range_nmi || r > pts[pts.length - 1].range_nmi) return null;
  const j = pts.findIndex((p) => p.range_nmi >= r);
  if (pts[j].range_nmi === r) return { ...pts[j] };
  const a = pts[j - 1], b = pts[j], t = (r - a.range_nmi) / (b.range_nmi - a.range_nmi);
  const out = { range_nmi: r };
  for (const k of Object.keys(a)) if (typeof a[k] === "number" && typeof b[k] === "number") out[k] = a[k] + t * (b[k] - a[k]);
  return out;
}

// "Nice" tick values covering [a, b] with about n steps.
export function ticks(a, b, n = 6) {
  if (!(b > a)) return [a];
  const raw = (b - a) / n;
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const s = [1, 2, 2.5, 5, 10].map((k) => k * p).find((k) => k >= raw) ?? 10 * p;
  const out = [];
  for (let v = Math.ceil(a / s - 1e-9) * s; v <= b + 1e-9 * s; v += s) out.push(Math.abs(v) < 1e-12 ? 0 : +v.toPrecision(12));
  return out;
}

// Rotate ENU points about the vertical so the jet's track over its first frames points north (+y) and the
// jet's first position is the origin. Returns a function (e, n, u) -> [e', n', u] in metres.
export function alignToJet(fit, k = 10) {
  const e0 = fit.jet_e[0], n0 = fit.jet_n[0];
  const j = Math.min(k, fit.jet_e.length - 1);
  const a = Math.atan2(fit.jet_e[j] - e0, fit.jet_n[j] - n0); // track, rad clockwise from north
  const c = Math.cos(a), s = Math.sin(a);
  return (e, n, u) => { const x = e - e0, y = n - n0; return [x * c - y * s, x * s + y * c, u]; };
}

// Kinematics of a sampled path (metres, seconds): mean and max horizontal speed (kt), altitude range (ft) and
// peak acceleration (g) from central differences `h` samples apart after a centred moving average of `smooth`
// samples. Use exact sample times (i / fps): the exported 4-decimal times would add derivative noise.
export function pathKinematics(t, pts, smooth = 15, h = 5) {
  const n = pts.length;
  const sm = pts.map((_, i) => {
    let a = [0, 0, 0], c = 0;
    for (let k = Math.max(0, i - (smooth >> 1)); k <= Math.min(n - 1, i + (smooth >> 1)); k++) { a = [a[0] + pts[k][0], a[1] + pts[k][1], a[2] + pts[k][2]]; c++; }
    return [a[0] / c, a[1] / c, a[2] / c];
  });
  const vel = sm.map((_, i) => {
    const a = Math.max(0, i - h), b = Math.min(n - 1, i + h);
    const dt = t[b] - t[a];
    return [(sm[b][0] - sm[a][0]) / dt, (sm[b][1] - sm[a][1]) / dt, (sm[b][2] - sm[a][2]) / dt];
  });
  const acc = vel.map((_, i) => {
    const a = Math.max(0, i - h), b = Math.min(n - 1, i + h);
    const dt = t[b] - t[a];
    return Math.hypot(vel[b][0] - vel[a][0], vel[b][1] - vel[a][1], vel[b][2] - vel[a][2]) / dt;
  });
  const gs = vel.map((v) => Math.hypot(v[0], v[1]) / KT_MS);
  const lo = Math.floor(smooth / 2) + 2 * h, hi = n - lo; // skip the ends, where the average is one-sided
  const inner = (arr) => arr.slice(Math.min(lo, n - 1), Math.max(hi, Math.min(lo, n - 1) + 1));
  const alt = pts.map((p) => p[2] / FT_M);
  return {
    mean_ground_speed_kt: inner(gs).reduce((x, y) => x + y, 0) / inner(gs).length,
    max_ground_speed_kt: Math.max(...inner(gs)),
    alt_min_ft: Math.min(...alt), alt_max_ft: Math.max(...alt),
    max_accel_g: Math.max(...inner(acc)) / G0,
  };
}

// Rotate ENU points about the vertical so the jet's nose at frame i0 points north (+y), with the jet's first
// position at the origin. The nose is the first sight line's horizontal bearing minus the pod azimuth read on screen
// (az_deg, from the nose). Each fit has its own heading and the wind crabs each jet differently, so aligning on the
// ground track (alignToJet) leaves the fits' sight lines up to 25 deg apart; aligning on the nose puts every fit's
// sight lines where the pod pointed them. i0: the frame to align at (the first scored frame; before it a fit is
// extrapolated). Returns a function (e, n, u) -> [e', n', u] in metres.
export function alignToNose(fit, i0 = 0) {
  const n = fit.jet_e.length;
  let i = Math.max(0, Math.min(n - 1, i0));
  while (i < n - 1 && !(Number.isFinite(fit.obj_e[i]) && Number.isFinite(fit.az_deg?.[i]))) i++;
  if (!Number.isFinite(fit.az_deg?.[i])) return alignToJet(fit);
  const e0 = fit.jet_e[0], n0 = fit.jet_n[0];
  const brg = Math.atan2(fit.obj_e[i] - fit.jet_e[i], fit.obj_n[i] - fit.jet_n[i]);
  const a = brg - (fit.az_deg[i] * Math.PI) / 180; // nose, rad clockwise from north
  const c = Math.cos(a), s = Math.sin(a);
  return (e, n2, u) => { const x = e - e0, y = n2 - n0; return [x * c - y * s, x * s + y * c, u]; };
}

// Altitude above sea level (m) of an ENU point on the spherical Earth the scorer uses (solve/frames.py R_EARTH; the
// ENU origin is at sea level). The scorer's altitudes (results.json derived.altitude_ft_mean) use this, so every view
// does too; the flat "up" coordinate reads up to a few thousand feet low at 40 nmi.
export const R_EARTH = 6371008.8;
export function altitudeM(e, n, u) {
  return Math.sqrt(e * e + n * n + (R_EARTH + u) * (R_EARTH + u)) - R_EARTH;
}

// The assumed-range domain (nmi) shared by the god's-eye slider and the range explorer: 1 nmi to just past the
// farthest range any curve or best fit reaches. extraNmi: best-fit mean ranges.
export function rangeDomain(data, variant, extraNmi = []) {
  const vk = variant ?? "";
  const xs = [...(data.rangeCurve?.variants?.[vk] ?? []).map((p) => p.range_nmi),
    ...Object.values(data.rangeCurves?.variants?.[vk] ?? {}).flat().map((p) => p.range_nmi), ...extraNmi].filter(Number.isFinite);
  return [1, Math.max(2, Math.ceil(Math.max(...xs, 1) * 1.04))];
}
