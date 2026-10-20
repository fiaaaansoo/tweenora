# Native state machine comparison (P4-2b)

> Note of 2026-10-20: the original campaign covered 403 files with a state machine (491 in total), of which 402 identical traces, 1 common failure, 13,676 steps, 363 files with a state change, 12 with an event (65 events) and 38 with an input. 7 third-party files were removed from the repository and from the manifest (task `publication-8-retrait-runtime-parite`); the campaign was replayed on the 396 remaining files (`sm_compare.py` then `--format twno`). 4 other third-party files, 2 of them with a state machine, were removed afterwards (task `publication-16-retrait-fichiers-tiers-2`); the campaign was replayed the same way on the 394 remaining files with a state machine (393 identical traces, 1 common failure, 13,371 steps, 354 files with a state change, 11 with an event, 36 with an input). 3 other files, 3 of them with a state machine, were removed (task `publication-18-retrait-fichiers-tiers-3`) and the campaign was replayed the same way on the 391 remaining files with a state machine (390 identical traces, 1 common failure, 13,272 steps, 351 files with a state change, 11 with an event, 36 with an input). 2 other files with a state machine were removed (task `publication-19-polices`) and the campaign was replayed the same way on the 389 remaining files with a state machine (388 identical traces, 1 common failure, 13,156 steps, 349 files with a state change, 11 with an event, 34 with an input); the figures in the text are those of this last replay.

P4-2b report: for each file of the manifest that has a state machine, an action script is generated from its
structure, played by the P4-2a trace harness built against the fork and against the official runtime, and the two traces
are compared (changed states, input values, events with their delay, `needsAdvance`, at each step). Release without
LTO, a single toolset (`msc`).

## Result

For each of the two formats (`.riv` rendered by both; `.twno` rendered by the fork, original `.riv` rendered by
the official runtime), over the 389 files with a state machine in the manifest (475 in total):

| Status | Files |
|---|---|
| Identical traces | 388 |
| Common failure (`same_failure`) | 1 |
| Difference, one-sided error | 0 |
| Unexplained difference | 0 |

What the traces exercised (identical for both formats): 13,156 steps in total; 349 files with at least one
state change; 11 files with at least one reported event (63 events, delays included); 34 files with at
least one input. Campaign duration: about 6 seconds per format (4 files in parallel).

The only common failure is `joel_signed.riv`: both runtimes print `Failed to import object of type 106` (signed
script object not imported in this configuration) and find no state machine. The behavior is the same on both
sides, but no trace was compared for this file: known limit.

**No behavior difference between the fork and the official runtime was found**; no fix to `runtime/` was
needed and no line is added to the D15 register.

## Method

- `sm_trace.exe <file> --describe` gives the default artboard and state machine, the artboard size and its inputs
  (name, type). The descriptions from the fork and from the official runtime must be equal, otherwise the file is a difference.
- `tools/parity/sm_actions.py` generates the script: one start-up step, each boolean to true then false, each number to
  0, 1, -1, 50 and 100, each trigger fired alone followed by two steps, then five pointer positions (center and four
  quarters) with move, press and release, and a final second; a 0.25 s step after each action; at most
  400 actions. Deterministic for a given file.
- `tools/parity/sm_compare.py` runs both binaries on each file (`--format riv` or `--format twno`), compares the
  traces, returns a JSON summary and exit code 1 on any unexplained difference (`tools/parity/sm_explained.json`, empty).

## Limits

- Default artboard and default state machine (otherwise the first one) of each file: the other artboards and the other
  state machines of the files are not played.
- Inputs are fixed values, not combinations: transitions conditioned on two inputs at once are
  only reached by chance.
- Pointers target five positions of the artboard, not the target shapes of the listeners; few files have reported
  events (12).
- Inputs bound by data binding or scripts that set their own values are not driven; view models are not
  traced; audio is not played (events are, the trace compares events, not sound).
- A layer's state is only given by the `typeKey` of the current state when it changes (no state name).
- `NoOpFactory`: no image. A single toolset, release only, a single machine.

## Reproduce

```powershell
powershell -ExecutionPolicy Bypass -File tools\parity\build_goldens.ps1 -Config release -NoLto
powershell -ExecutionPolicy Bypass -File tools\parity\sm_trace\build_sm_trace.ps1
python -I tools\parity\sm_compare.py
python -I tools\parity\sm_compare.py --format twno
python -I -m unittest discover -s tools\parity\tests
```
