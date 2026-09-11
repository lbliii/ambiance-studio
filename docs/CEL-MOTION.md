# Cel motion workbench

The first release adds source-bound studies, named fit/check landmarks, regional inspection, bounded translation correction, assisted patch tracking and synchronized proof. It runs through `./ambiance`; the localhost viewer is optional. Research and later work remain in the [design](architecture/CEL-MOTION-WORKBENCH.md) and [research review](architecture/CEL-MOTION-RESEARCH.md).

## Start from the selected layer

```sh
./ambiance --project PROJECT asset motion init --layer LAYER --out PROJECT/study-01.json
./ambiance --project PROJECT asset motion analyze PROJECT/study-01.json --out PROJECT/inspection-01
```

Alternatively, pass a pack directory or catalog asset ID to `init`, with `--display-width 180 --fps 6`. Layer initialization captures the real cel clock, original scene/catalog and displayed full-cell width at time zero. That width is the declared scale for asset-local pixel tolerances; it is not an animated world-space contact measurement. A source-backed compiled pack must be inside the selected project. Rebuild legacy art with the existing compiler when it lacks a registration mapping; the tool does not invent lost source coordinates.

An incomplete study is valid to inspect. The result gives a packet path/hash, actual-size contact sheets, transition strips and paged findings. `--finding ID`, `--region NAME`, `--offset N` and `--limit 1..20` limit returned findings; full evidence stays in the artifact. `inspect` reports missing work; `check` returns nonzero if constraints remain unresolved.

## Author intent in batches

`landmarks` are named source-cel pixel observations. `fit` points determine the translation. `check` points are excluded from fitting and independently test the result. `fixed` means the point should stay at its reference location over the declared cel interval; `observe` records intentional movement without imposing that constraint. Fixed landmarks share the solve reference cel. A missing, hidden, rejected or merely proposed point never silently becomes selected evidence.

An edit batch has `version: 1` and `operations`. Supported operations are:

| Operation | Fields |
| --- | --- |
| `landmark` | `name`, complete `value` or null to remove |
| `region` | `name`, complete `value` or null to remove |
| `observe` | `name`, `cel`, complete observation `value`; optional `view` |
| `solve`, `view`, `tracking` | `values` containing fields to update |
| `note` | `text` |

A complete landmark looks like this for a three-cel asset:

```json
{
  "role": "fit", "mode": "fixed", "reference_cel": 0,
  "cels": [0, 1, 2], "tolerance_px": 0.5, "weight": 1,
  "observations": [
    {"point": [23, 39], "visible": true, "origin": "manual", "state": "selected"},
    {"point": [26, 37], "visible": true, "origin": "manual", "state": "selected"},
    {"point": [21, 40], "visible": true, "origin": "manual", "state": "selected"}
  ]
}
```

Use the `study_sha256` returned by `inspect` for concurrency protection:

```sh
./ambiance --project PROJECT asset motion edit PROJECT/study-01.json \
  --changes PROJECT/observations.json --expect-study SHA256 --out PROJECT/study-02.json
```

Edits validate the whole resulting study before saving a fresh file and report affected cels/regions. For a click measured in a crop, add `"view": {"packet": {"file": "inspection-01/packet.json", "sha256": "..."}, "id": "region-body-1"}` to an `observe` operation. The point then uses that image's pixels, and the saved view transform returns it to source coordinates. Packet identities reject stale crops. Raw/prepared/candidate/region views have separate, stable IDs. Multiple observations can use the same packet in one batch.

Regions use either a polygon `points` in baseline full-cell pixels or a project-relative hash-bound `mask` referencing a full-cell grayscale PNG. They also declare `mode` (`stable`, `observe`, `ignore`), `cels`, `reference_cel`, `alpha_threshold` and `color_threshold` (0–255 mean absolute difference). Masks retain gray weights; ignore regions subtract their declared area from overlapping regions during those cel intervals. The report includes alpha coverage/centroids, silhouette bounds and selected landmark distances. Premultiplied RGB ignores invisible RGB; the color threshold applies to straight RGB on alpha-weighted overlap. Below 5% overlap or one fully weighted pixel, color is explicitly unavailable while alpha measurements remain available. Appearance findings are advisory; they cannot identify an anatomical feature or automatically justify a correction.

## Solve and build once from the original inputs

