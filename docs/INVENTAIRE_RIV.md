# Inventory of `.riv` mentions (P1-2)

Compiled on 2026-10-15 over `runtime/` (base `daf55385`, see `UPSTREAM.md`),
excluding `dependencies/`, `out/` and binary files. Rule (D5, D6): the runtime
opens `.riv` and `.twno` files; we rename only what the user reads or types.
Internal mentions stay, to keep the upstream merge simple.

## Summary

The categories below overlap with the 41 mentions of the next section:
the player message (`player.cpp:1036`) counts among the 5 displayed texts, and
`src/wasm/web/README.md:155` among the 8 documentation lines.

| Category | Lines | Decision |
|---|---|---|
| Comments in `src/`, `include/` and `tests/player/` | 39 | Unchanged (internal, D6) |
| Text displayed by a `tests/` tool | 5 | **Switched to `.twno` by P1-2** |
| Documentation (README) | 8 | Handled in P1-3 |
| Extension filter on a folder | 3 | Kept as is, see below |
| Test file names in `tests/unit_tests/` | 1,160 (159 files) | Unchanged: these are the parity `.riv` files |
| Other comments and fixture names (`dev/`, `bench`, `web_scripting`, ...) | see "Internal" | Unchanged |

`rivinfo/` contains no mention: the tool opens the path given by
`--file`, without looking at the extension.

## The 41 mentions in `src/`, `include/`, `rivinfo/` and `tests/player/`

These are the ~40 mentions of the plan (`PLAN.md` § 4). 39 are comments, 2
are visible: a piece of documentation (`src/wasm/web/README.md`, handled in P1-3) and
a player message (handled here, with its equivalents below).

