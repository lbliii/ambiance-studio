# Production improvements after Midnight Reading Room

Implementation design, September 11, 2026. Based on the [production audit](../../reports/MIDNIGHT-WORKFLOW-AUDIT-2026-09-11.md) and checkout `31390fbe7c8039aca9f39ef9695cc9a55a41343a`. Status and dependencies live in [PRODUCTION-IMPROVEMENTS.yaml](PRODUCTION-IMPROVEMENTS.yaml), under MRR-01 through MRR-10. The [implementation handoff](MIDNIGHT-IMPLEMENTATION-HANDOFF.md) records shipped interfaces, evidence and remaining limits, including the subsequent MRR-11 cleanup and MRR-12 configuration requests. This design records original proposals; current command contracts live in [production operations](../MIDNIGHT-OPERATIONS.md). Completed foundation tasks retain their status.

The intended result is a shorter path from a creative concern to a useful comparison, with production state that tells the operator what happened and what to do next. Keep the renderer, scene transactions, canonical plan, inventory, captures, editions, and local iteration runner. Build the smallest missing operations around them.

## Decisions

1. Details and movement need an artistic reason. A physical cause or established thematic contribution can justify movement; a demand for visible activity alone cannot. Review excessive motion as well as insufficient motion.
2. Creative intent stays in the production plan. Initially use element `purpose`, action `description`, and expectation `direction`/`rationale`; do not add a mandatory motivation field or an automatic aesthetic score.
3. Feedback records describe what was reported. Resolution records describe work addressing it. Existing review records continue to own observations and readiness. None implicitly approves the others.
4. Routine queries return bounded summaries and direct evidence references. Detailed render and media reports remain available separately.
5. New authoring commands use existing domain validators and transaction semantics. Project-specific masks, folds, palettes, and take choices remain authored project data.
6. Every new production capability has a CLI path. Studio consumes the same services and adds playback and inspection, rather than becoming an independent production authority.
7. Optimize only after measuring the actual stage resolution and preserving visual/encoded behavior. An intentional look change is a creative derivative, not an equivalent fast path.

## Ownership and module boundaries

| Owner | Responsibility and implementation boundary |
| --- | --- |
| `production_plan.py`, `production_coverage.py` | Intent validation and the existing readiness evaluator. Reuse their results; do not copy their rules into status, packets, or feedback. |
| New `feedback.py` | Feedback validation, legacy adapters, immutable observations, resolution events, list/inspect projections. Move the existing feedback functions out of `deliveries.py`; retain forwarding wrappers while callers migrate. |
| New `production_queries.py` | Bounded delivery/run/project projections and next-work aggregation. Accept existing evaluation results and the request-scoped `Fingerprints` cache. |
| `production.py` and new `run_control.py` | Existing iteration orchestration plus owned-process identity, progress, cancellation, and effective state. Keep durable step recovery and selection comparison in the runner. |
| `rendering.py`, `tools/render-scene.mjs` | Benchmarking and progress at real render/encode boundaries. Final results stay on stdout; progress uses a separate atomic file. |
| `scene_authoring.py`, `tools/scene-command.mjs` | A clock operation through `SceneTransaction`, the shared engine, and normal history. No second scene writer. |
| `planning.py`, new `inventory_authoring.py` | Inventory fulfillment patches using the current inventory evaluator, source hashes, and project lock. No duplicated intent or review authority. |
| New `iteration_recipes.py`, `review_packets.py` | Pure recipe construction and packet orchestration over existing capture/render/audio/media/delivery services. Extract only the functions these paths need from parser-driven orchestration. |
| `activity.py`, preparation/compiler modules | Explicit comparison variants and registration-preserving preparation transforms. No cloth simulation engine. |
| `studio_server.py`, `studio/studio.mjs` | Render summary data, ordinary feedback, run health, and paired review playback. Preserve server origin/path protections. |

Do not introduce a database, scheduler, plugin framework, generic workflow language, or application-wide service layer. Extract functions in the slices that need them. Imports must not create assets, directories, or production runs.

## MRR-02: untimed feedback and resolution

### CLI and subject selection

Proposed examples, with `--project PROJECT` before each command:

