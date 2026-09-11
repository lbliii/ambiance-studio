# Production inventory and asset proofs

`plan inspect`, `plan check` and `plan next` read `plans/asset-inventory.json` in the selected project. Use `--inventory PROJECT_RELATIVE_PATH` for another plan. New projects start with an empty inventory, which is explicitly reported as not yet authored. Existing projects can add a version 1 inventory without migrating the executable scene.

```sh
./ambiance --project projects/the-midnight-collection plan inspect
./ambiance --project projects/the-midnight-collection plan next
./ambiance --project projects/the-midnight-collection plan check --out projects/the-midnight-collection/reports/inventory-check.json
```

The check reconciles declared assets and parts with the actual project catalog, scene, hashes and dependencies. Missing planned work is normal incompleteness; broken references, stale evidence, fabricated completion and dependency cycles cause nonzero failures. `next` returns up to five incomplete work items whose declared prerequisites are satisfied, ordered by authored priority; use `--limit N` for more. It executes no production actions. Corrupt inputs produce no ready-action list. Deferring a dependency does not fulfill another object's requirement for that produced part.

Use `plan check --require-complete` before claiming declared production scope complete. It also fails empty inventories and unfinished/transitively blocked items, and returns `completion.outstanding` with IDs and next actions. It permits optional, deliberately deferred items. A nonzero result does not prevent showing a labeled partial draft or continuing production.

Mark selected requirements with optional boolean `required: true`. Such items must have tracked `required_parts` and cannot be `static-deferred`; changing the declared artistic scope is an explicit project decision. Omitted `required` retains legacy behavior. Existing version 1 inventories need no migration, and ordinary `check` still allows honest incomplete work. The completion check reuses the same evidence/dependency evaluator; it does not infer objects, validate unwritten format requirements, or turn pending artistic reviews into approval. See [seed-to-stage production](SEED-TO-STAGE.md).

## Version 1 inventory

```json
{
  "version": 1,
  "items": [
    {
      "id": "rat",
      "name": "Near-floor rat",
      "state": "not-produced",
      "priority": "next",
      "method": "painted gait cels plus authored travel",
      "existing_asset_ids": [],
      "required_parts": ["registered gait", "contact shadow"],
      "dependencies": ["floor-repair"],
      "next_action": "Prepare the gait after its floor backing exists."
    },
    {
      "id": "floor-repair",
      "state": "not-produced",
      "priority": "next",
      "required_parts": ["rat-free tiles"],
      "dependencies": [],
      "next_action": "Repair the original animal and shadow footprint."
    }
  ]
}
```

Optional reference identity uses `reference: {file, sha256}`. All paths in inventory evidence are project-relative, cannot contain `..`, and remain inside the project after resolving symlinks. `id` values are unique. Existing asset IDs identify ingredients, never fulfillment of the missing parts. `method`, `location` and `next_action` are authored descriptions; the CLI does not infer object boundaries, source technique or physical realism from filenames.

Supported declared states are `planned`, `in-progress`, `not-produced`, `partial-light-only`, `keep`, `implemented-subtle`, `static-support`, `static-deferred` and `complete`. The retained states require actual scene use to satisfy scope; static-deferred is explicitly unscheduled. The project-specific states preserve compatibility with the museum's inventory. A `complete` declaration requires completed structured parts.

Priorities sort as `next`, `prepare-with-flame`, `exploration`, `preserve`, `retain-or-tune`, `retain`, `retain-or-disable`, `optional`, then other authored labels. Prerequisite dependencies determine readiness before this ordering. The inventory is a worklist, not a scheduling or generation service.

Replace a planned string with a structured part as work progresses:

```json
{
  "id": "run-cycle",
  "description": "Near rat gait",
  "stage": "placed",
  "target_stage": "placed",
  "files": [{"file": "assets/production/rat-v1/atlas.png", "sha256": "ACTUAL_SHA256"}],
  "asset_id": "rat-v1",
  "layer_ids": ["near-rat"],
  "review": {"state": "pending"}
}
```

Stages are `planned`, `source`, `prepared`, `compiled`, `placed`. Non-planned stages require hashed file evidence. Compiled/placed stages require a real catalog asset; placed also requires matching scene layers. `target_stage` defaults to placed; a prepared backing/reference deliverable can intentionally stop at prepared. Production completion is separate from artistic review.

Review states are `pending`, `accepted` and `needs-revision`. The last two require an `evidence` list of hashed files. A pending review is not reported as accepted. A produced part with needs-revision remains actionable, even though its recorded production stage remains placed. This inventory does not replace the studio's gate receipts or validate the truth of a written artistic observation.

## Discover and inspect actual assets

```sh
./ambiance library find flame
./ambiance library inspect flame-cels
./ambiance asset inspect assets/compiled/smoke-v1
./ambiance asset proof flame-cels --landmark wick --fps 6 --out work/flame-study-01
```

Library search includes the bundled catalog, an explicitly selected project, and initialized projects under `projects/` (override with `--directory`). Results include source/proof paths, origin metadata and integrity. They do not grant artistic approval or promote an asset into an accepted library. Use `library inspect ID --catalog PATH` or `asset proof ID --catalog PATH` to select an exact catalog when IDs appear in several projects. `asset proof` also accepts a compiled pack directory.

Asset inspection reports actual cel slots, distinct decoded RGBA cels, and distinct alpha shapes. These are descriptive facts, not a score: holds repeat frames intentionally, and opaque local patches can change visibly while retaining identical alpha. Authored method records still explain whether the source consists of painted poses, interpolation, rigid cutouts or light modulation.

`asset proof` creates a fresh directory containing a contact sheet, prepared playback GIF, registered onion skin, HTML viewer and output hashes. Existing destinations fail. `--fps` is the inspection cadence, not an inferred production clock; `--width` controls thumbnail width. For actual placement, overlap and timing, use [render proof](RENDERING.md).

The HTML viewer exposes the original recipe frames and source anchors when their integrity can be verified. Click each source frame to adjust the named landmark, then export a new `landmarks.json`. For an uncompiled study, anchors refer to its current cells. The viewer never saves over source art or accepted packs.

## Compile exported named landmarks

```json
{
  "mode": "landmarks",
  "landmarks_file": "landmarks.json",
  "landmark": "wick",
  "target": [0.5, 0.85]
}
```

Use that object as a recipe's `registration`. The landmark file is version 1 with `landmarks: {"wick": [[x,y], ...]}`, one source-pixel point per ordered cel. Named files and inline `points` cannot be combined. The compiler validates the coordinates, applies one common scale and embeds resolved points in the portable recipe. It retains the named file's identity in provenance; changed or missing recorded landmark sources fail a rebuild. Recompile into a new version directory, then inspect and admit through the existing commands.

## Decode and return a source repair

Use `asset preflight` to inspect actual transparency before planning matte cleanup. For a bounded enlarged edit, `asset crop` preserves the native rectangle and export scale; `asset return` requires an explicitly authored registration and optional native-resolution blend mask. It creates a new mapped patch and source composite. These outputs can become inventory parts without claiming they are already compiled, placed or artistically accepted.

See [raster preparation and compiler source mappings](ASSET-PREPARATION.md) for the versioned recipes, path conventions and runnable independent example. These commands make derivatives only; they do not generate artwork or modify the source.
