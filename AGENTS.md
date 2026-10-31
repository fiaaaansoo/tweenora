# AGENTS.md — Tweenora

Invariants guide + repo map for any agent (Claude Code or other) working on
this project. The full context is in `PLAN.md`, which is kept in the working repository.

## Stack

No project-specific code yet. Verified on 2026-10-13:

- **Reference** (`vendor/rive-runtime`, MIT, commit `daf55385`): C++
  (`cppdialect('C++17')` in `build/rive_build_config.lua`), premake5 build
  via `build/build_rive.sh` / `build_rive.ps1`, Luau scripting, C++ unit tests
  in `tests/unit_tests`, file format 7.4.
- **Planned** (`PLAN.md`, decisions D2, D3, D11, D12): C++ fork of the runtime,
  web runtime WASM + JS (emsdk 4.0.23, WebGL2 GPU rendering), Flutter editor
  with a C++ core called through `dart:ffi` (desktop) or in WASM (web), Python
  tools.
- **Reference environment**: git 2.53, Python 3.14, Node 24 / npm 11, Visual Studio 2022
  Community (MSVC 14.44), Ninja 1.13, `sh.exe` (Git for Windows) on the PATH.
  **Build toolset: `msc` (MSVC)**: the clang-cl component of VS is not
  installed there. Upstream builds with clang on Windows, so a rendering parity
  gap remains possible; the same toolset is used in P0-4. The WASM build
  (P3-1) does not need clang-cl: it uses emsdk 4.0.23's clang, which
  `build_rive.sh` installs itself. Flutter in P5-1.

## Repository map

```text
(root)                    repository fiaaaansoo/tweenora
  README.md               technical overview and folder map
  PLAN.md                 project plan: decisions, phases, tasks Px-y
  PRODUCT.md              product summary
  docs/NOM.md             name check (Motio abandoned, Tweenora chosen)
  docs/UPSTREAM.md        tracking of rive-runtime: base, merge procedure
  vendor/rive-runtime/    shallow reference checkout, read-only, untracked
  runtime/                fork of rive-runtime (git subtree, base: docs/UPSTREAM.md)
  web/                    (phase 3) WASM runtime + npm package + demo
  platforms/              (phase 5) Flutter, Unity, Unreal, etc. runtimes
  editor/                 (phase 6) Flutter editor
  server/                 (phase 7) cloud
  tools/                  (phases 1-4) twno-convert, twnoinfo, schema extractor
```

## Verified commands

Debug build of the runtime (verified on 2026-10-14: 0 errors, 34 warnings,
about 4 min the first time, dependencies included). From PowerShell:

```powershell
cd runtime\tests
$env:GIT_CONFIG_COUNT='1'; $env:GIT_CONFIG_KEY_0='core.longpaths'; $env:GIT_CONFIG_VALUE_0='true'
powershell -ExecutionPolicy Bypass -File ..\build\build_rive.ps1 --toolset=msc *> $env:TEMP\build.log
```

Prerequisites and pitfalls:

- Visual Studio 2022 (MSVC) and `sh.exe` on the PATH (`C:\Program Files\Git\bin`).
- Run from an ordinary PowerShell, `cd runtime\tests` being relative to the
  repository root. In a Developer PowerShell, `fxc` is already on the PATH, so
  `build_rive.ps1` skips `setup_windows_dev.ps1`, which is the one that adds
  `runtime\build` to the PATH: `sh build_rive.sh` is then no longer found.
- `core.longpaths=true` must be active in the repositories the build clones: the
  local `core.longpaths` of the main repository (see `docs/UPSTREAM.md`) does not
  apply to them, and without it the harfbuzz clone fails at checkout (paths
  longer than 260 characters, made worse by the worktree folder). The
  environment variables above enable it without touching the global Git config.
