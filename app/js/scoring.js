// Client-side re-scoring from per-criterion log-likelihoods (D-011).
// Pure functions, no DOM: shared by the app and tests/js/scoring.test.mjs.
//
// Python (solve/score.py) defines, for one fit:
//   physics_total  = sum over non-testimony criteria of loglik * weight   (includes prior and complexity penalty)
//   weighted_total = physics_total + w_T * testimony_loglik
// results.json stores two fits per hypothesis: one optimised at the default w_T, one at w_T = 0.
// In the browser we cannot refit, so a live total at any w_T is the best of the stored fits
// evaluated at that w_T (an envelope). At the two weights Python fitted it reproduces Python, except
// where a stored fit beats the solver's own optimum (reported as a shortfall, never hidden).

export function fitPhysicsTotal(fit, overrides = {}) {
  let s = 0;
  for (const c of fit.criteria) {
    if (c.kind === "testimony") continue;
    const w = Object.prototype.hasOwnProperty.call(overrides, c.name) ? overrides[c.name] : c.weight;
    s += c.loglik * w;
  }
  return s;
}

export function fitTestimony(fit) {
  let s = 0;
  for (const c of fit.criteria) if (c.kind === "testimony") s += c.loglik;
  return s;
}

export function fitWeightedTotal(fit, testimonyWeight, overrides = {}) {
  return fitPhysicsTotal(fit, overrides) + testimonyWeight * fitTestimony(fit);
}

export function fitByName(h, name) {
  return h.fits.find((f) => f.fit === name) || null;
}

// Both totals for one hypothesis at a testimony weight.
// mode "stored": exactly Python's definition (testimony-weighted fit at w, physics-only fit's physics total).
// mode "envelope" (app default): the best stored fit at w, for both totals. It equals "stored" wherever the
// solver reached its own optimum; where one stored fit beats the other on the other's objective (an optimiser
// shortfall), the envelope is higher and `shortfall` says by how much.
export function hypothesisTotals(h, testimonyWeight, overrides = {}, mode = "envelope") {
  const tw = fitByName(h, "testimony_weighted");
  const po = fitByName(h, "physics_only") || tw;
  const stored = {
    testimonyWeighted: tw && tw.criteria.length ? fitWeightedTotal(tw, testimonyWeight, overrides) : -Infinity,
    physicsOnly: po && po.criteria.length ? fitPhysicsTotal(po, overrides) : -Infinity,
  };
  if (mode === "stored") return { ...stored, testimonyFit: "testimony_weighted", physicsFit: "physics_only", shortfall: 0, shortfallPO: 0 };
  let best = -Infinity, bestFit = null, bestP = -Infinity, bestPFit = null;
  for (const f of h.fits) {
    if (!f.criteria.length) continue;
    const t = fitWeightedTotal(f, testimonyWeight, overrides);
    if (t > best) { best = t; bestFit = f.fit; }
    const p = fitPhysicsTotal(f, overrides);
    if (p > bestP) { bestP = p; bestPFit = f.fit; }
  }
  return {
    testimonyWeighted: best, physicsOnly: bestP, testimonyFit: bestFit, physicsFit: bestPFit,
    shortfall: best - stored.testimonyWeighted, shortfallPO: bestP - stored.physicsOnly,
  };
}

// Rank valid hypotheses of one variant. Returns rows sorted by the testimony-weighted total.
export function scoreVariant(variant, testimonyWeight, overrides = {}, mode = "envelope") {
  const rows = variant.hypotheses.map((h) => ({ h, ...hypothesisTotals(h, testimonyWeight, overrides, mode) }));
  const valid = rows.filter((r) => r.h.valid && Number.isFinite(r.testimonyWeighted));
  const bestTW = Math.max(...valid.map((r) => r.testimonyWeighted));
  const bestPO = Math.max(...valid.map((r) => r.physicsOnly));
  const byTW = [...valid].sort((a, b) => b.testimonyWeighted - a.testimonyWeighted);
  const byPO = [...valid].sort((a, b) => b.physicsOnly - a.physicsOnly);
  for (const r of rows) {
    r.gapTW = r.testimonyWeighted - bestTW;
    r.gapPO = r.physicsOnly - bestPO;
    r.rankTW = byTW.indexOf(r) + 1 || null;
    r.rankPO = byPO.indexOf(r) + 1 || null;
  }
  return rows.sort((a, b) => (a.rankTW ?? 99) - (b.rankTW ?? 99));
}