```text
feedback add painted-review --scope delivery --note-file feedback/curtain-motivation.md --by operator
feedback add painted-review --scope entry --view portrait --role score --time 8.2 --note "Cloth pulls attention away from the fire" --by operator
feedback add painted-review --scope entry --view landscape --role score --from 7 --to 12 --note-file feedback/observation.txt --by operator
feedback inspect FEEDBACK_ID
feedback list [DELIVERY_ID] --state open --limit 20
feedback resolve FEEDBACK_ID --resolution FILE --by operator --expect-head HASH
feedback reopen FEEDBACK_ID --note "The new comparison still needs revision" --by operator --expect-head HASH
```

`--scope delivery` excludes view, role, and time. Entry scope requires an unambiguous existing entry; a point or range is optional. Point and range are mutually exclusive. Points satisfy `0 <= time < duration`; ranges satisfy `0 <= from < to <= duration`. Reject non-finite numbers and boolean-as-number values. Preserve the existing maximum note/actor lengths. Exactly one of `--note` and `--note-file` is required.

Legacy `add DELIVERY --role ... --view ... --time ... --by ...` remains valid and retains its observer semantics. New explicit-scope calls treat `--by` as the reporter; optional `--observed-by` names an actual viewer only when known. Do not fill in a viewer or orientation from the delivery default. Optional action/element references must include the applicable captured plan identity and validate against that plan; they are navigation aids, not inferred observations.

### Stored contract

Continue `format: ambiance-movie-feedback`; new records use schema version 3 independently of the delivery version. The observation contains:

| Field | Contract |
| --- | --- |
| `id`, `created_utc`, `payload_sha256` | Existing safe ID, UTC, and sealing conventions. |
| `subject` | `kind: delivery` plus delivery ID and sealed payload hash; or `kind: entry` plus that delivery reference, entry key, movie path/hash/bytes, and captured revision/edition/view identities where available. |
| `time` | `null`, `{kind: point, seconds}`, or `{kind: range, start_seconds, end_seconds}`. Only entry subjects may carry time. |
| `reporter`, `observer` | Reporter is required; observer may be null. |
| `note`, `references` | Original report text and optional validated plan/source references. Preserve uncertainty about who viewed which movie. |

Keep observations at `feedback/movies/ID.json`. Keep sealed resolution events at `feedback/events/ID/SEQUENCE-EVENT_ID.json`. Each event references the original observation hash, preceding event hash, author, time, reason, and transition. Compute current state by folding the verified chain; never rewrite the observation or a legacy record.

States are `open` and `resolved`. A resolution file declares outcome `addressed`, `withdrawn`, or `superseded`. `addressed` requires an exact revision or delivery reference and an explanation of the change. `superseded` requires another feedback ID. `withdrawn` records the authored reason. Resolving means the work item has a recorded disposition; it does not change visual/listening gates or claim user acceptance. Reopening appends another event. Deferred work stays open.

Use the project lock and `--expect-head` to reject competing updates. With no events, the expected head is the observation's sealed payload hash. Write a complete event to a temporary file, then atomically install it; duplicate sequence numbers, broken chains, or changed evidence are errors, not silently skipped records. List/inspect include integrity status, state, head hash, and evidence paths. A changed referenced movie preserves the historical comment while preventing it from masquerading as feedback on the current bytes.

Read versions 1 and 2 through adapters: preserve timestamp, observer, movie, and original meaning; derive an entry subject only from their recorded identities. New readers must not rewrite captured files. Explicit import of the curtain note records the note's source hash and the known delivery; it does not invent a viewing date, timestamp, or multiple auditions. An optional caller request ID makes retrying a submitted observation idempotent; reusing it with different content fails.

Studio uses the same service. Delivery-wide notes have no seek button; entry ranges seek to their start. Feedback on earlier deliveries remains discoverable after a new review is selected.

## MRR-03: compact queries and useful next work

`project overview` becomes a summary response with its own `data.format: ambiance-project-overview` and `data.schema_version: 2`; the outer CLI envelope remains version 1. Add `--details` to return the previous expanded data shape, including full evidence. Update first-party CLI examples and Studio consumers in the same slice. Document the default-shape change and the compatibility flag in the release notes. Do not apply a summary adapter to sealed storage.

Summary fields are project identity/URLs, selected review and release references, working-versus-selected identities, readiness counts, bounded issues, runs, recent deliveries, and next work. Entries contain view, role, duration, size, availability, exact watch path, and evidence references. Run rows contain recorded/effective state, stage, last update, progress when known, and inspect/resume references; exclude step result bodies.

