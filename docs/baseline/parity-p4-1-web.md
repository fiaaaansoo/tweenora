# Web runtime render parity against native (P4-1d, causes of the differences)

The `@tweenora/webgl2` web package (WASM, WebGL2) renders a sample of 34 files from the manifest at 0 and 60 frames (68
comparisons, 1600 x 1600); each render is compared pixel by pixel with that of the native fork (`goldens`, release
configuration without LTO).

**Result after the harness fix (2026-10-20)**: 47 of the 68 comparisons are **pixel-identical** to the
native reference of the same stack (ANGLE on Direct3D 11, MSAA 4x), 2 are in class `edge` (`click_event`: 1 pixel off
by 3 levels), **19 (10 files) remain structural differences**. These 19 have an established or localized cause (Luau scripts
absent from the native `goldens`, NaN formatting, text rasterization); none is a proven defect of the fork. Web
parity is therefore not closed, but the difference is bounded: the web render is the native one wherever the comparison is
valid.

| | Initial P4-1d | After fix |
|---|---|---|
| Native reference | `gl` (interlock), 76% of the image compared (383 transparent rows ignored) | `angle_d3d` (same stack as Chrome), whole image; counter-check `d3d` (default Windows path), whole image |
| Identical | 2 | 47 |
| Rounding | 27 | 0 against `angle_d3d` (25 against `d3d`) |
| Edge | 7 | 2 (22 against `d3d`) |
| Structural | 32 comparisons, 17 files | 19 comparisons, 10 files (19 against `d3d`, the same ones) |

## Environment

| Item | Value |
|---|---|
| Browser | Chrome 155 driven by the `playwright` MCP, a single browser |
| Browser GPU | `ANGLE (NVIDIA, NVIDIA GeForce RTX 3060, Direct3D11)`, WebGL2, canvas `antialias: true` (MSAA 4x); no interlock |
| Native, main reference | `goldens -b angle_d3d -d`: EGL on ANGLE Direct3D 11, same card; the renderer answers "no interlock mode supports this frame, drawing it in depthStencil with 4x MSAA", i.e. the web's mode |
| Native, counter-check | `goldens -b d3d -d`: native Direct3D 11, the fork's default path on Windows (raster order) |
| Web package | `tweenora-webgl2-0.1.0.tgz` from the batch D worktree (`13d6bbd25`), not rebuilt here |
| Size | 1600 x 1600, `cover` fit, center alignment, opaque white background |
| Instants | 0 and 60 frames at 60 fps, `advanceAndApply` (state machine) or `artboard.advance` (no state machine) |
| View model binding | blank instance `model.instance()`, like the native `goldens` (`createViewModelInstance(artboard)`) |

Limit: a single browser and a single GPU; no software rendering (the MCP does not allow choosing the launch
arguments).

## Established causes

The first series of measurements (P4-1d) mixed harness defects and real differences. Order of discovery:

### 1. Harness defects, fixed

