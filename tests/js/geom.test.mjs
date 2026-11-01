// Parity: client-side geometry (app/js/geom.js) against the Python exports (tools/app_predictions.py via
// tools/build_app_data.py) and against closed-form cases. If this fails after the solver reran, regenerate the
// exports: .venv/Scripts/python tools/build_app_data.py --no-frames
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import {
  cameraBasis, project, horizonAngleInImage, predictedImage, frameLock, interpCurve, pathKinematics,
  soundSpeedKt, alignToJet, pointAtRange, wrap90, NMI_M, KT_MS, G0,
} from "../../app/js/geom.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const CASES = { gimbal: "gimbal", gofast: "gofast", flir1: "flir1_navy" };
const load = (p) => JSON.parse(readFileSync(p, "utf8"));

for (const cid of Object.keys(CASES)) {
  const path = join(ROOT, "app", "data", cid, "predictions.json");
  test(`${cid}: predicted image position and frame-lock errors equal the Python export`, { skip: !existsSync(path) && "no predictions.json" }, () => {
    const P = load(path);
    let nFits = 0;
    for (const [vn, v] of Object.entries(P.variants)) {
      for (const [h, fits] of Object.entries(v.hypotheses)) {
        for (const [fn, f] of Object.entries(fits)) {
          if (f.valid === false) continue;
          nFits++;
          for (let i = 0; i < f.img_x.length; i += 7) {
            const p = predictedImage(f, v, P.picture, i);
            if (f.img_x[i] === null) { assert.equal(p, null); continue; }
            assert.ok(Math.abs(p.x - f.img_x[i]) < 0.01 && Math.abs(p.y - f.img_y[i]) < 0.01,
              `${cid} ${vn} ${h} ${fn} frame ${i}: JS (${p.x}, ${p.y}) vs Python (${f.img_x[i]}, ${f.img_y[i]})`);
          }
          const js = frameLock(f, v, P.picture, P.measured);
          const py = f.frame_lock;
          assert.equal(js.object_n, py.object_n, `${cid} ${h} ${fn} object frames`);
          assert.equal(js.horizon_n, py.horizon_n, `${cid} ${h} ${fn} horizon frames`);
          for (const k of ["object_px_median", "horizon_px_median"]) {
            if (py[k] === null) { assert.equal(js[k], null); continue; }
            assert.ok(Math.abs(js[k] - py[k]) < 0.01, `${cid} ${vn} ${h} ${fn} ${k}: JS ${js[k]} vs Python ${py[k]}`);
          }
        }
      }
    }
    if (cid !== "flir1") assert.ok(nFits >= 12, `checked ${nFits} fits`);
  });
}

test("the camera basis puts the horizon at the requested image angle", () => {
  for (const th of [-62.5, -30, -1, 0, 12.25, 45, 89]) {
    for (const f of [[1, 2, -0.05], [-3, 0.4, -0.2], [0.1, -1, 0.01]]) {
      const b = cameraBasis(f, th);
      assert.ok(Math.abs(wrap90(horizonAngleInImage(b) - th)) < 1e-9, `theta ${th}`);
      // orthonormal, right-handed with f
      const d = (a, c) => a[0] * c[0] + a[1] * c[1] + a[2] * c[2];
      assert.ok(Math.abs(d(b.r, b.u)) < 1e-12 && Math.abs(d(b.r, b.f)) < 1e-12 && Math.abs(d(b.u, b.f)) < 1e-12);
    }
  }
});

test("pinhole projection: the boresight lands on the picture centre, an offset of fov/2 on the picture edge", () => {
  const pic = { cx: 317.5, cy: 239.5, width_px: 426 };
  const f = [0, 1, 0];
  const b = cameraBasis(f, 0);
  const c = project([0, 0, 0], b, [0, 1000, 0], pic, 0.7, 1.05);
  assert.ok(Math.abs(c.x - 317.5) < 1e-9 && Math.abs(c.y - 239.5) < 1e-9);
  const a = (0.35 * Math.PI) / 180;
  const e = project([0, 0, 0], b, [1000 * Math.tan(a), 1000, 0], pic, 0.7, 1.05);
  assert.ok(Math.abs(e.x - (317.5 + 213)) < 1e-6, `edge x ${e.x}`);
  // up in the world is up on screen (y decreases), compressed by the pixel aspect
  const u = project([0, 0, 0], b, [0, 1000, 1000 * Math.tan(a)], pic, 0.7, 1.05);
  assert.ok(Math.abs(u.y - (239.5 - 213 / 1.05)) < 1e-6, `up y ${u.y}`);
});

