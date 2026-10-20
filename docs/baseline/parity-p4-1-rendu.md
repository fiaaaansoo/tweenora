# Render comparison on the 491 files (P4-1c)

> Note of 2026-10-20: the campaign described here was run on 491 files (5553 renders per runtime). 7 third-party files have since been removed from the repository and from the manifest (task `publication-8-retrait-runtime-parite`); their 225 renders were all identical. Recounted from the raw campaign records, without these files: 484 files, 5328 renders per runtime, 5307 identical, 15 non-deterministic, 6 `same_failure`, 0 differences. 4 other third-party files were removed afterwards (task `publication-16-retrait-fichiers-tiers-2`); their 21 renders were all identical. Recounted the same way: 480 files, 5307 renders per runtime, 5286 identical, 15 non-deterministic, 6 `same_failure`, 0 differences. 3 other files were removed (task `publication-18-retrait-fichiers-tiers-3`; their 36 renders were all identical) and 15 files had their embedded third-party images replaced by neutral images of the same dimensions; their 114 renders were replayed as `.riv` and as `.twno` (`render_compare.py --files`, 114 identical out of 114 for each format). Recounted the same way: 477 files, 5271 renders per runtime, 5250 identical, 15 non-deterministic, 6 `same_failure`, 0 differences. 2 other files were removed (task `publication-19-polices`; their 6 renders were all identical). Recounted the same way: 475 files, 5265 renders per runtime, 5244 identical, 15 non-deterministic, 6 `same_failure`, 0 differences. The text below keeps the figures of the original campaign.

Final P4-1c report: the fork (`runtime/`) and the official runtime (`vendor/rive-runtime`, `daf55385`)
render the 491 files of the manifest, at instants 0, 15 and 60 frames, default artboard then
each named artboard, and the images are compared pixel by pixel (alpha channel included). `gl` backend,
`msc` toolset, one GPU (NVIDIA GeForce RTX 3060). The bench and the harness are described in
`parity-p4-1-banc.md` and `parity-p4-1-harnais.md`.

## Result

For each of the two formats (`.riv` rendered by both runtimes; `.twno` rendered by the fork, original
`.riv` rendered by the official runtime), over 5553 renders per runtime:

| Status | Renders | Meaning |
|---|---|---|
| Pixel-identical | 5532 | fork image equal to the official one |
| Non-deterministic | 15 | the image varies from one render to the next of the same binary, on both sides (see below) |
| `same_failure` | 6 | both runtimes fail the same way, no image to compare (see below) |
| Unexplained difference | 0 | |
| One-sided error | 0 | |

The `.riv` and `.twno` results are identical status by status. **No rendering difference between the fork and
the official runtime was found**; no fix to `runtime/` was needed and no line is
added to the D15 register.

## Course of the work

1. Full batch in debug build (3 renders in parallel): about 85 minutes for the `.riv` files, about
   63 minutes for the `.twno` files (11106 `goldens` renders each, two runtimes). Command:
   `python -I tools/parity/render_compare.py --all --jobs 3 --checkpoint <file.jsonl>` then the same with
   `--format twno`. Result: 5208 identical, 12 non-deterministic, 333 `same_failure`.
2. The 333 renders in `same_failure` concern 31 files. Cause: debug build assertions
   present identically in the official runtime (`assert(!m_content)` in `file_asset_importer.cpp:24` for 29
   scripting and view model files, `assert(r.width() >= 0)` in `aabb.hpp:204` for `data_viz_demo.riv`)
   or rejection of the file. A debug build therefore makes it impossible to compare images for them.
3. Build of `goldens` in release in both trees, then render of the 31 files (381 renders per
   runtime, about 4 min 20 s for the `.riv` files; of which 48 already identical in debug, replayed):
   - 324 renders move from `same_failure` to identical;
   - 3 renders of `data_viz_demo.riv` are non-deterministic;
   - 6 remain in `same_failure`.

   Release builds (`tools\parity\build_goldens.ps1 -Config release -NoLto -Mp 4`, one tree at a time):
   fork 5 min 51 s, official 5 min 18 s.

