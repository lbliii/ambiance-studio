# Scene activity and picture cue evidence

`scene activity` measures the selected scene through the production evaluator, `editor/timing.mjs`, and the existing named-view projection and stage renderer. It writes an immutable receipt and compact JSON summary. It never assigns artistic readability from pixels.

```sh
./ambiance --project PROJECT scene activity --view portrait --view landscape --out reports/activity-state
./ambiance --project PROJECT scene activity --action-id mouse-turn --view portrait --view landscape --raster --long-edge 320 --out reports/activity-proof
./ambiance --project PROJECT scene activity --layer mouse --raster --frames 90 --out reports/mouse-draft
```

Actions come from the canonical production plan: action ID, owning element's realization layers (or the explicit action subset), target views, 0–4 readability targets, method, cadence, and timing targets. `--layer ID` adds a diagnostic intervention with ID `layer-ID`, without inventing a semantic requirement. `--action-id` filters plan actions; repeat `--view` for up to two outputs. An absent plan permits diagnostic drafts; an invalid plan fails. `--revision ID` selects captured inputs and its captured plan.

The artifact directory contains:

| Artifact | Evidence |
| --- | --- |
| `activity-report.json` | `kind: ambiance-scene-activity`, schema version 1; exact scene/catalog/plan/expectation/revision/view identities, source hashes, implementation hashes, sampling, joins, compact summaries and artifact manifest |
| `state.json` | Original authored cel holds/rates from `sceneTiming`; sampled projected painted polygons, opacity, eligibility, cell content identity, travel, speed, local/world transforms, effective binding values and action windows |
| `painted-cells.json` | Decoded nonzero-alpha bounds and normalized RGBA content hash per cel; transparent RGB is ignored |
| `raster.json` | Actual full-frame differences and per-action disabled-intervention residuals at the declared cadence |
| `maps/ACTION/VIEW.png` | Maximum sampled per-pixel residual change; red intensity is an 8-bit RGB difference, not salience |
| `index.html`, `frames/` | Hash-bound normal-speed PNG playback, synchronized views and interventions; present only with `--raster` |

`ambiance_studio.activity.verify_receipt(path)` verifies required files and every manifest hash before returning the full receipt. Consumers must additionally match its scene/catalog/plan/expectation/view identities to their selected subject. The verifier does not turn measurements into an artistic pass. The ordinary command summary contains only per-view action IDs, applicability, warning IDs, maximum sampled rest, unreviewed status, performance and artifact paths.

## Units and sampling

Sample times are production frame numbers divided by the existing output fps. `--start-frame`, `--frames`, and `--stride` select a bounded interval; stride must divide its frame count. Default stride is one. Playback uses `fps / stride`, so decimation changes temporal sampling, never picture speed. Reports retain both clocks. The first sample has no preceding saved temporal observation. Subframe events and skipped frames remain unknown. Authored holds remain exact and independent of sampling; bound cell channels may have sampled evidence without inferred subframe boundaries.

Painted bounds exclude transparent padding but precede finishing. A transformed bounding box intersecting the view is not proof that a foreground occluder permits visibility. World anchor travel includes the camera and parents. Local anchor and matrix changes exclude that inherited movement. Corner travel also detects rotation/scale and changing painted extent. Units include display pixels, pixels/second, object diagonal fractions and output diagonal fractions. These measurements do not classify a movement as a character gesture.

`sampled_windows` are half-open runs of changed projected state. Their onset, duration and rest are sampled candidates, not independent authored action schedules. A continuous route may stay active through several gestures; changing cel indices may select identical paint. Read exact timing holds, the action's direction, and the normal-speed proof together. Do not treat a zero-at-start comparison or an interval between sparse samples as observed stillness.

## Raster attribution and warning calibration

For action layer set A, the renderer produces the target F and the scene with A disabled, Foff, using the same finishing pipeline. Attached descendants and source-driven followers respond through existing runtime semantics. Contribution is `F − Foff`. Temporal residual change compares that signed difference across two sampled times. All metrics use the maximum absolute RGB channel delta per pixel in 8-bit sRGB; alpha is excluded. Full-frame change remains a separate column. A global pulse cannot automatically satisfy a character or environmental requirement.

