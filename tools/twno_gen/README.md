# tools/twno_gen/

Python writer for `.twno` / `.riv` files (batch H, public demo). It produces valid files from
the specification alone ([`docs/FORMAT_TWNO.md`](../../docs/FORMAT_TWNO.md)) and the schema
([`docs/schema/schema.json`](../../docs/schema/schema.json)), without an editor. Python 3.9 or later, standard
library only (Pillow and NumPy are only used for render checks).

## Hygiene

The writer derives only from the schema and the specification. No byte, file or structure is copied from an upstream
or Rive `.riv`. The generated files are Tweenora works (license: see `docs/examples/`).

## Usage

```python
from twno_writer import Document, Obj, rgb

doc = Document()
doc.add(Obj("Backboard"))
artboard = doc.add(Obj("Artboard", name="A", width=100.0, height=100.0))
shape = doc.add(Obj("Shape", parent=artboard, x=50.0, y=50.0))
doc.add(Obj("Rectangle", parent=shape, width=40.0, height=40.0))
fill = doc.add(Obj("Fill", parent=shape))
doc.add(Obj("SolidColor", parent=fill, colorValue=rgb("#ff8000")))
doc.write("a.twno")
doc.write("a.riv")
```

- `Obj("Type", property=value, ...)`: the type and the properties are resolved by name in the schema (inheritance and
  mixins included). An unknown or abstract type, a property that does not belong to the type, a value of another
  `fieldType`, or a non-serialized property (computed at runtime, callback) are rejected with a `WriteError`.
- `Document.add` validates the properties; `to_bytes()` and `write()` validate the references.
- Flags (`bitmask`) and bit fields (`bitField`) are written into their `storage` property (for example
  `colorRed` into `colorValue`, `isVisible` of a `LayerMask` into `maskFlags`), from the given value or, failing
  that, from the schema default.
- References (`fieldType` `id`): never an integer. Give the object (`parent=shape`), its name (`animation="slide"`),
  `NONE` (`kEmptyId`) or, as a last resort, `RawId(n)`. The `Id` suffix is optional (`parent`, `stateTo`,
  `object`, `input`, `interpolator`). The known properties and the list they point into (objects of the artboard, animations,
  states of a layer, inputs of a state machine, artboards of the file) are in `ID_RULES` of `twno_writer.py`;
  an `id` property missing from this table accepts only `NONE` and `RawId`. Each entry carries the type of the target
  (for example a `KeyFrameInterpolator` for `interpolatorId`) and, when the runtime reads the list at import, the requirement
  that the target be written before the source; the input type of a condition or of a `Listener*Change` is that of
  the condition (boolean, number, trigger).
- Numbering (spec § 6.2): computed by `Document`; `obj.slot` (number in the artboard, `None` if it takes
  none), `obj.index` (rank in its list: animation, state, input, state machine, artboard) and `obj.artboard` are
  filled in after `to_bytes()`. Animation and state machine objects are written in the order they were added, which
  is the stream order (a `KeyedObject` belongs to the last `LinearAnimation`, etc.).
- Tweenora extensions: `doc.declare_property(50001, "uint", name="...")` (keys 50000 to 59999; classes `uint`,
  `string`, `double`, `color`); the key is then recorded in the header table (spec § 9). Extension objects
  are not covered.

## Scenes and examples

- `scene_kit.py`: scene tools (solid shapes, cubic interpolators, animation tracks by property name,
  looping playback state machine).
- `scenes/`: one scene per example (`build()` returns a `Document`); `build_examples.py` writes
  `docs/examples/*.riv` (`--check`: exit code 1 if a versioned file differs from the regenerated one). Description of the
  examples: `docs/examples/README.md`.
- `NOTES_DATA_BINDING.md`: objects, order and references of a color data binding (`tinted_shape` scene).
- `render_check.py`: rendering through `goldens` (`render`, `find_goldens`, `hidden_rows`) for the tests. `goldens` plays only one
  state machine, and after N advances of 1/60 s the animation is at frame (N - 1).

## Writing choices

- Version 7.4, file id 0 (`Document(minor=..., file_id=...)`).
- Property table: `table="used"` (default) lists all the keys actually written, with their size
  class; `table="minimal"` lists only the declared extension keys. Both forms load in the native
  runtime and give the same image (`tests/test_native_render.py`). The full form is the default: it
  reproduces the 20-byte example of spec § 10 and remains readable by an older runtime that would not know
  a key.
- Properties of an object are written by ascending key: the output does not depend on the order of the arguments.
- `.twno` and `.riv` differ only by the first 4 bytes.

## Tests

```text
python -I -m unittest discover -s tools/twno_gen/tests
TWNO_GOLDENS=<path to goldens.exe> python -I -m unittest discover -s tools/twno_gen/tests
```

- `test_primitives.py`: varuint, zigzag, float32, color, strings, bytes, booleans.
- `test_writer.py`: the two byte examples of spec § 10, rejections, bits, numbering, references, header,
  determinism.
- `test_references.py`: hand-computed numbering (`ScriptInput*`, scroll physics, user inputs),
  indices of animations, states and inputs, expected target types, write order required by the runtime, `NONE`
  and `RawId`, the `ID_RULES` table.
- `test_scenes.py`: identical regeneration, scene structure re-read by `twnoinfo`, loop without a jump, native renders
  measured against hand-computed values.
- `test_roundtrip.py`: `tools/twnoinfo.py --json` (a separately written reader) re-reads types, properties, numbers and
  `parentId`; round trip through `tools/twno_convert.py`.
- `test_native_render.py`: render through the fork's `goldens` (`-b gl`, advance 0), skipped if `goldens` is not built
  (`TWNO_GOLDENS` or `runtime/tests/out/debug/goldens`) or if Pillow/NumPy are missing. `goldens` fills the image with
  white (`clearColor`): the background of an example is therefore white in these renders, and the first 383 lines of the image
  stay transparent (behavior also observed on an upstream file, unrelated to the generated file).
