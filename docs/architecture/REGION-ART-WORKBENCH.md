# Region art workbench

Status: first-release implementation completed September 11, 2026; see the [executable contract](../ART-REGIONS.md) and [handoff](REGION-ART-HANDOFF.md). This document records the design and milestone criteria. The first release prepares and returns still artwork for a traced region; it also records the space required by planned motion.

## Intended result

Given a painting, the agent can outline an irregular window, choose what to illustrate inside it, calculate an appropriate rectangular generation frame and resolution, export the references, and bring returned art back into that exact opening. The human can inspect or adjust the same shape and framing on localhost. The complete production operation works through saved recipes and CLI commands without browser interaction.

The visible opening, required paint coverage, and rectangular reference frame are different things. Squaring the reference adds space; it never stretches the painting. Generation supplies artwork, while a local mask controls its exact visible boundary. An image prompt is guidance, not a geometric guarantee.

## Existing foundation and gaps

| Existing implementation | Reuse | Addition needed |
| --- | --- | --- |
| `ambiance_studio/asset_prep.py` | Decoding, image identities, affine math, premultiplied resampling, crop/return inspection | Uniform fit and padding, region packet, explicit sizing, high-resolution mapped return |
| `ambiance_studio/preparation.py` | Ordered additive/subtractive polygons and imported grayscale masks | Shared mask helpers callable without an already-generated backing image |
| `editor/preparation-workbench.mjs` and `.html` | Source inspection and polygon interaction | Region editing, box/aspect controls, dimensional readout and generation-frame preview |
| `ambiance_studio/preparation_server.py` | Verified snapshots and bounded in-memory draft evaluation | Region draft endpoint using the same evaluator as CLI builds |
| `editor/engine.mjs`, `editor/views.mjs`, `editor/source-placement.mjs` | Actual scene transforms, output projections and mapped placement | Measurement of a region's output pixel demand through those transforms |
| Compiler, scene transactions and revision dependencies | Stable registration, restorable placement and dependency validation | Typed region provenance covering padded exports and returned paint |
| `asset request record/reconcile/inspect` | Durable request and returned-file identities | Export a compatible request draft and preserve its relationship to the region packet |

Current crop recipes accept only rectangles inside the original image. They can resize the two axes independently. Current `asset return` deliberately makes a patch at native crop resolution. Neither behavior should silently change. A padded generation frame and a high-resolution region asset need an explicit new contract that composes the underlying helpers.

Current revision traversal also assumes that a structured source-mapping registration refers to a legacy crop manifest. Extend its typed dependency handling; do not disguise a padded region packet as a legacy crop manifest or omit its provenance.

## First-release experience

1. Open an existing source and name the region, for example `north-window`.
2. Draw a rectangle or trace an opening with a polygon. Add separate polygons for disconnected panes and subtract mullions or other protected details. The agent can author the same coordinates directly.
3. Describe the intended paint. Keep the window frame and other foreground objects explicit. Choose a tight, square, or custom-aspect reference frame; adjust context padding and any required hidden paint separately.
4. Inspect the full painting with overlays, the clean generation reference, the shape on contrasting backgrounds, and the suggested pixel dimensions. When scene-bound, show the region at the actual size of each intended output.
5. Build a versioned packet with references, masks, mappings, sizing rationale and a prompt/request draft. This works before replacement paint exists.
6. After an independently authorized generation or selection of existing artwork, inspect the returned file, author its alignment, and build a mapped asset plus a contextual comparison.
7. Compile and place the selected asset through the existing commands, then inspect its edges and framing in the intended views.

The browser offers rectangle draw/resize, aspect lock, zoom/pan, polygon add/subtract, vertex correction, undo and overlays. Its controls use plain labels: **Visible shape**, **Extra paint**, **Reference frame**, **Image size**, and **Preview in painting**. Show an annotated guide separately from the clean reference so guide strokes cannot accidentally become paint in the final asset.

## Saved contract

Introduce `ambiance-art-region` version 1 with project-relative references. Initialization pins the actual source hash and dimensions. Edits publish fresh checkpoints, preserving their parent recipe and applied batch.

