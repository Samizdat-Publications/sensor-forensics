# three.js, vendored

- Version: **0.170.0** (revision r170, released 10/31/2024 on npm)
- License: MIT, see `LICENSE` in this folder (copied unmodified from the package)
- Downloaded 11/01/2026 from jsDelivr, pinned to the exact version. Files are unmodified.

| File | Source URL | SHA-256 |
|------|------------|---------|
| three.module.js | https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js | ce1fa418de16a19495a9f72495580e3015d7745c296d3ce0485897f902ddedfb |
| addons/controls/OrbitControls.js | https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/controls/OrbitControls.js | 80efaadea4f8a636a65fb0bd08bfef62f3d93a0bb94e2e7500f23176c5c07f4e |
| LICENSE | https://cdn.jsdelivr.net/npm/three@0.170.0/LICENSE | 4c40a1ef62450b857c3b2aaf294936304cd552d965fbcd9d32d4c5bcf4ba4454 |

The app loads these through an import map in `app/index.html`:
`three` maps to `./vendor/three/three.module.js` and `three/addons/` to `./vendor/three/addons/`.
To upgrade, download the same three files at the new version, update this table, and log it in DECISIONS.md.
