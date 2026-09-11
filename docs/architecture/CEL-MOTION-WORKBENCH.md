# Cel motion workbench — implementation plan

Implementation update: the first release is available; see [CLI usage](../CEL-MOTION.md) and [validation handoff](CEL-MOTION-HANDOFF.md). Milestones 4–6 remain planned.

Status: planned September 11, 2026; no production commands or runtime changes implemented by this document. Scope follows the user's request to plan landmark authoring, constrained stabilization, localized jitter diagnostics, synchronized correction previews, and improved motion continuity. Cloud deformation is a later experimental extension.

Revised after the September 11 [web research and agent operation review](CEL-MOTION-RESEARCH.md). The first release now includes source/scene-driven initialization, compact observation packets, validated batch edits and bounded classical point propagation. Learned tracking stays later. Propagation proposes observations; it does not decide which artistic motion should be removed.

## Outcome and first delivery

An agent can describe which painted features should remain steady, inspect measured departures from that intention, build a bounded correction, and compare actual original/corrected playback. The human can observe the same work and optionally edit its landmarks. Each result identifies its sources, recipe, correction and viewing conditions.

The first delivery completes multiple landmarks and stable regions, localized diagnostics, translation-only correction through the existing compiler, synchronized comparison, and an isolated scene proof using the production clock. Establish the manual path first, then include bounded classical propagation before the operational pilot so an agent need not re-enter every point. Propagation remains an optional capability with manual fallback. Scene contact rules and continuous motion curves follow; cloud deformation receives a separate experiment after those foundations are demonstrated.

Use existing art and local fixtures for implementation. The current museum project records its cat statue as future work; it is a prospective example, not an existing animated-cat benchmark. Existing flame/creature sequences provide production material where suitable. This plan does not require a new generation or a change to a selected movie.

## Existing capabilities and integration points

| Existing component | Reuse | Gap this plan fills |
| --- | --- | --- |
| `tools/asset_tool.py` | Fixed/landmark/bottom-center registration, one sequence scale, premultiplied resampling, mappings and immutable packs | Multiple constraints, bounded correction at fixed geometry, explicit correction provenance |
| `ambiance_studio/assets.py` | Pack integrity, raw/prepared cel inspection, onion skins, playback and named landmark export | Multiple editable landmarks, regional diagnostics and synchronized correction playback |
| `ambiance_studio/edge_quality.py` | Isolated cel resizing, light/dark proofs, dependency validation patterns and exclusive artifact publication | Temporal measurements after accounting for declared motion |
| `editor/engine.mjs`, `editor/timing.mjs` | Absolute-time sampling, authored holds, per-cel sockets and actual scene timing | Continuous-through-key curves and contact/velocity diagnostics |
| Scene authoring, rendering and revisions | Validated transactions, real scene proofs, pinned source dependencies | Candidate comparison, corrected attachment/mask handling and typed motion provenance |
| Preparation preview server | Bounded local calculations over captured inputs | Optional landmark editing and recalculated draft proofs using the same Python implementation |

Follow [CLI-first architecture](CLI-FIRST.md), [asset preparation](../ASSET-PREPARATION.md), [edge quality](../EDGE-QUALITY.md), [scene timing](../SCENE-TIMING.md), [source placement](../SOURCE-PLACEMENT.md), and [revisions](../REVISIONS.md). Extend these mechanisms rather than create another compiler, scene clock or review system. Existing landmark files and legacy scenes continue to work unchanged.

## Saved motion study

Introduce `ambiance-asset-motion`, `schema_version: 1`, stored inside the selected project, for example `assets/motion/<study>/study-v1.json`. The authored study is an input; each analysis/proposal/proof captures its exact bytes in a fresh output directory. New edits produce new study versions. A draft may contain missing observations, but commands report what remains required for a solve.

All referenced files in the study use explicit project-relative `{file, sha256}` identities. Shell command paths retain the existing shell-relative convention. Source cel identity includes source input index, exact source rectangle, ordered cel index and the verified compiler mapping. A cel is never identified only by its filename or array length.

Initialization resolves this bookkeeping from the chosen pack or scene layer. The agent edits named points, constraints and bounds rather than copying hashes and atlas offsets. Initial inspection can run before annotations are complete; it reports raw transitions and available timing without inferring which movement is wrong. Each inspection view records a stable ID and exact view-to-source affine so edits can reference the observed crop instead of requiring manual coordinate conversion.

