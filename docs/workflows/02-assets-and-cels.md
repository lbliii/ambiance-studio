# 02 — From source art to reusable assets

**Input:** layer plan and style reference. **Output:** production cutouts, clean plates, masks, atlases, metadata, preparation recipes, and review evidence. **Gate:** assets.

## Choose the cheapest sound production decision

Search the library by subject, style, lighting direction, perspective, size, and motion role. A compatible reusable smoke plume is valuable; an incompatible viewpoint is not fixed by calling it reusable. Decide whether to reuse unchanged, derive a new version, or generate.

Write a generation request with references and desired output before sending it. Record the expected cost or uncertainty within the authorized scope. Keep one local request identity and returned provider IDs where available. Do not resubmit an uncertain request automatically.

## Source generation contract

For a rigid cutout: specify framing, intended scene location, lighting, perspective, complete silhouette, margins, transparency request, and the attachment/pivot. For a clean plate: identify the removed objects and the scenery that should continue behind them.

For cels: establish a master pose, fixed camera and canvas, grid/cell order, frame count, margins, palette, light, common scale, pivot, and exactly what changes. Describe the continuous action across the last-to-first transition. A rising smoke sequence should not be made to reverse downward merely because ping-pong playback is convenient.

Keep source images and chosen takes intact. A generator may return apparent transparency, uneven cells, stray fragments, inconsistent scale, or structural changes. Treat those as preparation/review issues rather than silently claiming the generation is ready.

## Preparation contract

1. Decode and inspect the actual file. Record dimensions, color/alpha information, and source hash.
2. Establish cell rectangles and discard labels/gutters from the production region deliberately.
3. Inspect/repair alpha. View on contrasting backgrounds and in the intended scene. Look for matte tint, bright or dark fringes, opaque proofing grids, and clipped translucent detail.
4. Remove unwanted neighboring fragments without erasing deliberate wisps or leaves.
5. Register a consistent pivot and common sequence scale. Preserve meaningful variation in content bounds; a flame is supposed to change shape.
6. Save fixed-cell frames or an atlas plus exact layout metadata. Keep individual normalized frames when useful for editing and provenance.
7. Save the transformation/matting recipe and input/output hashes. Regenerate the derived version from the recipe rather than destructively changing its source.

Choose suitable available tools for those operations. A supplied script is a tool only after it exists and has been exercised. The current kit includes `tools/asset_tool.py` for recipe-driven registration and fixed-grid packing of prepared transparent cels. It creates light/dark proofs and a playback preview. Follow the [workbench guide](../RIG-WORKBENCH.md). General cutout extraction and matte repair remain separate tasks.

## Inspect before admission

Technical checks: files decode, dimensions match the atlas grid, frame count fits, alpha is real, no cell accesses another cell, and the catalog resolves every asset. Visual checks: shared scale/pivot, edge quality, consistent light/perspective/style, intentional deformation, and a natural closing transition. Inspect both a contact sheet and actual playback.

Keep unlit geometry, emissive detail, and glow distinct when animated lighting needs range. A window painted at maximum warmth can hide its overlaid animation; fix the base/overlay relationship.

Create a new asset version when content changes. Catalog its stable ID, hash, preview, compatibility tags, sockets, and default cycle. Preserve accepted versions used by prior films. Record observed defects and rejected candidates so future runs do not repeat the same failure.
