# Continuous integration: unit tests and fast tests (P4-3a, state as of 2026-10-20)

**Real verification of 2026-10-20 (public repository):** a throwaway branch with a deliberately failing test showed that `fast-tests` stayed green: under PowerShell, a multi-command step only keeps the exit code of the last one. The Python tests step was switched to `shell: bash` (stops at the first error) and the `push` trigger is limited to branches (an upstream tag was launching the workflow). Measured time: `fast-tests` about 2 min 30 s; `unit-tests`: see the result below once it has finished.

**Update of 2026-10-20 (evening):** the `workflow` scope of the `gh` token was granted by the user and the workflow is now in `.github/workflows/tests.yml` (the static test reads it from there). Both jobs carry `if: ${{ !github.event.repository.private }}`: while the repository is private, they are skipped (seen on `main` and on the PR: "skipped" runs) and consume no minutes; they trigger as soon as the repository is public (free minutes). The real verification (green on `main`, red on a deliberate failure, measured time) therefore remains to be done once the repository is public. The expected count is 2598 unit tests since the removal done by task `publication-8` (the 2601 further down is the earlier value).

**State: draft ready, not pushed, not run.** The workflow is not in `.github/workflows/`: the `gh` token on
this machine does not have the `workflow` scope (`gh auth status`: `gist`, `read:org`, `repo`), so a push of this
file would be refused, and the choice of platform and of GitHub Actions minutes consumption is up to the user
(absent). The workflow is now in `.github/workflows/tests.yml` (see the update above), with a static test.

## Proposed platform: Windows

Provisional decision, the least risky (to be confirmed): `windows-latest`. It is the only platform where the fork and the official
runtime have been built and tested (`--toolset=msc`, 2601 unit tests passed outside 3 excluded); Linux and macOS have
never been exercised (`docs/baseline/non-regression-p1-6.md`): choosing Linux would first require discovering and handling
any build differences.

Estimate, not measured on GitHub (no runner was launched):

| Step | Source of the estimate | Duration |
|---|---|---|
| Debug build of `unit_tests` (first time, premake dependencies included) | `goldens`: 4.5 to 6 min in release on this 12-processor machine; a GitHub runner has 4 | 15 to 30 min (to be measured) |
| Unit suite (2601 tests) | `AGENTS.md`: 143 s on this machine | 3 to 6 min |
| Fast Python and Node tests | `tools/parity/tests`: about 75 s; other suites a few seconds | 2 to 4 min |

At the Windows rate of a private repository, a run consumes on the order of 25 to 40 runner minutes, multiplied by the
Windows multiplier of the account's GitHub plan; without a cache of the build toolchain, every push pays for the build again. A cache
of the premake dependencies and of `runtime/tests/dependencies/` is to be added once the real time is measured.

## What the draft contains

- Trigger: every push and every pull request; cancellation of duplicate runs for the same ref.
- Job `fast-tests`: `python -I -m unittest discover` on `tools/tests`, `tools/parity/tests`, `web/examples/tests`,
  `web/deploy/tests`, and `node --test web/parity/render-compare.test.mjs`. Dependencies: Pillow and numpy.
- Job `unit-tests`: build with `test.bat --toolset=msc -m "glsl_mix"` (same variables as `AGENTS.md`: `CL=-MP4`,
  `core.longpaths`, `sh.exe` on the PATH), then the suite with the exact filter from `AGENTS.md` (the static test compares the two),
  build log published as an artifact.
- Excluded from the push path: WASM build (about 15 minutes), upstream jest (22 minutes), `goldens` renders, trace harness
  (they require `vendor/rive-runtime`, absent from the repository; P4-3b).

Limits of the draft, not verified: writing the log with `*>` around `test.bat`, the behavior of `test.bat` under
a runner without an interactive session, and whether 4 processors fit within the 90-minute timeout. Measured locally, in this
worktree without `vendor/` or a generated assets directory (close to a fresh clone, without being exactly one): `tools/tests` 133 tests
passed, `web/examples/tests` 61, `web/deploy/tests` 31, `tools/parity/tests` 220, `node --test web/parity/render-compare.test.mjs`
14; none of these tests references `vendor/`.

## To finish (user action)

1. Choose Windows or Linux and accept the minutes consumption; enable Actions on `fiaaaansoo/tweenora` if needed.
2. `gh auth refresh -s workflow` (interactive).
3. Push a branch with the workflow from `.github/workflows/tests.yml`, measure the real time, verify green,
   then a deliberate failure (throwaway branch) to verify red; adjust the durations above and add the cache.
4. Update the "Continuous integration" section of `AGENTS.md` with the real measurements.