test("range curve interpolation reproduces the Python grid and is linear between points", () => {
  const py = load(join(ROOT, "data", "derived", "gimbal", "results.json"));
  const app = load(join(ROOT, "app", "data", "gimbal", "range_curve.json"));
  for (const [vn, pv] of Object.entries(py.variants)) {
    const grid = pv.range_curve_angles_only.filter((p) => p.valid !== false);
    const curve = app.variants[vn];
    for (const p of grid) {
      const q = interpCurve(curve, p.range_nmi);
      for (const k of ["air_speed_kt", "ground_speed_kt", "altitude_ft_mean", "vertical_speed_fpm", "line_of_sight_loglik"])
        assert.ok(Math.abs(q[k] - p[k]) <= 1e-9 * Math.max(1, Math.abs(p[k])), `${vn} ${p.range_nmi} nmi ${k}: ${q[k]} vs ${p[k]}`);
    }
    for (let j = 0; j + 1 < grid.length; j++) {
      const a = grid[j], b = grid[j + 1], t = 0.3, r = a.range_nmi + t * (b.range_nmi - a.range_nmi);
      const q = interpCurve(curve, r);
      const want = a.air_speed_kt + t * (b.air_speed_kt - a.air_speed_kt);
      assert.ok(Math.abs(q.air_speed_kt - want) < 1e-9 * Math.max(1, want), `${vn} at ${r}`);
    }
    assert.equal(interpCurve(curve, grid[0].range_nmi - 0.5), null);
  }
});

test("path kinematics: a level circle at known speed and radius", () => {
  const fps = 29.97, v = 120 * KT_MS, R = 2000;
  const t = Array.from({ length: 900 }, (_, i) => i / fps);
  const pts = t.map((s) => [R * Math.cos((v / R) * s), R * Math.sin((v / R) * s), 7620]);
  const k = pathKinematics(t, pts, 15, 5);
  assert.ok(Math.abs(k.mean_ground_speed_kt - 120) < 0.5, `speed ${k.mean_ground_speed_kt}`);
  assert.ok(Math.abs(k.max_accel_g - (v * v) / R / G0) / ((v * v) / R / G0) < 0.02, `accel ${k.max_accel_g}`);
  assert.ok(Math.abs(k.alt_min_ft - 25000) < 0.1 && Math.abs(k.alt_max_ft - 25000) < 0.1);
});

test("ISA speed of sound and the jet alignment", () => {
  assert.ok(Math.abs(soundSpeedKt(0) - 661.5) < 0.5);
  assert.ok(Math.abs(soundSpeedKt(25000) - 602.2) < 0.6);
  assert.ok(Math.abs(soundSpeedKt(40000) - 573.6) < 0.6);
  const fit = { jet_e: [100, 110, 120], jet_n: [50, 50, 50], jet_u: [7620, 7620, 7620] }; // heading east
  const al = alignToJet(fit, 2);
  const p = al(120, 50, 7620);
  assert.ok(Math.abs(p[0]) < 1e-9 && Math.abs(p[1] - 20) < 1e-9, `aligned ${p}`);
});

test("fixed-range point lies on the sight line at the requested range", () => {
  const fit = { jet_e: [0], jet_n: [0], jet_u: [7620], obj_e: [3000], obj_n: [4000], obj_u: [7620], horizon_deg: [-20] };
  const q = pointAtRange(fit, 0, NMI_M);
  assert.ok(Math.abs(Math.hypot(q[0], q[1], q[2] - 7620) - NMI_M) < 1e-6);
  assert.ok(Math.abs(q[0] / q[1] - 0.75) < 1e-12);
});
