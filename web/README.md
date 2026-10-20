# web/

Tweenora web runtime: a WASM build of the runtime with the WebGL2 GPU
renderer (D11), the JavaScript layer, the npm package and a self-hosted demo
page. Planned for phase 3 (`PLAN.md` § 5, P3-x).

## Status

- `p3-1-check/index.html`: minimal page that loads a `.twno` or a `.riv`
  (`?file=<url>`) in the WASM player built from the fork (P3-1). Procedure and
  results: `docs/baseline/wasm-build-p3-1.md`. It is neither the demo nor the
  JavaScript layer (P3-2 to P3-5).
- `rive-wasm/`: Rive's WASM and JavaScript layer, imported with `git subtree`
  and compiled against `runtime/` (P3-2). `UPSTREAM.md` gives the base, the
  tracking method and the register of deviations. `build_webgl2_package.sh`
  produces the `@tweenora/webgl2` package, and `p3-2-check/index.html` tries it
  in a browser.
- `parity/`: inventory of the package's JavaScript API (P3-3a). `node
  web/parity/api-inventory.mjs` reads the `rive.d.ts` of the built package with
  the TypeScript compiler from `rive-wasm/js/node_modules` (`npm ci` in
  `web/rive-wasm/js`), updates `parity/api-inventory.json` (the equivalent,
  example, status, reason and subtask columns entered by hand are kept) and
  regenerates `docs/baseline/api-parity-p3-3.md`. `--check` fails if either
  is stale, `--dts <file>` reads another `.d.ts`, and a hand-entered row that
  disappears from the API makes generation fail unless `--allow-removed` is
  given. Tests: `node --test web/parity/api-inventory.test.mjs` (the extraction
  tests are skipped without TypeScript, and the last four also require the
  built package).
- `demo/`: demo page (P3-5): open a `.twno` or a `.riv`, choose the animation
  and the state machine, set the inputs. See `demo/README.md`.
- `examples/`: runnable examples of the package API, shared tooling
  (`prepare_assets.py`, `serve.py`) and the choice of browser test mode
  (P3-3b). See `examples/README.md`. Tests:
  `python -I -m unittest discover -s web/examples/tests`.
- Upstream jest suite: first build the `canvas_advanced_single` variant (`-w -c -s`, a single
  compile job, about 22 minutes), copy its `.mjs` into `web/rive-wasm/js/npm/canvas_advanced_single/`,
  then run `npm test` in `web/rive-wasm/js`: 28 suites, 486 tests. Command, prerequisites, results and
  upstream defects: `docs/baseline/jest-p3-3h.md`.