| File:line | Kind | Excerpt |
|---|---|---|
| `runtime/src/animation/linear_animation.cpp:56` | code comment | `// empty on .riv-loaded animations).` |
| `runtime/src/artboard.cpp:438` | code comment | `// hydration passes. initialize() only ever runs for .riv-imported` |
| `runtime/src/artboard.cpp:1572` | code comment | `// • '.riv'-loaded objects — 'CoreIdType::runtimeDeserialize'` |
| `runtime/src/core/field_types/core_id_type.cpp:29` | code comment | `// '.riv' wire format read into an editor build: the on-wire value` |
| `runtime/src/file.cpp:326` | code comment | `// The .riv importer is exclusively the runtime path (editor flow` |
| `runtime/src/importers/text_asset_importer.cpp:21` | code comment | `// build verify .riv files signed locally via 'SampleSigningContext', which` |
| `runtime/src/layout_component.cpp:693` | code comment | `// and the first pump runs. Runtime .riv imports are marked validated` |
| `runtime/src/lua/renderer/lua_gpu.cpp:603` | code comment | `/// ShaderAsset from file->assets() (runtime .riv path).` |
| `runtime/src/lua/renderer/lua_gpu.cpp:630` | code comment | `// Runtime path: ShaderAsset from the .riv file's asset list. Same` |
| `runtime/src/shapes/image.cpp:149` | code comment | `// Runtime '.riv' loads don't need this — the RenderImage is` |
| `runtime/src/shapes/mesh.cpp:52` | code comment | `// Runtime .riv loads: indices must be present and in range.` |
| `runtime/src/solo.cpp:117` | code comment | `// it via activeComponentIdChanged). Runtime .riv imports are marked` |
| `runtime/src/wasm/web/README.md:155` | web demonstrator documentation (handled in P1-3) | `'--no-wamr' skips rive-cli and loads the committed '.riv' files.` |
| `runtime/include/rive/animation/linear_animation.hpp:44` | code comment | `// don't fit the 'unique_ptr' ownership contract used by the '.riv'` |
| `runtime/include/rive/animation/linear_animation.hpp:46` | code comment | `// coexistent within a single editor binary: a runtime '.riv'` |
| `runtime/include/rive/artboard.hpp:528` | code comment | `// their onAddedDirty. Runtime '.riv' loads install the factory via` |
| `runtime/include/rive/artboard.hpp:532` | code comment | `// Editor-mode Drawable registration. Runtime '.riv' loads populate` |
| `runtime/include/rive/artboard.hpp:544` | code comment | `// Runtime '.riv' loads populate these via 'ArtboardImporter::` |
| `runtime/include/rive/artboard.hpp:554` | code comment | `// the runtime Artboard. Runtime '.riv' loads still go through` |
| `runtime/include/rive/artboard.hpp:565` | code comment | `// 'sortDependencies' is private in the runtime '.riv' load path` |
| `runtime/include/rive/artboard.hpp:1054` | code comment | `/// does internally for '.riv'-loaded sources).` |
| `runtime/include/rive/backboard.hpp:12` | code comment | `// panel layout, never wired through coop or the '.riv' file. The` |
| `runtime/include/rive/backboard.hpp:20` | code comment | `// stacked panel layout. Never reaches '.riv' or coop. Empty stubs` |
| `runtime/include/rive/component.hpp:252` | code comment | `/// 'Filthy' at construction; the runtime '.riv' path runs an` |
| `runtime/include/rive/core/field_types/core_color_type.hpp:14` | code comment | `// the runtime '.riv' wire stays raw uint32. Used by generator-` |
| `runtime/include/rive/core/field_types/core_fractional_index_type.hpp:38` | code comment | `// never reached from '.riv' import. Provided for symmetry with` |
| `runtime/include/rive/core/field_types/core_id_type.hpp:12` | code comment | `// On the '.riv' wire (runtime file format) an Id is a single varuint —` |
| `runtime/include/rive/core/field_types/core_id_type.hpp:40` | code comment | `// Runtime wire format ('.riv' file): single varuint.` |
| `runtime/include/rive/core/id.hpp:14` | code comment | `// 'm_Objects' array (runtime '.riv' file layout).` |
| `runtime/include/rive/core/id.hpp:20` | code comment | `// b) '.riv' (runtime) references loaded at edit time:` |
| `runtime/include/rive/core/id.hpp:36` | code comment | `// not '{0, 0}'. Runtime '.riv' files use index '0' as a legitimate` |
| `runtime/include/rive/lua/rive_lua_libs.hpp:2965` | code comment | `// during requestVM), then \|fileAsset\| if non-null (runtime .riv path).` |
| `runtime/include/rive/relative_local_asset_loader.hpp:16` | code comment | `/// path relative to the original .riv file looking for them.` |
| `runtime/include/rive/shapes/paint/linear_gradient.hpp:33` | code comment | `// a '.riv'-loaded file's importer-added stops don't get` |
| `runtime/include/rive/shapes/path.hpp:109` | code comment | `/// ('Component::childOrder().compareTo(...)'). The runtime '.riv' import` |
| `runtime/include/rive/shapes/path.hpp:126` | code comment | `/// retries and mixed-mode ('.riv'-imported + coop-edited) files.` |
| `runtime/include/rive/text/text.hpp:192` | code comment | `/// comparator. The runtime '.riv' import preserves sibling` |
| `runtime/include/rive/wasm/wasm_scripting_vm.hpp:20` | code comment | `/// Executes a .riv's self contained wasm script module (VM + bindings +` |
| `runtime/tests/player/player.cpp:55` | code comment | `// The FPS readout drawn over the .riv, and the resources it needs.` |
| `runtime/tests/player/player.cpp:783` | code comment | `// Draw the .riv.` |
| `runtime/tests/player/player.cpp:1036` | error message displayed when no file is given to the player | `fprintf(stderr, "no .riv file specified");` |

## Text displayed by a `tests/` tool: switched to `.twno` (P1-2)

| File:line | Before | After |
|---|---|---|
| `runtime/tests/player/player.cpp:1036` | `no .riv file specified` | `no .twno or .riv file specified` |
| `runtime/tests/command_buffer_example/command_buffer_example.cpp:267` | `no .riv file specified` | `no .twno or .riv file specified` |
| `runtime/tests/goldens/goldens_arguments.hpp:17` | `Reads a .riv file, ...` | `Reads a .twno or .riv file, ...` |
| `runtime/tests/wasm_gc_bench/wasm_gc_bench.cpp:71` | `usage: wasm_gc_bench <file.riv> [frames]` | `usage: wasm_gc_bench <file.twno|file.riv> [frames]` |
| `runtime/tests/deploy_tests.py:80` | `INPUT directory of .riv files to render` | `INPUT directory of .twno or .riv files to render` |

