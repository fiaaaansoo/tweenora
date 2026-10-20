# Data binding: feasibility study (Examples 2c)

Conclusion: feasible without an editor. Sources read: `runtime/src/file.cpp` (import), `runtime/src/data_bind/data_bind.cpp`,
`data_bind_context.cpp`, `data_context.cpp`, `runtime/src/viewmodel/*.cpp`, `runtime/src/importers/*viewmodel*`,
`docs/schema/schema.json`. No upstream `.riv` is used as a model.

## Objects to write, in stream order

1. `Backboard`.
2. At file level, before the artboard (no `parent`, no number in the artboard):
   - `ViewModel` (`name`): opens an import context for the properties that follow.
   - `ViewModelPropertyColor` (`name`), one per property: attached to the preceding `ViewModel`; its identifier is
     its rank (0 for the first).
   - `ViewModelInstance` (`name`, `viewModelId` = rank of the `ViewModel` in the file): default instance, the
     first of the view model (`ViewModel::defaultInstance`).
   - one `ViewModelInstanceColor` per property (`viewModelPropertyId` = rank of the property, `propertyValue` =
     initial color): attached to the preceding instance.
3. `Artboard` with `viewModelId` = rank of the view model. The import binds no instance: `viewModelId` designates the view
   model that the host instantiates (`File::createDefaultViewModelInstance` or `createViewModelInstance`, `file.cpp`) and then
   binds to the artboard; the value displayed at the start therefore depends on the host (the web library binds the default
   instance, `goldens` a fresh one).
4. In the artboard, `SolidColor` then, **immediately after**, one `DataBindContext` per bound property: the import designates as target the
   last object that is not a `DataBind` (`file.cpp`, `lastBindableObject`). A `DataBind` has no number in
   the artboard.

## Fields of the `DataBindContext`

- `propertyKey`: key of the target property, here `SolidColor.colorValue`.
- `flags`: 0 = from source to target, a single direction, unnamed path (`DataBindFlags`).
- `sourcePathIds`: bytes, a sequence of varuints: `[rank of the view model, rank of the property]`. `DataContext` compares the
  first term to `viewModelId` of the instance, then follows the properties (one term per level of nested view model).
- `converterId`: absent (no converter).

## References

The rank of a view model, of a property and of an instance has no table in `ID_RULES`: the generator writes them
with `RawId` (a case foreseen by the notice in `README.md`), and the test re-reads the file (`twnoinfo` and stream bytes) and checks
that the binding of each `SolidColor` reads the property whose instance carries the color of that `SolidColor` (two
properties of rank 0 and 1, so that a swap fails).