| Field group | Meaning |
| --- | --- |
| Identity | Region ID/title, source image identity, format/version/path base |
| Intent | Intended asset role, plain-language paint brief, preserved details, optional production-plan/inventory binding |
| `visible_mask` | The final still-image aperture; existing ordered add/subtract polygons and optional full-source grayscale mask |
| `paint_coverage` | Required artwork bounds: visible mask plus explicit per-side bleed or an authored reveal envelope; never inferred from reference padding |
| `frame` | Tight/square/custom ratio, context padding in source pixels, optional explicit frame rectangle, and uniform contain fit |
| `sizing` | Scene-bound or manual demand, quality multiplier, optional explicit dimensions or allowed output sizes, and a recorded limit policy |
| `context` | Optional scene/catalog identities, mapped reference base layer, intended views and evaluated time range |
| Raster policy | Explicit mask rasterization/edge settings and image resampling; exported derivatives record the effective settings |

Use one source coordinate system. Polygon vertices retain the existing pixel-center convention. Rectangles use half-open pixel-edge bounds. Put conversions in shared helpers and test them at borders; never copy browser display coordinates into the recipe as source pixels.

The visible mask may contain holes and disconnected regions. Preserve imported soft alpha. Do not apply automatic feathering, dilation, or segmentation to a user's traced boundary. Additional paint coverage can expand without changing the final aperture.

Frame geometry is derived and displayed before building. An explicit frame that clips required paint is a validation error. Context padding may be reduced only through an explicit edit. When an aspect expansion crosses the source edge, export a uniformly mapped, padded reference and a separate source-availability mask. Missing reference pixels are labeled as missing, never stretched or represented as reconstructed art. First-release visible/reveal requirements stay inside the source canvas; expanded-stage outpainting is separate work.

Keep draft initialization possible with an empty mask. `inspect` reports the incomplete shape; `check` and `build` require a nonempty valid region. Reject unknown fields, unsupported versions, nonfinite geometry, degenerate polygons, invalid paths and incompatible image identities. Use preparation's existing bounded polygon limits. Start with its source pixel budget and the compound/compiler-compatible 4092-pixel side ceiling; report resource limits explicitly rather than silently reducing quality.

## Sizing and aspect policy

The report distinguishes four quantities: source-space region size, required paint coverage, reference frame size, and requested output pixels. Increasing reference context must not reduce the subject's intended detail.

For scene-bound sizing:

1. Resolve the source-to-layer mapping from the recorded compiler/base mapping.
2. Use the shared scene sampler and view projection to obtain source-to-output transforms at every output-frame time in the declared interval, for every intended view.
3. Measure the largest directional scale of each transform's linear part. Its largest singular value gives a conservative uniform pixel density; a rotated bounding-box width alone does not.
4. Let `d` be the maximum measured output pixels per source pixel. Request at least `d × quality_multiplier` pixels per source pixel across the entire generation frame. Start with an explicit default multiplier of 1.5, exposed as adjustable headroom rather than an artistic guarantee.
5. Choose the smallest supplied allowed size that meets the density while containing the frame uniformly. Extra aspect space becomes padding. If no allowed size meets demand, report the shortfall and require an explicit size/demand change before marking the packet ready.

For an unbound region, accept manual intended display dimensions; label them as assumptions. Initialization may suggest native density, but cannot claim it is sufficient for an unspecified final use. Bound production regions must account for every intended view. Report maximum demand, which view/time caused it, whether the region intersects each view, and the actual sampled interval. Do not claim coverage beyond that interval or ignore density just because a region is partly occluded.

An optional allowed-size list represents capabilities supplied by the caller after verification. Without one, report ideal dimensions and mark provider compatibility as unchecked. Do not hardcode a provider's current size menu into the region contract. If provider aspect differs, enlarge/pad the mapped frame without stretching or cropping its required coverage.

Record bleed and motion needs separately from resolution. For the first release, reveal envelopes are authored inputs, with their origin and units recorded. Scene transform sampling measures display demand; it does not infer the hidden geometry of an opening door or rotating object. Compiler padding and any later scale reduction also appear in the final density report.

## Generation packet

`build` writes a fresh, receipt-verified directory containing:

- Source/recipe snapshots and `region-manifest.json` with exact identities and forward/inverse coordinate mappings.
- A clean `reference.png`, separate `guide.png`, and `source-availability.png` for any padded reference area.
- Native and export-space visible/coverage masks, with labels describing their coordinate spaces and purposes.
- `sizing.json`, compact `report.json`, a full-context preview and an isolated shape preview.
- `prompt.md` containing the supplied paint brief and preserved-context requirements, plus a compatible `request-draft.json`.
- `return-template.json` with expected returned dimensions and an unset registration transform.

The request draft lists actual image references only. It can be passed to the existing generation ledger once the agent supplies the prompt and actual tool settings. Packet building never submits a request or creates a paid job. Prompt-guided and mask-capable generation routes can both consume the packet through their supported interfaces; local compositing remains responsible for the final aperture. Record which references were actually supplied.

Use the existing request ledger for returned candidates and uncertain outcomes. Keep the packet, request ID, chosen returned-file hash and final region derivative linked. Reopening a packet must find its existing result before any further generation is considered.

## Return, resolution and placement

`return` accepts the packet, actual returned file and an explicit registration recipe. It decodes the file, checks its dimensions/identity, and produces an alignment comparison. Equal image dimensions never imply correct alignment. Scale/translation/rotation remain explicit; perspective correction and learned registration are follow-up work.

Retain a high-resolution registered paint derivative and mask in the canonical export frame. Preserve the returned original separately. Compose `edit → export → source` mappings rather than shrinking the production asset back to native crop dimensions. Transform and rasterize polygon masks at the target grid through the shared helper; imported raster masks retain their measured source detail. Use explicit, bounded supersampling for a region's vector-edge raster policy, while preserving the legacy preparation raster behavior unchanged.

Produce a static aperture-clipped `patch.png`, a registered uncut `paint.png` with its coverage mask, a native-size contextual `composite.png`, edge previews, and a compiler recipe. The composite is an inspection derivative; the mapped high-resolution patch is the still-image production input. Pixels outside the effective aperture remain identical in the decoded native composite. The tool must expose transparent/uncovered return pixels inside required paint, not conceal them by showing only the original underneath.

Add a typed region receipt to compiler/revision provenance, following the existing preparation/edge receipt patterns. Validate the source, packet, masks, registration recipe, returned original and production outputs. Share the dependency walker across admission, revision capture and packaging. A changed shape, scene/view used for sizing, or returned file requires an explicit new derivative or refreshed sizing; it never silently redefines an old packet.

Use the existing `asset build/admit` and source-placement transaction for production. Preserve anchor, scale, base relationship and paint order. The workbench does not automatically replace a complete source layer or declare production approval.

For scenery moving behind a fixed window, the aperture must stay fixed and the paint must remain independent. The uncut paint and masks support a subsequent compound/occluder setup. A still patch moving with a baked alpha mask is not evidence of correct window clipping. First-release completion covers a static insert; animated assembly must use an existing explicit foreground/occluder arrangement and its own motion proofs, or be recorded as follow-up renderer work if that arrangement is insufficient.

## CLI surface

These routes are implemented; exact arguments and limitations are documented in the executable contract.

```sh
./ambiance --project PROJECT asset region init SOURCE --id north-window --out DRAFT
./ambiance --project PROJECT asset region inspect DRAFT
./ambiance --project PROJECT asset region edit DRAFT --batch EDITS --expect-sha256 HASH --out NEXT
./ambiance --project PROJECT asset region check NEXT
./ambiance --project PROJECT asset region build NEXT --out PACKET
./ambiance --project PROJECT asset region return PACKET RETURNED --recipe ALIGNMENT --out RESULT
./ambiance preview --region PACKET
```

Keep bounded edit operations at the level of `set-visible-mask`, `append-polygon`, `set-coverage`, `set-frame`, `set-sizing`, `set-context` and `set-intent`. A batch validates as a whole and publishes one new checkpoint. Direct recipe authoring uses the same validator. Avoid a command per mouse gesture.

`inspect` returns identities, bounds, unresolved inputs, sizing summary and exact preview paths. `check` gives structured issues and nonzero failure for an incomplete or invalid build contract. `build` publishes complete immutable outputs with a verified receipt. `return` records alignment and actual output density, with nonzero failure for invalid identity/geometry. An explicit below-target size may remain a labeled study; it cannot report that it meets production demand. Human visual review remains a separate recorded observation.

