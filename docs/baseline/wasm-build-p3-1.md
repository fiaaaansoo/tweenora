# WASM build and rendering in a browser (P3-1)

P3-1 report: the fork's runtime built to WebAssembly with the WebGL2 GPU
rendering engine (D11), and a file drawn in a browser, as `.twno` and
as `.riv`.

## Context

| Item | Value |
|---|---|
| Date | 2026-10-16 |
| Commit | `dc5f17d2` (`main`), working branch of the phase 3 batch |
| No `runtime/` deviation | the build and the file loading required no modification of `runtime/` (no D15 deviation) |
| emsdk / Emscripten | 4.0.23 (`emcc` 4.0.23, clang 22.0.0git, Node 24.19.0 provided by emsdk), installed by `build_rive.sh` in `runtime/build/dependencies/emsdk_4.0.23` (ignored by git) |
| premake | 5.0.0-beta7, downloaded by the script into `runtime/build/dependencies/premake-core` |
| Ninja | 1.13.2 |
| Host | Windows 11 Pro, Git Bash (`sh.exe`), Python 3.14 |
| Verification browser | Chrome 155 driven by Playwright, WebGL2 via ANGLE on Direct3D 11 (NVIDIA GeForce RTX 3060) |
| clang-cl | **not needed**: the WASM uses emsdk's clang. Visual Studio's clang-cl component, absent, does not block P3-1 |

## Verified command

From a Git Bash shell, in `runtime/tests`:

```bash
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.longpaths GIT_CONFIG_VALUE_0=true
sh ../build/build_rive.sh ninja release wasm player
```

The plan's command, `build_rive.sh ninja release wasm`, gives the same build.
The word `player` in the verified command is not a ninja target: the script puts it
among the premake arguments, where it has no effect (the `player` target
is declared unconditionally in `runtime/tests/premake5.lua` and is already
part of the default target of `build.ninja`). The build always produces
`player`, `goldens`, `gms` and `bench`. It stayed in the command because
the `out/wasm_release` directory was configured with it: the script refuses to
rerun an existing directory with other arguments. On a fresh directory,
omit it; the equivalence was not verified by a second build.

| Step | Result |
|---|---|
| First run | 1258 ninja steps out of 1258, exit code 0, 15 minutes end to end (21:27 to 21:42): download of premake and emsdk (one file of 641,817,859 bytes), then build |
| Outputs | `runtime/tests/out/wasm_release/`: `player.js` 395 kB, `player.wasm` 11.6 MB, `player.html`, and `bench`, `gms`, `goldens` (`.js` + `.wasm`, 9 to 11 MB) |
| Relink of `player` with `FS` exported | 1 step, a few seconds (see "Loading a file") |

## What the `.wasm` draws

Verification page: `web/p3-1-check/index.html`. It loads `?file=<url>`,
writes the bytes into the module's in-memory file system (`/scene.twno` or
`/scene.riv`), sets the `-b gl` argument in the URL hash (this is how
`rive_wasm_app.cpp` receives its arguments), then runs `player.js`. Its state
can be read in `window.twnoCheck.state` and in the page title:
`loading`, `loaded` (file written, `player.js` launched), `drawing` (the player
wrote `Drawing 1 copies of ...`), `error` (file not found, `Module.FS`
missing, `Bad header`, uncaught exception) or `aborted`. Only `drawing`
indicates a file that is actually supported.

Test file: `runtime/tests/unit_tests/assets/two_artboards.riv`, and its
`.twno` version produced by `tools/twno_convert.py`.

