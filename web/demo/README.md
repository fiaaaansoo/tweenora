# web/demo/

Tweenora demo page (P3-5): opens a `.twno` or `.riv` file (drag and drop, button, or examples list), picks the
artboard, the animation and the state machine, and exposes the state machine inputs and the view model
properties. Plain HTML, CSS and JavaScript with no framework and no build step; the only dependency is the
`@tweenora/webgl2` package (`/pkg/rive.js`). No external font or resource: no request leaves the served domain.

Live demo: https://tweenora-demo.pages.dev (Cloudflare Pages, see `web/deploy/README.md` and `docs/baseline/self-hosting-p3-4.md`).

## Run

```bash
bash web/build_webgl2_package.sh --no-wasm   # only if the package is not built
python web/examples/prepare_assets.py        # the example files (not versioned)
python web/examples/serve.py                 # http://127.0.0.1:8765/demo/
```

`#example=<id>` in the address opens an example (`examples.json`). To publish, serve `demo/`, the package and
the `.twno` files from the same domain with the headers from `docs/baseline/self-hosting-p3-4.md`.

## Contents

- `index.html`, `demo.css`, `demo.js`: the page. `window.tweenoraDemo.state()` and `.instance()` are meant for
  `playwright` scenarios.
- `examples.json`: the listed examples (files prepared by `prepare_assets.py`). Each entry carries
  `publishable`: `true` only if the file's license is established in `web/examples/ASSETS_PROVENANCE.md`
  (today the four original examples from `docs/examples/`, at the top of the list; upstream files stay
  `publishable: false`). An empty list hides the "Examples" section: the page remains usable with a local file.
- Footer: the notice "Derived from an MIT-licensed upstream runtime; independent project, not affiliated with or endorsed by its authors" and a link to
  `/pkg/THIRD_PARTY_NOTICES` (inventory: `docs/baseline/licences-et-mentions.md`).

## Design choices

Specification: the `designer` persona (a scene first, settings after, progressive disclosure), a sober palette
built on color tokens, light and dark themes (setting remembered), 44 px targets, `prefers-reduced-motion`
(no autoplay), a single polite `aria-live`. Deviations from the specification: collapsible `<details>` sections
instead of mobile tabs, and buttons that open a hidden file picker instead of a drop zone that would itself be a
field. No usage metrics are sent: events only go to the console.