Intervention differences are not exclusive causal attribution. Occlusion, blend modes, nonlinear finishing, camera travel and source/follower effects can influence the residual. The report explicitly preserves that uncertainty. Byte-identical cel paint can still yield small atlas-edge sampling differences; the duplicate-paint warning stays separate from actual changed pixels.

Warnings identify no projected presence, no measured contribution, no residual change, identical cel paint, small support (under 0.0005 of displayed pixels), and low frame-average contribution (under 0.05 RGB units). These are fixture-calibrated prompts to inspect, not universal salience thresholds. Readability levels stay authored/observed 0–4 judgments. No averaged artistic grade or minimum active-layer quota exists.

```sh
python3 examples/activity/replay.py --out /tmp/activity-replay
```

This public-CLI replay creates independent brush-mark cases and read-only copies of the repository's painted cloud cels. It saves tuning/held-out labels, every warning, false warnings, misses, and unflagged cases. Synthetic condition labels are not actual observer judgments. In particular, low-contrast cropped examples, excessive motion and pulse ambiguity can be missed; those limitations are retained. The example is not a completed ambiance film or private-film pilot.

## Match strength, then compare cadence

`--compare FILE --raster` accepts version 1 with optional `strength` and `cadence` arrays. Each supplied array has exactly two `{id, batch}` entries, alongside the unchanged `target`. Batches use the shared scene transaction evaluator in memory and are saved as derivative snapshots. They do not edit the project.

Strength batches may set width, height, scale and periodic-motion amplitudes while preserving cycles/phase. Cadence batches may set cycle duration, phase, motion cycles/phase or existing track key times while preserving amplitudes, track channels, value sets and interpolation. Both experiments preserve canvas clock and view definitions. Run `examples/activity/create_fixture.py --out /tmp/activity-example` for a complete quieter/target/stronger and separate cadence recipe.

Raster work is bounded to eight action interventions, sixteen panes, six hundred samples and four hundred million stage pixel samples. State work is bounded separately to two hundred thousand projected layer samples and sixty-four summary actions; the timing reporter retains its own bounds. Failure explains which filter, duration, stride or size to reduce. No silent truncation or cross-product of strength and cadence combinations occurs.

The replay records fixed single/paired workload costs, raster latency, peak process RSS, response bytes, saved frames, and declared playback sampling rate. Each run starts a fresh process; “warm” means the OS cache may be warm, not a controlled flushed-cache experiment. Live browser controls/clock need separate verification. Timing numbers are not CI pass thresholds. This feature makes no renderer optimization or legacy pixel change; parity tests compare saved frames byte-for-byte with the existing view renderer.

## Resume and observe

Reuse the identical command and add `--resume`. A completed receipt is verified before reuse. A partial run with an intact matching request regenerates deterministic frames, checks existing bytes, and fills missing files; it refuses changed files or changed options. No generation request is involved. Use a fresh directory when inputs change. Actual artist observations remain separate immutable files.

`scene activity-review INPUT --out FILE` records an `ambiance-activity-observation` schema version 1 containing the exact `receipt` path and `receipt_sha256`, `action_id`, `view_id`, and status `unreviewed`, `revise`, or `meets-direction`. A performed observation requires `observer`, a concrete `note`, `playback_rate: 1`, exact proof `display_width`/`display_height`, and `watched_start_seconds`/`watched_end_seconds` inside the saved interval. `observed_level` is null or 0–4; unreviewed records must leave it null. Recording validates the statement and artifact identity; it cannot verify that someone actually watched. Do not invent that statement. No phone review, listening, or gate closure is implied.

## Sound cues

See [audio sessions](AUDIO-SESSION.md). `audio cue-bind` preserves the original session and writes a derivative containing exact picture-action/cue anchors. `audio cue-check` identifies changed, deleted, retimed or repeated picture actions, changed loop lengths, retimed clips and changed selected PCM/source identities. A full-loop activity receipt at every production frame is required. View changes alone preserve shared cue identity when action state and clock remain identical. Retiming and listening stay explicit.
