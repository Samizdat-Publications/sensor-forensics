# ENGINE.md: binding engineering contract

Change this file only through a DECISIONS.md entry.

## Stack

- **Extraction and solving:** Python 3.12 in a uv-managed `.venv` (D-006) (opencv, numpy, scipy, an OCR engine, pandas); deterministic, tested.
- **App:** three.js (vendored, pinned), ES modules, no bundler; static, local preview; Playwright for screenshots.
- **Reuse:** if Sitrec's license allows, reuse or port pieces with attribution; otherwise reimplement from its documented methods and compare outputs.

## Repo layout

```
extract/       frame extraction, symbology OCR, correction tool
solve/         jet path, line of sight, trajectory families, hypotheses, scoring
app/           three.js web app
data/videos/   official videos (gitignored if large), hashes committed
data/derived/  per-frame tables (committed when small)
tests/  tools/  artifacts/  checkpoints/
schemas/       case file schema (D-007)
docs/          audit, prior work, reproductions, results, design (D-007)
handoff/       the original handoff package (D-007)
```

## Rules

- Every derived number traces to frames and a method.
- Hypotheses are data files; no per-hypothesis code paths beyond their physical model.
- No emdashes in UI strings.