| Cause | Evidence | Fix | Effect |
|---|---|---|---|
| **Non-equivalent view model.** The web bound `defaultInstance()` (values created in the editor); the native `goldens` binds `createViewModelInstance(artboard)`, a blank instance (`runtime/tests/goldens/goldens_shared.hpp`). | `bind: "blank"` against `"authored"` against `"none"` on the same goldens: `data_binding_artboards_test` 754,129 pixels (authored) against 1,787 (blank), `nested_events` 23,299 against 3,945, `data_binding_test` 112,062 against 88,755, `data_binding_lists` 1,290,910 against 1,066,920 (list with different content); without binding these files differ even more. | `web/parity/render.html` binds the blank instance by default (`window.parityOptions.bind`: `"blank"`, `"authored"`, `"none"`). | 4 files see their difference reduced (`data_binding_artboards_test` from 38.7% to 0.09% of compared pixels in the first report). |
| **Asynchronous image decoding.** The web package decodes images with `new Image()` and skips drawing an image that is "still decoding" (`wasm/js/webgl2_renderer.js`, `_drawImageMesh`); the page drew before it was finished. | `data_binding_images_test`: the web did not have the image (349,432 pixels, 17.9%), 2,095 pixels (max 4 levels) after waiting. | The page tracks the `Image` objects created and waits for them to finish before advancing and before drawing (`settleImages`). | 1 file. |
| **383 transparent rows in the native `goldens`.** `-b gl` opens a real window 1600 pixels high on a shorter screen: the rows off screen do not own the pixel. P4-1d calibrated and ignored them, which hid 24% of the image (including the text at the top of `new_text` and `layout_text_match`). | Window size: 383 rows with alpha 0 out of 68 renders; `-b angle_d3d` and `-b d3d` render offscreen: 1600 x 1600 fully opaque. The `-c 2 -r 1` grids do not work around the defect (the `gl` path loses the first cell, and the neighboring cell overflows onto the first as soon as the artboard is not square). | `tools/parity/web_goldens.py` renders with `angle_d3d` (and `d3d`) and rejects any golden containing a non-opaque pixel; no more calibration or ignored rows. | Whole image compared. |
| **Rendering path.** The web has no interlock: it draws in MSAA 4x. The native `gl` uses interlock (analytic anti-aliasing). The "rounding" differences (243 isolated pixels, background gradients at 1 level) and most of the edge differences came from this. | On the same file, native `gl` against `glmsaa` differ as much as the web against native (`data_binding_lists`: 1,061,361 pixels, `click_event`: 138,028); against `angle_d3d` (same algorithm and same stack), 47 comparisons out of 68 are identical and `rounding` disappears. | The main reference becomes `angle_d3d`; `d3d` remains as a counter-check. | The 27 roundings and most of the edges become identical. |
| **Compositing on white.** The web renders on a transparent background and then composites on white in a 2D canvas; the native clears to opaque white. Hypothesis tested: the 132,829 pixels at 1 level of `click_event` (7.1%) would come from it. | Against `angle_d3d` only one pixel remains: the difference came from the rendering path, compositing introduces no measurable difference. | None. | — |
| **Destruction order.** `renderer.delete()` before `file.delete()` threw `TypeError: ... reading 'deleteTexture'` on files with images as soon as the image existed (the previous defect masked it). | Error on `data_binding_images_test` at 0 and 60 frames; not reproduced outside the page with a file without a state machine. | The page destroys the file before the renderer. | — |

### 2. Remaining differences (19 comparisons, 10 files)

| Group | Files | Cause and evidence | Fork defect? |
|---|---|---|---|
| Luau scripts | `scripting_linear_animation` (60 frames) | The native `goldens` on this machine is built without scripting: on import, `Failed to import object of type 106`; the native render is identical at 1, 6, 30, 60 and 120 frames (112,649 pixels off the background each time); no `luaL_newstate` / `luau_load` symbol in `goldens.exe`. The web runs the script (two blocks, green and red, appear at 60 frames). | No: limit of the native bench. A `goldens` built with `--with-rive-scripting` is needed (runtime build, outside this task). |
| NaN formatting | `data_binding_test` (the majority of the 9,743 unexplained pixels against `d3d`) | A cell displays a NaN: native `-nan(ind)` (Windows C library), web `-nan` (musl, Emscripten). Side-by-side image: same cells, same fonts, shorter text on the web. | No: behavior of the C libraries, same source code. |
| Text | `data_bind_font_test`, `global_viewmodels_test`, `layout_text_match`, `layoutstest_8-planets-grid`, `new_text`, `runtime_nested_text_runs`, `data_binding_lists`, `text_fit_test` | Against `angle_d3d`, the native loses entire text runs (`new_text`: only "ok" is drawn, "text is", "now?" and "x" are missing; largest 16 x 16 block mean: 103 levels for `layout_text_match`). Against native `d3d`, the content is identical (side-by-side images for `new_text` and `data_binding_lists`; largest block mean of 2 to 6 levels for all) and only isolated glyph-edge pixels outside the rule remain: 6 to 148 pixels out of 2.56 million, except `data_binding_lists` 492, `layoutstest_8-planets-grid` 2,581 and `new_text` 1,234 and 3,035; up to about 70 levels on thin glyph edges. Probable cause: analytic anti-aliasing (interlock) against MSAA 4x on one-pixel strokes. | The native `goldens -b angle_d3d` loses text for an unestablished cause (same stack as the web, which draws it): to be studied with a second GPU; not entered in the D15 register for lack of proof that it is the runtime. |

Pass as identical (or within 1 pixel for `click_event`) against `angle_d3d`: `custom_property_enum`,
`data_binding_artboards_test`, `data_binding_images_test`, `data_binding_test_triggers`, `focusable_element`,
`grid_2x2`, `hosted_*`, `layout_aspect_ratio`, `layout_center`, `layout_scroll_vertical`, `list_items`,
`listener_input_values`, `looping_timeline_events`, `multiple_state_machines`, `nested_events`, `pointer_events`,
`script_inputs_test_1`, `sound`, `sound2`, `state_machine_triggers`, `two_artboards`, `click_event`.