| Field group | Required meaning |
| --- | --- |
| `baseline` | Exact pack asset, recipe, report and atlas identities; source dependencies; cel order; cell dimensions; pivot; shared scale and mapping identity |
| `landmarks` | Stable names and one observation slot per source cel: raw-cel pixel coordinates or null, visibility, manual/tracked origin, selected/proposed state, role `fit` or `check`, and fit weight where applicable |
| `constraints` | Named landmark, explicit cel set, mode `fixed` or `observe`, and reference cel for a fixed target; display-pixel tolerance for each enforced constraint |
| `regions` | Named polygons or grayscale masks in baseline full-cell pixels; selected cels; `stable`, `observe`, or `ignore` role; references for each selected cel where needed |
| `solve` | Mode `translation`; selected cels; explicitly unchanged cels; maximum displacement; reference cel fixed to zero correction; socket/companion policies |
| `view` | Required full-cell display width in output pixels; either explicit proof cadence or a pinned scene/layer binding; declared wrap versus open sequence |
| `diagnostics` | Explicit thresholds, enabled measurements, comparison reference and region scopes; initialized values are visible defaults, not inferred artistic tolerances |

Source editing uses raw-cel pixels. Prepared-image clicking and tracking map back through the verified inverse affine. Targets and corrections use baseline full-cell pixels; display measurements use a recorded scale from that cell to the requested display size. Reject missing/noninvertible mappings for source correction. Atlas-only legacy material can receive a clearly labeled inspection proof; rebuilding requires explicitly preparing a source-backed pack.

In the first delivery, `fixed` means stationary in the asset's registered local coordinates over the declared cel set. An animated nose can be `observe`, while seated paws are `fixed`. A point missing under an occlusion remains null; it does not become a guessed position. Independent fixed regions can use per-cel masks so a moving foreground part need not be compared as if it were stable.

World contact is a separate scene-time rule in milestone 5. A source cel can occur at multiple times with different parents, transforms and contacts; per-cel registration must not silently become a scene motion solver.

## Diagnostics that lead to a next action

Analyze all selected cels and actual scheduled transitions, including the last-to-first transition only when the study declares a wrap. For scene-bound studies, obtain holds, repeated cels, visibility and output samples from the shared evaluator. Standalone uniform playback is labeled with its selected cadence. An asset-local study cannot claim scene contact or occlusion correctness.

Each finding includes the cel pair, applicable scene times, region/landmark, measured value and units, declared tolerance when applicable, uncertainty, exact crop/proof paths and a suggested next operation. The default CLI response returns counts and the highest-priority findings with paths to the complete report. No frames are silently omitted from the underlying report.

Publish these results as a version-bound observation packet with direct PNG/clip paths and an optional localhost view. Include uncertain observations, a seam neighborhood and representative ordinary transitions alongside worst-ranked findings; the headline selection cannot prove that other transitions are sound. Support retrieving one finding/region and paging the complete index. A packet is usable through file/image tools without browser playback. Recorded observations identify the actual frames or clip inspected and the viewing method.

| Finding class | Measurements and interpretation |
| --- | --- |
| Constraint violation | Distance from a fixed landmark's target before/after correction; maximum and RMS residual; missing required observations. Can fail the declared technical check. |
| Shape/appearance anomaly | Pairwise landmark distances where meaningful, regional alpha coverage, outline change, premultiplied-color and alpha differences. Flags for inspection; not an automatic art failure or normalization request. |
| Tracking uncertainty | Missing/occluded points, weak/ambiguous matches and disagreement between forward/reverse/reference estimates. Report separately from motion. |
| Presentation discontinuity | Transition displacement divided by actual elapsed presentation time, cel hold changes, wrap behavior, and later world-space contact/velocity. Distinguish intentional held drawing changes from rigid movement. |

For stable regions, compare in the declared registered reference space using only explicit mappings and the proposed global correction. Preserve the uncorrected measurements alongside the corrected ones. Do not secretly align each region until its error disappears. Measure color on alpha-valid overlap, measure alpha separately, and mark insufficient overlap as unavailable. Ignore hidden RGB under zero alpha. Scale/outline/brightness measurements on deforming regions are descriptive.