Initial limits: five recent deliveries, five runs, eight next-work items, eight issues, and six selected-entry summaries. Include total/omitted counts and a detail command for every truncated collection. Cap prose excerpts at 160 characters without truncating IDs or hashes. Preserve unusual projects with more views/roles through pagination/detail queries. Test the full emitted JSON envelope against a 16 KiB target for the representative small-project fixture, including indentation. For larger collections, prove output size remains independent of media sample arrays and historical run count; do not use wall-clock CI thresholds.

Add `project next --limit N` for the broader work list; keep `plan next`'s inventory meaning. Each item has a stable ID, kind, exact subject, explanation, dependency IDs, evidence references, and either structured `argv` for a usable read/proof operation or a named creative decision. Never offer a fake executable command containing unresolved placeholders. Mark missing observations separately from mechanical failures.

Aggregate existing inventory, canonical coverage, feedback, gate, and run-health results. Dedupe by subject and underlying requirement. Order invalid/missing inputs and interrupted work first, then applicable open feedback and required production/coverage work, then outstanding observations. Return dependencies without making an open human check block independent work. Allow explicit kind filters; do not infer that all open feedback on an old delivery applies to every newer edition.

Split unmapped catalog reporting into active scene assets without inventory accounting and retained unused versions. The former is actionable; the latter is an informational count with details. Do not delete retained assets or relax source-integrity validation.

The initial effective run-state projection is deliberately conservative: a recorded terminal state remains terminal; a demonstrably absent owner is interrupted; a present PID without verified process identity is unknown. CLI and Studio use effective state, never raw `state === running`. Unknown is neither successful nor permission to kill a process. MRR-05 adds verified ownership for new runs.

## MRR-01 and MRR-07: motivated action and comparable alternatives

Authoring examples should answer three questions together: what causes this action or what theme it advances, what in the scene establishes that explanation, and how much emphasis fits. Use existing plan fields. Describe upper limits in direction as well as minimum readability; do not interpret the current evaluator's minimum readability check as an aesthetic preference for stronger motion.

For this room, the current direction has no established wind or haunting. The initial revision study should preserve the curtain's painted presence and compare a held pose with restrained deformation against the current result. An open/broken window or supernatural premise remains a separate creative option, not an automatic repair. Keep justified fire, steam, and outdoor movement. Change the selected plan explicitly with a reason and capture a new revision; never retrofit new requirements onto the old movie's evidence.

Extend `scene activity --compare FILE` with recipe version 2. Version 1 strength/cadence recipes retain their meaning. Version 2 declares an experiment kind, a baseline, explicit variant IDs, target layer IDs, and the property allowed to differ:

| Kind | Allowed difference | Required invariants |
| --- | --- | --- |
| `held-pose` | Named cel held throughout the study; changed cadence is labeled explicitly. | Object remains visible, with the same placement, size, camera, attachments, and look. |
| `cel-alternative` | Substitute an explicitly registered derivative atlas and cell mapping. | Same object geometry, source family, phase schedule, driver timing, anchors/sockets, and view sampling; registration proof must account for changed crop dimensions. |
| Existing strength/cadence | Existing constrained transform/clock operations. | Preserve version-1 validation; do not label whole-object scaling as less cloth deformation. |

Compile comparison variants into temporary derivative scene/catalog contexts using existing transaction validation. Do not edit the working scene or admit new catalog versions implicitly. A registered alternate must already exist with source/recipe hashes. Missing or incompatible companions, source identities, or cell maps fail with an actionable error. Followers that depend on the changed cell must use a declared compatible mapping; do not hold cloth while accidentally retaining animated cloth-specific shadows.

Use the same times, output sizes, cameras, framing, backdrop, and lighting inputs. Verify source placement and attachments at all variant cels, then render contextual proofs in both views. Report the intended differences and actual timing/geometry differences. Geometric checks cannot establish painted quality. A source-derived restrained atlas may be prepared explicitly, but the comparison service does not generate or infer cloth deformation.

## MRR-06: small authoring operations

### Clock

Add a scene transaction operation `{op: clock, values: {loop_seconds: 24}}` and convenience `scene clock --loop-seconds 24 --dry-run --expect-sha256 HASH`. Initially expose loop duration only; leave canvas dimensions and fps outside this slice. The operation supports ordinary atomic batches so clock and track edits can be validated together.

Use the shared validator and `scene timing` evaluator to return before/after effective clocks, cel-track precedence, loop closure, periodic bindings, and affected audio cue/master assumptions. Reject invalid final scene state. Report sound incompatibilities separately; editing the picture clock does not rewrite audio or assert that an existing mix fits it. Provide affected evidence identities and the needed checks. Preserve restorable snapshots and existing capture hashes. Never auto-stretch tracks, cycles, sound, or an old movie.

