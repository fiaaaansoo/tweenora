# Upstream tracking (rive-wasm)

`web/rive-wasm/` is Rive's WASM and JavaScript layer, integrated into the
`fiaaaansoo/tweenora` monorepo with `git subtree`, with its full history.
It is built against the monorepo's `runtime/`, not against a submodule.

## Reference

| Item | Value |
|---|---|
| Upstream | https://github.com/rive-app/rive-wasm (MIT, © 2020-2021 Rive) |
| Base commit | `589b787c8a50b528db0071d9bc22e6b21ab13604` (2026-10-12) |
| Runtime pinned by this commit | `daf55385b71fb861b2a1ae2930ae4492832d5db5`, the base of `runtime/` (`docs/UPSTREAM.md`) |
| Upstream package version | 2.44.2 |
| Local tag | `rive-wasm-base/589b787c` |
| Package produced | `@tweenora/webgl2`, version 0.1.0 |

The `rive-wasm` HEAD (2026-10-16) pins a runtime newer than our base. The base
chosen is therefore the `rive-wasm` commit whose submodule pointed exactly at
`daf55385`; it can be found with
`git log --format=%H -- wasm/submodules/rive-runtime` in a clone of
`rive-wasm`, by comparing `git ls-tree <commit> wasm/submodules/rive-runtime`.

## Integration method

`git subtree` without `--squash`, as for `runtime/` (P0-2, `docs/UPSTREAM.md`):

```bash
git remote add upstream-wasm https://github.com/rive-app/rive-wasm.git
git config remote.upstream-wasm.tagOpt --no-tags
git remote set-url --push upstream-wasm no_push
git fetch upstream-wasm <sha>
git subtree add --prefix=web/rive-wasm upstream-wasm <sha>
git tag -a rive-wasm-base/<short sha> <sha> -m "Base rive-wasm <short sha> (runtime <runtime sha>)"
```

The `upstream-wasm` remote is not carried over by `git clone`: recreate it.

## Policy

**Same base as the runtime.** `web/rive-wasm/` follows `runtime/`: when the
runtime moves to a new Rive base (D7, after phase 4), pick the `rive-wasm`
commit that pins that base (method above) and merge it with
`git subtree merge --prefix=web/rive-wasm <sha>`. Do not take the `rive-wasm`
HEAD until the runtime has the matching base.

## Register of deviations from the subtree

Every change to `web/rive-wasm/` is minimal, isolated in its own commit when
possible, and listed here. On each upstream merge, check every line.

