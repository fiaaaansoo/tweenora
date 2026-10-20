# Phase 1 non-regression (P1-6)

> Note of 2026-10-20: the figures below (2601 cases, 471 rewritten files of which 391 at the root of `unit_tests/assets`) were measured before the removal of 7 third-party files and of the 7 test cases that read them (task `publication-8-retrait-runtime-parite`). They have not been recomputed.

P1-6 report: the runtime unit test suite, rerun after P1-0 to
P1-5, first on the original `.riv` files, then on the same files rewritten as
`.twno`. To be compared with the P0-4 baseline (`unit-tests-daf55385.md`).

## Context

| Item | Value |
|---|---|
| Date | 2026-10-15 |
| Commit | `4f0c887e` (working branch of the phase 1 batch, `main` at `c37f2620` plus the close-out of P1-3) |
| Binary | `runtime/tests/unit_tests/out/debug/unit_tests.exe`, built on 2026-10-15 at 21:55, after all the phase 1 changes to `runtime/` |
| Machine, compiler, toolset | those of the P0-4 baseline (Windows 11 Pro, MSVC 14.44.35207, toolset `msc`, debug) |
| Framework | Catch v2.13.7 |
| Filter | the one in `AGENTS.md`: excludes the 3 D3D tests that crash ("Graphics Tools" missing) and the hidden `[.]` tests |

## Result

| | P0-4 baseline | original `.riv` | `.twno` |
|---|---|---|---|
| Test cases run | 2597 | **2601** | **2601** |
| Passed | 2597 | **2601** | **2597** |
| Failures | 0 | **0** | **4**, see below |
| Assertions | 133308114 | 133308203 | 133308128 (4 failed) |
| Duration | 143 s | 155 s | 164 s |
| Exit code | 0 | 0 | 4 |

- **Original `.riv`**: `All tests passed (133308203 assertions in 2601 test
  cases)`. This is the baseline (2597) plus the 4 cases added by P1-1, with no
  failure.
- **`.twno`**: 2597 cases passed out of 2601. The 4 failures are expected: they
  check the signature of the test file itself.

| Failing case | Assertion | Why |
|---|---|---|
| `a file with the TWNR signature is read` | `runtime_header_signature_test.cpp:16`, `memcmp(bytes, "RIVE", 4) == 0` | the fixture is read as `RIVE` bytes to build its variants |
| `a file with the RIVE signature is still read` | same | same |
| `a file with any other signature is rejected` | same | same |
| `Layout image composes user scale on top of fit for 7.2 files` | `data_binding_images_test.cpp:476`, `legacyBytes[0] == 'R'` (Catch shows line 167) | the test expects a `RIVE` file to compare it with its recent version |

The 4 cases therefore fail because their starting file is no longer a `RIVE`,
not because the runtime reads a `.twno` wrongly. The other 2597 cases, whose tests
load most of the 471 rewritten files (391 at the root of
`unit_tests/assets`, 80 in the subdirectories), give the same results with
the `TWNR` signature. The 4 cases
already pass on the original `.riv` files, and reading a `TWNR` file is
covered by `[signature]` (P1-1).

Unchanged since P0-4: the 3 tests that crash the process (`d3d11sdklayers.dll`)
remain excluded, and the 10 cases of `texture_compressor_test` and
`fence_wait_thread_test` are not built (D15 deviation of P1-0).

**Reading of the P1-6 criterion** ("2597 passed plus the new P1-1 tests,
0 failures"): met on the original `.riv` files (2597 + 4 = 2601 passed, 0 failures).
On the `.twno` files, 0 read failures and 4 signature assertions that cannot
hold on a `TWNR` file, hence 2597 passed out of 2601.

## Procedure

From `runtime\tests\unit_tests`, with an up-to-date binary (`.\test.bat --toolset=msc -m
"glsl_mix"` builds it), in a regular Windows PowerShell 5.1 with the PATH from
`AGENTS.md`:

1. `.riv`: the filtered suite from `AGENTS.md`, redirected through `cmd /c` (`--%` swallows
   the `>` redirection).
2. `.twno`: rewrite the signature of the 471 `.riv` files in `unit_tests\assets` in place,
   same name, same bytes except the first 4:

   ```python
   import sys
   from pathlib import Path
   sys.path.insert(0, "tools")
   import twno_convert
   for p in Path("runtime/tests/unit_tests/assets").rglob("*.riv"):
       p.write_bytes(twno_convert.riv_to_twno(p.read_bytes()))
   ```

   then run the same suite, and restore with
   `git checkout -- runtime/tests/unit_tests/assets` (verified: `git status` empty).

The tests open their files by a hard-coded name (`assets/foo.riv`): they cannot be
renamed to `.twno` without modifying the tests. This has no effect, because the runtime
reads the signature, not the extension (P1-1, P1-2).

## Limits

- The unit suite is the only part that was run. The reference images
  (`tests/goldens`, `gms`) and the pixel render comparison are for
  phase 4 (clock-driven animation: see `docs/INVENTAIRE_RIV.md`).
- Only the MSVC toolset on Windows is exercised: no Linux, macOS, wasm or
  Android.
- The 20 `.riv` files of `runtime/tests/web_scripting` (web runtime) are not
  exercised, and the `.twno` pass keeps the names as `.riv`: handling of the
  extension is not tested (the runtime does not read it).
- Milestone M1 is not reached by this report alone: P1-4 (legal notices,
  blocked by D13) remains to be done.
