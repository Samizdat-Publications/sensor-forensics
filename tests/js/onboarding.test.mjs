// The lab's plain-language layer and the 11/04/2026 view fixes, checked against the exported data: the "times less
// likely" wording, altitude above sea level on the curved Earth (the scorer's), the god's-eye alignment on the
// jet's nose, and every tour step's text built from the real files. If a data test fails after the solver reran,
// regenerate the exports: .venv/Scripts/python tools/build_app_data.py --no-frames
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { likelihoodWords, plainName, TERMS, INTROS } from "../../app/js/glossary.js";
import { altitudeM, alignToNose, rangeDomain, wrap180 } from "../../app/js/geom.js";
import { scoreVariant } from "../../app/js/scoring.js";
import { TOURS } from "../../app/js/tours.js";
import { tourContext } from "../../app/js/tour.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const load = (cid, f) => JSON.parse(readFileSync(join(ROOT, "app", "data", cid, f), "utf8"));
const CASES = ["gimbal", "gofast", "flir1"];

function caseData(cid) {
  const meta = load(cid, "meta.json");
  const has = (f) => meta.files.includes(f);
  const d = { meta, results: load(cid, "results.json"), readings: load(cid, "readings.json"), cues: has("cues.json") ? load(cid, "cues.json") : null,
    testimony: has("testimony.json") ? load(cid, "testimony.json") : null, pending: new Set(), failed: {} };
  d.predictions = { variants: {} };
  for (const [vn, f] of Object.entries(meta.predictions_files)) {
    const x = load(cid, f);
    d.predictions.picture = x.picture;
    d.predictions.measured = x.measured;
    d.predictions.variants[vn] = x.data;
  }
  return d;
}

test("likelihood gaps read as plain ratios (2.3 log units = 10 times)", () => {
  assert.equal(likelihoodWords(0), "best fit");
  assert.equal(likelihoodWords(-0.2), "about as likely");
  assert.equal(likelihoodWords(-Math.log(10)), "about 10 times less likely");
  assert.equal(likelihoodWords(-Math.log(3.04)), "about 3.0 times less likely");
  assert.equal(likelihoodWords(-4.7), "about 110 times less likely");
  assert.equal(likelihoodWords(-9.8), "about 18,000 times less likely");
  assert.equal(likelihoodWords(-20), "over a million times less likely");
  assert.equal(likelihoodWords(NaN), "not scored");
});

test("every explanation has a plain name and a glossary entry; every view an introduction", () => {
  for (const cid of CASES) {
    const v = load(cid, "results.json").variants[0];
    for (const h of v.hypotheses) {
      assert.notEqual(plainName(h.id), h.id, `${h.id} has a plain name`);
      assert.ok(TERMS[h.id], `${h.id} glossary entry`);
    }
  }
  for (const k of ["cockpit", "godseye", "range", "compare", "ledger"]) assert.equal(INTROS[k].length, 2);
});

