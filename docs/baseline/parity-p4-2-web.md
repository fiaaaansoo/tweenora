# Web runtime state machine parity (P4-2c)

> Note of 2026-10-20: this campaign was measured with the manifest of 491 files (403 with a state machine). 7 third-party files have since been removed from it (task `publication-8-retrait-runtime-parite`), 2 of which were among the 67 compared on the web (identical traces): 65 of the 67 files remain in the manifest of 484 files (396 with a state machine), all identical. 4 other third-party files were removed afterwards (task `publication-16-retrait-fichiers-tiers-2`), 1 of which was among the 67: 64 of the 67 files remain in the manifest of 480 files (394 with a state machine), all identical. 3 other files were removed (task `publication-18-retrait-fichiers-tiers-3`), none of them among the 67: 64 files remain in the manifest of 477 files (391 with a state machine). 2 other files were removed (task `publication-19-polices`), both among the 67: 62 files remain in the manifest of 475 files (389 with a state machine), all identical. Two of the 64 (`image_fit_alignment.riv`, `zombie_skins.riv`) had their embedded images replaced; their state machine traces do not depend on them and were not replayed on the web side. The other figures in the text are not recomputed: the sample is derived from the manifest and would be different today.

P4-2c report: the P4-2b action scripts are replayed by the `@tweenora/webgl2` web package (low-level API, in
Chrome 155 driven by the `playwright` MCP) and the resulting traces are compared with those of the native fork on the fields
that the web exposes. **Over 67 files, all 67 web traces are identical to the native traces for the input values and the
reported events (name and delay), at each step.**

## Scope

- 67 files with a state machine from the manifest: all those whose native trace contains at least one event (12 files,
  65 events) or one input (38 files), plus 20 other files taken in the order of a SHA-256 hash of the paths.
  64 of them change state at least once on the native side. 2,621 steps in total.
- One in six files with a state machine in the manifest (67 out of 403): this is not the full coverage of P4-2b, for lack of
  time. The sample favors files that exercise inputs and events.
- Default artboard and state machine of each file (the description comes from the native harness), as in P4-2b.
- Same environment as P4-1d: one browser, one GPU; the web package is the one from the batch D worktree (`13d6bbd25`).

## Compared fields

The web does not expose `stateChangedByIndex` (it only gives the names of the changed states) nor `needsAdvance`: these two
fields of the native trace are not compared. At each step, the following are compared: the list of inputs (name, type, value) and the
list of reported events (name, delay), as well as the artboard and the state machine of the header. Numbers are compared
with a relative tolerance of 1e-6 (native single-precision floats versus web doubles: `27.8432617` versus
`27.84326171875`); a boolean is never equal to a number. The P4-2a comparator now accepts `fields=` and
`float_tolerance=` (`tools/parity/trace_compare.py`), tested.

## Method

1. `python -I tools/parity/sm_web_prepare.py`: writes to `tools/parity/.work/sm_web/` the script (`<id>.script.jsonl`) and
   the native trace (`<id>.native.jsonl`) of each chosen file, plus `index.json`.
2. `python -I web/parity/serve.py` (port 8766) then, with the `playwright` MCP, open `http://127.0.0.1:8766/sm.html` and
   evaluate `await window.paritySm.run(await (await fetch('/sm/index.json')).json())`; the page loads each file,
   applies the script without a clock (only `advanceAndApply(dt)`), and returns the trace text of each one. The evaluation
   is saved to a file (`filename`), from which each trace is written as `<id>.web.jsonl`.
3. `python -I tools/parity/sm_web_compare.py`: compares each pair, JSON summary, code 1 on any unexplained difference
   (`tools/parity/sm_web_explained.json`, empty).

Two defects of the page were fixed during tuning (they do not come from the package): the web API wants
`input.asTrigger().fire()`, `asBool().value` and `asNumber().value` (the value of the generic input is undefined); the web
state machine has no `name` property.

## Result

| Status | Files |
|---|---|
| Identical on the common fields | 67 |
| Difference | 0 |
| Page error (loading, API) | 0 |

No behavior difference between the web package and the native fork appeared on these fields.

## Limits

- 67 files out of 403; a single browser; default artboard and state machine; same script generation limits
  as P4-2b (fixed values, five pointer positions, no driven data binding).
- The states traversed are not compared (native gives the `typeKey` of the state, web gives names): a transition
  divergence that changes neither an input nor an event would go unnoticed.
- The web trace is not compared on `needsAdvance`.
- The events of only 12 files (65 events in total) have a non-empty trace; their name is empty in the
  chosen files, so only their delay tells them apart.
- Files are loaded as `.riv` on the web side; loading of `.twno` files is not tested in this task.
- The native harness did not bind a view model, and neither did the web page: the equivalence is that of a state machine
  without data binding.

## Reproduce

```powershell
python -I tools\parity\sm_web_prepare.py
python -I web\parity\prepare_package.py --tgz <tweenora-webgl2-0.1.0.tgz>
python -I web\parity\serve.py
python -I tools\parity\sm_web_compare.py
python -I -m unittest discover -s tools\parity\tests
```