- `build_rive.ps1` does not propagate the build's exit code (it is 0 even on
  failure): always read the log. Under Windows PowerShell 5.1, `*>` writes it
  as UTF-16: use
  `Select-String -Path $env:TEMP\build.log -Pattern 'error|fatal|Erreur'`
  rather than `grep` (on a French-locale machine the MSBuild summary says
  `Erreur(s)`).
- Outputs in `runtime/tests/out/debug/` and `runtime/tests/dependencies/`,
  ignored by `.gitignore`. Since P1-3, the libraries produced are called
  `tweenora.lib`, `tweenora_pls_renderer.lib`, `tweenora_decoders.lib`, ... (the
  premake projects keep their `rive*` names); the `rive*.lib` files from an
  earlier build are stale.
- `player.exe`: `..\build\build_rive.ps1 --toolset=msc -- player` from
  `runtime\tests`, then `out\debug\player.exe -b gl <file> [--dump output.raw
  --dump-frame 3]`. The default backend (`vk`) fails on this machine and `d3d`
  requires "Graphics Tools": always `-b gl`.

Runtime unit tests (full baseline: `docs/baseline/unit-tests-daf55385.md`).
With the same variables and the same PATH as the build, from
`runtime/tests/unit_tests`:

```powershell
.\test.bat --toolset=msc -m "glsl_mix"
.\out\debug\unit_tests.exe --% ~"synthesizedFailureType" ~"ore binds a fragment compiled apart from its vertex" ~"ore layouts declare non-filtering samplers for depth-only use" ~[.]
```

The first command builds, then runs a test or a Catch filter (`-m`). The
second runs the whole default suite except 3 tests (2590 tests, about 143 s; 2605 before the removal of 7 cases, then 2598, 2596 and 2592 before those of 2, 4 and 2 cases, which read third-party files,
`All tests passed`); it assumes a prior build by `test.bat`, and
`--%` is required under Windows PowerShell 5.1.

- `rive_native/` and `texture_compressor/` are absent from Rive's public repository:
  the `premake5.lua` of `unit_tests` tests for them and, if they are missing, excludes 10 test
  cases (`texture_compressor_test` 7, `fence_wait_thread_test` 3), which are not covered
  (D15 deviation in `docs/UPSTREAM.md`, baseline: 2597 passed).
- 3 tests crash the process as long as the Windows "Graphics
  Tools" feature is absent (`d3d11sdklayers.dll`), hence the filter above. A
  purely negative filter without `~[.]` adds hidden benchmarks that crash
  as well.

WASM build of the runtime (verified on 2026-10-16: 1258 ninja steps, 0 errors,
about 15 minutes the first time, emsdk included). From Git Bash, in
`runtime/tests`; full report: `docs/baseline/wasm-build-p3-1.md`:

```bash
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.longpaths GIT_CONFIG_VALUE_0=true
sh ../build/build_rive.sh ninja release wasm
```

The verification of 2026-10-16 was done with one extra word, `player`, with no
effect (a premake argument); an already configured `out/wasm_release` folder requires
the same arguments on every run.

- No clang-cl and no manual installation: the script downloads premake
  5.0.0-beta7 and clones emsdk 4.0.23 (Emscripten 4.0.23, clang 22, Node 24 provided)
  into `runtime/build/dependencies/`, ignored by git. Ninja must be on the PATH.
- Outputs in `runtime/tests/out/wasm_release/` (ignored via `out/`):
  `player.{js,wasm,html}`, `goldens`, `gms`, `bench`. If the arguments change
  from one run to the next, the script refuses: `clean` first.
- The WASM player receives its arguments through the URL hash (`#-b%20gl%20<file>`)
  and reads the file from the module's in-memory file system. To be able to write
  into it from a page, relink `player` with
  `EMCC_CFLAGS="-sEXPORTED_RUNTIME_METHODS=ccall,cwrap,HEAPU8,HEAPU32,FS"` after
  deleting `player.js` and `player.wasm` (without modifying `runtime/`); the
  script's arguments stay those of the first build.
