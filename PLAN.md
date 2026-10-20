# Tweenora — Project plan

**Status:** v0.4, name and extension chosen (Tweenora, `.twno`) · **Date:** 2026-10-13
**Working folder name:** `openRive` · **Public name:** Tweenora
**Source:** public sources of the format in [`docs/ANALYSE.md`](docs/ANALYSE.md)

Markers used in this document:
- `[TO COMPLETE]`: missing information, to be provided.
- `[TO VALIDATE]`: proposal made, waiting for a yes/no.

Each `Px-y` task becomes a work task (see section 9).

---

## 1. Vision and scope

### Goal

**An open source runtime and editor for interactive vector animations, reading `.riv` files, with a paid cloud offering.**

- Goal: behavior that conforms to that of `rive-runtime` for files and runtimes, to be demonstrated in phase 4; for the editor, cover the same features, to be inventoried in P6-0.
- Same features in the editor (tools, panels, shortcuts, ways of working), with **our own look** (colors, icons, logo, texts).
- Own format: extension `.twno`, signature `TWNR`, same organization as `.riv` 7.x (only the first 4 bytes differ).
- Runtimes on all the platforms Rive covers.
- Cloud: self-hosted sync, real-time collaboration, sharing and community. This is the paid part.

### Model

Open source and free first (runtimes + editor). The paid cloud service will come in phase 7; domains, trademark and legal advice will be handled at that point.

### Out of scope

- Copying or decompiling the code of the Rive editor.
- Copying the look of Rive's interface pixel for pixel.
- Reusing a third party's content (docs, fonts, animations, images), its name or its logo.

### Overall success criteria

1. **Runtimes:** measured conformance, on each platform, of the Tweenora runtime's rendering and state machine states to those of the official runtime for `.riv` files of major version 7. The measurement and its limits are published (`docs/baseline/parity-p4-*`); no promise beyond the measurements.
2. **Self-hosted web:** a page served from our servers plays a `.twno` with no network call to rive.app or to a third-party CDN.
3. **Editor:** every feature listed in the inventory of the Rive editor (P6-0) exists in Tweenora and produces a file whose rendering and behavior are measured as conforming, as for the runtimes.
4. **Cloud:** sync, real-time collaboration, sharing and community. Details in the phase 7 plan.

---

## 2. Decisions