Total per format: 5208 + 324 = 5532 identical; 12 + 3 = 15 non-deterministic; 6 `same_failure`;
5532 + 15 + 6 = 5553.

## Non-deterministic (15 renders, excluded from the criterion, listed separately)

| File | Renders | Cause |
|---|---|---|
| `formula_random.riv` | 12 (3 instants, 4 artboards) | random formula in the file; the difference reaches 68 levels on one channel |
| `data_viz_demo.riv` | 3 (`Main` at 0 and 60 frames, default artboard at 60 frames) | only two possible images, alternating from one render to the next |

Proof for `data_viz_demo.riv` (12 consecutive renders per binary in release, `Main` at 0 frames): the fork
gives three PNG fingerprints (`253f563868` ×9, `ab5b828e68` ×2, `e30cddfc64` ×1), the official runtime two
(`253f563868` ×10, `ab5b828e68` ×2). The dominant fingerprints are the same on both sides: the file
depends on a state not fixed by `goldens` (randomness or clock), not on a runtime difference. At 15 frames the
same artboard stayed identical over 12 renders of each binary; at 60 frames the default render shows
three fingerprints for the official runtime (`4d9922d09b` ×1) against two for the fork.

A difference is only classified as non-deterministic if at least one of the two binaries gives, over 6 repeated renders,
an image different from the first (`RETEST_REPEATS` in `render_compare.py`). The initial check
with two renders let intermittent files through (2 diverging renders out of 12 for `data_viz_demo.riv`,
so two consecutive renders usually agree): the regression case is
`test_an_intermittent_fork_is_noise_even_when_two_repeats_agree` (`fake_goldens.py`, `flaky` mode).

## Residual `same_failure` (6 renders per format)

| File | Renders | Cause |
|---|---|---|
| `solar-system.riv` | 3 (default artboard) | deliberately malformed file: the unit test `file with bad blend mode fails to load` (`file_test.cpp`) expects `ImportResult::malformed`. Both runtimes answer `Bad riv file`, which is the expected behavior |
| `rewards_demo.riv` | 3 (artboard `Screenshot 2025-04-14 at 3.19.51 PM`) | `Can't load artboard` on both sides. The name contains a narrow no-break space (U+202F); hypothesis not demonstrated: the `-t` argument of `goldens` goes through Windows' narrow `argv`, so the name does not find its artboard. The other artboards of the file, including the default one, are identical |

No image is compared for these 6 renders: the equality concerns the failure behavior, not pixels.
This is a known limit. It does not prove a defect in the fork, both runtimes behave the
same way.

## Limits

- A single backend (`gl`), a single toolset (`msc`), a single GPU and a single driver: no proof for `d3d`
  (Windows "Graphics Tools" feature absent) nor `vk` (fails on this machine).
- Two configurations: debug for 5208 renders, release without LTO for 324. The release link with LTO fails
  on the fork (`LNK1257`, warning `C4743` treated as an error by `/WX`): hence `-NoLto`, which has no effect on
  rendering but is worth knowing when comparing with a published build.
- No comparison with the Rive editor itself: the proof is "the fork renders like the official runtime built the
  same way", not "like the editor".
- The state of the state machines is not driven here (P4-2); the instants are fixed by advancing
  (`RIVE_GOLDENS_ADVANCE`), not by clock.
- The 12 + 3 non-deterministic renders are not demonstrated equal: only their origin common to both
  binaries is demonstrated.

## Reproduce

See `AGENTS.md` (parity command). Raw campaign reports, ignored by git:
`tools/parity/.work/p41c/{riv,twno}.{json,md,jsonl}` (debug) and `tools/parity/.work/p41c/rel/` (release).
