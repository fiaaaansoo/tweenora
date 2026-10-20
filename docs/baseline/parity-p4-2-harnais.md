# State machine trace harness (P4-2a)

P4-2a report: a small C++ program (`tools/parity/sm_trace/sm_trace.cpp`) plays a file with an action script
and writes a deterministic text trace. It is compiled twice, against the official runtime (`tools/parity/.ref/`) and
against the fork (`runtime/`); a Python comparator (`tools/parity/trace_compare.py`) compares the two traces.

## Decision: option A (source outside `runtime/`)

Taken without the user (absent), recorded here: option A of the task file. The source lives in
`tools/parity/sm_trace/`, compiled against the headers and libraries of each tree (`rive*.lib` for the official one,
`tweenora*.lib` for the fork). Since the `rive` namespace is kept (D6), the same source compiles on both sides. No file
is added to `runtime/`: no D15 deviation, no upstream merge disturbed. Option B (premake tool in
`runtime/tests/`) remains possible if compiling outside premake becomes too fragile; it would add a line to the
D15 register of `docs/UPSTREAM.md`.

## Action script format (JSON lines)

One action per line, validated by `trace_compare.parse_script` before any execution:

| `op` | Fields | Effect |
|---|---|---|
| `advance` | `dt` (seconds, >= 0) | `advanceAndApply(dt)` |
| `bool` | `name`, `value` (boolean) | sets a boolean input |
| `number` | `name`, `value` (number) | sets a numeric input |
| `trigger` | `name` | fires a trigger |
| `pointer` | `kind` (`down`, `move`, `up`), `x`, `y` | pointer event at the artboard position |

No real clock: time only passes through `advance`. A missing input is ignored without error (same behavior on both
sides).

## Trace format (version 1, JSON lines)

1. Header: `{"trace": 1, "file": <name>, "artboard": <name>, "stateMachine": <name>}`. Default artboard and state machine
   if not named (the artboard's default state machine, otherwise the first one).
2. One line per action: `{"step": i, "action": {...}, "needsAdvance": bool, "changed": [{"index": k, "state": <typeKey>}],
   "inputs": [{"name", "kind", "value"}], "events": [{"name", "delay"}]}`. `changed` is `stateChangedByIndex` (the
   `typeKey` of the current state of each layer whose state changed), `events` is `reportedEventAt` in order, with
   the delay in seconds; floats are written with `%.9g`.
3. End: `{"end": true, "steps": n}`. A trace without this line, with an unreadable line, with non-consecutive steps or a
   wrong count is invalid or truncated.

The comparator returns `identical`, `different` (first difference: step, field, values on both sides), `truncated` or
`invalid`. Limits of the format: a layer's state is only given when it changes, and by its `typeKey` (no state name:
`LayerState` does not expose one); view model values are not traced.

## Building (Windows, `msc`)

```powershell
powershell -ExecutionPolicy Bypass -File tools\parity\sm_trace\build_sm_trace.ps1
```

Prerequisite: the `goldens` libraries built in the desired configuration (`build_goldens.ps1 -Config release
-NoLto`). Outputs: `tools\parity\sm_trace\out\fork\sm_trace_release.exe` and `out\ref\sm_trace_release.exe`, plus
`command_release.txt` (compile command line for each side). Verified: the 25 compile options (`/std:c++17`, `/GR-`,
`/EHs-c-`, `/MT`, `/O2`, the definitions...) are identical on both sides; only the paths and the library names
(`tweenora*` versus `rive*`) differ. The definitions are taken from the generated `rive.vcxproj`
projects.

## Proof of life (fork versus official, release)

```powershell
python -I tools\parity\run_trace.py --keep tools\parity\.work\sm
```

| Case | File | Kind | Steps | Result |
|---|---|---|---|---|
| `triggers` | `state_machine_triggers.riv` | trigger | 7 | identical |
| `pointer_bool` | `pointer_events.riv` | pointer and boolean | 15 | identical |
| `numbers` | `blend_test.riv` | numbers | 13 | identical |
| `events` | `looping_timeline_events.riv` | events (6 reported, non-zero delays) | 30 | identical |

Negative test: a trace in which an input's `kind` has been altered is rejected (`different`, field `inputs`, step 0);
`tests/test_run_trace.py` covers a missing event, an event with a different delay, truncated output and a binary
that fails.

## Limits

- Only four files: automatic generation of scripts from the inputs is the next task (P4-2b).
- Release build only; a single toolset (`msc`).
- The events of the proof files have no name (the `name` field is empty): only their delay tells them apart.
- Render layers, view models and script listeners are not traced.
- `NoOpFactory`: no image, no drawing; a rendering difference does not show up here (P4-1).
