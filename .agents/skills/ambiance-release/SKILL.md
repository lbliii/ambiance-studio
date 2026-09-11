---
name: ambiance-release
description: "Inspect encoded ambiance-video deliverables, record release reviews, package a handoff, and catalog reusable assets. Use after composition/mixing or when preparing a finished film for another operator."
---

# Inspect and hand off the film

Read `project.json`, current gate status, and [delivery workflow](../../../docs/workflows/05-release-and-library.md). Use the chosen media backend and its actual output, not a screenshot of a progress bar.

Use `media verify` for complete decode, expected dimensions/frame count/rate, timestamps, audio tracks and presentation duration. Request action-specific contacts when useful. Inspect encoded audio separately from WAV; raw extracted samples can include priming/padding outside the presented interval. See [rendering and media](../../../docs/RENDERING.md).

For soundtrack editions, use `media compose` to reuse supported encoded picture with explicitly selected PCM. Deliver the complete short master specified by the brief; longer files are separate requested derivatives. State all cycle/delivery durations and verify matching audio. For TV targets, follow the workflow's full-resolution and device/platform review guidance. Keep score, ambience-only and silent editions unambiguous, and preserve final files separately from scratch renders.

Follow [captured revisions and editions](../../../docs/REVISIONS.md): `revision capture/check`, revision-bound rendering/composition, `review draft --revision ID --edition ID`, then `review record`. Legacy folder-watch receipts remain valid on their own terms; capture does not migrate pass verdicts. Release requires actual human look/listen and phone observations of the exact edition. Reuse applicable feedback; leave unperformed checks open while continuing useful work.

Gate readiness is distinct from permission to publish. Follow explicit user instructions and existing authorization. Do not send files to another person, publish, or widen account access just because the gate passes. If the user elects to deliver with open checks, retain those limitations in the handoff instead of marking them passed.

Catalog accepted assets, grouped rigs, motion recipes, and sound recipes using stable IDs, hashes, compatibility notes, and source/preparation records. A human-readable preview should accompany a reusable module. Use the [contracts](../../../docs/CONTRACTS.md) and [scaling plan](../../../docs/SCALING.md); do not overwrite a version referenced by an existing film.

Register the completed movie set and select the current review through the [studio library](../../../docs/STUDIO-LIBRARY.md). Use `delivery handoff` for exact/current watch links, hashes and open checks; use `revision handoff` for deeper captured-input evidence. Retain authored creative context in `handoff.md`. Include rebuild/platform requirements and reusable pieces. A clearly labeled review movie can be presented while human release checks remain open. Earlier exports need explicit identity-bound registration, with no inferred approval transfer.

For multi-format films, use iteration schema 2 or a version-2 delivery selection. Each view/soundtrack pair needs its own verified edition, correctly sized poster, exact watch link and release evidence. `media verify --revision ID --edition ID` uses the recorded output dimensions and clock. Composition inherits its picture view. Keep feedback bound to the resolved view/role and movie hash; list open checks for every pair in the handoff. Existing copied project pipelines are not silently migrated.