| File | Reason | Removal condition | Commit |
|---|---|---|---|
| `web/rive-wasm/wasm/submodules/rive-runtime` (submodule pointer) and `web/rive-wasm/.gitmodules` removed | The monorepo already contains `runtime/`; a submodule pointer with no entry in the root `.gitmodules` would break `git submodule` and clones | None | `a6bec4613` |
| `web/rive-wasm/wasm/build_wasm.sh`, `web/rive-wasm/wasm/premake5.lua` | Look for `runtime/` three levels above `wasm/` (the monorepo root) before the upstream locations | None: the Tweenora monorepo layout differs from Rive's. The folder is only accepted if it contains `premake5_v2.lua` | `b74f3e63e` (`premake5_v2.lua` check: `c339d5e4e`) |
| `web/rive-wasm/wasm/build_wasm.sh` | On Windows, the `gmake2` build fails: `make` truncates the archive command for the runtime's 1500 objects (32 KB limit), and the Closure compiler reads a `/c/Users/...` path as a folder `c` at the root of `C:`. `RIVE_WASM_BUILD_SYSTEM=ninja` variable (generates a ninja build with the `premake-ninja` module from `runtime/build/dependencies`, which uses response files); externs path taken from `pwd -W` when it exists | None as long as the Windows build goes through ninja; upstream may drop `gmake2` | `f67b4dc38` |
| `web/rive-wasm/wasm/js/webgl2_renderer.js` | WebGL context error message without the sentence that recommends `@rive-app/canvas` | None | `f6b0ab08e` |
| `web/rive-wasm/js/examples/_frameworks/neostream-events/public/rive_logo.svg` (removed), `index.html` (`<img>` tag removed), `web/rive-wasm/README.md` (`rive_logo_dark_bg.png` image removed) | Rive logo: a third party's mark, not redistributable here | None | `6db7a30c0` |
| `web/rive-wasm/js/examples/_frameworks/neostream-events/` and `spotify-player-app/` (folders removed), `web/rive-wasm/assets/readme-code-sandbox.png` (removed), `web/rive-wasm/README.md` (rewritten) | Examples of unknown origin (sound effects, Spotify brand), an upstream image and Rive promotional text that contradicted "not affiliated"; no test or build reads them | None | `591d2ca07` |
| `web/rive-wasm/js/npm/webgl2/THIRD_PARTY_NOTICES` (file added) | Notices for the libraries linked into `rive.wasm`, required by their licenses and shipped in the package | None | `5a525d3cd` |
| `web/rive-wasm/js/examples/_frameworks/out_of_band_example/` and `web/rive-wasm/wasm/examples/out_of_band_example/` (folders removed) | Sound effects (`.wav`) with no established license and a third party's photo in `asset_load_check.riv`; no test or build reads them | None | `publication-20` |
| `web/.gitattributes` (file added, outside the subtree) | LF line endings so that shell scripts run on Windows | None | `c53f84381` |
| `web/rive-wasm/js/npm/webgl2/package.json`, `LICENSE`, `README.md` | Package renamed `@tweenora/webgl2` (D6): name, description, repository, author; `contributors` removed (names and addresses of Rive people, already covered by `LICENSE`); package `LICENSE` added; version 0.1.0 | None | `c208068b5` |
| `web/rive-wasm/js/src/rive.ts`, `runtimeLoader.ts`, `semantics/accessibilityOverlay.ts`, `rive_advanced.mjs.d.ts`, tests `initialisation.test.ts` and `text.test.ts` | User-visible messages without a Rive package name or link: five deprecation warnings without a migration link, messages that cited `@rive-app/canvas` and `@rive-app/webgl2`, "Rive editor", "Rive WASM", "Failed to fetch the Rive file", default `aria-label` "Rive animation" changed to "Animation" | None | `c208068b5` |
| `web/rive-wasm/js/test/helpers.ts` | `runtimeDir` looked for `runtime/` three levels above `test/` (Rive's monorepo); in Tweenora it is four levels above (repository root), hence the failure of `scriptingWithoutTools.test.ts`; the four-level path is tried first | None: the Tweenora monorepo layout differs from Rive's | `fc4587c94` |
| `web/rive-wasm/js/src/runtimeLoader.ts`, `test/initialisation.test.ts` | The default `.wasm` and fallback URLs no longer point at `unpkg.com` or `cdn.jsdelivr.net` but at `rive.wasm` and `rive_fallback.wasm` next to the script that loaded the package (`document.currentScript`, otherwise the bare name resolved by the page); the fallback test expects that file and not jsDelivr | None: plan criterion, no request outside the served domain (P3-4) | `5a5d5a6d2` |
| `web/rive-wasm/js/src/rive.ts`, test `test/selfHosting.test.ts` (added) | `enableRiveAssetCDN` is `false` by default (`Rive` and `RiveFile`): the Rive CDN asset loader (`public.rive.app`) is only added on request; parameter documentation updated | None: plan criterion (P3-4); a file with an asset that only exists on the CDN loads it again with `enableRiveAssetCDN: true` | `5a5d5a6d2` |
| `web/rive-wasm/js/src/rive.ts`, `rive_advanced.mjs.d.ts` (JSDoc comments only) | `rive.app` links are replaced by "the upstream Rive documentation" (or removed): the published `rive.d.ts` no longer points to `rive.app`. No code or identifier changes (D6) | None: redo on each upstream merge that adds a link | (this commit) |
| `web/rive-wasm/js/src/rive.ts` (`Rive#draw`) | The "no drawing on a zero-size canvas" guard only tested `_hasZeroSize`, which is updated by an asynchronous observer: `resizeDrawingSurfaceToCanvas()` sets the canvas to 0 and then draws synchronously, and WebGL2 rendering crashes (`memory access out of bounds`). The guard also tests `canvas.width` and `canvas.height` (`docs/baseline/plantage-webgl2-resize.md`) | Upstream fixes the guard (text of the report: `docs/baseline/signalement-amont-webgl2-resize.md`, not sent) | (this commit) |

## Names kept (minimal D6)

The package keeps the upstream API identifiers: the `Rive` class, `RiveFile`,
`RiveError`, the `rive` UMD global, the `rive.js` and `rive.wasm` files, and the
messages that cite these identifiers (for example
`Rive.suppressDeprecationWarnings`). It also keeps what it emits at runtime
that carries the name: `[Rive]` and `Rive:` log prefixes, `rive-a11y-N` DOM
identifiers, `rive:*` performance marks, deprecation identifiers
(`rive-events`), and the `https://public.rive.app/cdn/uuid` URL in the
`rive.wasm` binary (to be handled with P3-4). They are the API that P3-3 must
cover for parity; renaming them is a product decision to be made with P3-3.
The links to Rive's documentation in source comments (`rive.app/docs`) are
kept: they describe the upstream API.

## Loading the `.wasm`

`RuntimeLoader` builds the default `.wasm` URL from the package name and
version (`https://unpkg.com/<name>@<version>/rive.wasm`, falling back to
jsDelivr). With the new name, this URL only exists after publication. Replacing
it with self-hosting is P3-4.
