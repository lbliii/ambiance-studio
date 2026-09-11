---
name: ambiance-animate
description: "Assemble painted layers and sprite cels into a deterministic looping ambiance scene. Use for depth, anchors, shared rigs, periodic motion, scene placement, and visual loop testing."
---

# Assemble the animated picture

Read the production assets, [scene contract](../../../docs/SCENE-CONTRACT.md), and [animation workflow](../../../docs/workflows/03-scene-and-animation.md). Use CLI `render frame/proof/video` through the shared evaluator; [rendering](../../../docs/RENDERING.md) documents backend limits. The browser provides rig editing and preview checks, not MP4 export; historical effects outside the shared contract still need separate implementation.

Assemble the selected output compositions before movement, preserving the reference's identity and intended relationships. Use `scene place` for recorded source mappings and `scene reparent --keep-world --at` for an explicit reference pose; see [scene transactions](../../../docs/architecture/SCENE-TRANSACTIONS.md). These use the same dry-run/hash-checked mutation path as `scene apply`. Keep paint order separate from attachment and depth; preserving one pose does not preserve a whole trajectory.

Use [scene activity](../../../docs/SCENE-ACTIVITY.md) to measure semantic actions in each intended view, then produce bounded raster/disabled-element and matched strength/cadence proofs. Inspect warnings and misses; state activity and changed pixels never establish observed readability. Record only actual normal-speed observations bound to the exact receipt.

Use `scene timing` to inspect the actual timing driver before tuning cadence: a cell track overrides the fallback cycle. Sample absolute time; use compatible periods, deterministic paths and deliberate hidden resets where needed.

Animate shape changes with cels and rigid movement with transforms. Offset phases where reused sequences would otherwise look synchronized. Use the [motion direction scale](../../../docs/MOTION-DIRECTION.md) for a primary feature, readable supporting/environmental life and stable references. Judge amplitude and cadence separately. Quietness alone does not justify tiny, infrequent actions; every selected story action must read in the intended composition.

Use `render rig-proof` for compound rest/extreme, body-hidden and fixed-occluder comparisons. Inspect the actual backing: hiding descendants cannot erase baked imagery. Keep fixed glass and receiving shadows independent. Judge repeated flames' shape, cadence and phase together; compare supporting motion enabled/disabled when its readability is uncertain.

Make a low-resolution draft and inspect zero, intermediate times, camera extremes, and the join. Compare state at 0 and T, then inspect the transition from the final exported frame to frame zero. Export exactly N samples from frame 0 through N−1; do not add a duplicated endpoint. Check edge coverage and attachment drift during the whole cycle, not only the cover frame.

Save the scene and actual reports/proofs. Run `scene check` on the selected project, then the browser pixel check and visual inspection as separate evidence. For a captured revision, render with `--revision ID`; do not substitute the working scene. Reconcile placed parts with `plan check`.

Close `animation` from technical evidence, `plan check --require-complete` for the declared scope, and actual visual review in the requested compositions. Name observed story actions and too-still intervals as well as defects. Changes to assets or camera limits require a new affected review. Pure JSON validation cannot establish that a frame looks correct or that motion is noticeable. See [seed-to-stage production](../../../docs/SEED-TO-STAGE.md).

For multiple requested formats, use `view check` and `render views-proof --view portrait --view landscape` before final video. Inspect both crops at the same sample times, including edge coverage, attachments, receiving effects and last-to-first motion. The editor output panes and saved paired proof use a shared clock; independently playing final MP4s do not establish exact synchronization. Use `review draft GATE --revision ID --view ID` for separate picture-review subjects.
