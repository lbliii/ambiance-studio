---
name: ambiance-animate
description: "Assemble painted layers and sprite cels into a deterministic looping ambiance scene. Use for depth, anchors, shared rigs, periodic motion, scene placement, and visual loop testing."
---

# Assemble the animated picture

Read the production assets, [scene contract](../../../docs/SCENE-CONTRACT.md), and [animation workflow](../../../docs/workflows/03-scene-and-animation.md). The current browser editor implements named/nested attachments, cel-specific socket tracks, and preview loop checks; see the [workbench guide](../../../docs/RIG-WORKBENCH.md). Its full-film effects and MP4 export have not been implemented; choose an available renderer explicitly.

Use a saved scene recipe for artistic settings. Preserve the reference's composition before adding movement. Keep draw order distinct from depth; use shared parent transforms or sockets for attached elements. The cottage, chimney smoke, and ground must not acquire unrelated camera movement. Keep overlay positions in the same coordinate system as their base image.

Sample state from absolute time. Choose whole-number motion cycles and cel durations that fit the picture loop, or use an explicitly planned longer common period. Randomized particles need reproducible parameters and a circular schedule; frame generation must not depend on playback history.

Animate shape changes with cels and rigid movement with transforms. Offset phases where reused sequences would otherwise look synchronized. Preserve a hierarchy of motion: a primary feature, supporting activity, and subtle background movement. Do not make every object equally active.

Make a low-resolution draft and inspect zero, intermediate times, camera extremes, and the join. Compare state at 0 and T, then inspect the transition from the final exported frame to frame zero. Export exactly N samples from frame 0 through N−1; do not add a duplicated endpoint. Check edge coverage and attachment drift during the whole cycle, not only the cover frame.

Save scene data, actual reports, contact frames, and the loop preview under `scene/`, `reports/animation/`, and `deliverables/picture/`. `node editor/verify-engine.mjs` checks the bundled example's state invariants. For another scene, run `node tools/check-scene.mjs path/to/scene.json --catalog path/to/assets/catalog.json --out path/to/report.json` and record the result. Run the browser pixel check as separate evidence. Neither closes the animation gate without an actual visual review.

Close `animation` from both technical evidence and a visual review. Changes to assets or camera limits require a new affected review. Pure JSON validation cannot establish that a frame looks correct.