## Equality rule adopted

Exact equality is the rule; it is met against the reference of the same stack. The classes are computed on all
pixels (`classify`, `explainDifferences`, `blockMeanDifference` in `web/parity/render-compare.mjs`):

| Class | Condition | Acceptable |
|---|---|---|
| `identical` | no differing pixel | yes |
| `rounding` | all differing pixels differ by at most 2 levels | yes |
| `edge` | every pixel differing by more than 2 levels is "explained": each channel of each image is within the range of that channel over the 3 x 3 neighboring pixels of the other image, to within 2 levels (coverage difference between two neighboring colors); and the signed mean difference over each 16 x 16 pixel block is at most 8 levels | yes |
| `structural` | one unexplained pixel, or a mean block shift of more than 8 levels | no |

Justification:

- **No threshold on the fraction of pixels or on the maximum level.** The provisional rule (16 edge levels, 1% of
  pixels) rejected white text on a dark background whose rendering is correct (one fewer MSAA sample changes an
  edge pixel by several tens of levels) and accepted wrong content covering 1% of the image. A rule based on
  explaining each pixel does the opposite: a pixel whose color is absent from its neighborhood in the other image is a
  defect, whether it is alone or there are 150,000.
- **2 levels**: difference observed on gradients between native Direct3D and ANGLE (floating-point precision of the gradient
  shader); against the reference of the same stack, the maximum is 0 levels over 47 comparisons.
- **Block mean <= 8**: anti-aliasing noise has a signed sum of zero, it is not a geometric shift; 8
  levels correspond to a half-pixel displacement of a maximum-contrast edge. Measured by shifting the web render
  by one pixel (with the native `glmsaa` path): 10 to 20 levels on text and shapes, against 0 to 6 for correct
  renders against `d3d`.
- **Blind spot**: a shift of less than half a pixel on an edge with contrast below 255, and a constant
  shift of one or two levels over a whole surface, pass. They are below the visible threshold and below the variance
  between two native rendering paths.
- **Two references.** The web cannot use interlock; `angle_d3d` is the stack that comes closest
  (same ANGLE, same MSAA, same card). `d3d` serves as a content counter-check: a render is accepted if it passes either
  of the two.
- `explainDifferences` is tested (`web/parity/render-compare.test.mjs`): a pixel whose color is absent from the neighborhood is
  unexplained, an edge moved beyond the window is unexplained, an intermediate edge pixel is explained.

## Result (68 comparisons)

| Reference | `identical` | `rounding` | `edge` | `structural` |
|---|---|---|---|---|
| `angle_d3d` (same stack) | 47 | 0 | 2 | 19 |
| `d3d` (default path) | 2 | 25 | 22 | 19 |
| Better of the two | 47 | 0 | 2 | 19 |

Two consecutive runs of the page give the same pixel counts for all 68 comparisons (about 17
seconds per run, two references).

Full table (differing pixels out of 2,560,000; "unexplained": pixels outside the edge explanation):