```sh
./ambiance --project PROJECT asset motion check PROJECT/study-02.json
./ambiance --project PROJECT asset motion solve PROJECT/study-02.json --id ASSET-v2 --out PROJECT/proposal-02
./ambiance asset build PROJECT/proposal-02/compiler.json --out PROJECT/assets/compiled/ASSET-v2
./ambiance --project PROJECT asset motion proof PROJECT/study-02.json \
  --candidate PROJECT/assets/compiled/ASSET-v2 --out PROJECT/comparison-02 --context-seconds 2
```

The solve permits translation only and keeps the reference cel unchanged. `solve.cels` and `solve.unchanged` must partition the sequence. Every fixed constraint must have a selected observation, stay within its tolerance, and respect the declared maximum shift in display pixels. Conflicting fit/check points remain unresolved; an average cannot hide their residuals. An unresolved solve saves a diagnostic report and returns nonzero without a compiler recipe.

The compiler preserves cell size, frame order, pivot and shared scale. It composes each translation with the recorded raw-to-cell mapping and resamples from the original inputs once. Insufficient padding is an error with the required extra space; no shrinking or clipping is substituted. Candidate publication is atomic and refuses overwrite. Typed `motion_preparation` provenance is verified on build, cache lookup, pack inspection, admission, scene transactions and revision capture.

Declare each asset socket and layer override as `fixed_mount` or `follow_art`. Following sockets receive the corresponding per-cel translation; mounts retain their coordinates. Context proofs use the real renderer, inherited transforms, cel holds, scene grades and rendered shadows. Object-bound grade masks, alternate caster masks and art-bound light rectangles currently require a separate companion revision and block automatic context/adoption. The tool does not infer semantic bindings between independent scene layers.

A successful scene-bound proof contains `adoption.json` and the expected working scene hash. Admit the new pack, then apply that transaction with `scene apply ... --expect-sha256 HASH`. Existing scene snapshots supply restoration. A changed working scene is reported separately from the captured proof; review/rebase the transaction before adoption. A proof never edits a production scene itself.

## Propose tracking, then select evidence

```sh
./ambiance --project PROJECT asset motion track PROJECT/seeds.json --out PROJECT/tracked-01
```

The first adapter is `pillow-patch-ncc-v1`: local integer cell-pixel patch search, reference and neighboring-cel agreement, reverse checking, texture and ambiguity rejection. Pillow is sufficient; no OpenCV, model download or GPU is required. Stable region masks can restrict seed patch evidence. Work is bounded before search. Search radius, patch radius, correlation, ambiguity margin and disagreement limits live in `tracking`.

Outputs include a new study and detailed per-point diagnostics. Proposed observations stay `state: proposed`; choose useful points in an explicit `observe` batch with `state: selected`. Weak or disappearing features stay unresolved/null. Rejected/hidden annotations remain intact. Scores are not probabilities, and apparently good tracks still need spot checks. Repeating an identical request reuses verified output; changed inputs/settings/code require a new directory. The adapter is deliberately conservative: the initial painted-flame trial produced no acceptable automatic wick matches.

## Optional inspection and draft editing

```sh
./ambiance preview --motion PROJECT/comparison-02 --port 8791
```

Open the returned localhost URL. Both panes use one clock. Choose raw, prepared or captured scene views; pause/seek; inspect ordinary transitions and the loop join; toggle onion skins, trails, region outlines, light/dark grounds or temporary original alignment. Temporary alignment never changes solve measurements or built pixels.

Pause, select a landmark and click the original pane to revise a draft point, or edit its tolerance. The server validates the draft and uses the same Python solver and raw-input compiler function as the CLI. A failed correction shows unresolved constraints without presenting a ready draft. Scene context remains the labeled saved candidate until a new contextual proof is built. Export downloads a new study; the server never writes project changes. Draft editing requires the pinned project inputs to remain available; captured proof images can still be inspected independently.

## Reproducible fixture

Run [create_fixture.py](../examples/cel-motion/create_fixture.py) with a fresh `--out` project directory. It creates independent known drift, intentional head movement, a child attachment and unequal holds. `observations.json` supplies an explicit batch; `fixture-truth.json` records independent expected corrections. Follow the commands above with layer `figure`.

The manual path, tracked-selection path, fixed geometry, stale identities, independent checks, soft regions, ambiguous/disappearing features and HTTP drafts are covered by `tests/test_asset_motion.py`. Run `./ambiance test` for the shared regression suite. Browser raster and encoded-media observations are separate evidence; a passing numeric check is not an artistic review.

Later work remains: learned trackers, scene contact constraints, velocity/join analysis for new continuous curves, and a cloud deformation experiment. No automatic in-betweening, local warp or new artwork generation is implemented here.
