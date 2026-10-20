# CONTRIBUTING.md — Tweenora

## Branches

- `main`: always in a state that builds and whose tests pass.
- Work on one branch per task: `feat/<slug>`, `fix/<slug>`, `chore/<slug>`,
  `docs/<slug>` (the `<slug>` is that of the crew task).

## Commits

[Conventional Commits](https://www.conventionalcommits.org/):
`type(scope): summary`.

- Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `build`, `ci`,
  `perf`.
- Scopes: `runtime`, `web`, `platforms`, `editor`, `server`, `tools`, `docs`,
  `crew`.
- Example: `feat(runtime): accept the TWNR signature when reading`.

Merges from Rive (`upstream`) go in a dedicated commit:
`chore(runtime): merge upstream <commit>`. Procedure:
[`docs/UPSTREAM.md`](docs/UPSTREAM.md).

## Pull requests

- One PR per task, from the branch to `main`.
- A PR that imports or merges upstream is merged with a **merge commit** (never
  squash or rebase: Rive's history would be lost).
- Before merging: runtime unit tests and parity tests green (CI arrives in
  P4-3; until then, run them locally).
- `fiaaaansoo/tweenora` repository: no mandatory human review as long as the
  project has a single maintainer. A contribution is offered under the license
  of the folder it modifies (see `LICENSE`). Code of conduct:
  `CODE_OF_CONDUCT.md`.