### Fulfillment

Add `plan fulfill FILE --dry-run --expect-sha256 HASH`. The version-1 patch names stable inventory item/part IDs and replaces only fulfillment fields: `stage`, `files`, `asset_id`, and `layer_ids`. It cannot change creative scope, `required`, target stages, review verdicts, or entire items. Legacy string parts need explicit conversion to stable IDs before they can be patched.

Extract a pure inventory evaluation function from the current loader so the candidate can pass the same checks before saving. Verify file hashes, catalog identity, layer-to-asset mappings, and stage evidence. Compute production completeness from those checks; never turn `review: pending` into acceptance. Hold the project lock, check expected inventory hash and all read dependencies again, save a restorable before/after receipt, then atomically replace the inventory. Dry run writes nothing. A stale hash, invalid reference, or failed write leaves the prior inventory usable. Do not claim filesystem-wide transactions against unsupported direct writers.

### Recipe initialization

Add `iteration init FILE --out DIR`, where a small strict request identifies run/revision IDs, intended views, explicit default view/role, scope, size, and each role's PCM source/provenance/repeat count. Reuse the existing iteration and capture-selection validators. Return a validated iteration recipe, capture selection, resolved job summary, and input hashes. Refuse to overwrite an existing output directory; build then atomically rename the bundle. Initialization captures no revision, renders nothing, and changes no selection.

Do not choose the first audio take or silently inherit an old selected movie's working inputs. Missing roles, PCM duration mismatches, unresolved views, and incompatible clocks are actionable errors. Recipe construction becomes a pure service shared by the packet builder. Existing authored schema-1/2 iteration recipes remain supported unchanged.

## MRR-04: early picture-and-sound review packet

Add `review packet init FILE --out DIR` and `review packet run FILE --by operator`. The request names the source/capture recipe, intended views, long edge, review interval, selected audible role, explicit source-audition references, and open questions/feedback IDs. The initializer resolves and validates dependencies; the run produces or resumes a bounded draft using the existing iteration/media pipeline.

The interval must support the question: a full picture cycle for cadence/closure, and the relevant master/join interval for sound. Version 1 produces full picture loops and the selected whole PCM master through existing iteration recipes; the review interval is a marked playback range inside those files, not a new frame-accurate excerpt encoder. A short playback range must identify what it cannot establish. Default to the declared picture loop, not a universal two-second review. Freeze every input used by the packet. Store a sealed `ambiance-review-packet` version-1 manifest with exact revision/edition/movie identities, source auditions, questions, interval, dimensions, synchronization mode, and artifact paths. Creating a packet does not select it as the current review. Explicit `delivery present` remains the selection operation; add an internal non-presenting mode for packet runs without changing existing iteration defaults.

Extend the current Studio player with paired views, loop controls, and one shared audible source. Encoded movie playback is labeled approximately synchronized; exact rendered-frame proof remains a separate mode with its own evidence. Pause/seek both players together, correct drift, and mute every non-selected audio source. Bind feedback to the packet's exact delivery/entry. Playback events may report playback, not an audition or approval.

Generate a self-contained local HTML player using relative media paths and no required fetch/server API, plus an index of direct MP4 and audition paths. Local-file playback can have browser restrictions; direct artifacts remain the fallback. Keep HTTP origin checks and project-path containment intact. No messaging service is added.

## MRR-05: benchmark, progress, interruption, and resume

### Benchmark contract

Add `render benchmark FILE --out DIR` over the same validated iteration/job plan, with explicit sample count and encode-sample duration. Sample beginning, interior action/light states, and the end of the actual clock at the actual internal stage resolution and finishing configuration. Measure initialization, frame render/finishing, view projection, bounded encoding, and verification separately. Count the existing preroll and every planned view/role job in the estimate; disclose components inferred from a sample rather than executed in full.

The saved report binds scene/catalog/source/view/look/recipe hashes, backend/version, dimensions, supersampling, sample times, frames, durations, memory observations when available, and estimate assumptions. Return median/range and an uncertainty description, not a promised completion time. An unavailable native component is unknown, not zero. Do not automatically change finishing mode, output resolution, or encoder settings based on a benchmark.

### Progress and effective state

