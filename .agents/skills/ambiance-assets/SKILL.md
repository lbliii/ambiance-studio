---
name: ambiance-assets
description: "Produce and prepare reusable painted cutouts, masks, clean plates, and sprite atlases for an ambiance film. Use for generation, matte cleanup, cel registration, and asset-pack review."
---

# Prepare production assets

Read the layer plan, [asset workflow](../../../docs/workflows/02-assets-and-cels.md), and [production contracts](../../../docs/CONTRACTS.md). Use the host's image generation/editing skill or tool when available and applicable; do not assume a particular provider is installed. Existing files may be imported without regeneration.

For each asset, choose reuse, derived edit, or new generation. Inspect reference art before edits. Preserve originals in `assets/raw/`; produce versioned derivatives in `assets/production/`. Record a generation request before sending it, then its actual result and selected take in `plans/generation-ledger.json`. Missing output, timeout, and confirmed provider failure are different states.

For a cel sequence, lock framing, camera, lighting, palette, pivot, and stable geometry. Specify the changing shape, cell count/layout, margins, transparent-background request, and closing motion. Generate a master pose first when the object's identity is not established. Do not promise that a prompt guarantees correct alpha, frame registration, or an exact loop.

Inspect alpha on contrasting backgrounds and inspect cels as both contact sheets and playback. Remove matte contamination and neighboring-cell fragments with a suitable editing workflow. Register against one pivot and sequence scale; do not resize every frame independently to its own content bounds. Intentional smoke/flame deformation should survive preparation.

Retain an unlit base for animated windows and a separate illumination layer when needed. Keep exact crop rectangles, atlas geometry, alpha convention, masks, and attachment sockets in metadata. Store preparation recipes and input/output hashes so cleanup is repeatable.

Run available asset checks and inspect their actual limits. Use `tools/asset_tool.py` and the [workbench guide](../../../docs/RIG-WORKBENCH.md) for prepared transparent cels. It supports fixed pivots, explicit per-cel landmarks, and a bottom-center silhouette estimate, with one sequence scale and immutable cached output. Inspect its proofs and warnings. Catalog registration does not close a quality gate. `kit.py check` verifies catalog integrity; it is not a general matte-quality detector. Record visual edge/registration review separately. Use [failure recovery](../../../docs/TROUBLESHOOTING.md) for recurring source defects.

Close `assets` only with the production files, catalog/recipes, actual inspection reports, and visual observations. A pretty atlas image with opaque checkerboard squares is not a ready alpha asset.