Preview every finding at intended display size plus a nearest-neighbor magnification of those same output pixels. Keep light/dark comparison available and reuse edge inspection when resampling or matte damage is suspected. Report pass, violation, advisory and unavailable states separately; no universal smoothness score and no automatic quality-gate closure.

Inspect multiple frames around the join, label their actual holds and preserve movement direction. Endpoint resemblance alone can miss a reversal. This sampled evidence belongs in the first release using the current engine; analytical world-contact/velocity checks and new curves remain later. Keep an explicit inspection-only alignment mode available for comparing shapes, with its transforms excluded from correction measurements and candidate builds.

## Translation correction and compiler extension

For cel `i`, map each selected fixed source landmark with role `fit` into baseline cell coordinates. Its desired displacement is the reference target minus the observed position. Solve one weighted least-squares 2D translation from those displacements. Use only explicitly selected, visible observations; tracking scores are not automatically fit weights. Report every constraint's residual so conflicting landmarks cannot be hidden by their average. Landmarks with role `check` remain outside the solve and supply independent before/after measurements; a failed declared check stays visible even if fitted points align perfectly.

The reference cel has zero correction. Each cel solves directly against its declared reference targets, avoiding chained frame-to-frame drift. One valid fixed point can determine a translation; additional points test consistency. Missing constraints, incompatible targets, excessive correction or excessive residual leave that cel unresolved. A ready compiler recipe is emitted only when every requested cel is solved and all others are explicitly unchanged. No silently clamped correction, inferred rotation, per-cel rescaling, local warp, crossfade or in-between generation.

Extend the existing compiler with an opt-in, versioned registration-correction input and fixed-geometry mode. Preserve baseline full-cell dimensions, pivot, one shared scale, frame order and declared source rectangles. Compose the correction with the recorded raw-to-cell affine, then resample directly from the original compiler inputs once. Do not repeatedly translate a previously resampled atlas. Existing recipes without the extension retain their current behavior.

The compiler currently chooses scale from all cel extents. Re-running that automatic fit after changing landmarks could shrink the whole sequence. Fixed-geometry mode therefore must fail when corrected nonzero alpha plus required filter padding does not fit; it must not shrink or clip it. Report the additional padding required. A separately authored geometry revision can handle that case through existing placement review.

Declare each existing socket as `fixed_mount` or `follow_art`. A following socket receives the same per-cel cell-pixel translation, converted to normalized full-cell coordinates; a static socket can become a per-cel track. A mount remains fixed by intention. Layer socket overrides must be accounted for in scene-bound proofs and adoption. Source-registered object masks or emissive companions require an explicit shared correction binding; receiving shadows and fixed occluders retain their separate scene relationships. Unsupported bindings block a ready scene-adoption proposal and identify the required repair.

The proposal records the baseline, study, observations, numerical settings, per-cel translations, mappings, residuals and algorithm/runtime identities. Add a typed `motion_preparation` reference to the new compiler recipe and pack provenance. Share verification across compile/cache lookup, asset proof, scene authoring and revision capture. Rehash dependencies before atomic no-replace publication. Accepted packs, source bytes and catalog entries remain intact.

## Proposed CLI and operator workflow

All interfaces in this section are proposals. Document them as executable in `docs/CLI.md` only after implementation.

| Proposed interface | Result |
| --- | --- |
| `asset motion init PACK_OR_ID --out FILE` or `asset motion init --layer ID --out FILE` | Source-bound draft, inferred bookkeeping, source/proof references and missing artistic inputs; layer selection pins timing and bindings; the subsequent analysis can inspect this incomplete draft |
| `asset motion inspect FILE` / `asset motion check FILE` | Compact state, dependency integrity, coordinate validation, missing observations and readiness; no build |
| `asset motion edit FILE --changes BATCH --expect-study HASH --out NEW_FILE` | Validate a bounded batch of landmark/rule edits against exact study/view identities; save a new version and report affected cels/regions |
| `asset motion analyze FILE --out DIR` | Observation packet with reports, crops, contacts and exact cadence; incomplete studies receive raw transition views and explicit unavailable constraint measurements |
| `asset motion solve FILE --id NEW_ID --out DIR` | Bounded correction proposal and ready compiler recipe when solvable; explicit unresolved results otherwise |
| Existing `asset build RECIPE --out DIR` | Compile the candidate through the extended sole compiler |
| `asset motion proof FILE --candidate PACK --out DIR` | Synchronized original/candidate asset proof and, when scene-bound, an isolated contextual comparison |
| `asset motion track FILE --out DIR` | First release: bounded classical propagation with proposed observations and uncertainty; later adapters use the same result contract; an explicit new study selects observations for solving |
| `preview --motion DIR` | Optional localhost inspection and draft editing of a verified motion proof |

