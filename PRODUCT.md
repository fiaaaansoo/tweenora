# PRODUCT.md — Tweenora

Product summary. The detailed plan (decisions, phases, tasks) is in
`PLAN.md`, which is kept in the working repository.

## Vision

A runtime and, later, an open source editor for interactive vector animations.
They read `.riv` files (major version 7), with a format of their own (`.twno`,
signature `TWNR`) and a visual identity of their own. The goal is behavior that
conforms to `rive-runtime`; this remains to be demonstrated (phase 4 of
`PLAN.md`).

## Target user

Designers and developers who build interactive animations (state machines, data
binding) for the web, mobile, desktop and games, and who want an open,
self-hostable tool that does not depend on a proprietary service.

## Model

Open source and free first (runtimes + editor). A paid cloud service (sync,
real-time collaboration, sharing, community) will come in phase 7.

## Current scope

Nothing has shipped yet. What exists today:
- the public sources of the format (`docs/ANALYSE.md`);
- the plan (`PLAN.md`);
- the choice of the name (`docs/NOM.md`) and the reserved `@tweenora` npm scope.

## Out of scope (explicitly)

- Copying or decompiling the code of any third-party editor.
- Copying the look of another product's interface: our own look.
- Reusing third-party content (docs, fonts, animations, images), names or
  logos.
- Domains, trademark filing and legal advice: deferred to the cloud launch.
