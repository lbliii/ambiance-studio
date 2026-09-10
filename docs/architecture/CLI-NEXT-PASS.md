# Next tooling pass: reliable revisions and easier layered assembly

Status: **implemented in 0.6.0**, 2026-09-10. This document preserves the design rationale and acceptance targets. The [command reference](../CLI.md) and linked contracts describe the exact shipped schemas; the [implementation handoff](CLI-V06-HANDOFF.md) records validation and remaining boundaries.

This plan follows the local museum adoption audit at `projects/the-midnight-collection/reports/retrospective/cli-adoption-audit-20260910/audit.md`. That project-owned evidence is not distributed with the studio package; the demonstrated problems are summarized below. The audit identifies its frozen scene/catalog and distinguishes saved command receipts from inference. The museum agent is continuing production, so these observations justify engineering fixtures; they do not describe every later project revision.

The CLI is already useful for asset preparation, scene transactions, sprite timing and real rendering. The next pass should make a layered scene easier to assemble and make it clear which picture, soundtrack and review belong together. Keep the shared compiler, evaluator, renderer and review criteria. Extend their adapters where the production trial exposed repeated work.

## Scope and delivery order

| Slice | User-visible result | Implementation boundary |
| --- | --- | --- |
| 1. Correct timing reports | Rat gait reports identify their actual cel tracks instead of reporting the unused fallback clock | A small reporting fix, suitable for 0.5.1 |
| 2. Revision and evidence binding | Working v5 and reviewed/exported v4 can coexist without confusing their evidence | Primary correctness work for 0.6; explicit capture, typed dependencies, review subjects and handoff |
| 3. Source placement and reparenting | Import prepared parts in reference coordinates and attach the accepted gesture without reconstructing its placement | Shared scene transactions and compiler registration metadata |
| 4. Asset and rig inspection | Inspect transparency facts, return enlarged repairs to their source position, and compare rest/lift/hidden-part proofs | Reuse the existing asset compiler and raster proof renderer |
| 5. Picture reuse and precise contacts | Make two soundtrack editions from one encoded picture and inspect the actual requested action frames | Public adapter over existing macOS composition/decode support |

Land and verify each slice independently. Slices 2–3 form the core 0.6 milestone; slices 4–5 can follow independently if they would delay that milestone. Do not make a broader audio processor or provider queue a prerequisite. No production migration or museum artwork changes are part of implementing these features.

## 1. Report the timing that actually runs

**Observed problem:** `kit.py` divides atlas frame count by `cycle_seconds` even when `tracks.cell` overrides that clock. The audit's eight-cel rats report 0.333 cel fps although their authored active gait schedules run at 10 and 15 cel selections per second.

Add `scene timing [--layer ID --out FILE]` and use the same timing summary in `project check`. Compute sampled behavior through the shared JavaScript evaluator. Python must not acquire another implementation of track, wrapping or inherited visibility rules.

The report identifies:

- `timing_driver`: `cycle`, `cell_track` or `static`, plus separately labeled fallback cycle/phase.
- Authored cel changes and holds over one picture loop. Consecutive keys selecting the same cel are a hold, not a new pose.
- Cel selections at the export clock, including transitions too fast to appear in the encoded film. Report intervals/rate segments rather than forcing a variable schedule into one average fps.
- Effective visibility windows after parent inheritance, zero-opacity intervals, and hidden resets at the join. These describe evaluator state; they do not establish visibility through painted occluders or identify distinct-looking artwork.

Keep the outer JSON envelope stable. Version the timing payload. Retain legacy `cycles[].seconds` as documented fallback information; set `cel_fps` to null for overridden clocks and add the new driver/summary fields. Automatic cycles retain their existing numeric result. Document this correction for consumers.

**Acceptance:** independent fixtures cover automatic cycling, explicit 10/15-rate schedules, variable holds, repeated cel values, inherited visibility, fractional key times and a hidden seam reset. The scene file and sampled output remain unchanged. The rate report distinguishes authored events from frame-quantized presentation.

## 2. Bind reviews to explicit revisions

**Observed problem:** actual audio and movies live under revision directories while legacy gates watch `audio/masters`, `audio/stems` and `deliverables/final`. Hashing a README does not verify the WAV/MP4 it describes. Also, release review currently requires a `deliverables/final/` path rather than recognizing a selected edition by identity.

### Revision contract

