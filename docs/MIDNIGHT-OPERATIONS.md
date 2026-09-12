# Feedback, review studies, and local run control

These commands extend the existing production pipeline. Use `./ambiance --project PROJECT` before each command. Creative direction stays in the production plan; fulfillment, runtime, feedback and review observations remain separate authorities. The [implementation design](architecture/MIDNIGHT-PRODUCTION-DESIGN.md) records the rationale and the [backlog](architecture/PRODUCTION-IMPROVEMENTS.yaml) records acceptance status.

## Feedback

```text
feedback add DELIVERY --scope delivery --note "The curtains move too much for this sheltered room" --by Reporter
feedback add DELIVERY --scope entry --view portrait --role score --time 8.2 --note "Cloth distracts from the fire" --by Reporter
feedback add DELIVERY --scope entry --view landscape --role score --from 7 --to 12 --note-file NOTE --by Reporter
feedback list --state open --limit 20 --offset 0
feedback inspect ID
feedback resolve ID --resolution FILE --by Operator --expect-head HASH
feedback reopen ID --note "Still needs work" --by Operator --expect-head HASH
```

Delivery scope has no view, role or timestamp. Entry scope must select one movie; a point/range is optional. `--by` identifies the reporter; `--observed-by` names an actual viewer when known. Legacy calls without explicit scope retain `--role`, `--time` and observer semantics. `--note-file` preserves the report text and records a source hash when the source is inside the project. `--request-id` makes an unchanged add retry idempotent; changed content needs a new request ID.

New observations use `ambiance-movie-feedback` schema 3. Versions 1/2 are read without rewriting. `subject` binds the sealed delivery and, for an entry, its exact movie and captured identities. `time` is null, a point, or a range. Resolution/reopen events are sealed, ordered and append-only under `feedback/events/ID/`. `inspect` returns the current `head`, state, event history and reference integrity. A stale head prevents competing updates.

Resolution files contain `outcome` and `note`. `addressed` also needs an exact `revision` or `delivery`; `superseded` needs another `feedback` ID; `withdrawn` records the reason. Resolution disposes of a work item; it never passes a movie gate. Deferred work stays open. Damaged observation/event seals are errors. Missing/changed referenced media remains visible as an integrity problem alongside the historical report.

## Routine state

`project overview` returns `ambiance-project-overview` schema 2 inside the unchanged CLI envelope. `project overview --details` retains expanded evidence, including canonical readiness and per-entry checks. First-party Studio pages use the summary and load a selected delivery separately. Earlier consumers that require the previous shape should request `--details`.

`project next --limit 8 [--offset N --kind feedback|run|input|production|coverage|observation]` combines existing inventory, coverage, feedback and review results. It returns exact subjects and usable inspection commands or named creative decisions. Open observations do not stop independent authorized work. `plan next` retains its inventory-only meaning. Retained unused catalog versions are informational; unmapped active assets appear as next work. `iteration list --limit 20 --offset 0` returns bounded run summaries; `--details` or `iteration inspect ID` retrieves full evidence.

Summaries cap collections and provide counts/details. The initial real-room response decreased from 1,173,801 bytes to 14,454 bytes; this does not imply a corresponding latency improvement. Source/dependency validation still costs time.

## Authoring

`scene clock --loop-seconds N [--dry-run --expect-sha256 HASH]` changes only the loop duration through the ordinary scene transaction. It reports before/after effective timing and audio-review impact. An atomic scene batch may combine `{"op":"clock","values":{"loop_seconds":24}}` with track edits. Invalid final scene state is rejected. Tracks, bindings, audio and old captured evidence are never silently stretched.

`plan fulfill FILE --expect-sha256 HASH [--dry-run]` accepts this shape:

```json
{
  "format": "ambiance-fulfillment",
  "schema_version": 1,
  "parts": [{
    "item": "curtain", "part": "cutout",
    "values": {"stage": "prepared", "files": [{"file": "assets/prepared/curtain.png", "sha256": "REPLACE_WITH_ACTUAL_SHA256"}]}
  }]
}
```

Only stage, hashed files, asset ID and layer IDs may change. Stable item/part IDs are required. Scope, target stage, `required` and artistic verdicts cannot be changed by fulfillment. The existing evaluator checks the candidate and dependencies before saving. Prior bytes are retained in `.ambiance/inventory-history/`; `pending` reviews remain pending. A dry run writes no candidate/history artifacts.

`iteration init FILE --out DIR` validates and writes a fresh project-local bundle. The request uses `format: ambiance-iteration-request`, `schema_version: 1`, run/revision IDs, explicit `views`, `default`, `editions`, optional size/scope/documents/audio selection. Its iteration fields match [the existing contract](STUDIO-LIBRARY.md). The initializer requires a fresh revision ID; existing saved iteration recipes can still resume captures. It emits `iteration.json`, `capture-selection.json`, `inputs.json` and `job-plan.json` without capturing, rendering or selecting a review. Sound roles require explicit matching PCM and provenance.

## Painted motion alternatives

Use `scene activity --compare FILE --raster` with version 2:

```json
{
  "version": 2,
  "variants": [
    {"id": "still", "kind": "held-pose", "layers": [{"layer": "curtain", "cell": 0}]},
    {"id": "restrained", "kind": "cel-alternative", "layers": [{"layer": "curtain", "asset": "curtain-atlas", "cell_map": [0, 1, 0, 1]}]}
  ]
}
```

The map covers every original cel and may select existing cels from the same atlas or a compatible registered derivative. Geometry, framing and other tracks remain fixed. A held pose changes cadence explicitly. Distinct atlases need common source evidence and matching registration/pivots. Changed cell dimensions, per-cel sockets and cell-driven companions currently require a separately authored coordinated study; the command rejects them. Version-1 strength/cadence comparisons are unchanged.

