---
name: ambiance-release
description: "Inspect encoded ambiance-video deliverables, record release reviews, package a handoff, and catalog reusable assets. Use after composition/mixing or when preparing a finished film for another operator."
---

# Inspect and hand off the film

Read `project.json`, current gate status, and [delivery workflow](../../../docs/workflows/05-release-and-library.md). Use the chosen media backend and its actual output, not a screenshot of a progress bar.

Use `media verify` for complete decode, expected dimensions/frame count/rate, timestamps, audio tracks and presentation duration. Request action-specific contacts when useful. Inspect encoded audio separately from WAV; raw extracted samples can include priming/padding outside the presented interval. See [rendering and media](../../../docs/RENDERING.md).

For soundtrack editions, use `media compose` to reuse supported encoded picture with explicitly selected PCM. Keep score, ambience-only and silent editions unambiguous, and preserve final files separately from scratch renders.

Follow [captured revisions and editions](../../../docs/REVISIONS.md): `revision capture/check`, revision-bound rendering/composition, `review draft --revision ID --edition ID`, then `review record`. Legacy folder-watch receipts remain valid on their own terms; capture does not migrate pass verdicts. Release requires actual human look/listen and phone observations of the exact edition. Reuse applicable feedback; leave unperformed checks open while continuing useful work.

Gate readiness is distinct from permission to publish. Follow explicit user instructions and existing authorization. Do not send files to another person, publish, or widen account access just because the gate passes. If the user elects to deliver with open checks, retain those limitations in the handoff instead of marking them passed.

Catalog accepted assets, grouped rigs, motion recipes, and sound recipes using stable IDs, hashes, compatibility notes, and source/preparation records. A human-readable preview should accompany a reusable module. Use the [contracts](../../../docs/CONTRACTS.md) and [scaling plan](../../../docs/SCALING.md); do not overwrite a version referenced by an existing film.

Use `revision handoff` for captured editions and retain `handoff.md` as the working summary. Include exact files, validation, open checks, rebuild/platform requirements and reusable pieces. A packaged review draft is useful even when human release checks remain open.