for (const cid of CASES) {
  test(`${cid}: altitude above sea level on the curved Earth equals the scorer's mean altitude`, () => {
    const d = caseData(cid);
    let n = 0;
    for (const v of d.results.variants) {
      const P = d.predictions.variants[v.variant ?? ""];
      const [a, b] = P.window_frames;
      for (const h of v.hypotheses.filter((x) => x.valid)) for (const f of h.fits) {
        const p = P.hypotheses[h.id]?.[f.fit];
        if (!p || p.valid === false || !Number.isFinite(f.derived?.altitude_ft_mean)) continue;
        let s = 0, k = 0;
        for (let i = a; i <= b; i++) if (Number.isFinite(p.obj_u[i])) { s += altitudeM(p.obj_e[i], p.obj_n[i], p.obj_u[i]); k++; }
        assert.ok(Math.abs(s / k / 0.3048 - f.derived.altitude_ft_mean) < 2, `${cid} ${v.variant} ${h.id} ${f.fit}: ${s / k / 0.3048} vs ${f.derived.altitude_ft_mean}`);
        n++;
      }
    }
    assert.ok(n >= 6, `checked ${n} fits`);
  });

  test(`${cid}: aligned on the nose, each fit's sight line points where its pod azimuth says`, () => {
    const d = caseData(cid);
    for (const v of d.results.variants) {
      const P = d.predictions.variants[v.variant ?? ""];
      const i0 = P.window_frames[0];
      const brg = [];
      for (const [id, fits] of Object.entries(P.hypotheses)) {
        const f = fits.testimony_weighted?.valid !== false ? fits.testimony_weighted : fits.physics_only;
        if (!f || f.valid === false) continue;
        let i = i0;
        while (!Number.isFinite(f.obj_e[i]) || !Number.isFinite(f.az_deg[i])) i++;
        const al = alignToNose(f, i0);
        const j = al(f.jet_e[i], f.jet_n[i], f.jet_u[i]), o = al(f.obj_e[i], f.obj_n[i], f.obj_u[i]);
        const b = (Math.atan2(o[0] - j[0], o[1] - j[1]) * 180) / Math.PI;
        // the nose points north, so the sight line's bearing is the azimuth the pod read
        assert.ok(Math.abs(wrap180(b - f.az_deg[i])) < 1e-6, `${cid} ${id}: bearing ${b} vs azimuth ${f.az_deg[i]}`);
        brg.push(b);
      }
      assert.ok(brg.length >= 3, `${cid} ${v.variant}: ${brg.length} fits`);
    }
  });

  test(`${cid}: both range sliders get one domain covering every curve and best fit`, () => {
    const d = caseData(cid);
    d.rangeCurve = load(cid, "range_curve.json");
    d.rangeCurves = existsSync(join(ROOT, "app", "data", cid, "range_curves.json")) ? load(cid, "range_curves.json") : null;
    for (const v of d.results.variants) {
      const fits = v.hypotheses.filter((h) => h.valid).flatMap((h) => h.fits.map((f) => f.derived?.range_nmi_mean));
      const [lo, hi] = rangeDomain(d, v.variant, fits);
      assert.equal(lo, 1);
      assert.ok(hi >= Math.max(...fits.filter(Number.isFinite)), `${cid}: ${hi} covers the fits`);
    }
  });

  test(`${cid}: every tour step's text is built from the data, with no missing value`, () => {
    const d = caseData(cid);
    const v = d.results.variants[0];
    const s = { data: d, variant: v.variant, frame: 0, wT: v.weights.testimony };
    const rows = scoreVariant(v, v.weights.testimony, {});
    const ctx = tourContext(s, rows, v);
    for (const [k, st] of TOURS[cid].steps.entries()) {
      const txt = st.text(ctx);
      assert.ok(txt.length > 60, `${cid} step ${k + 1} has text`);
      assert.ok(!/undefined|NaN|null|\[object/.test(txt), `${cid} step ${k + 1}: ${txt}`);
    }
    // the score sentences use the same words the rail shows
    const byPO = [...rows].sort((a, b) => b.physicsOnly - a.physicsOnly);
    assert.equal(ctx.leadPO.h.id, byPO[0].h.id);
    assert.equal(ctx.words(byPO[1]), likelihoodWords(byPO[1].physicsOnly - byPO[0].physicsOnly).replace(" less likely", " more likely"));
    assert.equal(ctx.leadPO.h.id, d.meta.summary.leader_physics_only, `${cid}: the tour's leader is the case file's`);
  });
}

test("GOFAST's tour reads the range off the screen; FLIR1's knows its range slot is a placeholder", () => {
  const g = caseData("gofast"), f = caseData("flir1");
  const ctxG = tourContext({ data: g, variant: "" }, scoreVariant(g.results.variants[0], 1, {}), g.results.variants[0]);
  assert.deepEqual(ctxG.rangeReads, ["4.4", "3.3"]);
  const ctxF = tourContext({ data: f, variant: "" }, scoreVariant(f.results.variants[0], 1, {}), f.results.variants[0]);
  assert.equal(ctxF.placeholder?.value, "99.9");
  assert.equal(ctxF.rangeReads, null);
  assert.ok(ctxF.rotation && ctxF.rotation.leader === "H-ART", "FLIR1's rotation-noise crossover names the glare model");
});