Assess cause/theme, the cues establishing it and appropriate emphasis before deciding which variant fits. Stillness can fit a sheltered curtain while fire, steam and outside weather remain active. Do not introduce a draft or haunting solely to excuse already-authored movement. Actual paired viewing remains separate from geometry, pixel-change measurements and schema validation.

## Early review packets

`review packet init FILE --out DIR` wraps an explicit iteration request with `format: ambiance-review-packet-request`, `schema_version: 1`, `iteration`, `audible_role`, optional `[start,end]` interval, project-relative `auditions`, `questions` and `feedback_ids`. `review packet run DIR/packet-request.json --by Operator` produces/resumes the iteration without selecting it as the current review. `review packet inspect DIR/packet/packet.json` verifies the packaged evidence.

Packets render full picture loops and selected PCM masters; the interval controls playback, not frame-accurate excerpt encoding. The portable HTML includes both movies, one audible soundtrack, source audition controls and questions. Its media paths are relative and require no fetch API. Direct MP4 paths remain available when a browser cannot play local files. Studio also provides paired-format playback. Both movie modes are approximately synchronized; exact frame proofs are separately identified. Neither playback nor packet creation records an audition or approval.

## Benchmark and run control

`render benchmark FILE --out DIR` takes `format: ambiance-render-benchmark`, `schema_version: 1`, project-relative iteration `recipe`, `sample_count` (3–20) and `encode_sample_seconds` (0–5 within the loop). Zero explicitly skips native sampling. Sampled frames use the actual planned views, stage resolution and finishing settings. Reports contain source times, initialization, render timings, memory, optional native sample/verification and a picture-render estimate including each view's full preroll. Total completion time remains unknown: composition and native throughput are not falsely inferred from picture-only samples.

New iteration runs record a UUID and platform process start identity. `iteration inspect ID` exposes effective state and a separate progress file. A heartbeat is not completed work; frame counts, preroll and advancement are separate. Legacy PID-only owners are unknown while present. Missing owners are interrupted; stale verified heartbeats are unresponsive.

`iteration cancel ID --expect-run TOKEN` requests cooperative cancellation, then may signal only verified owned processes. `iteration reconcile ID` verifies an absent owner and completed outputs before recording interruption and removing its matching stale lock. Active owned children prevent reconciliation/resume until stopped. An unverifiable owner is never killed. Run the unchanged recipe to reuse intact completed steps. Current selection comparison still prevents an older run from displacing a newer selected review.

## Transparent cel preparation

`asset trim-cels LAYER --id NEW_ASSET_ID --out DIR` produces a common crop across every cel, including anchors and static/per-cel sockets. It saves source identity, pixel mapping, compiler recipe and a placement batch. It does not modify the catalog or scene. Build, inspect and admit the new pack, then dry-run/apply the placement with the saved scene hash. Review dependent painted masks/receivers before adoption.

The compiler verifies `cel_trim` provenance against exact original/cropped pixels and enforces unit-scale registration. Integer unit-scale copies preserve RGBA bytes; other registrations keep the existing resampling path. Prior packs are untouched. The crop may provide no useful size reduction; inspect `area_ratio` before adoption. Layers participating in finishing or bindings are rejected pending coordinated preparation. General renderer caching and preroll removal remain conditional experiments, not enabled defaults.

## Layered iteration configuration

`iteration resolve FILE` previews an `ambiance-iteration-config` schema 1 in JSON or YAML. `iteration init` and nested packet iteration requests also accept it. Ordered project-relative `layers` use `ambiance-iteration-layer` schema 1 and contain `recipe` and `values` objects. Request `values` and `overrides` win last. This supports studio presets, project choices and per-run adjustments in a small declarative form.

Objects merge recursively, arrays replace entirely, and null removes a key. An entire `{"$value":"render.long_edge"}` mapping inserts a typed literal from `values`; values are not recursively expanded. There are no shell expressions, environment lookups, remote includes, implicit list merging or executable templates. Layer paths stay inside the project. The resolved recipe still passes the existing iteration/scene/audio validators. An invalid expansion does not create a bundle.

The preview reports the resolved request, used values, ordered source hashes and winning setting origins. Initialization saves `config-resolution.json` with the explicit `iteration.json`, selection, inputs and job plan. Layer changes before a packet's capture invalidate its pending input selection; captured media continues to refer to its frozen scene, recipe and edition evidence. See the [working example](../examples/midnight-production/README.md).

## Cleanup cycle

Use `project storage` after a review iteration to see file/JSON counts, bytes by directory, the largest files and exact duplicate JSON totals. Duplicate bytes are a diagnostic, not permission to merge distinct evidence records.

`project cleanup plan --keep-days 30 [--include reports/BUNDLE] --out FILE` saves a sealed, reviewable plan. An explicit include can select a generated report bundle or one run-attempt directory; default discovery checks those locations. A recognized render/compose/activity/benchmark/view receipt is required. Originals, catalogs, plans, reviews, captures and whole runs are outside these cleanup roots. Active or unverified runs, recent files, symlinks and references from other project documents protect candidates. Corrupt nonempty JSON prevents establishing a safe reference closure. Project-local plans belong under `.ambiance/cleanup/plans/`; external plan files are also supported.

`project cleanup apply FILE` rechecks current references, age and every candidate file before moving eligible bundles into `.ambiance/trash/ID/`. One receipt per cleanup batch supports `project cleanup inspect ID` and `project cleanup restore ID`, including interrupted moves/restores. Changed trash or occupied restoration paths fail visibly. This clears active workspace clutter while retaining recoverable bytes; it does not reclaim disk space or permanently purge anything. Permanent deletion and source deduplication remain separate decisions. The default 30-day period is an operator default, not an automatically scheduled job.