Introduce `ambiance_studio/revisions.py` and a versioned selection/manifest contract. A selection lists the intended brief/inventory, scene, catalog, sound plan, optional executable audio session and selected existing masters. Missing later-stage products are allowed and remain incomplete; capture is not a passed gate.

Proposed interfaces:

```text
revision capture ID --selection FILE [--dry-run --expect-selection-sha256 HASH]
revision inspect ID
revision check ID [--out FILE]
revision compare ID --working [--out FILE]
render frame|proof|video --revision ID ...
review draft GATE --revision ID [--edition ID] --out FILE
review record FILE
revision handoff ID [--edition ID] --out DIR
```

`capture` resolves and prints a dependency plan in dry run. Its selection digest covers both the declaration and resolved input identities, so a changed input invalidates a later apply. Capture validates under the project lock, copies mutable control documents into a fresh `revisions/ID/` directory, verifies inputs again, then promotes the complete directory atomically. IDs cannot be overwritten. Selected binary assets, original sources and existing masters are pinned by exact project-relative path, byte count and SHA-256; no mutable hard links or broad directory watches are used as substitutes for identity.

A normalized runtime catalog contains only assets used by the captured scene; preserve the original catalog identity as provenance. Resolve catalog, recipe and session paths using their existing contracts, then record their project-relative targets. The scene's values and cel registration do not change during capture. Rendering from a revision reads its captured documents and verified dependencies, with no fallback to the working scene.

Later rendering/composition creates a fresh **edition receipt** linked to the revision and the actual selected picture/master/output hashes. It does not append outputs to or rewrite the frozen revision manifest. An edition may explicitly select a separately prepared immutable audio run. The receipt must include that run's dependency closure; it cannot silently substitute it for the revision's declared audio. Review drafts identify that exact edition when audiovisual evidence is required.

### Explicit dependency closure

Use registered readers for known contracts, not a generic recursive search through arbitrary JSON or Markdown. Each dependency records its role, path, hash, owning section and reason it was included.

| Section | Files that must be verified |
| --- | --- |
| Intent/layout | Captured settings, reference, brief, layer plan and selected inventory |
| Assets/picture | Captured scene, used catalog records, decoded image files, compiled pack records, recipes, registration files and declared original/prepared sources |
| Sound | Captured sound plan/source ledger, selected session, explicitly selected sources, and chosen run/master/stems |
| Edition | Encoded picture input, selected PCM and its sound dependencies, output movie, technical verification evidence and render/composition recipe |
| Review | Exact evidence files, the applicable section dependencies, upstream review receipt identities, criterion configuration and cited feedback |

Reuse existing asset/audio integrity checks. For a custom preparation script, require explicit source/output/recipe references; mark unsupported processing as externally prepared. A descriptive report alone cannot establish its dependency closure or reproducibility. Unknown required contract versions fail with an actionable message.

### Freshness, status and migration

Keep distinct concepts: **working changes**, **revision integrity**, **review verdict**, and **edition readiness**. `project status` lists them separately. Recording a positive observation does not turn an unperformed phone or listening check into a pass.

Changing the working scene after capture is normal divergence; the captured revision still describes its old picture. Changing the captured scene or a pinned atlas/WAV/movie makes affected evidence stale. A new, unselected draft does neither. Section-specific dependencies keep an independent sound-source review current when only picture assets change; existing downstream gate dependencies still apply. Manifest tampering invalidates the revision itself.

Revision reviews use a version-2 receipt in a separate revision/edition namespace with preserved history. The receipt identifies the revision/edition, dependency policy version, applicable section digests and exact evidence. Extend the existing review validator in `studio.py`; do not create a second review rules engine. Replace the final-directory prefix assumption with exact edition membership for revision-aware human evidence. Store gate criteria and dependency configuration snapshots so editing the working pipeline cannot silently redefine an old review. The revision dependency policy replaces legacy folder watches only for these new receipts. An explicit re-review can adopt new criteria.

Legacy projects continue using their existing path-watch semantics and are labeled accordingly. Do not auto-upgrade old receipts, infer reviewed filenames, copy pass verdicts into a new revision, or rewrite `handoff.md`. Adoption is an explicit capture plus newly recorded review evidence; existing feedback can be cited when its exact subject and criterion match. `revision handoff` writes a new report with exact products, readiness, working divergence and outstanding checks. It never publishes or changes a verdict.

