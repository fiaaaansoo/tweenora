# web/deploy/

Prepares the static folder of the demo to publish. **Nothing here deploys anything or creates an account**: deployment is up to the project owner, with their own account at the host.

## Assemble the folder

```bash
bash web/build_webgl2_package.sh --no-wasm   # only if the .wasm files are already built (the script exits with an error otherwise)
python web/deploy/build_site.py              # writes web/deploy/site/ (ignored by git)
python web/deploy/build_site.py --clean      # replaces a folder built earlier
```

The `web/deploy/site/` folder contains:

- `index.html`: home page (title, description, canonical, Open Graph, `SoftwareApplication` JSON-LD, links to `/demo/`, GitHub and the notices); `sitemap.xml`, `robots.txt` (with the `Sitemap:` line) and `social-preview.png` (copy of `docs/images/`); `demo/favicon.svg`. The reference address (`BASE_URL` in `build_site.py`) is `https://tweenora-demo.pages.dev`: change it if the domain changes.
- `demo/`: the demo page. Its `examples.json` only keeps the examples with `publishable: true`, whose license is established by `web/examples/ASSETS_PROVENANCE.md` (today the four original examples in `docs/examples/`: ball, square, button, tinted shape; if the list were empty, the "Examples" section would be hidden and the demo would only serve local drag and drop, the file never leaving the browser).
- `pkg/<version>-<hash>/`: `rive.js`, `rive.wasm`, `rive_fallback.wasm`, `LICENSE`, `THIRD_PARTY_NOTICES`. The folder carries the `package.json` version and a short content hash: the URL changes as soon as a file changes, which makes the `immutable` cache safe. The `.wasm` loads next to `rive.js` (P3-4), hence under the same path.
- `assets/`: the publishable `.twno` files, one per publishable example (absent if there are none). `python web/examples/prepare_assets.py` must have been run first: without the prepared files, `build_site.py` stops with an error instead of producing a site with no examples. The table fingerprint covers the `.riv`; the published `.twno` is the one `prepare_assets.py` derives from it, and a `.twno` placed by hand in `web/examples/assets/` would not be checked.
- `404.html`: without it, the host may answer 200 with the home page for an unknown path.
- `_headers`: the headers for Cloudflare Pages.
- `.tweenora-site`: marker for `--clean` (published with the rest, harmless).

Before writing anything, the script refuses: an example that is not marked "yes" in the provenance table, a `.riv` whose SHA-256 fingerprint no longer matches the table, a file outside `/assets/`, an incomplete package (missing notices), a modified demo page, and a non-empty output folder it did not build.

## Check locally

```bash
python -c "import sys; sys.path.insert(0, 'web/examples'); import serve; serve.make_server('127.0.0.1', 8766, {'/': 'web/deploy/site'}).serve_forever()"
```

Open http://127.0.0.1:8766/: the demo is displayed, a dropped `.riv` or `.twno` file opens, and no request leaves `127.0.0.1:8766`. This server does not apply `_headers`: the headers are checked on the host.

Result of 2026-10-19 with the original examples (`playwright` MCP, `prepare_assets.py` then `build_site.py --clean`, site served locally): the "Examples" section lists the four examples, each opens without error at 320, 768 and 1280 px, no horizontal scrolling, 0 requests outside the domain; `button` exposes the `actif` input and `tinted-shape` the `accent` and `couleur` properties; the console only contains "Could not find a View Model linked to Artboard ..." for files without a view model (library behavior).

Result of 2026-10-17 (site without examples): `/` leads to `/demo/`; at 320, 768 and 1280 px no horizontal scrolling, footer and notices link present, "Examples" section hidden (no publishable example); the `.wasm` loads from `/pkg/<version>-<hash>/rive.wasm`; `multiple_state_machines.riv` chosen with the file picker opens without error (5 state machines); 0 requests outside the domain.

## Publish on Cloudflare Pages (recommended, free, no domain purchase)