| Entry | Pixels (angle_d3d) | Max | Class | Unexplained | Pixels (d3d) | Max | Class | Unexplained |
|---|---|---|---|---|---|---|---|---|
| click_event-0 | 1 | 3 | edge | 0 | 431166 | 60 | edge | 0 |
| click_event-60 | 1 | 3 | edge | 0 | 431166 | 60 | edge | 0 |
| custom_property_enum-0 | 0 | 0 | identical | 0 | 276274 | 1 | rounding | 0 |
| custom_property_enum-60 | 0 | 0 | identical | 0 | 276274 | 1 | rounding | 0 |
| data_bind_font_test-0 | 3160 | 216 | structural | 3160 | 169880 | 97 | structural | 148 |
| data_bind_font_test-60 | 3160 | 216 | structural | 3160 | 169880 | 97 | structural | 148 |
| data_binding_artboards_test-0 | 0 | 0 | identical | 0 | 193169 | 34 | edge | 0 |
| data_binding_artboards_test-60 | 0 | 0 | identical | 0 | 193169 | 34 | edge | 0 |
| data_binding_images_test-0 | 0 | 0 | identical | 0 | 412440 | 4 | edge | 0 |
| data_binding_images_test-60 | 0 | 0 | identical | 0 | 412440 | 4 | edge | 0 |
| data_binding_test-0 | 154088 | 227 | structural | 153925 | 165279 | 227 | structural | 9743 |
| data_binding_test-60 | 154088 | 227 | structural | 153925 | 165279 | 227 | structural | 9743 |
| data_binding_test_triggers-0 | 0 | 0 | identical | 0 | 195835 | 22 | edge | 0 |
| data_binding_test_triggers-60 | 0 | 0 | identical | 0 | 195835 | 22 | edge | 0 |
| focusable_element-0 | 0 | 0 | identical | 0 | 164781 | 7 | edge | 0 |
| focusable_element-60 | 0 | 0 | identical | 0 | 164781 | 7 | edge | 0 |
| global_viewmodels_test-0 | 22111 | 231 | structural | 22111 | 165531 | 78 | structural | 7 |
| global_viewmodels_test-60 | 22111 | 231 | structural | 22111 | 165531 | 78 | structural | 7 |
| hosted_audio_file-0 | 0 | 0 | identical | 0 | 152120 | 1 | rounding | 0 |
| hosted_audio_file-60 | 0 | 0 | identical | 0 | 152120 | 1 | rounding | 0 |
| hosted_font_file-0 | 0 | 0 | identical | 0 | 278992 | 1 | rounding | 0 |
| hosted_font_file-60 | 0 | 0 | identical | 0 | 278992 | 1 | rounding | 0 |
| hosted_image_file-0 | 0 | 0 | identical | 0 | 278992 | 1 | rounding | 0 |
| hosted_image_file-60 | 0 | 0 | identical | 0 | 278992 | 1 | rounding | 0 |
| grid_2x2-0 | 0 | 0 | identical | 0 | 0 | 0 | identical | 0 |
| grid_2x2-60 | 0 | 0 | identical | 0 | 0 | 0 | identical | 0 |
| layout_aspect_ratio-0 | 0 | 0 | identical | 0 | 266072 | 67 | edge | 0 |
| layout_aspect_ratio-60 | 0 | 0 | identical | 0 | 246644 | 48 | edge | 0 |
| layout_center-0 | 0 | 0 | identical | 0 | 276594 | 1 | rounding | 0 |
| layout_center-60 | 0 | 0 | identical | 0 | 276594 | 1 | rounding | 0 |
| layout_scroll_vertical-0 | 0 | 0 | identical | 0 | 8603 | 2 | rounding | 0 |
| layout_scroll_vertical-60 | 0 | 0 | identical | 0 | 8603 | 2 | rounding | 0 |
| layout_text_match-0 | 152806 | 216 | structural | 152806 | 260930 | 78 | structural | 62 |
| layout_text_match-60 | 152806 | 216 | structural | 152806 | 260930 | 78 | structural | 62 |
| layoutstest_8-planets-grid-0 | 161895 | 236 | structural | 160193 | 340096 | 172 | structural | 2581 |
| layoutstest_8-planets-grid-60 | 155709 | 236 | structural | 153990 | 341723 | 172 | structural | 2284 |
| list_items-0 | 0 | 0 | identical | 0 | 161802 | 1 | rounding | 0 |
| list_items-60 | 0 | 0 | identical | 0 | 161802 | 1 | rounding | 0 |
| listener_input_values-0 | 0 | 0 | identical | 0 | 231056 | 1 | rounding | 0 |
| listener_input_values-60 | 0 | 0 | identical | 0 | 231056 | 1 | rounding | 0 |
| looping_timeline_events-0 | 0 | 0 | identical | 0 | 278992 | 1 | rounding | 0 |
| looping_timeline_events-60 | 0 | 0 | identical | 0 | 278992 | 1 | rounding | 0 |
| multiple_state_machines-0 | 0 | 0 | identical | 0 | 278992 | 1 | rounding | 0 |
| multiple_state_machines-60 | 0 | 0 | identical | 0 | 278992 | 1 | rounding | 0 |
| nested_events-0 | 0 | 0 | identical | 0 | 267896 | 41 | edge | 0 |
| nested_events-60 | 0 | 0 | identical | 0 | 267896 | 41 | edge | 0 |
| new_text-0 | 3915 | 255 | structural | 3915 | 282163 | 138 | structural | 1234 |
| new_text-60 | 9025 | 207 | structural | 9025 | 285257 | 104 | structural | 3035 |
| pointer_events-0 | 0 | 0 | identical | 0 | 257982 | 1 | rounding | 0 |
| pointer_events-60 | 0 | 0 | identical | 0 | 257982 | 1 | rounding | 0 |
| runtime_nested_text_runs-0 | 39576 | 255 | structural | 39576 | 281878 | 127 | structural | 6 |
| runtime_nested_text_runs-60 | 39576 | 255 | structural | 39576 | 281878 | 127 | structural | 6 |
| script_inputs_test_1-0 | 0 | 0 | identical | 0 | 278992 | 1 | rounding | 0 |
| script_inputs_test_1-60 | 0 | 0 | identical | 0 | 278992 | 1 | rounding | 0 |
| scripting_linear_animation-0 | 0 | 0 | identical | 0 | 278992 | 1 | rounding | 0 |
| scripting_linear_animation-60 | 221312 | 161 | structural | 221312 | 476209 | 161 | structural | 221312 |
| data_binding_lists-0 | 258021 | 253 | structural | 58023 | 1470861 | 83 | structural | 492 |
| data_binding_lists-60 | 258021 | 253 | structural | 58023 | 1470861 | 83 | structural | 492 |
| sound-0 | 0 | 0 | identical | 0 | 270516 | 17 | edge | 0 |
| sound-60 | 0 | 0 | identical | 0 | 278017 | 10 | edge | 0 |
| sound2-0 | 0 | 0 | identical | 0 | 277618 | 21 | edge | 0 |
| sound2-60 | 0 | 0 | identical | 0 | 277937 | 22 | edge | 0 |
| state_machine_triggers-0 | 0 | 0 | identical | 0 | 276278 | 17 | edge | 0 |
| state_machine_triggers-60 | 0 | 0 | identical | 0 | 276278 | 17 | edge | 0 |
| text_fit_test-0 | 128442 | 216 | structural | 128442 | 157955 | 98 | structural | 25 |
| text_fit_test-60 | 67124 | 216 | structural | 67124 | 141932 | 100 | structural | 22 |
| two_artboards-0 | 0 | 0 | identical | 0 | 272037 | 9 | edge | 0 |
| two_artboards-60 | 0 | 0 | identical | 0 | 272037 | 9 | edge | 0 |

