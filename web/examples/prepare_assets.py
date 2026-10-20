import argparse
import sys
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXAMPLES_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import twno_convert

UPSTREAM_ASSETS = REPO_ROOT / "runtime" / "tests" / "unit_tests" / "assets"
ORIGINAL_EXAMPLES = REPO_ROOT / "docs" / "examples"
DEFAULT_OUT_DIR = EXAMPLES_DIR / "assets"
ALLOWED_SUFFIXES = (twno_convert.RIV_SUFFIX, ".ttf", ".wav", ".mp3")

ASSET_SOURCES = [
    (
        ORIGINAL_EXAMPLES,
        ("bouncing-ball.riv", "spinning-square.riv", "button.riv", "tinted-shape.riv"),
    ),
    (
        UPSTREAM_ASSETS,
        (
            "two_artboards.riv",
            "multiple_state_machines.riv",
            "hosted_image_file.riv",
            "focusable_element.riv",
            "state_machine_triggers.riv",
            "sound.riv",
            "click_event.riv",
            "looping_timeline_events.riv",
            "nested_events.riv",
            "listener_input_values.riv",
            "pointer_events.riv",
            "data_binding_test.riv",
            "custom_property_enum.riv",
            "list_items.riv",
            "data_binding_images_test.riv",
            "data_bind_font_test.riv",
            "data_binding_artboards_test.riv",
            "global_viewmodels_test.riv",
            "data_binding_test_triggers.riv",
            "kablammo.ttf",
        ),
    ),
    (UPSTREAM_ASSETS / "semantic", ("data_binding_lists.riv",)),
    (
        UPSTREAM_ASSETS,
        (
            "new_text.riv",
            "runtime_nested_text_runs.riv",
            "hosted_font_file.riv",
            "text_fit_test.riv",
            "layout_text_match.riv",
            "layoutstest_8-planets-grid.riv",
            "sound2.riv",
            "script_inputs_test_1.riv",
            "viewmodel_access.riv",
            "scripting_linear_animation.riv",
            "audio_script.riv",
            "hosted_audio_file.riv",
            "NotoSansArabic-VariableFont_wdth,wght.ttf",
        ),
    ),
    (
        UPSTREAM_ASSETS / "layout",
        (
            "layout_aspect_ratio.riv",
            "layout_center.riv",
            "grid_2x2.riv",
            "layout_scroll_vertical.riv",
        ),
    ),
    (
        UPSTREAM_ASSETS / "fonts",
        (
            "IBMPlexSansArabic-Regular.ttf",
            "Inter_18pt-Regular.ttf",
            "OpenSans-Italic.ttf",
        ),
    ),
    (
        REPO_ROOT / "web" / "rive-wasm" / "js" / "test" / "assets",
        ("fallback_fonts_test.riv", "audio_test.riv"),
    ),
    (UPSTREAM_ASSETS / "audio", ("what.wav",)),
]


class PrepareError(Exception):
    pass


def check_name(name):
    if Path(name).name != name or Path(name).suffix not in ALLOWED_SUFFIXES:
        raise PrepareError(
            f"{name}: expected a bare file name ending in {', '.join(ALLOWED_SUFFIXES)}"
        )


def read_asset(name, source):
    data = source.read_bytes()
    if Path(name).suffix != twno_convert.RIV_SUFFIX:
        return data, None
    try:
        return data, twno_convert.riv_to_twno(data)
    except twno_convert.ConversionError as error:
        raise PrepareError(f"{name}: {error}") from error


def prepare(sources, out_dir):
    out_dir = Path(out_dir)
    seen = set()
    plan = []
    for directory, names in sources:
        for name in names:
            check_name(name)
            if name in seen:
                raise PrepareError(f"{name}: declared by two sources")
            seen.add(name)
            source = Path(directory) / name
            if not source.is_file():
                raise PrepareError(f"{name}: not found in {directory}")
            data, twno = read_asset(name, source)
            plan.append((name, data, twno))
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, data, twno in plan:
        path = out_dir / name
        path.write_bytes(data)
        written.append(path)
        if twno is not None:
            twno_path = path.with_suffix(twno_convert.TWNO_SUFFIX)
            twno_path.write_bytes(twno)
            written.append(twno_path)
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Copy the .riv files used by the examples (Tweenora examples and "
        "upstream test files) and convert them to .twno. The output is not versioned."
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)
    try:
        written = prepare(ASSET_SOURCES, args.out_dir)
    except PrepareError as error:
        print(f"prepare_assets: {error}", file=sys.stderr)
        return 1
    print(f"{len(written)} files in {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