**Acceptance:** changing a pinned WAV/MP4/atlas while its README stays unchanged produces a stale reason naming that file and its dependent gates. A captured scene edit is detected; a working-scene edit is shown as divergence. Rejected draft additions do not affect the selected edition. Two audio editions share picture identity but have separate mix/export evidence. Missing sources, path escapes, changed inputs during capture and existing IDs fail without partial promotion. Legacy receipts remain readable and byte-identical. A historical pass cannot be attributed to a new edition by selecting it.

## 3. Place and reparent parts in source coordinates

**Observed problem:** project helpers repeatedly compensate for a 941×1672 reference, a 945×1676 padded plate, the base scale and socket coordinates. Generalize the calculation, not those particular dimensions.

Add a versioned placement manifest, compiler registration mapping, and two operations to `scene apply`:

```text
place_from_source: asset, new layer ID, mapping, reference layer/socket, anchor, paint-order placement
reparent: child, parent, socket, preserve=world_at_time, at_seconds
```

A convenience `scene place FILE` / `scene reparent ... --keep-world --at N` must use the same operations, lock, stale-scene check, candidate validation and history. Dry run shows the resulting placement, transformed corners, inherited properties and any field changes.

The placement mapping records source-image hash/dimensions, crop rectangle, any resize/return transform, raw-cel registration, compiler scale/padding, full cell dimensions and chosen source-space anchor. Native cutouts can derive physical size from this chain. Generated sprites need an explicit intended source-space size and anchor; atlas size or alpha bounds cannot tell us how large a rat should be in the scene. Reject missing mappings instead of guessing. Edited artwork is not assumed to retain landmark positions merely because its dimensions match.

The JavaScript bridge composes these transforms using the same matrices and socket evaluation as rendering. Account for canvas aspect ratio and parent/group/camera transforms. Preserve explicit paint order: parenting a mummy to a casket must not move it in front of the casket rim or move the fixed glass with it.

For reparenting, `--at` means an exact reference pose. Solve the new local transform using the inverse parent/socket transform and verify resulting world corners. Keep cell timing and per-cel sockets. A new animated parent deliberately changes later movement; no whole-animation preservation is promised. Reject child transform tracks in this slice; do not silently delete or rewrite them. Resolve existing sinusoidal motion at the chosen time when solving base fields, using an exported evaluator helper, and report its subsequent parent-local interpretation. The audit's accepted mummy hand and eye layers have neither transform tracks nor additive motion, so this scope covers that concrete use case.

Do not silently change effective visibility or opacity at the reference pose. Preserve them where representable, otherwise fail with the conflicting inheritance identified. Reject singular/unrepresentable transforms and attachment cycles. Do not clamp scale/opacity into a different pose. Full trajectory baking, arbitrary shear and dynamic reparenting remain outside this slice.

**Acceptance:** independent padded/scaled crop fixtures align in portrait and landscape canvases; malformed mappings fail. Reparenting a static or supported moving gesture preserves reference-pose corners and a raster composite within declared tolerance. A nested lift is applied once; fixed glass stays fixed; front-rim paint order stays unchanged. Cel timing remains identical. Unsupported child tracks and impossible opacity/visibility preservation fail without saving. Also inspect a short browser proof from the actual transaction output.

## 4. Reuse the recurring inspection operations

Deliver three focused helpers, each writing a fresh artifact directory and binding exact input hashes:

1. **`asset preflight SOURCE`:** decoded format, dimensions, channel mode, alpha presence/range, transparent-pixel counts and light/dark previews. An RGB painted checkerboard is not transparency. Describe measured facts; neither checkerboard heuristics nor an alpha channel certify a clean matte.
2. **Crop/return recipe:** `asset crop SOURCE --recipe FILE --out DIR` and `asset return EDIT --mapping FILE --out DIR`. Preserve native crop coordinates, exported scale, returned dimensions, explicit registration correction and blend mask. Produce a derivative plus placement mapping, never overwrite the source or call a generation provider. A return with unexpected geometry requires an updated mapping. Reuse the compiler for subsequent registration/packing.
3. **`render rig-proof FILE --out DIR`:** a declarative matrix of explicit times and layer overrides for rest, maximum lift, body hidden, fixed glass hidden and an accepted-gesture comparison. Reuse `drawScene` and proof playback; force disabled variants to stay disabled even when a visibility track exists. Preserve the canonical scene. Show which descendants were hidden, so a blank composite is not mistaken for a clean backing proof.

