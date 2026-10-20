# `.twno` format

Specification of the Tweenora file format (P2-2). A `.twno` is a Rive `.riv`
file whose signature is `TWNR` instead of `RIVE` (`PLAN.md` § 3, D5). Everything
below therefore applies to both formats, unless stated otherwise.

The list of object types and properties is not copied here: it is in
[`docs/schema/schema.json`](schema/schema.json), produced by
`tools/schema_extract.py` from the runtime's generated headers (P2-1). This
document describes the bytes; the schema describes what they stand for.

The words MUST and MUST NOT have their usual specification meaning.

## 1. Conventions

- All fixed-size integers are **little-endian** (least significant byte
  first).
- **varuint**: unsigned integer in LEB128. Each byte carries 7 bits of value,
  least significant first; bit 7 is 1 if another byte follows. Values up to 64
  bits. A varuint that runs past the end of the file, that is longer than 10
  bytes, or whose value exceeds 64 bits makes the file invalid. Type keys,
  versions and table keys are read as 31 bits, known `uint` and `id` values as
  32 bits; a larger value makes the file invalid. Only an unknown `uint`
  (§ 5.3) is read as 64 bits.
- **uint32**: 4 bytes, little-endian.
- **float32**: 4 bytes, IEEE 754 single precision, little-endian.
- **String**: a varuint `n`, then `n` UTF-8 bytes. `n` must not exceed the
  remaining bytes. The runtime does not check the encoding: a tolerant reader
  replaces invalid bytes instead of rejecting the file.
- **Bytes**: same shape as a string, with no encoding constraint.

## 2. File structure

```text
file      = header object*
header    = signature major-version minor-version file-id
            property-table
object    = type-key ( property-key value )* 0
```

The file ends with the last object. There is no footer, no checksum, and no
announced object count: objects are read until the bytes run out.

## 3. Header

| Field | Encoding | Note |
|---|---|---|
| Signature | 4 ASCII bytes | `TWNR` when writing. A reader MUST accept `TWNR` and `RIVE`. Any other value makes the file invalid. |
| Major version | varuint | 7 (D9). |
| Minor version | varuint | 4 for the reference format; the test files range from 0 to 4 (298 of 475 are 0). A reader rejects none of them, but the runtime adapts some behaviors to the minor version (7.2 to 7.4, see `runtime/include/rive/file.hpp`). |
| File id | 64-bit varuint | May be 0. No effect on reading. |
| Property table | see § 3.1 | |

### 3.1 Property table

1. A sequence of non-zero varuints, each a **property key**, terminated by a
   varuint `0`. Let `n` be the number of keys.
2. Then `ceil(n / 4)` uint32 words. The property at index `i` (0 for the first
   key in the list) is described by bits `2·(i mod 4)` and `2·(i mod 4) + 1` of
   the word at index `floor(i / 4)`. The 24 high-order bits of each word are
   unused; a reader ignores them.

The two-bit code gives the **size class** of the value:

| Code | Class | Value in the stream |
|---|---|---|
| 0 | uint | a varuint (a boolean, written as one byte equal to 0 or 1, is also read as a varuint) |
| 1 | string | a string or bytes (§ 1) |
| 2 | double | a float32 |
| 3 | color | a uint32 |

The table is used to **skip** a property the reader does not know (§ 5.3). It
does not replace the schema for known properties. A property absent from both
the table and the schema cannot be skipped: the file is invalid.

The table is not exhaustive. In the test files, no key below 160 appears in it
(key 13, the `x` of a `Node`, appears in none of the 475 files), and a few
files also omit a higher key that the schema knows. A reader MUST NOT require
that a key known to the schema appear in it. A writer is bound to it only for
keys the schema does not define (§ 9).

If `n` is 0, no word follows. A key repeated in the list is allowed; the
runtime keeps the last one.

## 4. Object stream

Each object is:

1. a **type key**, a varuint (for example 23 for a `Backboard`);
2. zero or more properties, each a **property key** (non-zero varuint, 65,535
   at most) followed by its value;
3. a varuint `0`, which ends the object.

A property key identifies a property across the whole format: it is unique from
one type to another (key 13 is always the `x` of a `Node`). An inherited
property keeps the key of its original type. The order of an object's
properties is not significant. A missing property takes the schema's default
value (`default`, or `defaultExpr` when `default` is null). For an `id`
property, the value `4294967295` (2³² − 1, `kEmptyId`) means "no reference".

An object can carry a property that its type does not declare: the key is still
decodable through the schema or the table, and it is up to the runtime to
ignore it or not. Nearly all minor-version-0 files contain some (148 cases in
the test files, 141 of them in minor 0), for example type key 9 with `parentId`
(§ 6.2).

