import argparse
import sys
from pathlib import Path

RIV_SIGNATURE = b"RIVE"
TWNO_SIGNATURE = b"TWNR"
RIV_SUFFIX = ".riv"
TWNO_SUFFIX = ".twno"


class ConversionError(Exception):
    pass


def rewrite_signature(data, expected, replacement):
    if len(data) < len(expected):
        raise ConversionError("file shorter than a 4-byte signature")
    found = data[: len(expected)]
    if found != expected:
        raise ConversionError(
            f"expected signature {expected.decode()}, found {found!r}"
        )
    return replacement + data[len(expected) :]


def riv_to_twno(data):
    return rewrite_signature(data, RIV_SIGNATURE, TWNO_SIGNATURE)


def twno_to_riv(data):
    return rewrite_signature(data, TWNO_SIGNATURE, RIV_SIGNATURE)


CONVERSIONS = {
    RIV_SUFFIX: (TWNO_SUFFIX, riv_to_twno),
    TWNO_SUFFIX: (RIV_SUFFIX, twno_to_riv),
}


def conversion_for(source):
    try:
        return CONVERSIONS[source.suffix.lower()]
    except KeyError:
        raise ConversionError(f"{source}: extension must be .riv or .twno") from None


def convert_file(source, output, out_dir, force):
    target_suffix, convert = conversion_for(source)
    if output is not None:
        if output.suffix.lower() != target_suffix:
            raise ConversionError(f"{output}: extension must be {target_suffix}")
        destination = output
    else:
        name = source.with_suffix(target_suffix).name
        destination = (out_dir if out_dir is not None else source.parent) / name
    if not source.is_file():
        raise ConversionError(f"{source}: no such file")
    if destination.exists() and source.samefile(destination):
        raise ConversionError(f"{source}: source and destination are the same file")
    if destination.exists() and not force:
        raise ConversionError(f"{destination}: already exists (use --force)")
    converted = convert(source.read_bytes())
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(converted)


def build_parser():
    parser = argparse.ArgumentParser(
        prog="twno-convert",
        description="Convert .riv files to .twno and back by rewriting the 4-byte signature.",
    )
    parser.add_argument("inputs", nargs="+", type=Path, help=".riv or .twno files")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("-o", "--output", type=Path, help="destination file (one input only)")
    target.add_argument("--out-dir", type=Path, help="destination directory")
    parser.add_argument("--force", action="store_true", help="overwrite existing destinations")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.output is not None and len(args.inputs) != 1:
        parser.error("--output accepts a single input")
    failures = 0
    for source in args.inputs:
        try:
            convert_file(source, args.output, args.out_dir, args.force)
        except (ConversionError, OSError) as error:
            print(f"twno-convert: {error}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
