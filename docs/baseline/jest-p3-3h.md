# `rive-wasm` jest suite and parity close-out (P3-3h)

P3-3h report: the upstream jest suite run in full on the fork, tied to the inventory domains
(`api-parity-p3-3.md`), and the list of upstream defects and limits noted from P3-3b to P3-3g.

## Context

Build prerequisites: `runtime/build/build_rive.sh ninja release wasm` first (installs emsdk, premake and
premake-ninja, `AGENTS.md`), premake5 in the `PATH`, and on Windows a replacement `getconf` in the
`PATH` (`web/build_webgl2_package.sh`, lines 39 to 44, creates one).

| Item | Value |
|---|---|
| Date | 2026-10-17 |
| Build | `OUT_DIR=build/canvas_advanced_single/bin/release ./build_wasm.sh -w -c -s release` in `web/rive-wasm/wasm` (command from `build_all_wasm.sh`), `RIVE_WASM_BUILD_SYSTEM=ninja`, emsdk 4.0.23; a single compile process because `build_wasm.sh` reads `getconf _NPROCESSORS_ONLN` and a replacement `getconf` reported 1 (`TWEENORA_JOBS` is only read by `web/build_webgl2_package.sh`) |
| Build duration | 21 min 40 s (662 ninja steps, a single compile process), finished without error |
| Output | `canvas_advanced_single.mjs`, 3,676,821 bytes (the `.wasm` is embedded in the `.mjs`), copied to `web/rive-wasm/js/npm/canvas_advanced_single/` (ignored by git) |
| Memory | 1.7 GB of free physical memory out of 15.9 GB at launch (test browser closed); the build succeeded, no peak measurement |
| Suite | `npm test` in `web/rive-wasm/js`: **28 suites, 486 tests, 0 failures** (35 s) |

## Results by suite and by domain

| Inventory domain | Suites (tests) |
|---|---|
| P3-3b Loading and reading | `initialisation` (33), `rivefile` (10), `artboard` (5), `taskQueue` (1), `deferredRendering` (17), `outOfBand` (10), `deprecationWarnings` (9) |
| P3-3b Accessibility (lines classified as b) | `accessibilityOverlay` (102), `semanticTreeModel` (33), `semanticsMode` (3) |
| P3-3c Animations, state machines, events, pointers, keyboard | `playback` (6), `playbackStates` (2), `stateMachine` (16), `events` (18), `registerTouchInteractions` (39), `registerKeyboardInteractions` (68), `keyMap` (27), `focusManagement` (14), `directionalFocus` (10), `textInputSession` (17) |
| P3-3d Data binding | `data_bind` (12), `global_view_models` (7) |
| P3-3e Text and layout | `text` (5), `nested_text` (9), `fallback_fonts` (1), `layout` (7), `resonsive_layout` (4) |
| P3-3f Audio | no jest suite |
| P3-3g Scripting | `scriptingWithoutTools` (1) |

## Deviation fixed in `web/rive-wasm`

`test/helpers.ts` looked for `runtime/` three levels above `test/` (the layout of the Rive monorepo).
In Tweenora, `runtime/` is four levels above: `scriptingWithoutTools.test.ts` failed with
`The "path" argument must be of type string. Received undefined`. The four-level path is tried
first; one line is added to the register of `web/UPSTREAM.md`. It was the only failure of the 28 suites.

## What does not run

- `npm run test:scripting` (`jest.scripting.config.js`): fails at load time
  (`Could not locate module ./rive_advanced.mjs`). It requires the `canvas_scripting_single` variant
  (`./build_wasm.sh -s -w -t release`), that is, in addition to `-s -w`, the `-t` option (unsigned
  script modules), which upstream says exists only in its monorepo. Not tried: no inventory
  line depends on it (`scripting-p3-3g.md`).
- No suite covers audio: P3-3f relies only on the examples and on listening
  (real listening, outside scripted scenarios).

## Upstream defects and behaviors noted

Observed through the P3-3b to P3-3g examples, not fixed (the fork follows upstream, D7):

1. `Rive#disableFPSCounter` throws "this.runtime.disableFPSCounter is not a function": `wasm/js/webgl2_renderer.js`
   does not assign `Module.disableFPSCounter` (`renderer.js` does).
2. `EventType.Draw` is emitted by no code in the package.
3. Three defects in `Rive`: `load({ shouldDisableRiveListeners })` ignores this field (only read in the
   constructor); `setupRiveListeners({ isTouchScrollEnabled })` does not rewrite `Rive#isTouchScrollEnabled`;
   `Rive#load` does not keep the original `artboard`.
4. In `nested_events.riv`, only the parent's event reaches JavaScript; those of the child artboard
   are not delivered.
5. `LoopType.OneShot` is never emitted by `onLoop`.
6. Each view model accessor (`string(path)`...) returns a new object: `off()` only unregisters if
   it is called on the object that set `on()`.
7. `DataType` has no `font` member, although `properties` returns the `font` type;
   `BindableArtboard#destroy` has no effect with `getBindableArtboard` (`selfUnref` false).
8. Replacing `GlobalLabels` or `GlobalColors` with the "Override" instance (`setGlobalViewModelInstance`) returns
   true without changing the observed render (other globals not tried).
9. Audio: a volume written before the user gesture is lost; `decodeAudio` does not reject invalid
   bytes (log "Invalid file"); `EventType.AudioStatusChange` is internal.
10. `resizeToCanvas` only acts on the layout bounds; the mouse wheel is not handled.
11. A view model value is only applied to the drawing if a state machine is playing (without `stateMachine`,
    the default linear animation does not read the view model); the `on` callbacks only fire in the
    draw loop and the trigger's is called without an argument.
12. The user gesture (`pointerdown`) enables the package's audio without calling `resume()`: the actual state of
    the `AudioContext` after the click depends on Chrome.
13. `grid_2x2.riv` only has "Auto Generated State Machine": it must be named, otherwise "State Machine with name
    State Machine 1 not found".
14. Strings still visible that say "Rive" (`[Rive: ...]` prefixes, `rive-a11y-N` identifiers, default
    `.wasm` URL on unpkg and jsdelivr): fall under the D6 convention (upstream API identifiers kept or renamed), to be validated, and under P3-4.

## Limits of the examples

- Renders compared by hash of captures and by values read: Playwright cannot hear sound and has no
  GPU (slow rendering on large files); real listening and visual judgment of the scripting examples cannot be scripted.
- No example for editable text (`text_input*.riv`, no public input API), the
  `*StateAtPath` (no asset with a nested input), `OpenUrl`, multi-touch, pointer exit,
  the `layout_scroll_*` assets other than `layout_scroll_vertical`.
- Still to do on the examples side: the common bootstrap of the 25 pages (`ex.open()`, `ex.input()`, `ex.show()`), which requires replaying the capture scenarios.
- The 521 inventory lines are classified (364 demonstrated, 157 not demonstrated with their reason); the
  D6 convention remains to be validated by the user.
