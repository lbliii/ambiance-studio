# 02 — From source art to reusable assets

**Input:** layer plan and style reference. **Output:** production cutouts, clean plates, masks, atlases, metadata, preparation recipes, and review evidence. **Gate:** assets.

For edge problems, use `asset edges` at an explicit displayed cel size and optional context rectangle before choosing a repair. `asset edge-repair` preserves original bytes and uses opt-in matte cleanup, choke, feather and padding. Attach its explicit `edge_preparation` report when compiling the derivative so revisions retain the source/recipe chain. See [edge quality](../EDGE-QUALITY.md); inspect all cels and the downstream encoded motion, preserving fine alpha by default.

## Choose the cheapest sound production decision

Search the library by subject, style, lighting direction, perspective, size, and motion role. A compatible reusable smoke plume is valuable; an incompatible viewpoint is not fixed by calling it reusable. Decide whether to reuse unchanged, derive a new version, or generate.

When a prior film is named as a movement reference, inspect its actual source sheet and how the film used it before substituting a different effect. An atlas filename or catalog entry alone does not show its changing shape, registration quality, or final scale. Preserve its accepted version; reuse or derive only after checking the new scene's style and lighting.

Write a generation request with references and desired output before sending it. Record the expected cost or uncertainty within the authorized scope. Keep one local request identity and returned provider IDs where available. Do not resubmit an uncertain request automatically.

## Source generation contract

For a rigid cutout: specify framing, intended scene location, lighting, perspective, complete silhouette, margins, transparency request, and the attachment/pivot. For a clean plate: identify the removed objects and the scenery that should continue behind them.

For cels: establish a master pose, fixed camera and canvas, grid/cell order, frame count, margins, palette, light, common scale, pivot, and exactly what changes. Describe the continuous action across the last-to-first transition. A rising smoke sequence should not be made to reverse downward merely because ping-pong playback is convenient.

Keep source images and chosen takes intact. A generator may return apparent transparency, uneven cells, stray fragments, inconsistent scale, or structural changes. Treat those as preparation/review issues rather than silently claiming the generation is ready.

## Preparation contract

1. Use `asset preflight` to inspect decoded dimensions, alpha facts and source hash; its previews do not certify a clean matte.
2. Establish cell rectangles and discard labels/gutters from the production region deliberately.
3. Inspect/repair alpha. View on contrasting backgrounds and in the intended scene. Look for matte tint, bright or dark fringes, opaque proofing grids, and clipped translucent detail.
4. Remove unwanted neighboring fragments without erasing deliberate wisps or leaves.
5. Register a consistent pivot and common sequence scale. Preserve meaningful variation in content bounds; a flame is supposed to change shape.
6. Save fixed-cell frames or an atlas plus exact layout metadata. Keep individual normalized frames when useful for editing and provenance.
7. Save the transformation/matting recipe and input/output hashes. Regenerate the derived version from the recipe rather than destructively changing its source.

Use `asset build/inspect/proof/admit` for registration, fixed-grid packing and proofs; see the [workbench guide](../RIG-WORKBENCH.md). Authorized sprite preparation includes applicable local decode, crop, registration, packing and deterministic matte cleanup on derivatives. Continue within existing authority; creative repaint or a different generation route follows the host's image-tool instructions. Preserve raw output and identify derived alpha honestly. These commands do not infer segmentation or automatically remove checkerboards.

Keep a backing's **removal mask** separate from the **retained object's alpha**. Removal may need a wider region to clear old fragments and reveal clean paint; the cutout must exclude neighboring rims or fixtures. Inspect isolated parts and a contextual body-hidden proof, including inherited child visibility. A scene flag cannot remove imagery baked into another layer.

When a full-frame edit leaves a tiny ghost, try an enlarged, bounded repair crop before another full-frame request. Use `asset crop/return` with recorded source coordinates, inspected return registration and a local blend mask; see [raster preparation](../ASSET-PREPARATION.md). Use only the needed hidden/reveal paint and retain original foreground rails or cup lips. Returned dimensions alone do not prove alignment.

## Inspect before admission

Technical checks: files decode, dimensions match the atlas grid, frame count fits, alpha is real, no cell accesses another cell, and the catalog resolves every asset. Visual checks: shared scale/pivot, edge quality, consistent light/perspective/style, intentional deformation, and a natural closing transition. Inspect both a contact sheet and actual playback.

Keep unlit geometry, emissive detail, and glow distinct when animated lighting needs range. A window painted at maximum warmth can hide its overlaid animation; fix the base/overlay relationship.

### Flame shape versus light modulation

For a visibly flickering candle, separate the stable holder/wick, changing flame silhouette and core, and any softer light/reflection response. Brightness-only variation may suit a distant glow, but does not demonstrate a deforming flame sequence. Remove or dim the old painted flame across the full new silhouette's sweep to prevent a stationary duplicate beneath it. Register cels to the physical wick with a common scale, preserving intentional height, lean and width changes; centering each moving bright silhouette can make the emission point wander. Split multiple flames into independent emitters when they need distinct behavior, and tie each reflection to its actual source.

The Last Lantern's [eight-pose flame study](../../assets/lantern/flame-cels.png) is a concrete shape reference: its tips, silhouettes and inner cores change. The [production notes](../../reference/visual-production.md) distinguish that standalone study from the flame poses incorporated into twelve cottage cels. Its warm stylized treatment is not automatically a match for another painting. Inspect it at the new candle's intended screen size; derive compatible poses or a new version when needed.

Show a compact proof of source poses, the prepared atlas and actual-speed playback in the scene. Distinguish authored/generated key poses, interpolated frames, held cels and light-only changes; the number of stored slots is not the amount of independently drawn animation.

Create a new asset version when content changes. Catalog its stable ID, hash, preview, compatibility tags, sockets, and default cycle. Preserve accepted versions used by prior films. Record observed defects and rejected candidates so future runs do not repeat the same failure.