New runs record a run UUID, host identity, owner PID plus process start identity, and owned child identities. A monotonic sequence and atomic `progress.json` hold phase, completed/expected frames, preroll/encoded counters, recent throughput, and heartbeat UTC. The Python run owner is the sole progress-file writer; children emit bounded JSON-line events on a dedicated pipe. Throttle writes to at most two per second plus phase transitions; cap retained event history. Track owner heartbeat separately from last work advancement so a quiet or stalled child does not fabricate throughput. Counters distinguish rendered frames from encoded output. Verification phases without a denominator report activity with no invented percent. Stdout still contains one final JSON result.

Extract a small subprocess executor using `Popen` where streaming/control is required. Keep quiet finite commands on their existing path. The Node renderer reports progress to the supplied channel and owns cleanup of its native encoder. Durable run checkpoints remain authoritative for completed jobs; an ephemeral progress file cannot claim an edition is complete.

For new runs, effective state is running only with verified owner identity and a fresh owner heartbeat; a verified owner with a stale heartbeat is unresponsive; absent owner is interrupted; unverifiable identity is unknown. Start with a documented 15-second heartbeat freshness threshold and do not turn it into automatic cancellation. A fresh owner with no recent child advancement is running with an explicit no-progress diagnostic, not evidence of successful work. Record raw state alongside effective state and the reason. Compatibility reads of legacy PID-only records remain conservative.

### Cancel and reconcile

Add `iteration cancel ID --expect-run TOKEN` and `iteration reconcile ID`. Cancellation first writes a request bound to the run UUID; a cooperating owner stops work, cleans up its children, saves `interrupted`, and releases its own lock. A bounded fallback may signal only a process whose host, PID, start identity, and recorded ownership still match. Implement supported-platform process identity behind a small adapter and fail closed when unavailable. Never kill by PID alone or signal an unverified process group; unsupported ownership is a reported manual-recovery condition.

Handle cancellation during rendering, native encoding, verification, and between steps. Preserve completed editions, logs, partial-attempt directories, and the selected review. Reconcile changes durable state only after verifying the owner is absent and checking completed output/edition receipts. Remove only the matching stale run lock under project coordination. Resume uses the same recipe and existing validated step reuse; a changed recipe needs a new run. Preserve the selection compare-and-swap so an old resumed run cannot displace a newer review.

## MRR-08: measured preparation and renderer improvements

First add a registration-preserving union crop to the existing asset compiler/preparation path. Compute bounds across all cels, preserve transparent padding required for attachments, transform source mappings/anchors/sockets consistently, and validate static/dynamic companions. Retain original art and a hashed preparation recipe. Empty cels, changing silhouettes, nonuniform cell sizes, and moving attachments need explicit fixtures. Room-specific crop assumptions stay in the project.

Use MRR-05 to profile scratch allocation, grade/mask loops, and repeated receiver appearances in `drawFinished`. The engine already caches source pixels/cells; do not duplicate that cache. Implement one measured optimization at a time. Prefer bounded scratch reuse first if profiling supports it. Any further cache must key all influencing source/scene/look/view/size/cel/binding inputs and have a documented memory bound and invalidation tests.

Classify results as exact, tolerance-bounded, or intentionally approximate. Define tolerances before comparing a candidate; retain baseline and candidate raster/encoded artifacts. Test edges, occlusion, all discrete lighting states, both views, and the encoded join at intended resolution. Do not promote the room's Canvas light bake as equivalent to linear compositing. Shared-stage fan-out and preroll reuse remain experiments until memory and encoded-boundary evidence justify them; no preroll removal in the initial slice.

## MRR-09 and MRR-10: skills and observed trials

Keep the six stage skills. Each opens with inputs to inspect, the short supported command path, the artifact to present, and the decision to judge. Link uncommon recovery cases. Update command examples only as their implementation ships; preserve authority, original protection, independent backing, exact versions, and honest review rules. Put the general cause/theme/emphasis rule in the existing motion/layer references, with short pointers from deconstruct/animate. Bring source audition into the first motion-and-sound packet. Avoid duplicating the same long rule across every skill.

Add fixtures and operator trials to the existing evaluation harness, using supplied art and local resources:

| Case | Required distinction |
| --- | --- |
| Sheltered room | Still/restrained cloth can fit; justified fire/steam/outdoor life remains. |
| Open window | Established airflow can justify movement; strength and frequency still need judgment. |
| Established haunting | Uncanny behavior advances an authored premise; no invented premise solely to excuse a defect. |
| Untimed report | Original uncertainty, exact delivery, no invented timestamp/view, actionable next work, traceable resolution. |
| Interrupted paired run | Honest state, safe cancellation/reconciliation, verified reuse, preserved selected review. |