Browser previews use captured input bytes and bounded in-memory drafts. Exported JSON rebuilds through the CLI. Preserve the current source path/origin restrictions and last valid preview on a rejected edit. No browser edit is required to complete the agent path.

## Implementation milestones

| Order | Deliverable | Exit evidence |
| --- | --- | --- |
| 1. Region contract and geometry | Shared mask helpers; init/inspect/edit/check; rectangle/polygon regions; coverage, aspect expansion and padded mapping | CLI fixtures show square and concave regions with holes, correct edge coordinates and source preservation |
| 2. Sizing and packet | Manual and scene-bound sizing; all intended views; source-availability masks; build, previews and request draft | A rotated/magnified dual-view fixture yields correct conservative density; changing context does not reduce subject detail |
| 3. Registered high-resolution return | Explicit return alignment, aperture and coverage products, typed provenance, compiler and placement compatibility | Existing local art returns at higher density, preserves the window border, compiles and places without hand-reconstructing coordinates |
| 4. Visual workbench | Region overlay, rectangle/aspect controls, vertex editing, undo, sizing readout and source/return comparison | Browser edits and CLI rebuild produce the same mask/mapping outputs; draft failure preserves the last valid result |
| 5. Independent pilot and handoff | One irregular painted window plus a different non-window region; saved public-command replay and actual visual inspection | Complete agent-operated preparation/return/placement path, legible browser observation, full-resolution edge inspection and all intended-view proofs |

Milestones 1–3 establish the useful agent capability. Milestone 4 makes it convenient to observe and adjust. Milestone 5 is required before calling the whole tool complete. Use existing cleared art for engineering tests and available local paint for the pilot; generation can be separately authorized if the pilot requires it. A synthetic fixture establishes behavior, not painted integration or time savings.

Likely implementation homes: new `ambiance_studio/art_regions.py` and command adapter; a small shared mask module extracted from `preparation.py`; a measurement helper beside the current JS source/view operations; thin additions to `assets.py` and `cli.py`; a region page/server reusing preparation patterns; focused compiler/revision dependency extensions. Preserve existing crop/return and preparation recipes and tests. Add public contract/usage docs and the capability-index entry only when each route is executable.

## Verification and completion

Meaningful regression cases:

- Non-square source into a square request: known circles/landmarks remain undistorted and round-trip to their source coordinates.
- Concave opening, disconnected panes, subtractive mullions, one-pixel border contact and imported soft alpha.
- Reference frame extending past a source edge: availability mask and mapping are correct, with no fabricated reference paint.
- Scene/view zoom, rotation, inherited scale and different output sizes: density follows the actual shared transforms and all declared frame times.
- Returned shift or changed dimensions: missing registration fails; an explicit correction restores intended placement.
- Higher-resolution return survives compiler packing and mapped placement; measured final density detects any compiler reduction.
- Required coverage contains transparent or missing paint: diagnostic remains visible even when the composite would hide it.
- Changed source, mask, scene/view, packet or return; output collisions; failed/interrupted writes; reopen and ledger reconciliation.
- Real browser draft followed by CLI rebuild: identical recipe/raster semantics, with guide overlays absent from exported artwork.

Run focused preparation/crop/compound, view and CLI regressions as affected. Registration/compiler work requires `python3 tests/test_assets.py` and `node tests/test-rig.mjs`. Shared changes require `./ambiance test`, including the package audit, and the existing editor checks when its behavior changes. Test actual pixels in addition to matrices. New provenance must survive capture and package round trips and reject changed dependencies.

The pilot handoff identifies the source, packet, return and exact placed result; presents before/after and edge details at intended size; records visual findings in every requested composition; and reports correction steps, undocumented workarounds and agent/UI effort separately. If a movie is produced, register and explicitly present its current review delivery using the existing library workflow.

Completion means the agent can trace the region, anticipate the required canvas and resolution, prepare a reviewable generation packet, and return usable artwork without guessing placement or writing project-specific image scripts. Automatic object selection, Bezier/freehand tools, perspective warping, provider queues, expanded-stage outpainting and a new animated clipping engine are later extensions, not prerequisites for this first release.
