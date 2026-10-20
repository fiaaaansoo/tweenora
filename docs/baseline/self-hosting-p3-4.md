# Package self-hosting (P3-4)

P3-4 report: no more default requests outside the served domain, verified in a browser, and the
headers to serve.

## Context

| Item | Value |
|---|---|
| Date | 2026-10-17 |
| Package | `@tweenora/webgl2` 0.1.0 rebuilt after the changes (`bash web/build_webgl2_package.sh --no-wasm`) |
| Criterion | the network tab shows no request outside our domain (global success criterion no. 2 of the plan) |
| Test page | `web/examples/loading/self-hosted.html`: loads `rive.js` and a file with a hosted resource without any configuration (neither `setWasmUrl` nor `enableRiveAssetCDN`) |

## Inventory of default loads

| Load | Where | Before | After |
|---|---|---|---|
| `rive.wasm` | `RuntimeLoader.wasmURL` (`runtimeLoader.ts`) | `https://unpkg.com/@tweenora/webgl2@0.1.0/rive.wasm` | `rive.wasm` next to the script (`document.currentScript`), otherwise (module, bundler, `blob:` URL) the bare name resolved by the page: in these cases `RuntimeLoader.setWasmUrl` must be called |
| `rive_fallback.wasm` | `RuntimeLoader.wasmFallbackURL` | `https://cdn.jsdelivr.net/npm/@tweenora/webgl2@0.1.0/rive_fallback.wasm` | `rive_fallback.wasm` next to the script |
| Rive hosted resources (images, fonts, audio) | `enableRiveAssetCDN`, `rive.ts` (`Rive` and `RiveFile`); `CDNFileAssetLoader` loader | enabled by default: `https://public.rive.app/cdn/uuid/<uuid>` | disabled by default; active only with `enableRiveAssetCDN: true` |

The three changes are deviations from `web/rive-wasm`, recorded in the register of `web/UPSTREAM.md`.

## Verification

- Jest test `test/selfHosting.test.ts` (7 tests, three of them on resolution next to the script, `currentScript` simulated): the default URLs are not external; a `RiveFile` and a `Rive`
  that load `hosted_image_file.riv` open no external request (XHR spied on); with
  `enableRiveAssetCDN: true` the external request still goes out. Written before the change: 3 tests failed; the case of a `blob:` script URL first failed (`Invalid URL`), hence a `try/catch` in `siblingUrl`. Only `XMLHttpRequest` is spied on: it is the only network path of the wasm glue (`wasm/js/shared.js`); `fetch` is only used for the `src` supplied by the application, and no `importScripts`, `instantiateStreaming`, font or audio by URL exists in `js/src` and `wasm/js`.
- Full jest suite: 29 suites, 493 tests, 0 failures.
- Browser (`playwright` MCP, `self-hosted.html`): state `drawing`, `rive.wasm` served from
  `http://127.0.0.1:8765/pkg/rive.wasm` without configuration, **0 requests outside `127.0.0.1:8765`** out of the 6
  requests of the page (page, CSS, `rive.js`, `common.js`, `rive.wasm`, the `.twno`).

## Headers to serve

`web/examples/serve.py` serves as the reference (error responses stay `no-store`, even with `--cache`): `Content-Type: application/wasm` for `.wasm` files (essential for
`WebAssembly.instantiateStreaming`), `application/octet-stream` for `.riv` and `.twno`. Options:
`--cors` (`Access-Control-Allow-Origin: *`, useful if the files are served from a different domain than the page)
and `--cache` (`Cache-Control: public, max-age=31536000, immutable`, to be reserved for files versioned by their
URL: the package name carries the version). Without options: `no-store`, for development. In production:
the package's `.wasm` and `.js` with long, `immutable` caching under a versioned URL; `.twno` and `.riv` with a
short cache or validation (`ETag`); `br` or `gzip` compression for the `.wasm` files (about 3 MB).

## What remains

- Text strings containing Rive addresses in the package (documentation links `rive.app/docs/...`
  in comments and messages, `github.com/rive-app/rive-cpp`), without a request: they fall under the
  D6 convention (upstream API identifiers kept or renamed), to be validated.
- `rive.wasm` still contains the string `https://public.rive.app/cdn/uuid` (default value of
  `FileAsset::m_CdnBaseUrl`, generated file in `runtime/`): unused as long as the CDN loader is not
  enabled; changing it is a D15 deviation in `runtime/`, not done. The low-level `Module.load` glue keeps
  its `enableRiveAssetCDN = true` parameter, but the package's JavaScript layer always passes an
  explicit value.
- **Demo host**: Cloudflare Pages, see "Online demo" below.

## Online demo (2026-10-17)

Deployed at https://tweenora-demo.pages.dev (Cloudflare Pages project `tweenora-demo`, free subdomain, no domain purchased) with `wrangler pages deploy web/deploy/site` (see `web/deploy/README.md`). No example is published (licenses not established): the demo only serves local drag and drop.

Verification on the real URL (`playwright` MCP and `curl -H 'Accept-Encoding: br, gzip'`):

| Resource | Status | Content-Type | Cache-Control | Content-Encoding |
|---|---|---|---|---|
| `/` and `/demo/` | 200 | `text/html; charset=utf-8` | `public, max-age=0, must-revalidate` | `br` |
| `/pkg/0.1.0-63b16bc5/rive.wasm` and `rive_fallback.wasm` | 200 | `application/wasm` | `public, max-age=31536000, immutable` | `br` |
| `/pkg/0.1.0-63b16bc5/rive.js` | 200 | `application/javascript` | `public, max-age=31536000, immutable` | `br` |
| `/pkg/0.1.0-63b16bc5/THIRD_PARTY_NOTICES` | 200 | `text/plain; charset=utf-8` | `public, max-age=31536000, immutable` | `br` |
| `/pkg/0.1.0-63b16bc5/LICENSE` | 200 | `text/plain; charset=utf-8` (after the rule was added; first `application/octet-stream`) | `public, max-age=31536000, immutable` | not compressed (1.2 kB) |
| `/pkg/rive.js` (unversioned path) and `/nonexistent` | 404 | `text/html` (`404.html`) | `no-store` | `br` |

All responses carry `x-content-type-options: nosniff`; the host adds `Access-Control-Allow-Origin: *` (no effect, everything comes from the same domain). The `Content-Type` set by `_headers` does override the host's for files without an extension.

`playwright` scenario on the real URL: `/` leads to `/demo/`; at 320, 768 and 1280 px no horizontal scrolling, footer "Derived from an MIT-licensed upstream runtime; independent project, not affiliated with or endorsed by its authors." and the notices link (200, `text/plain`); "Examples" section hidden; `multiple_state_machines.riv` (5 state machines) and `two_artboards.twno` chosen with the file picker open without error; 25 requests, **none outside `tweenora-demo.pages.dev`** (excluding `blob:` and `data:`).