An agent initializes a study, authors a few points/rules as JSON or a validated batch, optionally propagates proposals, checks/analyzes them, selects useful observations, solves, builds and inspects the proof. The report points directly to failing transitions and missing inputs. It can revise and repeat without browser editing or downloading a file. Selecting observations is an operator action within the task, not a fresh human approval for every point. Avoid a command per landmark gesture; batch authoring through the saved study is the primary path.

Preserve selected observations, unresolved findings and reasons for rejecting candidates. Inspection after resumption reports differences and next work without relying on chat history. Reuse unchanged captured inputs and analyses; return affected cels/regions after edits. Separate cheap diagnosis from full contextual render/encode and expose progress for longer work. Measure cold/warm latency and output size in the pilot; do not claim an interactive latency target has been achieved without measurement.

Keep the current JSON envelope and exit-code conventions: malformed/stale input is invalid input; unavailable runtime is a runtime failure; unsatisfied requested technical checks/solves return a nonzero check result with any completed diagnostic artifacts. Advisory appearance findings alone do not fail a valid build. Output-size limits are checked before work; use the compiler's current cel/atlas bounds and bounded proof paging. An incomplete run cannot appear as a finished candidate.

Candidate adoption uses existing `asset admit` and scene transactions against an expected scene hash. Generate any necessary socket/mask updates as an explicit inspectable transaction; validate the whole candidate dependency graph before saving. Proofs can use isolated project snapshots without changing the film's working scene or selected delivery.

## Synchronized workbench

Both panes sample one absolute clock, select identical cels, and show the same scale and background. Provide pause/seek, original versus candidate, neighboring onion skins, landmark trails, region overlays and finding selection. Keep raw-source, prepared-cel and scene views labeled. Show view scale, cel index, presentation time and input/candidate identities.

An optional temporary alignment overlay supports shape comparison, following the inspection pattern described in the research review. Label it as inspection-only and retain immediate access to raw registration. View IDs carry source mappings; batch edits and browser clicks use the same conversion. Distinguish a viewed still/strip from a continuously inspected clip in recorded observations.

Editing a point or tolerance requests a bounded draft recalculation from the same Python solver/compiler used by the CLI. Update both candidate pixels and residuals; discard stale responses from earlier edits. Label an in-memory draft separately from a saved candidate. Exporting a study and rebuilding it through the CLI must reproduce the same correction and raster result on the same runtime. Do not implement a different browser-only warp.

Scene comparisons use captured scene/catalog inputs and the actual selected layer's timing, transforms, attachments, finishing and occluders through the shared renderer. Report what the asset-local proof cannot diagnose. The first release can preserve existing scene interpolation while still using its exact clock for before/after playback.

## Tracking and later capabilities

### Assisted tracking