## 5. Values

### 5.1 Choosing the type of a value

For each property key encountered, the reader determines the type as follows,
in this order:

1. if the key is in `schema.json` (`properties` array), its `fieldType`;
2. otherwise, if the key is in the header table, its size class;
3. otherwise, the file is invalid.

The schema type takes precedence over the table's size class: the runtime
consults the object first, then its registry, then the table
(`runtime/src/file.cpp`, `readRuntimeObject`). A disagreement between the schema
and the table is rare: a single case in the test files (key 766, schema
`string`, table `uint`, with a single null byte, hence the same reading).

### 5.2 Decoding by `fieldType`

| `fieldType` | Value in the stream | Result |
|---|---|---|
| `uint` | varuint | unsigned integer |
| `int` | varuint `z` | signed 32-bit integer, zigzag: `(z >> 1) XOR -(z AND 1)` |
| `bool` | one byte, always read as one byte | true if the byte is 1, false otherwise (the test files only write 0 or 1) |
| `id` | varuint | object index (§ 6) |
| `double` | float32 | floating-point number |
| `string` | string | UTF-8 text |
| `bytes` | bytes | raw data |
| `color` | uint32 | ARGB color, `0xAARRGGBB` (`0xFF747474`: opaque gray) |
| `callback` | nothing | never written to a file |

Properties whose `serialized` is `false` in the schema have no entry of their
own in the stream:

- a flag (`bitmask`) or a bit field (`bitField`) is stored in the property
  indicated by its `storage` (`bitmask.storage`, `bitField.storage`); if a file
  nevertheless contains one, as a standalone value, it is decoded with its
  `fieldType` like any other property;
- the others (values computed at run time, callbacks) are never written. The
  keys of the four callbacks (395, 401, 869, 1016) are known to no runtime
  registry: such a key encountered without an entry in the table makes the file
  invalid.

### 5.3 Unknown property

A key absent from the schema but present in the table (§ 3.1) is decoded
according to its size class and its value is discarded: a reader does not lose
synchronization. An unknown `uint` is read as a 64-bit varuint.

### 5.4 Non-instantiable object

An object is **non-instantiable** when its type key is absent from the schema,
or present with `abstract` equal to `true` (abstract types that the runtime does
not build, such as keys 9 and 10). This does not stop reading: the object's
properties are read and discarded as above (§ 5.3), up to the closing `0`. The
object is ignored, but it may **occupy a slot** in the object list of its
artboard (§ 6.2).

## 6. Objects, artboards and references

The meaning of an object depends on those that precede it in the stream: the
write order MUST be preserved as is.

### 6.1 Artboard scope

- An object of type `Artboard` (key 1) opens a scope that lasts until the next
  `Artboard` or the end of the file.
- Objects placed before the first `Artboard` (`Backboard`, assets, view models
  and their instances) are **global**. They receive no artboard number, even
  when their type descends from `Component` (the global `ViewModelInstance*`
  carry a `parentId` that is not an artboard number; its meaning is not covered
  by this document).
- In most files, the `ViewModelInstance*` are global. In 19 test files, some
  follow an `Artboard`: they are then in its scope and follow the rule below.

### 6.2 Numbering

Within an artboard scope, the `Artboard` is object **0**. Each following object
that "takes a number" receives the next number, in stream order. These take a
number:

- every type that descends from `Component` in the schema (`parent` chain),
  except: the `Artboard` itself, `ScrollPhysics`, `ClampedScrollPhysics` and
  `ElasticScrollPhysics` (the runtime files them with the `Backboard`, never in
  an artboard), and `ScriptInput*` whose `parentId` is 0 (a `ScriptInput*`
  counts only if `parentId` is non-zero);
- every type that descends from `KeyFrameInterpolator`
  (`CubicEaseInterpolator`, `ElasticInterpolator`, ...), because keyframes and
  transitions designate them by number;
- every type that descends from `UserInput` (runtime rule; the test files do
  not allow confirming it: these objects are always the last of their artboard
  there and no property designates them);
- every non-instantiable object (§ 5.4), unless it is consumed by a more
  recently opened structure: after an animated object (`KeyedProperty`) it is
  discarded without a slot; in a state machine layer it becomes an empty state
  (it shifts the `stateToId`); in a state machine it becomes a null input (it
  shifts the input indices). Among components, it takes a number: skipping such
  an object without counting it shifts all following numbers.

Types that are in none of these families do not take a number: `LinearAnimation`
and the other animations, `KeyedObject`, `KeyedProperty`, the `KeyFrame`s,
`StateMachine`, `LayerState`, `StateTransition` and their elements. Note that
`NestedAnimation`, `NestedStateMachine`, `NestedInput`, `Event` and others
descend from `Component` and therefore take a number.

