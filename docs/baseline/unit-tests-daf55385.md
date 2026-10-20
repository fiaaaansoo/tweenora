# Runtime unit test baseline (daf55385)

P0-4 reference report: state of the Rive runtime unit tests, unmodified, before any Tweenora change. The failures listed here already existed and
must not be attributed to the changes of phase 1 and later.

## Context

| Item | Value |
|---|---|
| Date | 2026-10-14 |
| Base commit | `daf55385b71fb861b2a1ae2930ae4492832d5db5` (upstream tag `runtime-v0.1.552`) |
| `runtime/` tree | `cf3797c2d9fc82a43a0e2a063e25d1a911593711`, identical to the base before and after the measurements. Measurements taken with an uncommitted local patch, equivalent to the P1-0 guard (since removed); since P1-0, only `tests/unit_tests/premake5.lua` differs from the base (D15, `docs/UPSTREAM.md`) |
| Machine | Windows 11 Pro 10.0.22631.6199 |
| Compiler | Visual Studio 2022 17.14.29, MSVC 14.44.35207 |
| Toolset | `msc` (clang-cl absent, see `AGENTS.md`), not Rive's default clang |
| Configuration | debug, `--with_rive_tools --with_rive_audio=external --with_rive_scripting --no_ffp_contract` |
| Framework | Catch v2.13.7 |

## Result

| | Count |
|---|---|
| Tests in the default suite (hidden `[.]` tests excluded) | 2600 |
| Passed | **2597** |
| Assertion failures | **0** |
| Process crashes (D3D, see below) | **3** |
| Tests that cannot be built, hence not run | 10 (2 files) |

Catch summary of the full suite without the 3 tests that crash:
`All tests passed (133308114 assertions in 2597 test cases)`, in 143 s.

Each test run in its own process gives the same outcome: 2597 exit codes
0 and 3 crashes, 270 s cumulative. The longest test is
`packNormalizedDepth-exhaustive-0-to-1` (16 s).

Worth knowing when reading these figures:

- 5 passed tests declare themselves skipped (`no GPU render context
  available, skipping` x3, `no Ore GL backend available headless; skipping` x2):
  Catch counts them as passed. GPU coverage of this baseline is therefore
  partial.
- 22 passed tests contain no assertion (`assertions: - none -`).
- The number of assertions depends on the exhaustive traversal of a few numeric
  tests: it is a reference point, not a quality metric.

## Deviations from the standard run

### 1. The `unit_tests` target does not build outside Rive's monorepo

`.\test.bat` fails at build time, 3 constant MSBuild `C1083` errors:

- `tests/unit_tests/premake5.lua` unconditionally adds
  `../../../texture_compressor/src/write_ktx2.cpp` and two include
  directories (`../../../rive_native/native/include`,
  `../../../texture_compressor/src`), siblings of `runtime/`.
- These sources do not exist in Rive's public repository nor in a public
  repository under these names (404 for `rive-app/rive-native`, `rive_native`,
  `texture_compressor`, checked on 2026-10-14). The reference clone
  `vendor/rive-runtime`, not versioned and present in the main checkout,
  contains the same lines: this is not a defect of the Tweenora import.
- Files affected: `texture_compressor/src/write_ktx2.cpp` (source), and the tests
  `runtime/texture_compressor_test.cpp` (7 cases, includes `write_ktx2.hpp`)
  and `renderer/fence_wait_thread_test.cpp` (3 cases, includes
  `rive_native/fence_wait_thread.hpp`).

Workaround: since P1-0, `tests/unit_tests/premake5.lua` tests for the presence of
`rive_native/native/include/rive_native/fence_wait_thread.hpp` and of
`texture_compressor/src/write_ktx2.cpp` (paths computed relative to the script,
one guard per directory). When a source is absent, the target adds neither its
include directory nor `write_ktx2.cpp`, and excludes the corresponding test file with `removefiles`. When it is present, the target is Rive's. The
baseline was measured with an equivalent local patch, since removed.

**Coverage gap:** these 10 test cases (`texture_compressor_test` 7,
`fence_wait_thread_test` 3) are **excluded, embedder code absent**, hence **not
covered**, as long as `rive_native/` and `texture_compressor/` are not public.
The baseline remains valid: 2600 tests listed, 2597 passed.

### 2. Three tests crash the process: D3D11 debug layers missing

| Test | File | Result |
|---|---|---|
| `ore binds a fragment compiled apart from its vertex` | `renderer/ore_split_stage_test.cpp:340` | constant crash |
| `ore layouts declare non-filtering samplers for depth-only use` | `renderer/ore_split_stage_test.cpp:365` | constant crash |
| `synthesizedFailureType` | `renderer/rendering_tests.cpp:111` | constant crash |

Constant: 3 crashes out of 3 for each (once in the test-by-test pass,
twice when rerun in isolation).

Message: `fiddle_context_d3d.cpp:310: D3D error ... D3D11CreateDevice(...)`
(`DXGI_ERROR_SDK_COMPONENT_MISSING`, "missing or incompatible SDK component"),
exit code `0xC0000409` (127 as seen from Git Bash).

Cause: in debug configuration, `fiddle_context_d3d.cpp` creates the device
with `D3D11_CREATE_DEVICE_DEBUG`, which requires the optional Windows feature
"Graphics Tools". On this machine `d3d11sdklayers.dll` is absent from
`System32`. The `VERIFY_OK` macro then exits the process, without a test failure.

Consequence: `.\test.bat` run as is stops at the 224th test and prints
no summary. A run without a filter therefore does not give a baseline.

These three tests are to be replayed once "Graphics Tools" is installed (human
action, administrator rights). There is no failure attributable to Rive's code.

## Commands

In a regular Windows PowerShell 5.1, with the Git variables and the PATH from
`AGENTS.md` (§ Verified commands).

From `runtime/tests/unit_tests`, build (and run the suite, which
stops at the first D3D crash):

```powershell
.\test.bat --toolset=msc
```

A single test or a filter, with incremental rebuild:

```powershell
.\test.bat --toolset=msc -m "glsl_mix"
```

Full suite without the 3 crashes, without going through `test.bat` (a
`.\test.bat` must have built beforehand, it also creates `silvers/tarnished/`):

```powershell
.\out\debug\unit_tests.exe --% ~"synthesizedFailureType" ~"ore binds a fragment compiled apart from its vertex" ~"ore layouts declare non-filtering samplers for depth-only use" ~[.]
```

`--%` is necessary: under Windows PowerShell 5.1, passing the filter in single
quotes with inner double quotes mangles it (0 tests selected, verified).
With `--list-test-names-only` in front, the same line does list 2597 tests.

The filter is mandatory: a purely negative filter also runs the hidden
`[.]` tests, including benchmarks that crash on the same D3D problem.

One test per process (useful when a crash hides the rest of the suite): list with
`.\out\debug\unit_tests.exe --list-test-names-only`, then run each escaped name
(commas and brackets preceded by `\`) with `--warn NoTests`.

## Logs

The raw logs are not attached (several MB, MSVC warnings
included). Full build of `unit_tests` (dependencies included): 6 min 52,
245 warnings, 3 errors without the exclusion of absent sources. With the
exclusions (local patch, then the P1-0 guard): 0 errors, and incremental rebuilds
take a few seconds.
