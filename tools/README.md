# tools/

Tools around the format: `twno-convert` (`.riv` ↔ `.twno` conversion, P1-5),
the schema extractor into `docs/schema/schema.json` (P2-1), `twnoinfo`
(file inspection, P2-3), the render comparison bench (phase 4), and `twno_gen` (`.twno` / `.riv` writer
for the demo examples, batch H: `tools/twno_gen/README.md`).

## twno-convert

Converts a `.riv` file to `.twno` and back by rewriting the first 4
bytes (`RIVE` ↔ `TWNR`). The rest of the file is copied as is
(`PLAN.md` § 3, "Format compatibility"). Python 3, standard library
only.

```text
python tools/twno_convert.py scene.riv                  # writes scene.twno next to it
python tools/twno_convert.py scene.twno                 # writes scene.riv next to it
python tools/twno_convert.py scene.riv -o out/final.twno
python tools/twno_convert.py a.riv b.riv --out-dir out/
python tools/twno_convert.py scene.riv --force          # overwrites the destination
```

- The direction is inferred from the extension of the input (`.riv` or `.twno`).
- A signature that does not match the requested direction (for example a `.riv`
  that starts with `TWNR`), a file shorter than 4 bytes or an unknown extension
  gives an error, exit code 1, and nothing is written.
- An existing destination is never overwritten without `--force`, and a file
  is never converted onto itself, even with `--force`.
- `-o` accepts a single input only and must carry the target extension (`.twno`
  for a `.riv`, `.riv` for a `.twno`); `-o` and `--out-dir` are mutually exclusive.
- The parent folders of the destination are created if missing.
- An error on one input (file system errors included) is reported on
  stderr and does not stop the other inputs; the exit code is then 1.

### Tests

```text
python -I -m unittest discover -s tools/tests
```

The round-trip test converts the 475 `.riv` files of `runtime/` to `.twno` and
back to `.riv`, and checks that the bytes are identical.

## schema_extract

Reads the generated headers of `runtime/include/rive/generated/` and writes
`docs/schema/schema.json` (P2-1). The file replaces Rive's `dev/defs`,
which are absent from the public repository, and is the basis of the editor. Python 3, standard library
only.

```text
python tools/schema_extract.py                 # regenerates docs/schema/schema.json
python tools/schema_extract.py -o out/schema.json
python tools/schema_extract.py --headers other/generated
python tools/schema_extract.py --check         # exit code 1 if the file is stale
```

Content of the JSON, sorted by key, with no machine-specific path:

- `types`: the 356 `typeKey` entries (name, key, `parent`, `mixins`, header, keys of the
  declared properties, `abstract`). `parent` is `null` for a root.
  `abstract` is true for the 62 types that `core_registry.hpp` cannot
  build (`makeCoreInstance`): a file may contain them, and the runtime
  treats them as an unknown object.
- `mixins`: the interfaces without a `typeKey` (`ColorChannels`).
- `properties`: the 664 `propertyKey` entries (key, name, owner type, `fieldType`,
  `serialized`, default value, `bitmask` or `bitField` for fields
  packed into another property).

`fieldType` is `bool`, `bytes`, `callback`, `color`, `double`, `id`, `int`,
`string` or `uint`. It comes from the deserialization `switch` of the header, then from
`core_registry.hpp`; a property that neither of them types makes the
extraction fail. `serialized` is true when the property has its own entry in
that `switch`, hence its own key in the binary stream. It is false for
flags (`bitmask`) and bit fields (`bitField`), whose value is
stored in another property (`storage`), and for values computed at
runtime and callbacks. `default` is the literal value when the header
gives one (`0.0f` gives `0.0`); `defaultExpr` keeps the original C++ expression
(`kEmptyId`, `Core::invalidPropertyKey`). A flag or a bit field has no
`default`: derive it from the `storage` property. With `--headers` outside the
repository, `header` is an absolute path.

A stale `schema.json` file makes the test fail: regenerate after any
upstream merge that touches `generated/`.

```text
python -I -m unittest discover -s tools/tests -p "test_schema_extract.py"
```

The test compares the JSON with the headers (type and property keys re-read
independently, owner, inheritance, presence in the `switch`), with the registry
and with the versioned file.

## twnoinfo

Prints the header, the property table and the object tree of a `.twno`
or `.riv` file (P2-3). A reader independent of the runtime: it applies
[`docs/FORMAT_TWNO.md`](../docs/FORMAT_TWNO.md) and reads names from
`docs/schema/schema.json`. Python 3, standard library only.
`runtime/rivinfo/` (the high-level C++ dumper) is not modified.