The case of type key 9. In the minor-version-0 files of the test base (10 files,
130 objects), key 9 is an object that carries `parentId` (key 5) and sits
between a shape or a vertex and the next `Fill`. The schema names it
`BindableProperty`, with no properties, and marks it abstract: it therefore
follows the rule for non-instantiable objects and takes a number. No special
rule is needed, and this is what makes the `parentId`s of these files
consistent.

Verification: with these rules, the 95,676 `parentId` and `interpolatorId`
references of the 475 test files (128,360 over the 491 files from before the
removals of third-party files) all land on an object of the right type.

### 6.3 References

A property of type `id` is an index, but not always into the artboard's list.
In the test files:

- **Artboard object numbers**: `parentId` (key 5, 0 designates the artboard),
  the `objectId` of a `KeyedObject`, the `sourceId` of a `ClippingShape`, the
  `interpolatorId` of a keyframe or a transition, `targetId`, `drawableId`.
- **Indices into other lists**: the `animationId` of an animation state (the
  artboard's animations), the `stateToId` of a transition (the layer's states),
  the `artboardId` of a `NestedArtboard` (the file's artboards), the
  `viewModelId` of an artboard (the file's view models), the `converterId` of a
  data bind (the file's data converters) and `scriptAssetId` (the file's
  assets).

The complete list of `id` properties is in `schema.json` (`fieldType` = `id`).
The list each one refers to is not given there; it can be read from the runtime
(`runtime/src/`).

## 7. Versions

- The major version MUST be 7 (D9). A reader rejects any other value.
- The minor version may be higher than the one the reader knows: new properties
  are skipped thanks to the table (§ 5.3), new objects are ignored (§ 5.4).
- A major version 8 on Rive's side is a migration project, not an evolution of
  this document.

## 8. Relationship with `.riv`

- A `.twno` and the corresponding `.riv` differ only in the first 4 bytes.
  `tools/twno_convert.py` goes from one to the other by rewriting the signature
  (exact round trip, verified on the reference files).
- A Tweenora reader reads `.twno` and `.riv` (D5). A Tweenora writer writes
  `TWNR`.
- Rive's official runtime rejects a `TWNR` signature. To open one with it, go
  through `twno_convert`.

## 9. Tweenora extensions

Type and property keys from **50,000 to 59,999** are reserved for objects and
properties specific to Tweenora (D8). Rive's keys currently go up to 1,071
(types) and 1,099 (properties).

- Every extension property key written in a file MUST appear in the header
  table (§ 3.1), so that a reader that does not know the extension, including
  the official runtime, can skip it.
- A reader cannot skip a property that neither the schema nor the table knows
  (§ 5.1): the obligation in the previous point is the only guarantee that
  readers can skip it. Keys that Rive's schema defines need not appear there,
  except the four callback keys (§ 5.2).
- An extension property carried by a Rive object (official type key, property
  key 50,000 or more) is skipped in the same way.
- An extension object (type key 50,000 or more) is ignored by a reader that does
  not know it (§ 5.4). Written within an artboard scope among the components, it
  occupies a slot (§ 6.2): the writer MUST number it accordingly, or place it
  before the first `Artboard`, or outside animations and state machines.

These behaviors are established by reading `runtime/src/file.cpp` at base commit
`daf55385` (`readRuntimeObject`, lines 249-324) and confirmed by
`runtime/tests/unit_tests/runtime/extension_keys_test.cpp` (P2-4): the runtime
loads a file containing an extension property on an official object and an
extension object placed among the components, ignores both, keeps the number of
the ignored object (the next object that designates it by `parentId` does attach
to its parent) and reads the same file with the `RIVE` signature. An extension
property absent from the table makes the file invalid
(`ImportResult::malformed`). Extension objects placed in an animation or a state
machine are not covered by this test.

## 10. Examples

Minimal file, a `Backboard` with no properties. The bytes in hexadecimal:

```text
54 57 4e 52   signature "TWNR"
07            major version 7
04            minor version 4
00            file id 0
00            empty property table (no key, hence no word)
17            type key 23, Backboard
00            end of the object
```

A `Node` (type key 2) whose `x` (key 13) is 1.0, with this property declared in
the table (unnecessary for a schema key, but valid). Complete 20-byte file. This
is an example of bytes: a `Node` outside any `Artboard` is rejected at import by
the runtime.

```text
54 57 4e 52   signature "TWNR"
07 04 00      versions 7 and 4, file id 0
0d 00         table: key 13, then end of list
02 00 00 00   one word: code 2 (double) for key 13
02            type key 2, Node
0d            property key 13, x
00 00 80 3f   float32 1.0
00            end of the object
```
