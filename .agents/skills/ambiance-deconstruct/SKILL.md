---
name: ambiance-deconstruct
description: "Break an ambiance reference image into a painted layer plan, clean plates, attachment groups, and animation opportunities. Use before generating cutouts or extending a scene's depth."
---

# Deconstruct the reference

Read the project brief, reference image, and [image-to-layer workflow](../../../docs/workflows/01-reference-and-layers.md). Follow the [style guide](../../../docs/STYLE-GUIDE.md) where the user has not specified another direction.

Describe the focal point, light sources, palette, edge character, atmospheric distance, perspective, and foreground framing. Mark proposed objects separately from observed ones. A single image does not provide unseen geometry or a physically accurate depth map.

Create `plans/layer-plan.json` using [the production contracts](../../../docs/CONTRACTS.md), and record composition observations in `plans/layout-notes.md`. Give each planned object a stable ID, screen bounds, draw order, artistic depth, anchor, intended size, parent or socket, motion method, and source/reuse strategy.

Plan the pixels behind every moving object and beyond the frame edges. Separate clean backgrounds, opaque bases, alpha cutouts, masks, and emissive overlays. Identify seams likely to reveal duplicate roofs, silhouettes, or transparent gaps under camera motion. Plan modest camera limits before choosing overscan.

Use cels for deformation or internal changes; transforms for rigid motion; deterministic particles/paths for repeated small elements. Keep stable architecture fixed unless structural deformation is intentional. A building with animated windows is often a reusable rig; a newly generated building in every frame is not a stable substitute.

Create a layer proof or labeled layout only when it resolves composition or occlusion uncertainty. Preserve a clean approved still as the visual reference. Do not regenerate the original solely to force it into a preset template.

Evidence for `intent` and `layout`: preserved reference, completed brief, layer plan, clean-plate/occlusion notes, attachment decisions, and explicit review observations. A generated plan is not evidence that its assets exist or that a camera move is already safe.