```text
python tools/twnoinfo.py scene.twno
python tools/twnoinfo.py -p scene.riv            # also lists the properties of each object
python tools/twnoinfo.py --json scene.twno       # same content as JSON
python tools/twnoinfo.py a.riv b.twno            # several files in a row
```

- The output gives the signature (`TWNR` or `RIVE`), the version, the file
  id, the property table (key and size class), the global
  objects (before the first `Artboard`), then for each artboard the tree of
  numbered objects (the number in square brackets) and, separately, the "other
  objects" that have no number (animations, state machine states, keyframes,
  data bindings...), flat, in file order.
- An object is attached to its `parentId`. With no `parentId`, or with a
  `parentId` that designates no object of the artboard (missing, itself, a loop,
  "no reference"), it is attached to the artboard and marked
  `(no parentId)` or `(invalid parentId)`. Several `parentId` entries on one
  object: the last one counts, as in the runtime.
- A type or a property absent from the schema is displayed as `unknown(<key>)`: an
  object of unknown type keeps its number (spec § 6.2), and an unknown property
  is skipped thanks to the table. A string that is not valid UTF-8 is
  read with a replacement character (the runtime does not check the
  encoding).
- Names and strings are displayed with control characters
  escaped (`\x0a`): a name cannot forge fake lines.
- With `--json`, the output is an object for one file and an array of objects
  for several. The tree is a flat list (`slot`, `parentSlot`, `depth`).
  Objects appear in `objects` and, as the case may be, in `globalObjects` or
  `others`. A non-finite `double` (NaN, infinity) becomes the string `"nan"` or
  `"inf"`. A byte array is summarized by its length.
- Numbering applies the spec rule without the cases where a runtime importer
  consumes an unknown object placed in an animation or a state
  machine (spec § 6.2): on such files, the displayed numbers may
  differ from those of the runtime after that object.
- A read error (signature, major version other than 7, truncated file,
  out-of-range varuint, property unknown to both the schema and the table)
  is written to stderr with the file and the byte offset; the exit
  code is 1. The other files on the command line are still
  read.
- The output is UTF-8 with `\n` line endings, whatever the system.
  A `.riv` and its `.twno` give the same report, except for the `File`
  and `Signature` lines.

```text
python -I -m unittest discover -s tools/tests -p "test_twnoinfo.py"
```

The tests read the 475 `.riv` files of `runtime/` and their `.twno` versions
(text report, `-p` and JSON identical except for the signature), check that each
`parentId` and each `interpolatorId` lands on an object of the artboard (and
for the latter on a `KeyFrameInterpolator`), cut a real file at every
byte, and cover the numbering rules, cycles, a 5,000-object
file, varuint limits and the command line.

## extension_fixture

Builds the P2-4 `.twno` files that use the key range reserved for
Tweenora (`50000`–`59999`, D8) and checks, with the C++ test
`runtime/tests/unit_tests/runtime/extension_keys_test.cpp`, that the runtime
ignores them. Python 3, standard library only. The extension keys are
checked against `docs/schema/schema.json`: the tool refuses to produce a
file if one of its extension keys is outside the range or taken by the
schema.

```text
python tools/extension_fixture.py declared -o out/declared.twno
python tools/extension_fixture.py --cpp              # C++ arrays of the three variants
python tools/extension_fixture.py --check            # exit code 1 if the C++ test does not embed the up-to-date bytes
```

Three variants, all with a `Backboard`, an `Artboard` "main" and three
`Node` objects `a`, `b`, `c` (`c` designates the object numbered 3 through `parentId`):

- `declared`: an extension property on `a`, and between `a` and `b` an object
  of type `50000` that carries a string, a double and a color. The four
  property keys are declared in the header table (one per size
  class).
- `bare-object`: the same extension object without a property, no extension
  property anywhere (so an empty table).
- `undeclared-property`: like `declared`, but the table is empty; property
  `50001` is not declared in it.

The bytes are embedded in the C++ test as arrays, with no asset file
(the P1-1 signature test reads an existing asset and
replaces its first 4 bytes): after a change to the tool, copy the
output of `--cpp` into the test. The Python test
`test_extension_fixture.py` fails until this is done.

```text
python -I -m unittest discover -s tools/tests -p "test_extension_fixture.py"
```
