# Draft upstream report (not sent: for the project owner to review)

Target: https://github.com/rive-app/rive-wasm (JavaScript layer, `Rive#draw`).

**Title:** `resizeDrawingSurfaceToCanvas()` on a zero-size canvas traps with "memory access out of bounds" in `WebGL2Renderer.flush`

**Version:** rive-wasm commit `589b787c8a50b528db0071d9bc22e6b21ab13604` (package 2.44.2), WebGL2 build (`webgl2_advanced`), with rive-runtime `daf55385b71fb861b2a1ae2930ae4492832d5db5`. Chrome on Windows 11 (browser version and GPU to fill in before sending).

**Summary:** `Rive#draw` skips drawing when `_hasZeroSize` is true, but `_hasZeroSize` is only updated by an asynchronous size observer. `resizeDrawingSurfaceToCanvas()` sets `canvas.width` and `canvas.height` from `getBoundingClientRect()` (0 when the canvas is hidden), then calls `drawFrame()` synchronously. The observer has not run yet, so the guard does not apply and a frame is drawn into a 0x0 surface. With some files the renderer then traps.

**Steps to reproduce:**
1. Create a canvas with `display: none` (or CSS width or height 0).
2. Create a `Rive` with `autoplay: true` and `autoBind: true` on a heavy file (we used a 3 MB file with images, fonts and gradients), call `cleanup()` on it, then create a second `Rive` with a state machine on the same canvas.
3. In the second instance's `onLoad`, call `resizeDrawingSurfaceToCanvas()`.

**Observed:** `RuntimeError: memory access out of bounds` thrown from `WebGL2Renderer.flush` (`Rive.draw` <- `Rive.drawFrame` <- `Rive.resizeDrawingSurfaceToCanvas`). The instance is unusable afterwards.

**Expected:** no draw (and no error) while the canvas has no pixels; drawing resumes when the canvas becomes visible.

**Measured conditions:** traps for a `0x400` canvas, a `600x0` canvas and `display:none`; does not trap for `1x1` or `600x400`; does not trap with `autoplay: false`; does not trap for a single first instance on a hidden canvas; does not trap with the two smaller files we tried.

**Suggested fix (one line):** in `Rive#draw`, also test the real canvas size:

```ts
if (!this._hasZeroSize && this.canvas.width > 0 && this.canvas.height > 0) {
```

When the canvas becomes visible again the existing observer calls `resizeDrawingSurfaceToCanvas()`; we checked that rendering resumes when the size change is visible to the observer. If the canvas is hidden, resized and shown again within the same task, the observer sees no change and the surface stays at 0x0 until `resizeDrawingSurfaceToCanvas()` is called again; the crash is gone in that case too, but the canvas stays blank.

**Notes for the maintainers:** the exact C++ cause (zero-size surface in the pixel local storage renderer) is not established; we only know the JavaScript guard is bypassed. We cannot attach the 3 MB file; any file that traps on a hidden canvas reproduces the problem. This was not checked against a newer rive-wasm commit.
