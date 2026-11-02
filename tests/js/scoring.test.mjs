// Parity: client-side totals (app/js/scoring.js on app/data exports) equal the Python totals in
// data/derived/<case>/results.json for every hypothesis, at the default testimony weight and at 0.
// If this fails after the solver reran, regenerate the exports: .venv/Scripts/python tools/build_app_data.py --no-frames
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { hypothesisTotals, scoreVariant, fitWeightedTotal } from "../../app/js/scoring.js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const CASES = { gimbal: "gimbal", gofast: "gofast", flir1: "flir1_navy" };
const TOL = 1e-6;
const shortfalls = [];

function close(a, b, what) {
  const tol = TOL * Math.max(1, Math.abs(b));
  assert.ok(Math.abs(a - b) <= tol, `${what}: client ${a} vs python ${b} (diff ${a - b})`);
}

for (const [cid, folder] of Object.entries(CASES)) {
  test(`${cid}: client totals equal Python totals for every hypothesis`, () => {
    const appPath = join(ROOT, "app", "data", cid, "results.json");
    assert.ok(existsSync(appPath), `missing ${appPath}; run tools/build_app_data.py`);
    const app = JSON.parse(readFileSync(appPath, "utf8"));
    const py = JSON.parse(readFileSync(join(ROOT, "data", "derived", folder, "results.json"), "utf8"));
    const pyVariants = py.variants ?? { [py.variant ?? ""]: py };
    assert.equal(app.variants.length, Object.keys(pyVariants).length, "variant count");
    let n = 0;
    for (const v of app.variants) {
      const pv = pyVariants[v.variant];
      assert.ok(pv, `variant ${v.variant} missing in Python results`);
      const wDefault = pv.weights.testimony;
      assert.equal(v.hypotheses.length, pv.hypotheses.length, `${v.variant} hypothesis count`);
      for (const ph of pv.hypotheses) {
        const h = v.hypotheses.find((x) => x.id === ph.hypothesis);
        assert.ok(h, `${ph.hypothesis} missing in app export`);
        // Python's definition, recomputed in the browser: exact.
        const st = hypothesisTotals(h, wDefault, {}, "stored");
        close(st.testimonyWeighted, ph.total_testimony_weighted, `${cid} ${v.variant} ${h.id} testimony-weighted total`);
        close(st.physicsOnly, ph.total_physics_only, `${cid} ${v.variant} ${h.id} physics-only total`);
        // Envelope (the live slider): never below Python; any excess is a stored fit beating the solver's optimum.
        for (const [w, pyTot, key] of [[wDefault, ph.total_testimony_weighted, "testimonyWeighted"], [0, ph.total_physics_only, "testimonyWeighted"]]) {
          const e = hypothesisTotals(h, w);
          const tol = TOL * Math.max(1, Math.abs(pyTot));
          assert.ok(e[key] >= pyTot - tol, `${cid} ${v.variant} ${h.id} envelope at w=${w} below Python`);
          if (e[key] - pyTot > tol) shortfalls.push(`${cid} ${v.variant || "-"} ${h.id} w=${w}: +${(e[key] - pyTot).toFixed(4)} via ${e.testimonyFit} fit`);
        }
        n++;
      }
      // ranks agree with Python where Python stored them
      const rows = scoreVariant(v, wDefault, {}, "stored");
      for (const ph of pv.hypotheses) {
        if (ph.rank_testimony_weighted == null) continue;
        const r = rows.find((x) => x.h.id === ph.hypothesis);
        assert.equal(r.rankTW, ph.rank_testimony_weighted, `${cid} ${v.variant} ${ph.hypothesis} rank (weighted)`);
        assert.equal(r.rankPO, ph.rank_physics_only, `${cid} ${v.variant} ${ph.hypothesis} rank (physics only)`);
      }
    }
    assert.ok(n >= 6, `checked ${n} hypotheses`);
  });
}

test("optimiser shortfalls are reported, not hidden", () => {
  // Informational: a stored fit beating the solver's own optimum is a solver finding for the orchestrator.
  for (const s of shortfalls) console.log(`# shortfall (stored fit beats the solver optimum): ${s}`);
  assert.ok(shortfalls.every((s) => /via (testimony_weighted|physics_only) fit/.test(s)));
});

test("live testimony weight moves only the testimony term", () => {
  const h = { valid: true, fits: [{ fit: "a", criteria: [
    { name: "x", loglik: -10, weight: 1, kind: "physics" },
    { name: "s", loglik: 50, weight: 0, kind: "physics" },
    { name: "testimony", loglik: -4, weight: 1, kind: "testimony" }] }] };
  const t = hypothesisTotals(h, 0.5);
  assert.equal(t.physicsOnly, -10);
  assert.equal(t.testimonyWeighted, -12);
});
