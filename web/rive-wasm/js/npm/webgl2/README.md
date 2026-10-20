# @tweenora/webgl2

WebGL2 web runtime of Tweenora. It plays `.twno` files and the `.riv` files they
are derived from, with the GPU renderer compiled to WebAssembly from the
Tweenora fork of the runtime.

The package is built from `web/rive-wasm/` of the Tweenora repository, a fork of
rive-wasm (MIT, Copyright (c) 2020-2021 Rive). The JavaScript API keeps the
identifiers of the upstream package.

The package makes no request to a third-party host by default. The runtime loader
looks for `rive.wasm` (and `rive_fallback.wasm`) beside the script that loaded
`rive.js`, which works when `rive.js` is loaded by a classic `<script>` tag. When
the package is bundled or loaded as a module, call
`RuntimeLoader.setWasmUrl(...)` and `RuntimeLoader.setWasmFallbackUrl(...)` with
the URLs of your own copies. Assets hosted on the Rive CDN are not loaded unless
you pass `enableRiveAssetCDN: true`.

Calling `resizeDrawingSurfaceToCanvas()` on a hidden canvas (no pixels) is safe: nothing is drawn
until the canvas has a size, then the existing size observer resizes the drawing surface and rendering
resumes (if the canvas is hidden and shown again within the same task, call
`resizeDrawingSurfaceToCanvas()` again after showing it). Earlier builds trapped with `memory access out of bounds` in that case when a second `Rive`
was created on a canvas after the first was cleaned up.
