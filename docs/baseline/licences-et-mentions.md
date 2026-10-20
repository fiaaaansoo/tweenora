# Licenses and notices of the web package and the demo

> Note of 2026-10-20 (task `publication-8-retrait-runtime-parite`): the third-party MP3 audio file and the `echo_show_demo.riv` mockup are no longer in the repository, nor are six third-party brand files from `runtime/tests/unit_tests/assets/`. The reports in `docs/baseline/` that describe tests on `echo_show_demo.riv` are kept as a descriptive history. The test audio file is replaced by `silence.mp3`, produced by `tools/silent_mp3.py`.

Task `licences-et-mentions` (Batch E, 2026-10-17). This document records the inventory, the evidence and what remains to be decided. It is not legal advice.

## What is delivered

- `web/rive-wasm/js/npm/webgl2/THIRD_PARTY_NOTICES`: full license text of the projects compiled into `rive.wasm`, added to the `files` field of `package.json` (`npm pack --dry-run`: `LICENSE` and `THIRD_PARTY_NOTICES` appear there). The file is versioned in the package directory, which `web/build_webgl2_package.sh` never empties.
- Demo footer: "Derived from an MIT-licensed upstream runtime; independent project, not affiliated with or endorsed by its authors." and a link "Licenses and third-party notices" to `/pkg/THIRD_PARTY_NOTICES` (same domain, 44 px high, no horizontal scrolling at 320, 768 and 1280 px, no request outside the domain).
- `serve.py` serves files without an extension as `text/plain; charset=utf-8` (without this the browser would download the file).
- The `rive.app` links in the JSDoc comments of `rive.ts` and `rive_advanced.mjs.d.ts` are removed (deviation recorded in `web/UPSTREAM.md`).
- `web/examples/ASSETS_PROVENANCE.md`: provenance and "publishable" status of each example file. `web/demo/examples.json` carries a `publishable` flag per example, checked by `web/examples/tests/test_provenance.py`.

## Libraries linked into `rive.wasm` (`webgl2` variant)

The package build (`web/build_webgl2_package.sh` → `build_wasm.sh -w [-c] -r webgl2`) passes `--with_rive_text --with_rive_audio=system --with_rive_layout --with_rive_scripting` and `--no-rive-decoders`. The sources are downloaded to `web/rive-wasm/wasm/dependencies/` (ignored by git); each license is copied from this directory.

| Library | Version | License | Linked? | Evidence |
|---|---|---|---|---|
| rive-runtime | commit `daf55385` | MIT, © 2020 Rive | yes | `runtime/LICENSE` |
| rive-wasm | commit `589b787c` | MIT, © 2020-2021 Rive | yes | `web/rive-wasm/LICENSE` |
| Code derived from Skia and the Android Open Source Project (geometry, triangulation, rectangles, shaders) | sources in `runtime/` and `web/rive-wasm/wasm/src/skia_imports/` | BSD-3-Clause, © Google Inc. / LLC, © The Android Open Source Project | yes | 35 files carry "governed by a BSD-style license"; built by `runtime/premake5_v2.lua` (`src/**.cpp`), `runtime/renderer/premake5_pls_renderer.lua` (`src/*.cpp`, `src/shaders/*.glsl`) and `web/rive-wasm/wasm/premake5.lua` (`skia_imports/**.cpp`). The repository does not contain Skia's LICENSE file: the standard text is reproduced in the notices |
| HarfBuzz (Rive fork) | `rive_13.1.1` | "Old MIT" | yes (`--with_rive_text`) | `web/rive-wasm/wasm/premake5.lua`: `links({ 'rive_harfbuzz', ... })` under `options:with_rive_text` |
| SheenBidi | `v2.6` | Apache-2.0 (no NOTICE file) | yes (`--with_rive_text`) | same: `rive_sheenbidi` |
| miniaudio (Rive fork) | `rive_changes_5` | public domain or MIT-0, at your option | yes (`--with_rive_audio=system`) | same: `miniaudio` under `with_rive_audio=system` |
| Yoga (Rive fork) | `rive_yoga_fb91f6cb0f8f` | MIT, © Facebook | yes (`--with_rive_layout`) | same: `rive_yoga` under `with_rive_layout` |
| Luau | `rive_0_734_ice` | MIT, © Roblox and Lua.org | yes (`--with_rive_scripting`) | same: `luau_vm` under `with_rive_scripting` |
| libhydrogen | `rive_0_2` | ISC, © Frank Denis | yes (`--with_rive_scripting`) | `runtime/premake5_v2.lua`: `libhydrogen/libhydrogen.c` built with scripting |
| Emscripten 4.0.23, musl, libc++, libc++abi | 4.0.23 | MIT and UIUC; MIT; Apache-2.0 with LLVM exceptions | yes (added by `emcc`) | cannot be verified in the binary |
| libpng, libjpeg, libwebp | | | **no** | `--no-rive-decoders`: `runtime/decoders/premake5_v2.lua` does not build them |
| WAMR | | | no | `wamrBuildable` is false when `arch` is `wasm` (`runtime/premake5_v2.lua`) |
| DirectX-Headers, ply | | | no | Windows tools or targets, never linked into the wasm |

