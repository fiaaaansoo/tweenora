# Render parity bench (P4-1a)

P4-1a report: reference bench to compare the rendering of the fork (`runtime/`)
with that of the official runtime (`vendor/rive-runtime`, commit `daf55385`), using
the `goldens` tool and the OpenGL backend (`-b gl`). The following subtasks
(P4-1b, P4-1c) build on this bench.

## What the comparison proves

The fork is the official runtime plus renamings (D6) and D15 deviations
(`docs/UPSTREAM.md`). Comparing its rendering with the official one, built with the
same toolset, proves that these changes do not alter the rendering. It does not
prove conformance to the Rive editor itself (not comparable here). Only
the `gl` backend is covered: `d3d` requires the Windows "Graphics
Tools" feature (absent), `vk` fails on this machine (see `AGENTS.md`).

## Context

| Item | Value |
|---|---|
| Date | 2026-10-17 |
| Machine | Windows 11 Pro 10.0.22631, 12 logical processors, 16 GB of memory, NVIDIA GeForce RTX 3060 GPU (OpenGL context via `-b gl -d`) |
| Compiler, toolset | MSVC 14.44.35207, toolset `msc`, debug configuration (the one from `AGENTS.md`) |
| Fork | the repository's `runtime/`, `main` at `adb39dd5` |
| Official | `vendor/rive-runtime` at `daf55385`, cloned into `tools/parity/.ref/rive-runtime/` |
| `goldens` output | one 1600 x 1600 RGBA PNG per file, named after the `.riv` name (1 x 1 grid) |

## Location of the official build

`vendor/` is read-only: building there would write `out/` and `dependencies/` into it.
The official build is therefore done in `tools/parity/.ref/rive-runtime/`, a Git
clone of the `vendor/rive-runtime` directory (`git clone vendor/rive-runtime
tools/parity/.ref/rive-runtime`, same commit), ignored by git (`.gitignore`:
`tools/parity/.ref/` and `tools/parity/.work/`). The clone guarantees the exact commit
and a clean tree; `vendor/` is not modified. The full path stays within
Windows limits thanks to `core.longpaths` (environment variables from
`AGENTS.md`).

## Building the two binaries

