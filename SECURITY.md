# SECURITY.md — Tweenora

Short version: no accounts, server or user data until the cloud (phase 7)
exists. To be completed when the cloud launches.

## Secrets

- No secrets in the repository: no npm or GitHub token, no `.env` (ignored by
  `.gitignore`).
- Publishing to npm (later) is done from CI with a mechanism that respects
  two-factor authentication, never with a committed token.

## Untrusted files

The runtime reads `.twno` and `.riv` files that come from unknown parties (web
page, import into the editor). Rules:
- A malformed or booby-trapped file must never crash the runtime or read out of
  bounds: it is rejected cleanly.
- Files may contain Luau scripts. The runtime runs them in a sandbox with no
  access to files or the network.
- The runtime has been neither audited nor fuzzed: only open files you trust.

## Rive's proprietary content

- Never any decompiled code from the Rive editor in the repository.
- Never any third-party assets (documentation, fonts, animations, images), nor
  screenshots of Rive's editor.
- `vendor/` contains read-only, untracked MIT reference checkouts.

## Reporting a vulnerability

Do not open a public issue: use GitHub's private reporting (the "Security" tab,
"Report a vulnerability"). No audit or fuzzing of the runtime has been done to
date: only open files you trust.

## Auth boundaries

None for now. To be defined in phase 7 (accounts, sessions, sharing
permissions).
