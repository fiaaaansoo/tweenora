# WebGL2 renderer crash: resizing a zero-size canvas

Task `enquete-plantage-webgl2` (Batch E, 2026-10-17).

## Symptom

On `echo_show_demo.riv` (3 MB), the demo crashed with `RuntimeError: memory access out of bounds` in `WebGL2Renderer.flush`, called by `Rive.draw`, `Rive.drawFrame` and then `Rive.resizeDrawingSurfaceToCanvas`, itself called from `onLoad`. After the trap, the instance is unusable.

## Minimal condition (measured)

In the measured cases (three files, one browser), a trap occurs when all three conditions are met:

1. `resizeDrawingSurfaceToCanvas()` is called while one dimension of the canvas is 0 (canvas hidden with `display: none`, or CSS width or height of zero). Measurements: `0×400`, `600×0` and `display:none` crash; `1×1` and `600×400` pass.
2. The instance is a **second** `Rive` created on the same canvas after the `cleanup()` of the first.
3. `autoplay` is true (with `autoplay: false`: no trap).

A first `Rive` alone on a hidden canvas does not crash (the first draw does not happen). The other files tried (`two_artboards.riv`, `multiple_state_machines.riv`) do not crash at zero size.

Reproduction: `web/examples/loading/zero-size.html?file=/assets/echo_show_demo.riv&machine=State%20Machine%201` (hidden canvas, `&visible=1` to make it visible). Before the fix, `twnoCheck.resize` is `RuntimeError: memory access out of bounds`; after, `ok`.

## Cause (JavaScript)

`Rive#draw` already has a "do not draw on a zero-size canvas" guard (`if (!this._hasZeroSize)`). But `_hasZeroSize` is only updated by an asynchronous size observer (`onCanvasResize`). `resizeDrawingSurfaceToCanvas()` sets `canvas.width` and `canvas.height` to 0 and then calls `drawFrame()` synchronously: the observer has not run yet, the guard lets the call through, and the renderer draws into a 0-pixel surface. The C++ renderer then crashes in `flush` on this file. What is established: the JavaScript guard is bypassed. The fragility of the C++ renderer when facing an empty surface, and why it depends on a second `Rive` and on `autoplay`, were not investigated (no build with symbols).

## Fix

`web/rive-wasm/js/src/rive.ts`, `Rive#draw`: the guard also tests the real canvas size (`this.canvas.width > 0 && this.canvas.height > 0`) in addition to `_hasZeroSize`. One line; difference recorded in the register of `web/UPSTREAM.md`. When the canvas becomes visible again, the existing observer calls `resizeDrawingSurfaceToCanvas()` again: verified (`display: block` after loading: canvas 868×320, non-empty render, playback running).

## Case not covered

Hiding the canvas, calling `resizeDrawingSurfaceToCanvas()`, then showing it again **in the same task** (before any browser rendering) leaves the canvas at 0×0: the size observer sees no change in CSS size, so it does not call `resizeDrawingSurfaceToCanvas()` again. Measured by reading back: canvas 0×0, `_needsRedraw` true, playback running, blank render. Before the fix this case crashed: no regression. Workaround on the caller side: call `resizeDrawingSurfaceToCanvas()` again after showing the canvas. An automatic recovery (in `draw`, resize if the canvas has a CSS size but a null surface) is possible and was not done to keep the fix to one line; to be decided with upstream.

## Checks

- The 11 demo examples open without errors without the `requestAnimationFrame` workaround, removed from `web/demo/demo.js` (synchronous resize after the canvas is displayed).
- Upstream jest suite: 29 suites, 493 tests, 0 failures. Python tests in `web/examples/tests` passing.

## Limits

- Not checked against a more recent `rive-wasm` commit (no access to upstream in this task): the report says so.
- The empty surface is a trigger, not a sufficient condition: the exact cause in the C++ (`rive_pls_renderer`) remains to be established with an unoptimized build.
- No jest test added: WebGL2 rendering requires a browser. The scenario can be replayed with `playwright`, with the `zero-size.html` page and a static Python test.