## Known differences and limits

- One browser, one GPU, one driver; no software rendering.
- 34 files out of 491; two instants; default artboard only; state machine = the artboard's first, without
  inputs or pointer (P4-2).
- The view model binding is the blank instance, like the native `goldens`: the `defaultInstance()` path (editor
  values) has no native reference in this bench.
- The files with hosted resources (`hosted_*`) load from `public.uat.rive.app` on the web side without waiting for the
  download to finish: the render is taken without the resource, as natively. When the resource arrives after
  `file.delete()`, the package throws `RuntimeError: table index is out of bounds` (observed 4 times, outside rendering).
- The web logs `Could not find a View Model linked to Artboard ...` for files without a view model: the
  harness calls `defaultArtboardViewModel` without a prior check.
- Luau scripts: not comparable until the native `goldens` is built with scripting.
- The native `goldens -b angle_d3d` loses text (see above): cause not established.
- The web package tested comes from the batch D worktree, not from a rebuild.
- The native `goldens -b gl` on this machine (1600-pixel window) is no longer used by the web bench.

## Reproduce

```powershell
python -I web\parity\prepare_package.py --tgz <tweenora-webgl2-0.1.0.tgz>
python -I tools\parity\web_goldens.py
python -I tools\parity\web_goldens.py --backend d3d --out tools\parity\.work\web\golden-d3d
python -I web\parity\serve.py
node --test web\parity\render-compare.test.mjs
python -I -m unittest discover -s tools\parity\tests
```

Then, with the `playwright` MCP: open `http://127.0.0.1:8766/render.html` and evaluate
`const s = await (await fetch('/sample.json')).json(); await window.parity.run({entries: s.entries})` (the two
default references: `golden` and `golden-d3d`, a subdirectory of `tools/parity/.work/web/` each;
`window.parityOptions.bind`: `"blank"`, `"authored"` or `"none"`). `window.parity.view(entry)` shows web, native and
difference; `window.parity.crop(entry, [x0, y0, x1, y1], zoom)` enlarges an area; `window.parity.locate(entry, threshold)`
gives the box and the grid of the differences.