| ID | Subject | Choice | Status |
|---|---|---|---|
| D1 | Name, extension, signature | **Tweenora** · `.twno` · `TWNR`. "Motio" abandoned: trademark already filed for software in the EU and the USA (see [`docs/NOM.md`](docs/NOM.md)). `.twn` ruled out because it is already used by Twine | Chosen (2026-10-13) |
| D2 | First target | Web: self-hosted WASM runtime + demo | Chosen |
| D3 | Editor technology | **Flutter** + C++ core called natively (desktop) or in WASM (web), like Rive | Chosen |
| D4 | Ghidra + JDK 21 | No, the open source runtime is enough | Chosen |
| D5 | Reading `.riv` files | The runtime **and** the editor open `.riv` files; we always save as `.twno` | Chosen |
| D6 | Depth of the renaming | **Minimal**: signature, extension, packages, libraries, visible texts. C++ namespace `rive` kept (2,115 files) to merge Rive's updates easily | Chosen |
| D7 | Reference version | **Freeze, then follow.** Parity target: format 7.4, runtime at commit `daf55385` (editor version targeted by the public documentation: 1.8.5589). Once parity is reached, we follow each Rive version through an `upstream` remote | Chosen |
| D8 | Keys of Tweenora-specific objects | Range `50000–59999` for `typeKey` and `propertyKey` (Rive goes up to ~1,100; `propertyKey`s are read as `uint16`, max 65,535) | Chosen (technical choice, can be changed) |
| D9 | Format version | We follow Rive's major 7. A major 8 on Rive's side = migration project | Chosen (technical choice) |
| D10 | Code hosting | Repository `fiaaaansoo/tweenora` on GitHub, published once the name and the legal side are validated | Chosen |
| D11 | Web rendering | Rive's **WebGL2 GPU engine** (the only one that renders every effect, e.g. feathering) | Chosen |
| D12 | Platforms | **All of Rive's**, in this order: web → Flutter → C++ desktop, Unity, Unreal → React, React Native, iOS/macOS, Android, Rust | Chosen |
| D13a | License of the runtimes | `runtime/` and the future runtimes derived from rive-runtime stay **MIT**, Rive copyright kept and mentioned in a `NOTICE`. License received from upstream, cannot be modified | Chosen (`ceo` arbitration, 2026-10-16) |
| D13b | License of the editor and the server | Provisional target **AGPL-3.0** (a competitor that hosts a copy must publish its modifications, which protects the paid offering). The root `LICENSE` announces nothing as long as D13b is not closed. To be validated with a lawyer (scope of the AGPL for a SaaS, CLA, Rive's terms and trademark) before the first publication of the editor or server code; no consultation before phase 5 | `[TO VALIDATE]` Recommendation maintained on 2026-10-17: AGPL-3.0; a more flexible option: MPL-2.0 (obligation limited to modified files), to be compared with the lawyer |
| D13c | License of the code written by Tweenora (tools, scripts, examples, docs, demo page, fork modifications) | **MIT**, copyright fiaaaansoo, 2026; Rive's copyrights kept on the original code. Same family as the runtimes (D13a): simple, adoptable, no constraint for users. Text in the root `LICENSE` | Chosen (choice delegated by the founder, 2026-10-17) |
| D14 | Cloud host | To be chosen at the start of phase 7 | Deferred |
| D15 | Deviations from the `runtime/` subtree | Any change to `runtime/` that is not a rename (D6) must be minimal, isolated in its own commit, and listed in the deviation register of [`docs/UPSTREAM.md`](docs/UPSTREAM.md) with its reason and its removal condition. First deviation: `premake5.lua` of `unit_tests` made conditional on the `rive_native/` and `texture_compressor/` folders, absent from the public repository (P1-0) | Chosen (technical choice, `architect` recommendation) |

---

## 3. Target architecture

### Repository organization

```
(root)                   (repository fiaaaansoo/tweenora)
  runtime/     fork of rive-runtime, renamed (C++)
  web/         WASM runtime + npm package + demo page
  platforms/   Flutter, Unity, Unreal, React, RN, iOS, Android, Rust runtimes
  editor/      Flutter editor
  server/      cloud: accounts, sync, collaboration, sharing
  tools/       twno-convert, twnoinfo, schema extractor, comparison bench
  docs/        .twno format spec, JSON schema, examples, measurement reports, guides
  vendor/      reference checkouts, read-only
```

**Decided (P0-2, 2026-10-13): monorepo.** `runtime/` integrates rive-runtime through `git subtree` without `--squash` (complete history, base `daf55385`, remote `upstream`, merges through `git subtree merge --prefix=runtime`). Reasons: one commit and one PR per cross-cutting change, worktrees without the pitfalls of submodules, CI without a dedicated token, equivalent size (~127 MB). A separate runtime repository remains extractable through `git subtree split`. Procedure: [`docs/UPSTREAM.md`](docs/UPSTREAM.md).

### Pipeline

```
                ┌───────────── Tweenora editor (Flutter) ──────────────┐
                │  Flutter interface                                │
                │  C++ core (Tweenora runtime + editing logic)         │
                │    desktop : native call (dart:ffi)               │
                │    web     : WASM                                 │
                └──────┬───────────────────────────────┬────────────┘
                 saves .twno                       sync / collab
                       │                               │
                       ▼                               ▼
.riv file ──▶ read as is (D5)                   Tweenora cloud server
                       │
                       ▼
             Tweenora runtimes: web, Flutter, C++, Unity, Unreal,
                              React, RN, iOS/macOS, Android, Rust
```

### Format relationship with `.riv`

- Same structure as `.riv`: header, property table, `typeKey` + properties objects.
- Only difference at the start: the 4 signature bytes (`TWNR` instead of `RIVE`).
- Tweenora-specific objects: keys in the D8 range. The official runtime ignores them without crashing, provided they are declared in the property table (observed in `src/file.cpp`, `readRuntimeObject`). Confirmed by a test (P2-4): declared extension property and object ignored; undeclared property = malformed file.

---

## 4. Current state (verified on 2026-10-13)

### Reference runtime (`vendor/rive-runtime`)

| Item | Value |
|---|---|
| Commit | `daf55385` (2026-10-12) |
| Checkout | **shallow**, remote `origin` = `rive-app/rive-runtime` |
| Format version | 7.4 |
| Generated types / properties | 356 `typeKey` (max 1071) · 664 `propertyKey` (max 1099) |
| `.riv` test files | 475, of which 380 in `tests/unit_tests/assets` (491 and 391 before the removal of 16 third-party files at publication). These are our parity files (no personal files for now) |
| Tests | ~313 C++ unit test files + reference image tests (`tests/gm`, `tests/goldens`, `tests/imagediff`) |
| Build | premake5 via `build/build_rive.sh` / `build_rive.ps1` (premake installed automatically) |
| WASM build | `build_rive.sh ninja release wasm`, the script installs emsdk 4.0.23 itself |
| Writing | `BinaryWriter` exists (write primitives). A complete file serializer remains to be verified |
| Existing tool | `rivinfo/` (file inspection) |
| `.riv` mentions in the code | ~40 in `src`, `include`, `rivinfo`, `tests/player` |

### Reference environment tools

| Tool | State |
|---|---|
| git 2.53 + bash (Git for Windows) | OK |
| Python 3.14 | OK |
| Node 24 / npm 11 | OK |
| Visual Studio 2022 Community, MSVC 14.44 | OK |
| VS component "C++ Clang (clang-cl)" | **Absent** → install it, or build with `--toolset=msc` |
| Ninja | **Absent** (required for the WASM build) |
| Flutter / Dart | **Absent** (required for the phase 5 Flutter runtime and the editor) |
| CMake | Absent (not required a priori) |
| Emscripten, premake5 | Absent, installed by the build script |

---

## 5. Phases and tasks

Task format: **Goal** · **Done when** · **Depends on**.

### Phase 0 — Setup

#### P0-1 — Create the repository
- **Goal:** `git init`, folder tree from section 3, `README.md`, `.gitignore`, `fiaaaansoo/tweenora` repository on GitHub.
- **Done when:** first commit pushed to the repository.
- **Depends on:** D10.

#### P0-2 — Fork the runtime with history
- **Goal:** full (non-shallow) copy of `rive-runtime` in `runtime/`, remote `upstream`, branch `tweenora` (replaced by a base tag, see `docs/UPSTREAM.md`). Base at commit `daf55385` (D7).
- **Done when:** `git fetch upstream` works and the base is noted in `docs/UPSTREAM.md`.
- **Depends on:** P0-1.

#### P0-3 — Windows build chain
- **Goal:** install the clang-cl component (or validate `--toolset=msc`) and Ninja. Check `sh.exe` on the PATH.
- **Done when:** `build_rive.ps1` builds `tests/` in debug without errors.
- **Depends on:** P0-2.

#### P0-4 — Reference build and tests
- **Goal:** build the **unmodified** runtime, run the unit tests, archive the results.
- **Done when:** reference report in `docs/baseline/` (number of tests, failures already present).
- **Depends on:** P0-3.

#### P0-5 — Name check ✅ done on 2026-10-13
- **Goal:** check trademarks (INPI, EUIPO, USPTO), domains, npm, pub.dev, GitHub.
- **Result:** "Motio" abandoned, **Tweenora** chosen. Report: [`docs/NOM.md`](docs/NOM.md).
- **Done:** npm scope `@tweenora` reserved (npm organization, 2026-10-13).
- **Deferred to phase 7 (cloud):** reserve tweenora.com (+ .app, .dev), advice from an intellectual property counsel, trademark filing (classes 9 and 42). As long as the project stays open source and free, we accept the risk that someone takes the name before us.

### Phase 1 — Renaming

#### P1-0 — Unit tests buildable outside the monorepo
- **Goal:** make the 3 references to `rive_native/` and `texture_compressor/` conditional in `runtime/tests/unit_tests/premake5.lua` (and the `removefiles` list of the two test files concerned), in an isolated commit of `runtime/`. Paths computed relative to the script, not to the current folder. First entry of the deviation register of `docs/UPSTREAM.md` (D15).
- **Done when:** the subtree's `git diff` shows only this file; a clean build, with no local patch, again gives 2597 passed / 0 failures (3 D3D tests filtered as in the baseline); `docs/baseline/unit-tests-daf55385.md` is updated (no more local patch, 10 cases documented "excluded, embedder code absent"); `unit-tests-exclusions.patch` removed.
- **Depends on:** P0-4, D15.

#### P1-1 — `TWNR` signature
- **Goal:** modify `include/rive/runtime_header.hpp`: write `TWNR`, accept `TWNR` and `RIVE` when reading (D5).
- **Done when:** unit tests added and green for 3 cases: `TWNR` file read, `RIVE` file read, other signature rejected.
- **Depends on:** P0-4, P0-5, P1-0.

#### P1-2 — `.twno` extension
- **Goal:** inventory the ~40 `.riv` mentions, then switch to `.twno` those visible to the user (player, tools, messages), while keeping the opening of `.riv` files.
- **Done when:** the inventory is done and the player opens a `.twno` and a `.riv`.
- **Depends on:** P1-1.

#### P1-3 — Visible names
- **Goal:** rename produced libraries, packages, displayed texts, README (minimal renaming, D6).
- **Done when:** no "Rive" name visible to an end user in the produced binaries and packages, except legal notices.
- **Depends on:** P1-1.

#### P1-4 — Legal notices
- **Goal:** keep the MIT `LICENSE` and Rive's copyright; add a `NOTICE` ("based on rive-runtime, © Rive, MIT"); no logo or trademark name displayed prominently.
- **Done when:** `LICENSE` + `NOTICE` in place and proofread.
- **Depends on:** P1-3, D13a.

#### P1-5 — `twno-convert` tool
- **Goal:** conversion `.riv` → `.twno` and `.twno` → `.riv` (signature rewrite).
- **Done when:** the round trip gives identical bytes on the 475 test files.
- **Depends on:** P1-1.

#### P1-6 — Non-regression
- **Goal:** rerun the reference tests on the original `.riv` files and on their `.twno` versions.
- **Done when:** 2597 passed plus the new P1-1 tests, 0 failures, with the 3 D3D crashes as long as "Graphics Tools" is not installed (P0-4 baseline).
- **Depends on:** P1-2, P1-5.

### Phase 2 — Specification and schema

#### P2-1 — Schema extractor
- **Goal:** script in `tools/` that reads `include/rive/generated/` and produces `docs/schema/schema.json`: types, keys, field types, default values, inheritance. It stands in for the `dev/defs` absent from the public repository and serves as the basis for the editor.
- **Done when:** the JSON covers the 356 types and 664 properties; a test compares its content to the generated headers.
- **Depends on:** P0-2.

#### P2-2 — `FORMAT_TWNO.md` spec
- **Goal:** format spec: structure, `TWNR` signature, relationship with `.riv`, reserved key range (D8), version rules (D9).
- **Done when:** someone can write a minimal reader from the spec alone.
- **Depends on:** P2-1.

#### P2-3 — `twnoinfo` tool
- **Goal:** Python tool `tools/twnoinfo.py`, a reader independent of the runtime based on `docs/FORMAT_TWNO.md` and `docs/schema/schema.json`: displays the header, the property table and the object tree of a `.twno` or a `.riv`. `runtime/rivinfo/` is left as is (no D15 deviation); adapting it would have required modifying the core (private property table) and rerunning a heavy C++ build.
- **Done when:** it works on the 475 `.riv` files and their `.twno` without errors, gives the same output for a `.riv` and its `.twno` apart from the signature, and reports a truncated file with a clear error (non-zero exit code).
- **Depends on:** P1-1, P2-1, P2-2.

#### P2-4 — Extension tolerance test
- **Goal:** build a file containing an object and a property in the D8 range; verify that the official runtime ignores it without crashing.
- **Done when:** automated test green.
- **Depends on:** P1-5.

### Phase 3 — Web runtime (first target)

#### P3-1 — WASM build with GPU engine
- **Goal:** `build_rive.sh ninja release wasm` on the fork, with the WebGL2 GPU rendering engine (D11).
- **Done when:** a `.wasm` is produced and it draws a file in a browser.
- **Depends on:** P1-6.

#### P3-2 — JavaScript layer
- **Goal:** bring in `rive-wasm` (MIT license to be checked), plug it into the fork, rename the npm package (`@tweenora/webgl2`).
- **Done when:** `npm pack` produces an installable package.
- **Depends on:** P3-1.

#### P3-3 — JS API parity
- **Goal:** the whole public API of Rive's web runtime: loading, animations, state machines (inputs, events), data binding / view models, text, layout, audio, scripting.
- **Done when:** every function of Rive's API has its Tweenora equivalent, with a working example.
- **Depends on:** P3-2.

#### P3-4 — Self-hosting
- **Goal:** serve `.wasm`, `.js` and `.twno` from our server; remove any default loading from a CDN; MIME types (`application/wasm`), CORS, cache.
- **Done when:** the network tab shows no request outside our domain.
- **Depends on:** P3-2. `[TO COMPLETE]` demo host (may follow D14).

#### P3-5 — Demo page
- **Goal:** page that loads a `.twno` or a `.riv` (drag and drop or list), picks an animation and a state machine, exposes the inputs.
- **Done when:** demo online.
- **Depends on:** P3-3, P3-4.

### Phase 4 — Proof of behavior parity

#### P4-1 — Render comparison
- **Goal:** render each file with the official runtime (same commit) and with the fork, at fixed instants; compare the images (build on `tests/imagediff`).
- **Done when:** zero pixel difference on the 475 files, or each difference explained.
- **Depends on:** P1-6.

#### P4-2 — State machine comparison
- **Goal:** same input sequence → same states, same events, at the same instants, in both runtimes.
- **Done when:** automated test green on all files that have a state machine.
- **Depends on:** P4-1.

#### P4-3 — Continuous integration
- **Goal:** run unit tests and comparisons on every push (GitHub Actions).
- **Done when:** pipeline green.
- **Depends on:** P4-2.

### Phase 5 — Runtimes for the other platforms

Order (D12): Flutter → C++ desktop → Unity → Unreal → React → React Native → iOS/macOS → Android → Rust.

Each platform follows the same template task:

#### P5-x — `<platform>` runtime
- **Goal:** bring in the platform's official runtime (license to be checked for each), plug it into the fork, rename the package, provide a sample app.
- **Done when:** the sample app plays a `.twno` and a `.riv`, and passes the phase 4 comparisons.
- **Depends on:** P4-2.

| ID | Platform | Point of attention |
|---|---|---|
| P5-1 | Flutter | Install Flutter. Check the license and availability of the native library used by Rive's Flutter package. This runtime will be reused by the editor |
| P5-2 | C++ desktop | Windows, macOS, Linux. The fork itself, packaged |
| P5-3 | Unity | |
| P5-4 | Unreal | |
| P5-5 | React | On top of the web runtime (phase 3) |
| P5-6 | React Native | |
| P5-7 | iOS / macOS | |
| P5-8 | Android | |
| P5-9 | Rust | |

### Phase 6 — Editor (Flutter)

A detailed editor plan will be written after P6-0 and P6-1.

#### P6-0 — Functional inventory of the Rive editor
- **Goal:** list the features of a stateful vector animation editor (tools, panels, menus, shortcuts, inspector fields, export options, preferences) as Rive's public documentation and the `schema.json` schema describe them (each property of the format corresponds to a setting). Each feature receives an identifier and a parity status.
- **Done when:** the inventory covers all panels, and every property of `schema.json` is linked to at least one feature. Rive screenshots stay out of the repository.
- **Depends on:** P2-1.

#### P6-1 — Editor architecture
- **Goal:** design the Flutter editor: C++ core (Tweenora runtime + editing logic) called through `dart:ffi` on desktop and in WASM on the web; document model; undo/redo; file management.
- **Done when:** the editor architecture document is validated.
- **Depends on:** P5-1, P6-0.

#### P6-2 — Visual identity
- **Goal:** our design system: colors, typography, icons, logo. Same features and same layout as Rive, our own look.
- **Done when:** Flutter theme and icon set delivered.
- **Depends on:** P0-5.

#### Functional batches (in order)

| ID | Batch | Content |
|---|---|---|
| P6-3 | Document and files | Model built on `schema.json`, undo/redo, `.twno` saving, `.riv` import (D5) |
| P6-4 | Preview | The Tweenora runtime serves as the rendering engine in the editor |
| P6-5 | Vector canvas | Shapes, pen, selection, transforms, fills, strokes, gradients, feathering |
| P6-6 | Structure | Artboards, hierarchy, groups, components (nested artboards), assets (images, fonts, audio) |
| P6-7 | Animation | Timeline, keyframes, interpolations, curves |
| P6-8 | State machines | Graph, layers, inputs, transitions, conditions, events, listeners |
| P6-9 | Rigging | Bones, skinning, meshes, constraints |
| P6-10 | Text and layout | Text, fonts, flexbox layout |
| P6-11 | Data | Data binding, view models |
| P6-12 | Scripting and audio | Luau scripting (code editor, analysis), audio |
| P6-13 | Export | Runtime export, options, verification by the Tweenora runtimes |

**Editor MVP:** P6-3 to P6-7 (shapes + structure + timeline + export) with a file read identically by the web runtime.

### Phase 7 — Cloud (paid offering)

Detailed plan to be written at the start of the phase, with the choice of host (D14).

| ID | Batch | Content |
|---|---|---|
| P7-0 | Scoping | Host, server architecture, costs, pricing. Reserve the tweenora.com domains, advice from an intellectual property counsel, filing of the Tweenora trademark |
| P7-1 | Accounts | Sign-up, login, teams |
| P7-2 | Sync | Storage of files and assets, version history |
| P7-3 | Real-time collaboration | Several people on the same file, cursors, conflicts |
| P7-4 | Sharing | Share links, permissions, embedding |
| P7-5 | Community | Public gallery, remix |
| P7-6 | Billing | Subscriptions, quotas |

---

## 6. Milestones

| Milestone | Content | Tasks |
|---|---|---|
| M0 | Name validated, reference build OK | P0-1 → P0-5 |
| M1 | Renamed runtime, tests green, converter | P1-0 → P1-6 |
| M2 | Spec and tools | P2-1 → P2-4 |
| M3 | Self-hosted web demo | P3-1 → P3-5 |
| M4 | Parity proven and automated | P4-1 → P4-3 |
| M5 | Flutter runtime | P5-1 |
| M6 | Editor MVP | P6-0 → P6-7, P6-13 |
| M7 | Editor at full parity | P6-8 → P6-12 |
| M8 | Cloud | Phase 7 |
| M9 | All runtimes | P5-2 → P5-9 |

M8 and M9 can progress in parallel with M7.

---

## 7. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| Size of the project: Rive is the multi-year work of an entire team | Very long timelines | Milestones delivered one by one; web runtime and editor MVP first |
| Someone files "Tweenora" or reserves the domain before us | Renaming | Risk accepted as long as the project stays open source and free; domains and trademark handled at the cloud launch (P7-0) |
| Rive ships a major 8 of the format | Recent files unreadable | `upstream` tracking (D7), parity tests in CI |
| Conflicting upstream merges | Delay, divergence | Minimal renaming (D6), frequent merges after parity |
| Key collision with a future Rive version | Files misread | High reserved range (D8) |
| Undocumented features of the Rive editor | Incomplete editor | Systematic inventory (P6-0) linked to the format schema |
| Rive's trademark and look | Dispute | Our own look (P6-2), no Rive name or logo, clear `NOTICE` |
| License poorly chosen for the paid offering | A competitor resells our cloud | D13b to be validated with a lawyer before the first publication of the editor or server code |
| Overall legal status | Distribution blocked | Lawyer's advice before any commercial distribution |
| Heavy GPU build (D3D, Metal, Vulkan, WebGL) | Ramp-up time | Start with WebGL2 on the web, then one platform at a time |
| Real-time collaboration | Large technical undertaking | Dedicated plan in phase 7 |
| Current shallow checkout | No history to merge | Full copy in P0-2 |

---

## 8. Open questions

1. **D13b — License of the editor and the server**: AGPL-3.0? To be validated with a lawyer before their first publication (D13a, runtimes in MIT, is settled).
2. ~~Monorepo or one repository per component (section 3).~~ Settled in P0-2: monorepo, runtime as a `git subtree` (section 3).
3. Host for the web demo (P3-4) and the cloud (D14, deferred).
4. Price and content of the paid offering (P7-0).

---

## 9. Turning into tasks

- One work task per `Px-y` entry, grouped into batches.
- One batch per phase. Phases 0 and 1 follow each other strictly. Phases 2 and 3 can progress in parallel once M1 is reached. P6-0 (inventory) can start as soon as P2-1.
- `[TO VALIDATE]` decisions that block a task are listed in its "Depends on" field.
