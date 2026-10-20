# Public sources of the format and the runtimes

This note replaces the project's earlier analysis notes. It points only to public sources.

## File format

- The `.riv` format is described by Rive's public documentation: https://rive.app/docs/runtimes/advanced-topic/format
- The C++ reader of the `rive-runtime` repository (MIT) implements it: `runtime/include/rive/runtime_header.hpp` for the header,
  `runtime/include/rive/generated/` and `runtime/src/generated/` for the types and property keys.
- The specification of Tweenora's `.twno` format is in [`FORMAT_TWNO.md`](FORMAT_TWNO.md), the schema of types and
  properties in [`schema/schema.json`](schema/schema.json), and the inventory of reference files in
  [`INVENTAIRE_RIV.md`](INVENTAIRE_RIV.md).

## Upstream MIT repositories

Tweenora's C++ runtime and web layer come from `rive-runtime` and `rive-wasm`, both under the MIT license
(see [`UPSTREAM.md`](UPSTREAM.md) and [`../NOTICE`](../NOTICE)). The `rive-app` organization also publishes runtimes for
other platforms, under licenses to be checked one by one before any use.

## Editor

Rive's editor is proprietary and is not included in this repository, which ships no editor code, binary or resource.