- Verification page: `web/p3-1-check/index.html?file=<url>`, served with an HTTP
  server that gives `application/wasm` to `.wasm` files
  (`python -m http.server` works). Backend `-b gl` (WebGL2).

Web package `@tweenora/webgl2` (verified on 2026-10-16; report:
`docs/baseline/wasm-package-p3-2.md`). After the runtime build above
(it installs premake, premake-ninja and emsdk), from Git Bash at the root:

```bash
bash web/build_webgl2_package.sh            # both .wasm files, the bundle, npm pack
bash web/build_webgl2_package.sh --no-wasm  # bundle and pack only
```

- The `.tgz` is in `web/rive-wasm/js/build/pack/` (ignored). `TWEENORA_JOBS`
  sets the number of compilations (4 by default: 12 exhausted the machine's
  16 GB). About 10 to 12 minutes per variant the first time, 14 seconds
  after that.
- The build goes through ninja (`RIVE_WASM_BUILD_SYSTEM=ninja`): Windows `make`
  truncates the archiving command. The deviations from `rive-wasm` are in
  `web/UPSTREAM.md`.
- Test page: `web/p3-2-check/index.html?file=<url>` with `rive.js`,
  `rive.wasm` and `rive_fallback.wasm` of the installed package in the same folder.
- API examples: `python web/examples/prepare_assets.py` then
  `python web/examples/serve.py` (http://127.0.0.1:8765/loading/). The `.riv` files
  copied from upstream and their `.twno` go into `web/examples/assets/` (ignored
  by git). Browser scenarios go through the `playwright` MCP;
  details in `web/examples/README.md`.
- Demo page: `python web/examples/serve.py` then http://127.0.0.1:8765/demo/ (`web/demo/README.md`).
- JavaScript API parity: `node web/parity/api-inventory.mjs` regenerates the inventory
  (`--check` verifies), `node --test web/parity/api-inventory.test.mjs` tests it;
  upstream's jest suite (28 suites) requires the `canvas_advanced_single` variant
  built with `-w -c -s` (a single compile job, about 22 minutes) then
  `npm test` in `web/rive-wasm/js`; command and prerequisites: `docs/baseline/jest-p3-3h.md`.
- Native render parity, fork versus official (verified on 2026-10-20 over 491 files, recounted without the 16 third-party files removed since: 475 files, 5244 renders pixel-identical
  out of 5265, 15 non-deterministic, 6 common failures, 0 deviations; report
  `docs/baseline/parity-p4-1-rendu.md`). From an ordinary Windows PowerShell at the root, build the
  two `goldens` (`tools\parity\build_goldens.ps1`, `-Config release -NoLto` for release: the link with
  LTO fails), then render and compare:

  ```powershell
  powershell -ExecutionPolicy Bypass -File tools\parity\build_goldens.ps1
  python -I tools\parity\render_compare.py --all --jobs 3 --checkpoint tools\parity\.work\riv.jsonl
  python -I tools\parity\render_compare.py --all --format twno --jobs 3 --checkpoint tools\parity\.work\twno.jsonl
  python -I -m unittest discover -s tools\parity\tests
  ```

  About 85 minutes per format in debug; `--config release`, `--files <paths>` or `--sample 40`
  shrink the campaign. Exit code 1 on any unexplained deviation. The official build lives in
  `tools/parity/.ref/` (never in `vendor/`); details: `docs/baseline/parity-p4-1-banc.md`,
  `parity-p4-1-harnais.md`.
- Web render parity against native (measured on 2026-10-20, not closed: 47 comparisons out of 68 pixel-identical at
  `goldens -b angle_d3d`, 19 structural over 10 files whose causes are in
  `docs/baseline/parity-p4-1-web.md`): extract the package (`python -I web/parity/prepare_package.py --tgz
  <package>`), render the native goldens (`python -I tools/parity/web_goldens.py`, backend `angle_d3d`, then
  `--backend d3d --out tools/parity/.work/web/golden-d3d`), serve (`python -I web/parity/serve.py`, port 8766) then,
  with the `playwright` MCP, evaluate `window.parity.run` on `http://127.0.0.1:8766/render.html`; tests: `node --test
  web/parity/render-compare.test.mjs`. Do not use `-b gl` for the web: the native 1600-pixel window loses
  lines.
- Native state machine parity (trace harness, P4-2a; `docs/baseline/parity-p4-2-harnais.md`): after
  `build_goldens.ps1 -Config release -NoLto`, `powershell -ExecutionPolicy Bypass -File
  tools\parity\sm_trace\build_sm_trace.ps1` then `python -I tools/parity/run_trace.py` (4 cases, exit code 1 on any
  trace deviation). On all state machine files of the manifest (P4-2b, verified on 2026-10-20: 388 traces
  identical out of 389, 1 common failure, 0 deviations; `docs/baseline/parity-p4-2-state-machines.md`):
  `python -I tools/parity/sm_compare.py` then `--format twno` (about 6 seconds each, exit code 1 on any deviation).
- Web state machine parity (P4-2c, verified on 2026-10-20: 67 files, 67 traces identical on inputs and
  events, including 5 third-party files since removed from the repository (62 remain); `docs/baseline/parity-p4-2-web.md`): `python -I tools/parity/sm_web_prepare.py`, server
  `python -I web/parity/serve.py`, then `window.paritySm.run` on `http://127.0.0.1:8766/sm.html` with the `playwright` MCP
  (write the traces as `<id>.web.jsonl`) and `python -I tools/parity/sm_web_compare.py`.

## Code rules

- **Measured parity above all**: the goal is rendering and state machine
  behavior that conform to those of the upstream runtime, verified by
  measurements published with their limits (`README.md`, `docs/baseline/parity-p4-*`), with
  no promise beyond that. Any change to the runtime keeps the unit tests and
  the parity tests (phase 4) green; an observed difference is a bug.
- **Minimal renaming** (D6): only the signature, the extension, the packages,
  the libraries produced and the visible texts change. The C++ namespace `rive`
  and the internal symbols stay as they are, so that Rive's updates can be
  merged without conflicts.
- **Minimal diff with upstream**: group Tweenora-specific changes, avoid
  gratuitous reformatting and renaming in Rive's code.
- **Format**: signature `TWNR`, extension `.twno`. The runtime and the editor
  also read `.riv` files (D5); we always write `.twno`.
- **Tweenora-specific keys**: `typeKey` and `propertyKey` in the
  `50000–59999` range (D8), never in Rive's range.
- **`vendor/` read-only**: nothing is modified there, work happens in the
  fork.
- **Forbidden**: decompiled code from a third-party editor, third-party assets,
  and a third-party name or logo visible to the end user (except legal notices).

## Secrets and boundaries

See [`SECURITY.md`](SECURITY.md): no secrets in the repository, `.twno`/`.riv`
files treated as untrusted, no proprietary third-party content.

## Documentation routing

- Plan, decisions and upcoming tasks: `PLAN.md`.
- File format: `docs/FORMAT_TWNO.md`; inventory of `.riv` files: `docs/INVENTAIRE_RIV.md`.
- Product vision / scope: `PRODUCT.md`.
- Contribution conventions: `CONTRIBUTING.md`.
- Security limits: `SECURITY.md`.
- Name and trademark: `docs/NOM.md`.
- Upstream tracking (`upstream`, merges into `runtime/`): `docs/UPSTREAM.md`.

## Continuous integration

The `.github/workflows/tests.yml` workflow (Windows, `--toolset=msc`) runs the fast Python and Node tests and then the runtime unit suite with the filter of the command above. Its jobs are skipped as long as the repository is private (`if: ${{ !github.event.repository.private }}`) so as not to consume minutes. Report and estimate: `docs/baseline/ci-p4-3.md`. The heavy suites (WASM build, upstream jest) are not on the push path.