- **Rendering**: gray background `(49, 49, 49)`, gray rectangle `(116, 116, 116)` (the
  schema's default color `0xFF747474`) centered, and the FPS counter drawn
  by the runtime (text rendering works). Capture:
  [`wasm-p3-1-two-artboards.png`](wasm-p3-1-two-artboards.png) (`.twno` version,
  929 × 861 window).
- **Module log**: `GL GPU: ... WebGL`, `Drawing 1 copies of /scene.twno
  at 929 x 861`, then about 240 frames per second.
- **`.riv` and `.twno`**: identical captures, **0 pixels of difference** outside
  the FPS counter area (pixel-by-pixel comparison, 929 × 861).
- **Responsive**: default window of 929 × 861 (desktop), 768 × 1024
  (tablet) and 390 × 844 (mobile): the canvas follows the window, the rectangle
  stays centered.
- **Console errors**: `The root document of this element is not valid
  for pointer lock` comes from the player requesting pointer lock, with no
  consequence. `rive: no interlock mode supports this frame, drawing it in
  depthStencil with 4x MSAA` is written by the renderer: the test browser
  (ANGLE on Direct3D 11) offers no interlock mode, and the frame is
  drawn through the MSAA fallback path. D11 chooses WebGL2 for its full
  rendering (feathering in particular); what this fallback path renders of these
  effects is not verified here (see "Limits"). A static server adds a
  `favicon.ico` 404 if the page has no icon; the page declares an empty one.
- **Page error cases**, tested: `?file=absent.riv` gives the `error` state
  (`HTTP 404`), and an HTML page served under `?file=` gives `error` (`Bad
  header`) while the player then throws an exception. The absence of the
  `?file=` parameter is handled by the code but was not tried.
- **Other files**, tried during the independent review: `echo_show_demo.riv`
  (3 MB, images, gradients, fonts and text) is drawn correctly (photo,
  gradient screen, icon, text "06:11 / 31° | Wed, 12 Apr") at about
  236 frames per second; `jellyfish_test.riv`, `events_on_states.riv` and
  `script_create_text_runs.riv` launch without error, their pixels were not
  examined.

## Loading a file: the file system pitfall

The WASM player does not take a file as an argument as it does natively: it reads it
through `std::ifstream` or through the test server (`--test_harness`, a
WebSocket bridge from `deploy_tests.py`). Without a server, the file must be written to the
module's in-memory file system before `main`, which requires `Module.FS`.
The link in `runtime/tests/rive_tools_project.lua` does not export `FS`
(`-sEXPORTED_RUNTIME_METHODS=ccall,cwrap,HEAPU8,HEAPU32`).

Workaround without touching `runtime/`: the `EMCC_CFLAGS` environment variable,
which `emcc` adds to every invocation and in which the last `-s` wins:

```bash
rm out/wasm_release/player.js out/wasm_release/player.wasm
EMCC_CFLAGS="-sEXPORTED_RUNTIME_METHODS=ccall,cwrap,HEAPU8,HEAPU32,FS" \
  sh ../build/build_rive.sh ninja release wasm player
```

The outputs must be deleted so that ninja relinks (the variable is not in
the command line tracked by ninja). The script arguments must stay
identical to those of the first build, otherwise it refuses (`premake5 arguments ... do
not match`). The relink takes a few seconds.

## Reproducing the verification

```bash
SITE=/tmp/twno-site && mkdir -p $SITE
cp runtime/tests/out/wasm_release/player.js runtime/tests/out/wasm_release/player.wasm $SITE/
cp web/p3-1-check/index.html $SITE/
cp runtime/tests/unit_tests/assets/two_artboards.riv $SITE/
python tools/twno_convert.py $SITE/two_artboards.riv -o $SITE/two_artboards.twno
cd $SITE && python -I -m http.server 8765 --bind 127.0.0.1
```

Then open `http://127.0.0.1:8765/index.html?file=two_artboards.twno` (or
`.riv`). A server that serves `.wasm` with the `application/wasm` type is
required; Python 3.14's `http.server` does.

## Limits

- The pixel-by-pixel comparison covers a single, simple file
  (`two_artboards`). Text, images and gradients are drawn
  (`echo_show_demo.riv`), but the behavior of state machines was not
  exercised, and Luau scripts are probably not executed (the default build
  does not have the scripting option; not verified). Proof of rendering parity with
  the official runtime is the subject of phase 4.
- The test browser has no interlock: the frame goes through the MSAA
  fallback path. The rendering of advanced effects on the interlock path
  and on this one is to be compared in phase 4.
- The backend is `-b gl` (WebGL2). WebGPU (`--with-webgpu`) is not used
  (D11).
- The verification was done in a browser driven by Playwright, not in
  continuous integration; it is not automated in the repository (the JavaScript layer
  and the browser tests arrive with P3-2 to P3-5).
- Building in a worktree with a long path requires `core.longpaths` for the dependency
  clones (environment variables above).