These are displayed strings, not behavior changes: no D15 deviation.
The messages say `.twno or .riv` because both can be opened.

## Documentation: handled in P1-3

`runtime/README.md:10`, `:20`, `:109` (the runtime "loads `.riv` files", the
player "loads and displays a `.riv`"), `runtime/renderer/README.md:24`, `:37-39`
(`path_fiddle` usage), `runtime/src/wasm/web/README.md:155`.

## Behavior: kept as is

| File:line | Mention | Why |
|---|---|---|
| `runtime/tests/goldens/goldens.cpp:288` | `is_riv_file` keeps only `.riv` when `goldens` walks a folder | Behavior change, hence a D15 deviation. Not needed to open a specific file. To be revisited in P1-6 if the reference tests on `.twno` files go through a folder |
| `runtime/tests/deploy_tests.py:665`, `:711` | `glob("*.riv")` on a folder | Same |

The player and `goldens` already open a `.twno` given by its path: the runtime reads
the signature (P1-1), not the extension.

## Internal: unchanged

- `runtime/dev/core_generator/lib/src/*.dart`: 6 comments.
- `runtime/premake5_v2.lua:52` (comment) and `:394`: description of the test option
  `--with_rive_test_signature`, visible in `premake5 --help`. It stays:
  it is a Rive build option that refers to files signed by Rive's sample key,
  not to what a Tweenora user reads.
- `runtime/tests/ios_tests/ios_tests.xcodeproj/project.pbxproj:300` and `:367`:
  text of the iOS network permission (`Exchange .rivs and .pngs with the python test
  harness`). Left as is: test Xcode project, not buildable here.
- `runtime/scripting/wamr_nx/tools/gen_prelinked_aot.py:157`: variable `args.riv`.
- `runtime/tests/web_scripting/`: `.riv` fixture names in `test.sh`,
  `run.mjs`, `browser_probe.mjs`, `fixture/bake.sh`.
- `runtime/tests/bench/`: `.riv` asset names in `artboard_frame_bench.cpp` and
  `draw_pls_path.cpp` (and `assets/paper.riv.hpp`).
- `runtime/tests/common/`, `tests/include/`, `tests/goldens/goldens.cpp:429,475`:
  comments.
- `runtime/tests/unit_tests/`: 1,160 lines in 159 files, almost all of them
  `.riv` asset names (the `.riv` files in `unit_tests/assets`, 380 at the root of the folder, stay `.riv`).

## Verification: the player opens a `.twno` and a `.riv`

Verified on 2026-10-15. Built from an ordinary PowerShell, with the Git
variables from `AGENTS.md`, `cd runtime\tests` then
`..\build\build_rive.ps1 --toolset=msc -- player` (0 errors, `out\debug\player.exe`).
`tools/twno_convert.py` produced `falling.twno` from
`runtime/tests/unit_tests/assets/parity/falling.riv` (bytes 0-3: `TWNR`).

```text
player.exe -b gl falling.riv  --dump falling.riv.raw  --dump-frame 3   -> dumped 1920x1080 frame
player.exe -b gl falling.twno --dump falling.twno.raw --dump-frame 3   -> dumped 1920x1080 frame
player.exe -b gl                                                       -> no .twno or .riv file specified
player.exe -b gl bad.twno (signature JUNK) --dump ...                  -> Bad header
```

- Both images have the same size and are not uniform (about 2,200 distinct
  pixels sampled in each).
- The images cannot be compared byte for byte: the animation advances with the
  clock, and two renders of the same `.riv` already differ by about 230,000 bytes.
  Exact render comparison belongs to P1-6 and phase 4.
- The default backend (`vk`) fails on this machine ("Failed to create testing
  window"), and `d3d` requires the Windows "Graphics Tools" component (see the
  P0-4 baseline): use `-b gl`.