To be done by the project owner, with their own account (no account is created and no token is entered on their behalf):

1. Create a Cloudflare account (free), then create a **Pages** project by direct upload ("Upload assets"). The exact menu path changes often: follow the current interface.
2. Name the project, for example `tweenora-demo`: the address will be of the form `https://<name>.pages.dev` (subdomain provided, no domain to buy; if the name is taken, Cloudflare suggests another).
3. Upload the contents of the `web/deploy/site/` folder (the whole folder, `_headers` at the root).
4. From the command line, instead of the interface: `npx wrangler pages deploy web/deploy/site --project-name tweenora-demo` (logs in to your Cloudflare account; may offer to create the project).
5. Note the resulting URL: the `mise-en-ligne-demo` task then replays the `playwright` scenario on the real URL (0 requests outside the domain, headers, footer, notices link).

## Deployment of 2026-10-17

Deployed to https://tweenora-demo.pages.dev (project `tweenora-demo`). The Pages project had to be created with `npx wrangler pages project create tweenora-demo --production-branch main --force`: `wrangler` 4.151.1 redirected the creation to Workers (the `--force` option is not documented in the help, and was needed only once), then `npx wrangler pages deploy web/deploy/site --project-name tweenora-demo --branch main`. The measured results are in `docs/baseline/self-hosting-p3-4.md`.

## Deployment of 2026-10-20

Redeployed from `main` (`895b30bb8`), with the user's approval of 2026-10-20: `npx wrangler pages deploy <site folder> --project-name tweenora-demo --branch main`, deployment `e4ee65fc` (production URL https://tweenora-demo.pages.dev). The web package (`rive.js`, `rive.wasm`, `rive_fallback.wasm`, notices) is the one already online, fetched as is (folder `pkg/0.1.0-63b16bc5/`, same fingerprint): the package built in the other worktrees predates the fix for the zero-size canvas guard and would have regressed.

Published: home page `/` (no redirect), `sitemap.xml`, `robots.txt` with the `Sitemap:` line, `social-preview.png`, `demo/favicon.svg`, footer "rive-runtime and rive-wasm", four original examples (`bouncing-ball`, `spinning-square`, `button`, `tinted-shape`, as `.twno`). Findings on the real URL: `/`, `/demo/`, `/sitemap.xml`, `/robots.txt`, the image and the four `.twno` answer 200; a third-party `.riv` mockup removed from the repository and an unknown path answer 404; `.twno` served as `application/octet-stream` with `Cache-Control: public, max-age=3600` and `x-robots-tag: noindex`; `rive.wasm` as `application/wasm` with `immutable` cache; the demo opens on the button example through its URL fragment, 4 examples listed, 0 requests outside the domain, footer and notices link present, no horizontal scrolling. Rollback is possible from the Pages dashboard (redeploy the previous version).

## Points to check on the real URL (checked on 2026-10-17)

- `Content-Type: application/wasm` on `rive.wasm` and `rive_fallback.wasm`, `text/plain; charset=utf-8` on `THIRD_PARTY_NOTICES`: set by `_headers`, to be confirmed in the response headers.
- `Cache-Control: public, max-age=31536000, immutable` under `/pkg/<version>/`.
- `br` or `gzip` compression: applied by the host, to be confirmed with the `Content-Encoding` header of a request that accepts `br`.
- `Access-Control-Allow-Origin`: not set by `_headers` (everything comes from the same domain); the host may add one by default on static resources, with no effect here.
- A nonexistent path (for example `/pkg/rive.js` without a versioned folder) answers 404 thanks to `404.html`, and not 200 with the home page.
- The overlapping rules (`/pkg/<v>/*` and `/pkg/<v>/*.wasm`, `/*`) carry headers with different names; confirm that a `Content-Type` set by `_headers` does replace the host's for `THIRD_PARTY_NOTICES` (a file with no extension).

Other host: GitHub Pages does not allow custom headers (so no `immutable` cache and no forced MIME type for the file with no extension); not recommended.
