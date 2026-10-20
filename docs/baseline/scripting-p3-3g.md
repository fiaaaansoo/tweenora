# Scripting in the `@tweenora/webgl2` package (P3-3g)

P3-3g report: what runs Luau scripts in the package, what requires a different build, and what a browser shows on the upstream files that contain scripts.

## Context

| Item | Value |
|---|---|
| Date | 2026-10-17 |
| Package | `@tweenora/webgl2` 0.1.0: `rive.wasm` 2,889,392 bytes, `rive_fallback.wasm` 2,850,397 bytes |
| Test page | `web/examples/scripting/scripting.html?file=<url>` (`window.twnoCheck`) |
| Assets | `script_inputs_test_1`, `viewmodel_access`, `scripting_linear_animation`, `audio_script` (`runtime/tests/unit_tests/assets/`), as `.riv` and `.twno` |

## What requires what

- **`--with_rive_scripting`: already in the package.** `web/rive-wasm/wasm/build_wasm.sh` puts
  `--with_rive_scripting` in `PREMAKE_HEAVY_FLAGS` along with text, audio and layout; only the `-l`
  option ("lite" variant) removes these options. `web/build_webgl2_package.sh` does not use `-l`, so both
  `.wasm` files of the package (SIMD and non-SIMD fallback) have the Luau VM.
- **Proof in the binary**: both `.wasm` files each contain 18 occurrences of the string "Luau" (mostly
  names of internal VM options: the sources are linked; 0 for `lua_`, the symbols are not exported); `rive.wasm` also contains `ScriptAsset` and
  `bytecode`. Proof of execution: a file with a script draws and reacts in a browser (below).
- **`-w` (`--scripting_vm=both`): already in the package.** `web/build_webgl2_package.sh` builds both
  `.wasm` files with `./build_wasm.sh -w ...` (lines 60 and 65); `-w` adds `--scripting_vm=both`, which defines
  `WITH_RIVE_SCRIPTING_WASM` while keeping Luau (`runtime/premake5_v2.lua`, lines 21 to 40): wasm script
  modules run on the browser's wasm engine alongside Luau (WAMR is not compiled for
  the wasm architecture). The premise of the task ("`-w` missing from the package") was therefore wrong.
- **`-t` (`--with_rive_tools`): absent from the package.** Without it, `HYDRO_SIGN_VERIFY_ONLY=1` is defined
  (`premake5_v2.lua`, line 319): unsigned script modules are rejected. `npm run test:scripting`
  (`jest.scripting.config.js`) requires `-s -w -t` (variant `canvas_scripting_single`):
  `cd ../wasm && OUT_DIR=build/canvas_scripting_single/bin/release ./build_wasm.sh -s -w -t release`. What
  the package lacks for this suite is therefore `-t` and the `-s` variant, not `-w`. The upstream comment says
  this build "only exists in the monorepo"; the useful sources
  (`runtime/src/wasm/web/rive_scripting_pre.js`, `rive_script_runner.mjs`, `rive_module_imports.mjs`) are
  in `runtime/`, but the build was not tried: same memory constraint as `canvas_advanced_single`
  (P3-3h), and no line of the JavaScript API depends on it (P3-3g has no inventory line).
- **`scriptingWithoutTools.test.ts`**: run (`npx jest test/scriptingWithoutTools.test.ts`), it fails when
  loading `canvas_advanced_single.mjs` (`jest.config.js`), like the other jest suites not run in
  P3-2. The file says "This suite's build has no tools" and loads a wasm script module
  (`webScriptingFixture`, `raw_shader.riv`): the `canvas_advanced_single` variant of P3-3h must therefore be
  built with `-s -w` (and without `-t`) for it to run; nothing was run beyond
  loading, its result remains to be established in P3-3h.

## What the browser shows

| Asset | Observation |
|---|---|
| `script_inputs_test_1` | a pentagon drawn by the script appears when the `Trigger` trigger fires; its color follows the `Color` property at the time of the trigger (red, green, blue observed); `Color` alone does not change the capture |
| `scripting_linear_animation` | writing `mode` (text) then `time` (number) changes the capture |
| `viewmodel_access` | the script reads the view model at load time and draws its values (`10`, `10`, `bb`, `321`); writing `num` or `enu` afterwards does not change the capture |
| `audio_script` | loads without error, the seven triggers (`play`, `stop`, `seek`, `readTime`...) produce no error; no error in the browser console (the sound cannot be heard under Playwright: DEV) |

The `.riv` and `.twno` of each asset give the same results.

## Limits

- The JavaScript API exposes no scripting-specific member: scripts run in the `.wasm`
  and read the view model; the examples go through the view model properties (P3-3d).
- No script message was collected from the browser console; the `print` calls of the tested scripts were not looked for.
- The signed files (`*_signed.riv`) were not tried.
