# `@tweenora/webgl2` package (P3-2)

P3-2 report: Rive's WASM and JavaScript layer (`rive-wasm`) imported into
`web/rive-wasm/`, built against the fork's `runtime/`, and the npm package
`@tweenora/webgl2` produced by `npm pack`, installed in an empty directory and
tried in a browser.

## Context

| Item | Value |
|---|---|
| Date | 2026-10-16 |
| `rive-wasm` license | MIT, Copyright (c) 2020-2021 Rive (text read in `web/rive-wasm/LICENSE`) |
| `rive-wasm` base | `589b787c8a50b528db0071d9bc22e6b21ab13604` (2026-10-12), tag `rive-wasm-base/589b787c`; its submodule pinned `daf55385`, the base of `runtime/` |
| Import | `git subtree add --prefix=web/rive-wasm`, without `--squash`, 2891 commits of history |
| Tools | emsdk 4.0.23 (the one from P3-1, reused), premake 5.0.0-beta7, Ninja 1.13.2, Node 24, webpack 5.97.1 |
| Package | `@tweenora/webgl2` 0.1.0, `tweenora-webgl2-0.1.0.tgz`: 2.5 MB, 24 files, 7.2 MB unpacked |
| Package files | `rive.js` (558 kB), `rive.js.map`, `rive.d.ts`, `rive_advanced.mjs.d.ts`, `runtimeLoader.d.ts`, `semantics/`, `utils/`, `rive.wasm` (2,889,392 bytes), `rive_fallback.wasm` (2,850,397 bytes, no SIMD), `LICENSE`, `README.md`, `package.json` |

## Verified command

After a runtime build by `runtime/build/build_rive.sh` (which installs premake,
premake-ninja and emsdk, see `AGENTS.md`), from Git Bash at the repository root:

```bash
bash web/build_webgl2_package.sh
```

The script builds the two WASM variants (`webgl2_advanced`, with and without
SIMD), checks their compatibility (`verify_fallback_abi.py`), assembles the package
with webpack (`npm run build -- --env targets=webgl2`) and runs `npm pack`. The
`.tgz` is written to `web/rive-wasm/js/build/pack/` (ignored by git).
`TWEENORA_JOBS` sets the number of parallel builds (4 by default; 12
exhausted the machine's memory). `--no-wasm` skips the build. First
full run: about 10 to 12 minutes per variant with 4 jobs; a run
with no changes takes 15 to 25 seconds. The script installs the JavaScript
dependencies (`npm ci`) if `node_modules` is missing.

## Results

- **Build**: 949 ninja steps for each variant, 0 errors; the
  compatibility of `rive_fallback.wasm` with `rive.wasm` is confirmed (186
  imports, 32 exports, 1518 data segments).
- **Installation**: `npm install tweenora-webgl2-0.1.0.tgz` in an empty directory
  installs `@tweenora/webgl2` 0.1.0 (MIT license, `main` = `rive.js`).
- **In a browser** (page `web/p3-2-check/index.html`, package installed,
  `RuntimeLoader.setWasmUrl("rive.wasm")`, Chrome driven by Playwright):
  `new rive.Rive({ src, canvas, autoplay })` loads `two_artboards.twno` and its
  `.riv`, the state goes to `drawing`, no console errors. The two captures
  (929 × 861) have **0 pixels of difference**; background `(49, 49, 49)`, rectangle
  `(116, 116, 116)`, like the native player of P3-1.
- **Rich file**: `echo_show_demo.riv` (images, gradients, fonts, text,
  animation) is drawn correctly by the JavaScript API. Only message: an upstream
  deprecation warning (`[Rive: default-state-machine]`).
- **Package unit tests** (`jest`): 3 suites out of 28 run, 162 tests
  passed. The other 25 do not start: their configuration replaces
  `rive_advanced.mjs` with the `canvas_advanced_single` variant, a third
  build (about 15 minutes) that the machine could not finish for lack of
  memory. They were therefore **not run**, including the two tests whose message was
  adapted (`initialisation.test.ts`, `text.test.ts`).

## Pitfalls encountered (Windows, Git Bash)

1. `build_wasm.sh` downloads a Linux premake on MINGW: put `premake5.exe`
   (the one from `runtime/build/dependencies/premake-core`) on the PATH.
2. It clones a second emsdk (640 MB) into `wasm/bin`: a junction to the runtime's one
   avoids this (created by the helper script).
3. `getconf` is missing: the job count is empty and `make -j` or `ninja -j`
   fail, or run with unlimited parallelism. The helper script provides a
   temporary `getconf`.
4. GnuWin32's `make` is in a path with spaces and parentheses, which
   `$(MAKE)` cannot relaunch; and even once fixed, `make` truncates the archive
   command of 1500 objects (32 kB command line limit). Hence the
   switch to ninja (`RIVE_WASM_BUILD_SYSTEM=ninja`, register deviation).
5. `PREMAKE_PATH` with a trailing colon makes premake lose the `ninja` module:
   no trailing separator.
6. Closure reads a `/c/Users/...` path as a directory `c` at the root of `C:`:
   `pwd -W` (register deviation).
7. Linking does not track the `--pre-js` file: after a change in
   `wasm/js/*.js`, delete `webgl2_advanced.mjs` and `.wasm` to force the link
   (noted by upstream in `build_wasm.sh`).
8. Without `web/.gitattributes`, `core.autocrlf` turns the scripts into CRLF and `bash`
   rejects them.

## Limits

- The package name changes, not the API: the `Rive` class, `RiveFile`, `RiveError`,
  the `rive` global and the `rive.js` and `rive.wasm` files are upstream's,
  as are the `rive.app/docs` links in the JSDoc comments shipped in `rive.js`
  and in the `.d.ts` files (see `web/UPSTREAM.md`). The task asked for "no Rive name
  visible outside legal notices": respected for the package metadata, its
  documents, the links and the advice that cited other Rive packages;
  **not respected** for the API, the comments and part of what the
  package emits: `[Rive]` and `Rive:` log prefixes (accessibility,
  deprecation warnings, GPU rendering), the message "Rive source file or
  data buffer required", `rive-a11y-N` DOM identifiers, `rive:*` performance
  marks, deprecation identifiers such as `rive-events`. The
  `rive.wasm` binary also contains the URL `https://public.rive.app/cdn/uuid` (Rive's
  domain): to be handled with P3-4 (no request outside our domain).
- The default `.wasm` URL (`unpkg.com/@tweenora/webgl2@0.1.0/rive.wasm`)
  only exists after publication; the check page points to the local copy.
  Self-hosting is P3-4.
- The third-party libraries linked into the `.wasm` (harfbuzz, yoga, miniaudio,
  SheenBidi, Luau...) have their notices in their repositories; they are not
  copied into the package, as in the upstream package. To be settled before any
  publication (`NOTICE` only covers `runtime/tests/**/dependencies`).
- The browser captures are not all versioned: only
  `wasm-p3-2-two-artboards.png` (`.twno` version) is; the comparison with the
  `.riv` (0 pixels of difference) can be redone with the procedure above.
- Only one variant is packaged: `webgl2`. The upstream `canvas`, `canvas-lite`
  and `canvas-single` packages are not produced.
- The rendering path is that of the test browser (WebGL2 via ANGLE on
  Direct3D 11), with the MSAA fallback noted in `wasm-build-p3-1.md`.
