---
name: ambiance-release
description: "Inspect encoded ambiance-video deliverables, record release reviews, package a handoff, and catalog reusable assets. Use after composition/mixing or when preparing a finished film for another operator."
---

# Inspect and hand off the film

Read `project.json`, current gate status, and [delivery workflow](../../../docs/workflows/05-release-and-library.md). Use the chosen media backend and its actual output, not a screenshot of a progress bar.

Validate the final encoded video: complete decode, expected dimensions/frame count/frame rate, monotonic timestamps, correct audio track, and exact presentation duration. Inspect encoded audio separately from the WAV. Account for encoder delay/edit lists/padding; raw extracted sample count alone can misrepresent the presented interval. The Last Lantern reference retains examples of these reports.

If only audio changes, preserve already accepted picture through stream copying when supported. Keep named editions unambiguous: score, ambience-only, silent, cover, and lossless masters. Provide final files and source sessions separately from scratch renders. Record file hashes and the renderer/codec versions actually used.

Use `studio.py review-template` and `record` to capture checks with their evidence. The `release` gate includes real human look/listen and phone review of the exact final file. Existing user observations can be recorded with a feedback source when they establish those checks. Never invent an observation, observer, or device. Open checks do not prevent packaging a clearly labeled review draft or continuing independent work.

Gate readiness is distinct from permission to publish. Follow explicit user instructions and existing authorization. Do not send files to another person, publish, or widen account access just because the gate passes. If the user elects to deliver with open checks, retain those limitations in the handoff instead of marking them passed.

Catalog accepted assets, grouped rigs, motion recipes, and sound recipes using stable IDs, hashes, compatibility notes, and source/preparation records. A human-readable preview should accompany a reusable module. Use the [contracts](../../../docs/CONTRACTS.md) and [scaling plan](../../../docs/SCALING.md); do not overwrite a version referenced by an existing film.

Close with `handoff.md`: final file paths, creative intent, actual validation, remaining limits, rebuild instructions, and the next reusable pieces. A source archive may be complete even when its old native renderer requires a particular platform; state that requirement accurately.