Limit: `rive.wasm` carries no symbol names, so the presence of each library cannot be proven by searching for strings in the binary. The evidence is the list of `links` of the build and its options. The Emscripten, musl and libc++ lines describe what `emcc` links into any WebAssembly module, without verification in the binary. The licenses are all permissive; none requires publishing Tweenora's code.

Correction to the preliminary legal opinion: libpng, libjpeg and libwebp do not have to appear in the web package notices, because no decoder is linked (the browser decodes the images).

## Occurrences of `rive.app`

- `web/rive-wasm/js/src/rive.ts`: 20 JSDoc links (data binding migration guide, events, state machine actions). Replaced by "the upstream Rive documentation"; the link to the "bones" guide in `rive_advanced.mjs.d.ts` is removed. No more occurrences in `web/rive-wasm/js/src/`. No code or identifier changes (D6).
- The built files (`rive.d.ts`, `rive.js`) must be regenerated so that the published package no longer contains these links: they come from `rive.ts` at build time (`bash web/build_webgl2_package.sh --no-wasm`).
- `rive.wasm` contains the string `https://public.rive.app/cdn/uuid` (`runtime/include/rive/generated/assets/file_asset_base.hpp`). It is only used by the CDN resource loader: the package sets `enableRiveAssetCDN` to `false` by default (P3-4); the low-level glue (`webgl2_renderer.js` for this variant) keeps `true` as the default value, but the package does not use it. A request to `public.rive.app` only happens if the caller enables the CDN. Removing the string requires a C++ change in `runtime/` (D15): **proposed to the user, not done**.

## Example files

Details in `web/examples/ASSETS_PROVENANCE.md` (46 files).

- 5 fonts: SIL OFL 1.1 license read from the `name` table of each file (publishable, with the OFL license text to be included).
- One MP3 audio file: ID3 tags of a third-party artist and album, with a contact notice for licenses: third-party music, **not publishable**. Removed from the repository (see the note at the top).
- One `.riv` mockup naming a third-party product and embedding JetBrains Mono: **not publishable**. Removed from the repository (see the note at the top).
- `what.wav` and the 39 other `.riv` files: no proof of license in the repository (upstream's MIT covers the code): "to be verified", hence not published.

Consequence: none of the 11 demo examples is publishable today (`publishable: false`). The public demo is limited to local drag and drop (the file does not leave the browser). The page does not apply the flag itself: locally it shows the 11 examples. It is the assembly script of the task `mise-en-ligne-demo` that only publishes the `publishable: true` entries of `examples.json`; with an empty list the "Examples" section stays hidden and the page remains usable ("Open an animation", "Browse..." button; verified with `playwright`). Examples specific to Tweenora presuppose the editor, which does not exist yet.

## For the user

1. Should Rive be asked (or their upstream repository checked) about the license of the test `.riv` files so that a few can be published? Otherwise the public demo will have no example until the editor.
2. Should the `public.rive.app` string be removed from `rive.wasm` (C++ change D15)? Recommendation: no, it is inert.
3. If an OFL font is put online, include the OFL license text.