After the manual path works, include bounded classical point/patch propagation in the first release. OpenCV supplies [point tracking and masked image-alignment primitives](https://docs.opencv.org/4.13.0/dc/d6b/group__video__track.html); their usefulness on these painted sequences must be measured. Keep a replaceable local adapter and optional, version-reported capability in `doctor`. Manual authoring and analysis remain usable without it. Learned trackers are later comparison candidates, not default dependencies; evaluate local runtime and applicable code/weight terms before adoption.

Start from manually selected reference patches, bounded search regions and stable masks. Track forward and backward with reference-pose rechecks; save match errors and ambiguity/visibility states. Stop propagation at unresolved disagreement and keep missing observations null. Do not equate a correlation score to a calibrated probability. Disappearing features, large pose changes, textureless clouds or repeated patterns may require manual observations. Proposed points remain distinguishable from selected observations. Reuse annotations on repeated source cels only with identical source identity and geometry, while preserving their distinct presentation times. Benchmark correction effort and false confident matches, including spot checks of apparently good tracks, before expanding to rotation/scale estimation or learned tracking.

### Scene contacts and continuous curves

Add scene-time landmark constraints as a separate binding: landmark, named receiving layer/socket, half-open time windows, reference contact and output-pixel tolerance. Evaluate the landmark relative to its receiving surface using the actual cel and inherited transforms. Visibility reports do not infer raster occlusion. Report contact slipping and incompatible repeated-cel requirements; changing body motion or articulated parts remains an explicit scene/asset operation.

Add opt-in cubic Hermite interpolation for continuous numeric channels, with explicit in/out tangents in channel units per second. Keep legacy linear/smoothstep/hold behavior exact and cel/visibility channels discrete. Default joined tangents are equal unless a deliberate corner is authored. Validate continuous extrema for bounded channels such as scale and opacity; reject invalid curves instead of silently clamping. Rotation uses explicit unwrapped angles; shortest-path or angular-winding semantics require their own tested contract.

Extend the shared timing/audit modules to show one-sided velocity at keys and across the loop, alongside sampled final-frame-to-first movement. Compatible closed curves match value and tangent at the join. Test inherited motion and the final rendered path, since a child-only curve report does not prove world continuity. Preserve explicit hidden resets. No alternate Python interpolation engine.

### Cloud motion experiment

Separate overall cloud travel from internal evolution. Reuse the layer transform for travel; investigate a small, authored, periodic deformation field for the painted cloud and its alpha. Limit displacement, preserve coverage and examine local reversals/foldovers. Dense flow may be used as a diagnostic proposal, not proof of correct correspondence or automatic permission to synthesize frames.

Compare an existing cel sequence, rigid travel and a bounded deformation prototype at the same display size, speed and loop length. Judge whether it preserves the painting and gives useful rolling motion before proposing a production renderer extension. No cloud solver, general mesh warp, automatic in-betweening or new generated drawing is part of the first stabilization release. Any later renderer extension must remain deterministic at arbitrary time and share browser/export behavior.

## Milestones and acceptance

| Milestone | Deliverable | Exit evidence |
| --- | --- | --- |
| 1 — Saved intent and inspection | Study schema, source/layer initialization, observation packets, multiple manual landmarks/regions and validated batch edits | An agent starts without copying hashes or converting crop coordinates; incomplete studies are inspectable; invalid/stale edits are actionable |
| 2 — Diagnosis and correction | Regional reports, independent check points, translation solve, fixed-geometry compiler extension and typed provenance | Known drift is recovered; intentional deformation survives; contradictory constraints and clipping are reported; source geometry remains explicit |
| 3 — Complete first release | Bounded classical propagation, synchronized proof, draft recalculation, seam neighborhoods, actual-cadence scene comparison and adoption transaction | Compare manual versus propagated workflows through the CLI; inspect browser and encoded contextual results separately; same-runtime rebuild agrees with draft; resume avoids repeated work |
| 4 — Broader tracking | Optional learned/backend comparisons and harder pose/occlusion cases | Held-out painted fixtures demonstrate useful effort savings over the classical baseline; confidently wrong matches and local runtime are measured |
| 5 — Scene continuity | Contact bindings, Hermite tracks and velocity/join diagnostics | Planted-contact and moving-parent fixtures, derivative/extrema tests, actual scene and encoded wrap inspection; legacy scenes unchanged |
| 6 — Cloud experiment | Existing-art comparison and bounded deformation study | Recorded visual observations and a decision whether to design a supported renderer extension |

Implementation ownership follows existing module boundaries: new focused `ambiance_studio/asset_motion.py` for studies/analysis/solve/provenance; `tools/asset_tool.py` for raster compilation; existing CLI/assets/preview adapters for access; `scene_authoring.py` and `revisions.py` for dependency and adoption validation. Add a focused viewer/server module if needed rather than enlarge the embedded legacy proof page. Scene motion changes belong in `editor/engine.mjs`, `editor/timing.mjs` and `editor/audit.mjs`. One owner records pilot reviews at a time.

## Validation fixtures and production trial

Use independent fixtures with known defects, not expected values computed by the solver being tested:

- An asymmetric seated figure with known integer/subpixel translations, two planted landmarks and an intentionally moving head/tail. Recover the shift within 0.1 baseline-cell pixel from exact manual points; preserve relative head/tail movement. Integer shifts at unit scale allow exact decoded-pixel comparison; subpixel resampling needs separately stated raster tolerances.
- Conflicting landmark displacements, a deliberately missing point and a hidden feature. The translation solve remains unresolved instead of inventing a repair.
- An independent fixed check point excluded from fitting. A candidate that fits its chosen points but harms this feature cannot hide behind a low fit residual.
- A growing/leaning flame with a fixed wick. Preserve deliberate height/width changes and detect injected wick drift. No independent cel fitting or brightness normalization.
- Separate regional brightness and alpha-edge defects without geometric drift. Flag the affected regions; propose no translation from appearance differences alone. Ignore arbitrary transparent RGB.
- Faint edge detail with a correction that exceeds available padding. Fail with required extra space; do not clip or refit. An identity correction preserves decoded baseline pixels when rebuilt under the same compiler settings/runtime.
- Source-following and fixed sockets, a child attachment, an object-bound mask and a fixed occluder. Correct bindings follow the art; unsupported overrides are reported; examine actual raster overlap.
- Unequal cel holds, reused cels, hidden intervals, moving parent/camera and a visible wrap. Prove the comparison uses the shared production clock and distinguishes asset-local from world-space movement.
- Cropped/resized inspection views with nonzero atlas offsets; edits reference view IDs and round-trip to exact source coordinates. Reject stale views after study/source changes.
- Bounded tracking with a repeated mark, a disappearing feature and reference/neighbor disagreement. Preserve uncertain/missing states; include ordinary transitions and apparently good proposals in the review packet.
- Tampered study/source/mask/proposal, output collision, stale scene transaction and changed input during work. Fail before candidate publication, including on cache lookup and revision capture.
- Later: a pass-through trajectory and a matched-position loop with deliberately mismatched velocity; harder pose/occlusion cases for learned tracking; a cloud sequence with legitimate outline evolution.

Run focused Python/compiler tests during implementation, then `python3 tests/test_studio.py`, `python3 tests/test_assets.py`, `node tests/test-rig.mjs`, the existing editor checks and `./ambiance test` as applicable. Run package audit for added runtime resources. Scene/renderer changes require actual browser inspection and native render/encode verification where available; report unavailable checks honestly. Avoid rerunning unchanged suites without a new reason.

For the first-release pilot, select existing source-backed painted sequences and work in an isolated project under the active workspace. Include a creature/figure and wick-anchored flame where available, plus a diffuse cloud/smoke inspection case. Compare the current manual proof path, the new manual workbench and bounded propagation. Record identities, commands, manual annotations, wrong selected matches, unresolved points, correction rounds, cold/warm latency, operator turns/output volume, resumption work and remaining visual defects. Keep tuning and evaluation cases separate. Compare source cels, compiled atlas, rendered frames and decoded movie frames at the same display size. Watch at normal speed as well as scrubbing flagged transitions; do not equate contact-sheet inspection with continuous viewing.

Finish with a brief implementation handoff containing exact artifact/proof links, measured results, actual visual observations and remaining limits. If a movie review iteration is produced, register and present its exact review movie through the existing delivery mechanism. Technical evidence and any human review remain separately identified.

## Implementation status — 2026-09-11

Milestones 1–3 now have a CLI path and an optional localhost workbench. See [executable commands and limits](../CEL-MOTION.md). The first tracker uses bounded Pillow patch correlation; it requires no added runtime. Source/layer initialization, immutable edits, observation packets, fit/check landmarks, regional reports, fixed-geometry compilation, socket policies, typed provenance, draft parity and shared-clock scene comparisons are implemented. Object-bound companion masks and light rectangles are reported as unsupported bindings; they are not silently corrected. Learned tracking, continuous curves/contacts and cloud deformation remain planned. The isolated pilot and measured limitations are recorded in [the implementation handoff](CEL-MOTION-HANDOFF.md).

## Original implementation sequence

Begin milestones 1–3 as one bounded first release. Prove source coordinate conversion, useful observation packets, fixed geometry and manual translation recovery through the CLI, then add bounded propagation before the operational pilot. Prioritize validated batch edits and resumption over optional UI gestures. Keep later milestones visible without adding unsupported commands or fields to production documentation.