The rig proof should show full portrait context, detail crops, side-by-side comparisons and optional pixel differences. Overrides and comparison regions are saved in the recipe. A residual mummy painted into the rear plate remains an image for review; a matrix check cannot declare it absent. Bind the proof to the existing inventory part IDs rather than introducing another object inventory.

**Acceptance:** RGB/opaque-RGBA/real-alpha fixtures report different facts; a crop round trip restores coordinates within explicit sampling tolerance; a lost-registration return fails. A synthetic contaminated backing is visibly exposed by the hidden-body proof. Variant renders do not change the source scene, and reports distinguish selected samples from a full-loop check.

## 5. Reuse encoded picture and request exact action contacts

Add `media compose PICTURE --audio PCM --repeats N --out DIR`, plus repeatable `media verify --contact-time SECONDS` and `--contact-frame INDEX`. Composition records frozen input identities, backend/tool versions, recipe and output identity, then automatically verifies the complete encoded result. Expose it in `doctor` only when the backend exists.

Support the current proven boundary: CFR H.264 picture, selected stereo 48 kHz PCM with the exact final duration, and the macOS backend. Explicitly reject unsupported streams, wrong durations and missing audio. Reuse compressed picture samples; do not run the raster renderer or encode the picture again. Ignore an input movie's audio only as the documented replacement behavior of `--audio`; report selected input/output tracks. Integrate resulting edition receipts with slice 2.

Requested contact times use the displayed frame containing the timestamp: for supported CFR media, `floor(t × fps)` with a documented numeric boundary tolerance. Valid time range is `[0, duration)`; valid indices are `0..N−1`. Report requested time, actual frame index, presentation timestamp and image hash. Keep the standard seam contacts in addition to requested contacts. An out-of-range request fails rather than being silently clamped. VFR contact selection remains unsupported in this pass.

**Acceptance:** two audio editions preserve the compressed video sample payload sequence, including repeats; compare elementary sample hashes rather than whole-container bytes. Decode verifies dimensions, frame count, timing, AAC presentation length and joins. Requests such as 3.67 and 18.13 seconds map to documented frames. Wrong durations, source changes during processing and occupied output directories fail. Native tests run with actual macOS media-service access; an unavailable or sandbox-blocked backend is reported as untested/failed, not passed.

## Integration, guidance and proof of usefulness

One owner integrates CLI parsing, project locking, revision selection and review changes. Timing/placement can be developed in the shared JS bridge alongside revision work; media composition can be developed independently behind its module interface. Rig proofs depend on the placement contract. Keep tests and fixtures independent of the active museum's mutable files.

New manifest references are project-relative. Explicit command input/output paths retain the existing shell-relative convention. Return `resolved_path` and `path_base` in new path-bearing results and clarify invalid-path errors; do not silently reinterpret existing command arguments. Preserve nonzero failures, immutable artifact directories and the outer JSON envelope.

For each implemented slice, update its contract, a small runnable example and only the relevant stage guidance. Teach agents to inspect timing driver, capture/select a revision, place with recorded mappings and request a rig proof when actions expose overlaps. Avoid adding a new approval step or requiring every quiet prop to become a sprite. Update `AGENTS.md` only where the demonstrated failure calls for a general rule.

Run the focused regression suites as each slice lands, then `./ambiance test`. Shared review changes require `tests/test_studio.py`; compiler/registration changes require `tests/test_assets.py`; attachment/render changes require Node rig/track checks and an actual browser inspection. Native composition changes require the native-enabled integration checks. Package/link audit remains part of the release check.

Finish with an independent operator pilot in an isolated fixture: assemble a compound object, reparent an animated gesture, expose a backing defect, capture a revision, create two audio editions, then change a selected dependency. A successful pilot needs no project-specific coordinate formulas or direct native-binary invocation, reports actual timing, and identifies exactly which evidence became stale. Record remaining workarounds rather than declaring success from test counts alone.

## Deferred follow-up

The audio preparation script's fixed output names warrant a later fresh-run preparation adapter with source/processor hashes and event annotations retained through stem import. Distance EQ/convolution and picture/audio event comparison can follow when a film needs them. The accepted museum soundtrack does not justify rebuilding its audio now.

Also defer provider jobs/queues, automatic decomposition, full animation rebaking, reusable rig package migration, cross-platform video backends and a historical Last Lantern effect port. Keep those on the broader roadmap; they are not prerequisites for correcting the concrete problems above.
