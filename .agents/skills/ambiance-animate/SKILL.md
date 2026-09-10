---
name: ambiance-animate
description: "Assemble painted layers and sprite cels into a deterministic looping ambiance scene. Use for depth, anchors, shared rigs, periodic motion, scene placement, and visual loop testing."
---

# Assemble the animated picture

Read the production assets, [scene contract](../../../docs/SCENE-CONTRACT.md), and [animation workflow](../../../docs/workflows/03-scene-and-animation.md). Use CLI `render frame/proof/video` through the shared evaluator; [rendering](../../../docs/RENDERING.md) documents backend limits. The browser provides rig editing and preview checks, not MP4 export; historical effects outside the shared contract still need separate implementation.

Preserve the reference's composition before movement. Use `scene place` for recorded source mappings and `scene reparent --keep-world --at` for an explicit reference pose; see [scene transactions](../../../docs/architecture/SCENE-TRANSACTIONS.md). These use the same dry-run/hash-checked mutation path as `scene apply`. Keep paint order separate from attachment and depth; preserving one pose does not preserve a whole trajectory.

Use `scene timing` to inspect the actual timing driver before tuning cadence: a cell track overrides the fallback cycle. Sample absolute time; use compatible periods, deterministic paths and deliberate hidden resets where needed.

Animate shape changes with cels and rigid movement with transforms. Offset phases where reused sequences would otherwise look synchronized. Preserve a hierarchy of motion: a primary feature, supporting activity, and subtle background movement. Do not make every object equally active.

Use `render rig-proof` for compound rest/extreme, body-hidden and fixed-occluder comparisons. Inspect the actual backing: hiding descendants cannot erase baked imagery. Keep fixed glass and receiving shadows independent. Judge repeated flames' shape, cadence and phase together; compare supporting motion enabled/disabled when its readability is uncertain.

Make a low-resolution draft and inspect zero, intermediate times, camera extremes, and the join. Compare state at 0 and T, then inspect the transition from the final exported frame to frame zero. Export exactly N samples from frame 0 through N−1; do not add a duplicated endpoint. Check edge coverage and attachment drift during the whole cycle, not only the cover frame.

Save the scene and actual reports/proofs. Run `scene check` on the selected project, then the browser pixel check and visual inspection as separate evidence. For a captured revision, render with `--revision ID`; do not substitute the working scene. Reconcile placed parts with `plan check`.

Close `animation` from both technical evidence and a visual review. Changes to assets or camera limits require a new affected review. Pure JSON validation cannot establish that a frame looks correct.
