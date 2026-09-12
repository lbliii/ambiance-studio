---
name: ambiance-assets
description: "Produce and prepare reusable painted cutouts, masks, clean plates, and sprite atlases for an ambiance film. Use for generation, matte cleanup, cel registration, and asset-pack review."
---

# Prepare production assets

Read the layer plan and [asset workflow](../../../docs/workflows/02-assets-and-cels.md). Use `plan next` to identify ready parts and `library find/inspect` to examine reusable sources. Use the host's image skill/tool for applicable generation or creative edits; existing files need no regeneration.

Read the selected compositions and story requirements before choosing crops or generation framing. Prepare the production parts and hidden paint needed by both views and the intended motion envelope; retain useful source paint and create missing geometry/poses. See [seed-to-stage production](../../../docs/SEED-TO-STAGE.md). An easy cutout is a useful first test, not the complete asset scope. Record missing art as production work instead of reducing the action to what a static patch can perform.

Size sources for their largest displayed footprint across views and motion, tracing native detail through crop/registration and any enlargement. High output dimensions or supersampling do not recover missing paint. Use the workflow's source-detail checks and existing full-resolution proofs; planned TV profiles and automatic audits are not available commands.

For each asset, choose reuse, derived edit, or new generation. Inspect reference art before edits. Preserve originals in `assets/raw/`; produce versioned derivatives in `assets/production/`. Use `asset request record/reconcile/inspect` to preserve a generation request before any authorized external submission, then its actual returned image and selected take in `plans/generation-ledger.json`. A timeout is uncertain: reconcile existing results before any new charged request. Missing output, timeout, and confirmed provider failure are different states.

Inspect a named prior film's actual motion assets and their scene use before choosing a replacement method. Follow the workflow's flame example when the requested effect depends on changing silhouette; brightness-only cels are a different choice. Show the key poses, atlas and contextual preview, distinguishing new drawings, interpolation and holds.

For a cel sequence, lock framing, camera, lighting, palette, pivot, and stable geometry. Specify the changing shape, cell count/layout, margins, transparent-background request, and closing motion. Generate a master pose first when the object's identity is not established. Do not promise that a prompt guarantees correct alpha, frame registration, or an exact loop.

Start with `asset preflight` for decoded alpha facts and light/dark proofs. For enlarged repairs, use `asset crop/return` with explicit registration and masks; see [raster preparation](../../../docs/ASSET-PREPARATION.md). Follow the workflow's local preparation guidance, preserving raw pixels and any derived-alpha recipe.

For compound subjects, use `asset prepare init/inspect/check/edit/build/proof/place`; see [agent preparation](../../../docs/AGENT-PREPARATION.md). Bind parts to the canonical plan element/inventory part and every intended saved view. Follow [whole-object ownership and proof](../../../docs/LAYER-AND-LIGHT-PLANNING.md#whole-object-ownership-and-proof): prepare the complete subject before its animated subparts, clear its whole footprint from other layers, and preserve separate surroundings/occluders. Inspect the whole subject isolated and hidden, then internal rest/extreme rasters and actual full-speed playback. Missing body or backing remains required work; a local occlusion patch is not the complete object.

Retain unlit geometry and separate illumination where needed. Preserve exact source mappings, masks and sockets. Register against one pivot and sequence scale; independent fitting must not erase intentional flame/smoke deformation.

Use `asset build/inspect/proof/admit` for the existing compiler and immutable packs; the [workbench guide](../../../docs/RIG-WORKBENCH.md) covers pivot/landmark choices. Inspect contacts, edges, registration and playback in context. Record warnings and visual observations separately from integrity checks; admission is catalog availability, not artistic approval. Update inventory evidence and run `plan check`.

Close `assets` only with the production files, catalog/recipes, actual inspection reports, and visual observations. A pretty atlas image with opaque checkerboard squares is not a ready alpha asset.
