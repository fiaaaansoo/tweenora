# Render comparison harness (P4-1b)

P4-1b report: one command renders a list of files with the fork and with the
official runtime (`goldens`, `gl` backend), at several fixed instants, compares the
images pixel by pixel and writes a report. The bench (build, manifest,
determinism) is described in `parity-p4-1-banc.md`.

## Decisions

- **Comparator**: minimal Python (`tools/parity/pixeldiff.py`, Pillow and numpy,
  RGBA, alpha channel included), not the upstream `diff.py`: that one expects directories
  of goldens and goes through OpenCV, with threshold and histogram logic that the
  "exact pixel" rule rules out.
- **Equality rule**: exact pixel. No global tolerance. A difference is only tolerated
  if it is listed in the `explained.json` file of the `tools/parity/` directory (absent while the list is empty): key `path@frames@default` (or
  `path@frames@artboard:<name>`), value `{"status": "different", "reason": "..."}`. The expected
  status must be the one observed (a difference that became a crash is no longer explained); the difference
  is then counted as "explained" and does not make the command fail.
- **Instants**: `RIVE_GOLDENS_ADVANCE` at 0, 15 and 60 frames at 60 fps (0, 0.25 s and 1 s).
  Default artboard, then each named artboard if the file has several
  (`-t <name>`); duplicate names within the same file are only rendered once (`-t` picks the
  first artboard with that name; 9 files of the manifest have some). The state of the state machine is not driven here (P4-2).
- **Failure on both sides**: if both binaries fail with the same exit
  code (a real process code: a timeout or an exception does not count), the status is `same_failure` (equality, distinct from a success: no image
  was compared). Different codes give `both_error`, a failure on one side only gives
  `error_a` (fork) or `error_b` (official): these three statuses make the command fail.

## Command

```text
python -I tools/parity/render_compare.py --sample 40 --jobs 3 \
    --report-json tools/parity/.work/rc/riv.json --report-md tools/parity/.work/rc/riv.md
python -I tools/parity/render_compare.py --all --format twno --jobs 3
python -I tools/parity/render_compare.py --files runtime/tests/unit_tests/assets/rocket.riv --instants 0,30
```

- Selection: `--all` (all 475), `--sample N` (deterministic: 2 files per feature,
  then filled up in the order of the manifest's SHA-256 values) or `--files`.
- `--format twno`: the fork renders a copy of the input whose signature is rewritten to
  `TWNR` (`tools/twno_convert.py`, copy named `.riv`, because `goldens` only accepts
  that extension), the official runtime renders the original `.riv`. Used for P4-1c.
- `--jobs` limits the number of simultaneous renders (3 by default), `--timeout` the timeout per
  render (120 s). A crash or a timeout of a render is an error
  record, not an interruption of the batch. A missing source (`setup_error`) or an empty
  campaign (no render) makes the command fail.
- Output: JSON summary on stdout, detail of the unexplained differences on stderr, reports
  `--report-json` and `--report-md`. Exit code 1 on any unexplained difference.
- The default binaries are those of `build_goldens.ps1`; `--fork` and `--ref` replace
  them.

## Result on a sample of 40 files

Composition (40 files from `manifest.json`): 31 at the root of `unit_tests/assets`, 8 in
its subdirectories, 1 from `web_scripting`; features (can overlap): state machine 32,
vector 30, data binding 25, layout 18, text 11, nested artboard 10, image 5, scripting 3,
audio 2, mesh 2. 363 renders per runtime (121 per instant, of which 243 with a named artboard),
i.e. 726 renders.

| | `--format riv` | `--format twno` |
|---|---|---|
| Renders compared | 363 | 363 |
| Pixel-identical | **342** | **342** |
| `same_failure` | 21 | 21 |
| Differences, one-sided errors | 0 | 0 |
| Unexplained differences | 0 | 0 |
| Duration (3 renders in parallel) | 333 s | 355 s |

The 21 `same_failure` are all `relative_data_bind_path.riv` (7 renders, 3 instants): the
process aborts (SIGABRT, debug build assertion) in the fork as in the
official runtime. To be examined in P4-1c. The `.twno` files (signature `TWNR`) give exactly the same
statuses as the `.riv` files. This measurement applies to the `gl` backend, a debug build and a
single GPU.

## Tests

`python -I -m unittest discover -s tools/parity/tests`: render plan (instants, artboards,
unique keys), sample (determinism, feature coverage), campaign with a
fake `goldens` (identical, difference, common failure, one-sided failure, `twno` mode, missing
source, explained difference), report (Markdown, explained differences file), comparator on
synthetic PNGs (identical, one pixel, size, alpha, missing file), `bench.py` statuses
(corrupted PNG, no PNG, stale PNG).