A single command, from the repository root, in a regular Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File tools\parity\build_goldens.ps1
powershell -ExecutionPolicy Bypass -File tools\parity\build_goldens.ps1 -Target ref -Mp 2
```

The script clones the official runtime if missing, enables `core.longpaths`, puts `sh.exe` on
the PATH, limits parallel `cl.exe` builds (`-Mp`, 4 by default), runs
`..\build\build_rive.ps1 --toolset=msc -- goldens` in `runtime\tests` then in
`.ref\rive-runtime\tests`, reads the MSBuild summary from the log (the build script does not
propagate the return code) and fails if it counts an error. Outputs:

```text
runtime\tests\out\debug\goldens.exe                                   fork
tools\parity\.ref\rive-runtime\tests\out\debug\goldens.exe            official
```

| Binary | Duration (first build, dependencies included) | Errors | Warnings |
|---|---|---|---|
| Fork | about 4.5 min | 0 | 33 on the first pass, 1 on resume |
| Official | 6 min 14 s | 0 | 18 |

Release configuration (P4-1c): `-Config release -NoLto` (outputs in `out\release\`). Without `-NoLto`,
the fork's link fails (`LNK1257`, the `C4743` "vftable of different size" become errors under
`/WX`); premake's `--no-lto` option fixes it without touching the rendering. Changing arguments on an already configured
`out\release` directory requires deleting it (premake refuses otherwise). Release build: fork
5 min 51 s, official 5 min 18 s.

Pitfalls encountered:

- The `CL` environment variable limits the internal parallelism of `cl.exe`
  (free memory dropped to 0.5 GB on this machine): the value must be
  written `-MP4`, not `/MP4`. `sh.exe` (MSYS) converts a value that starts
  with `/` into a path (`C:/Program Files/Git/MP4`) and the build fails
  (`C1083 ... 'C:/Program'`); `MSYS2_ENV_CONV_EXCL=CL` also prevents this
  conversion.
- Same pitfall as in `AGENTS.md`: the return code of `build_rive.ps1` is 0 even
  on failure; read the summary (`Error(s)`, or `Erreur(s)` with a French-locale MSBuild). The PowerShell 5.1 log is UTF-16.

## Running a render

```powershell
$env:RIVE_GOLDENS_ADVANCE = 30
tools\parity\.ref\rive-runtime\tests\out\debug\goldens.exe -b gl -d -s <file.riv> -o <directory>
```

- `RIVE_GOLDENS_ADVANCE=N` advances the scene by N frames at 60 fps before rendering
  (`goldens.cpp`, `advanceScene`); without it, a single `advanceAndApply(0)`.
  This is what makes the tool deterministic, unlike `player.exe`, which
  advances with the clock.
- `-d` (offscreen) is necessary, `-t` selects the artboard, `-S` the state machine.
- `goldens` only accepts the `.riv` extension (`is_riv_file` in `goldens.cpp`):
  a `.twno` given to `-s` is treated as a directory and fails ("Bad src path").
  To be handled in P4-1c: pass the `.twno` under a `.riv` name (same `TWNR`
  content) or fix the fork's extension test (D15 deviation to record).
- A render takes about 3 seconds, context startup included.

## Tools in `tools/parity/`

| File | Role |
|---|---|
| `manifest.py`, `manifest.json` | frozen list of the 475 parity files (path, group, size, SHA-256, artboards, state machines, features); `python -I tools/parity/manifest.py [--check]` |
| `render.py` | `goldens` command, environment, render of one file |
| `pixeldiff.py` | exact-pixel comparison of two PNGs (RGBA, alpha channel included) |
| `bench.py` | `determinism` (two renders by the same binary) and `compare` (fork against official) |
| `build_goldens.ps1` | build of the two binaries |
| `tests/` | `python -I -m unittest discover -s tools/parity/tests` |

## Manifest of the 475 files

The manifest had 491 files at the close of P4-1a; 7 third-party files were removed from it at publication (task `publication-8-retrait-runtime-parite`), then 4 others (task `publication-16-retrait-fichiers-tiers-2`, 484 to 480) and 3 others (task `publication-18-retrait-fichiers-tiers-3`, 480 to 477), then 2 others (task `publication-19-polices`, 477 to 475); `manifest.py` regenerated it and the figures below are those of the 475 version.

380 `.riv` files at the root of `runtime/tests/unit_tests/assets`, 75 in its
subdirectories, 20 in `runtime/tests/web_scripting` (`fixture/` 15, `stress/` 5):
`manifest.json` freezes them. All 475 are read without error by `twnoinfo` (no
entry in `parse_error`). Detected features (a file can have several): state machine 389, data binding 279, vector 266, layout 191, text 146, nested
artboard 107, scripting 91, image 33, audio 4, mesh 2 (before the removals: 403, 290, 280, 199,
157, 115, 91, 42, 5 and 2). The tests
(`tools/parity/tests/test_manifest.py`) check the exact count, the absence of
duplicates, the existence of the paths, the sorting, the 380 / 75 / 20 split and that the versioned
file is identical to a regeneration.

## Determinism

Sample of 18 varied files (vector, text, image, mesh, state machine,
layout, data binding, scripting, audio, nested artboard; list below),
`RIVE_GOLDENS_ADVANCE=30`, two successive renders of the same file by the same
binary, comparison of the PNG SHA-256 values:

| Binary | Deterministic (PNGs byte-for-byte identical) | Error |
|---|---|---|
| Fork | 16 | 2 |
| Official | 16 | 2 |

No non-deterministic file in this sample (scripting files
included). The 2 errors are identical in both binaries:
`web_scripting/stress/mesh.riv` and `web_scripting/stress/text.riv` abort the
process with a debug build assertion (`!m_content`,
`file_asset_importer.cpp:24`, signal SIGABRT). These are stress files of the web
bench, to be handled separately in P4-1c (identical abort on both sides, so not a difference
of the fork).

## First compared render, fork against official

On the same 18 files, `RIVE_GOLDENS_ADVANCE=30`, `python tools/parity/bench.py
compare`: **16 pixel-identical and byte-for-byte identical** (0 different pixels,
maximum difference 0), 2 errors common to both binaries (above). Files in the
sample:

```text
under runtime/tests/unit_tests/assets/: parity/popsicle_loader.riv, rocket.riv,
stateful_component_image_test.riv, magic_alley_db_reduced_export.riv, luau_shader_signed.riv,
scripted_listener_context.riv, script_path_effects_test.riv, gamepad_inputs_test.riv,
ai_assitant.riv, off_road_car.riv, sound.riv, hosted_audio_file.riv,
layout/matrix/matrix_font.riv, layout/matrix/matrix_image.riv
under runtime/tests/web_scripting/: fixture/gradient_bounds.riv, stress/{data_list,mesh,text}.riv
```

`bench.py compare` statuses: `identical` (pixels and bytes), `identical_pixels_only`,
`different`, `error_a` / `error_b` (only one binary fails; a = fork, b = official),
`both_error`, `compare_error` (unreadable PNG). A failure does not stop the batch. `bench.py` gives one
output directory per file, because `goldens` names the PNG after the file name alone
(two files from different directories could carry the same name).

Negative test (the comparator does detect a difference): `popsicle_loader.riv` rendered by the
fork at 30 frames and by the official runtime at 0 frames: **766972 different pixels**, maximum
channel difference 254. The same file at 30 frames on both sides: 0 different pixels. The unit
tests of `pixeldiff.py` also cover a single-pixel difference, the alpha channel, a different
size and a missing file.

## Limits

- Only 3 of the 15 non-"stress" files of the sample change between 0 and 30 frames
  (`popsicle_loader.riv`, `script_path_effects_test.riv`, `sound.riv`): the image at 30
  frames only proves animation parity for those. State machine
  parity is the subject of P4-2.
- Debug build, `gl` backend only, a single GPU (NVIDIA).