For behavior trials, record actual interventions, custom script volume, response bytes, time to first useful combined review, unnecessary questions, and unresolved observations. Keep synthetic replay passes separate from observed operator trials. Do not aggregate aesthetic scores or mark old CI-02/PILOT-01 criteria complete unless their particular requirements were actually exercised.

## Implementation sequence and acceptance

| Slice | Backlog | Concrete acceptance before advancing |
| --- | --- | --- |
| 1. Ordinary feedback | MRR-02 | Import a derivative of the curtain note through CLI; list it untimed; resolve/reopen against exact evidence; legacy feedback remains intact. |
| 2. Operator queries | MRR-03 | Bounded overview, current/old feedback navigation, useful next work with complete assets, honest dead/unknown run status in CLI and Studio. |
| 3a–c. Authoring primitives | MRR-06 | Separate clock, fulfillment, and initializer changes, each with public CLI replay, stale-input rejection, and restorable/no-op failure behavior. |
| 4. Creative comparison | MRR-01, MRR-07 | Explicit revised direction and comparable current/still/restrained cloth in both views, with stable attachments and actual normal-speed observations. |
| 5. First useful review | MRR-04 | Produce and resume a packet using the initializer; play/seek/loop both views with one audible source; local-file fallback works; current review is unchanged until presented. |
| 6a–b. Run control | MRR-05 | Real-recipe benchmark/progress, absent/reused/unverifiable PID fixtures, cancel at multiple stages, native recovery and selection preservation. |
| 7. Measured improvements | MRR-08 | Retained timing/memory and fidelity comparison; promote only a measured improvement with passing invalidation and boundary checks. |
| 8. Supported workflow trials | MRR-09, MRR-10 | Shipped command examples, observed contrasting decisions and effort measurements, exact review artifacts, explicit remaining unknowns. |

The initializer precedes the packet so the packet does not acquire a second recipe-authoring path. Documentation and tests accompany each slice; the last slice consolidates the workflow and runs behavior trials. Renderer optimization is conditional on evidence and must not delay feedback, status, or the creative comparison. The MRR-10 trial dependency includes MRR-08's measured disposition, which may be “retain the baseline” when no candidate is justified.

Feature tests belong in the existing suites. Feedback tests cover compatibility, ambiguity, time bounds, duplicate retries, tampered hashes, and concurrent events. Query tests use deliberately huge sample arrays and growing history. Authoring tests exercise real cel-track precedence and invalid sound assumptions. Comparison tests cover transformed source geometry and companions, followed by raster review. Run tests use harmless owned subprocesses and the existing native media lane. Player tests require an actual browser playback/seek/audio check, not just JavaScript syntax or geometric state checks.

Run `./ambiance test` after shared-code changes; compiler/rig changes also use `python3 tests/test_assets.py` and `node tests/test-rig.mjs`. Keep native services in the existing supported macOS lane and report skipped checks honestly. Skill/package changes require the package audit. Completion evidence must distinguish unit/CLI tests, raster inspection, encoded checks, actual viewing/listening, and user feedback.

## Compatibility and rollout

- Leave existing scene, inventory, plan, capture, edition, delivery, and iteration schemas unchanged unless a slice explicitly versions its own contract. In particular, clock authoring changes a supported value, not the scene schema.
- Add feedback schema 3 and comparison recipe 2 with read adapters. Add separate versioned summary, progress, benchmark, and packet contracts. Do not rewrite historical evidence to adopt them.
- Keep `project overview --details` and legacy feedback argument behavior documented. Update first-party API consumers atomically with the summary change; reject unsupported response versions explicitly.
- New write operations validate first, expose structured failure codes using the existing exit conventions, preserve source hashes, and avoid partial canonical writes. A failed preview/generation is never an implicit request to regenerate originals.
- Leave new packet presentation explicit. Existing iteration presentation behavior remains unchanged. Sending/publishing stays outside this implementation.
- Add public routes to `CAPABILITIES.json` only after they are callable and tested. This design and the backlog remain the home for proposed routes.

The first implementation handoff is slices 1–2: feedback capture/lifecycle and compact, truthful next-work reporting. It has a concrete reproduction in this film and can ship without modifying the movie. The curtain comparison is the first creative pilot, with its actual result and acceptance left open until produced and reviewed.
