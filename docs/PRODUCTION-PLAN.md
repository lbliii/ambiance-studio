# Production intent contract

`plans/production-plan.json` is the one executable statement of story and creative scope. Version 1 uses `format: ambiance-production-plan` and `schema_version: 1`. The [example](../examples/production-plan.json) is a proposed nearly-still, single-format scene; its empty realization references deliberately describe work that has not been produced.

The plan owns the five semantic dimensions (`kind`, `depth_band`, `motion_role`, `cadence`, `readability_target`), actions and expectations. Readability 0–4 means still, trace, readable, featured and dominant. These are targets, never inferred observations. Element cadence describes its intent; optional action timing targets state maximum onset/rest and minimum duration in seconds. Per-action/view readability targets refine the element default. Actual timing, geometry, painter order, bindings and assets remain in scene/catalog. Inventory owns fulfillment stages and evidence; reviews own observations. No layer quota or aggregate aesthetic grade is computed.

Each element maps to zero or more `realization.inventory_parts` (`{item_id, part_id}`) and `layer_ids`. `realization.method` is `baked`, `cutout`, `rig`, `mask` or `painted-effect`. `required_art` names source, cutout, backing, occluder, mask or painted-effect obligations and their inventory part. Multiple semantic names on one plate do not establish independent control. Planned references may be unresolved; coverage, rather than syntax validation, determines readiness.

An action can narrow its realization using optional `layer_ids`, a subset of its owning element's layer references. A static parent or unrelated companion must not satisfy a gesture requirement.

Sources and relation dependencies use project-relative `{path, sha256}` identities. Relations join stable source/target element IDs; `scene_ref` is a runtime reference (or null while unimplemented). Outputs name the existing saved view IDs and requested soundtrack roles. They do not redefine a view's geometry.

Expectations require rationale, direction, a first applicable stage (`layout`, `assets`, `animation`, `export`), explicit `view_ids`, `element_ids`, `action_ids`, `relation_ids` and a requirement. Structural checks are `view`, `independent-control`, `art`, `relation`; measured checks are `raster`, `movie`, `activity`; observed checks are `readability`, `composition`, `lighting`. An activity requirement can name a metric and a finite minimum/maximum. Empty scope is valid to inspect, but never means complete production. Later stages include earlier requirements; animation does not require future export evidence.

## Authoring and explicit migration

```sh
./ambiance --project PROJECT plan spec inspect --details
./ambiance --project PROJECT plan spec apply proposal.json --dry-run
./ambiance --project PROJECT plan spec apply proposal.json --expect-sha256 absent
./ambiance --project PROJECT plan complexity
./ambiance --project PROJECT plan spec migrate proposal.json --original plans/asset-inventory.json --original plans/layer-notes.md --out PROJECT/checks/plan-migration-1
```

Every replacement identifies the exact previous file hash in `change.supersedes_sha256` and explains `change.reason`. First creation uses null and can compare against `--expect-sha256 absent`. Dry runs return a reviewable diff. Apply takes the shared project lock, validates sources, checks concurrent edits and saves the previous bytes under `.ambiance/plan-history/HASH.json`. To restore earlier intent, use that snapshot as the proposal, update its change reason/predecessor, then apply normally: rollback itself is an explicit scope revision.

Migration requires an authored JSON mapping proposal and explicit original paths. It does not guess typed meaning from prose. The fresh artifact directory inside the project contains unchanged original copies, `candidate.json`, and a report/diff; it does not modify the project plan. The candidate pins those preserved copies, so live inventory fulfillment can evolve independently. Review the candidate then apply it. Legacy optional/deferred flags that contradict a plan requirement yield stable `plan.required-contradiction.*` issues and prevent saving until reconciled. Originals and sealed reviews are never rewritten or granted new verdicts.

## Consumer API and evidence identities

`ambiance_studio.production_plan.load(project)` returns validated intent. `load_context(project, revision=None)` returns `{plan, path, plan_sha256, expectation_sha256, revision}`. `plan_sha256` is the exact saved file hash; the expectation map uses the repository's canonical JSON hash. Captured context uses the `production_plan` control role; legacy revisions without it remain legacy. `validate_binding(project, {element_id, inventory_part:{item_id,part_id}}, plan=None)` checks the declared mapping and actual inventory entry. `complexity(plan)` returns separate workload counts.

Evidence providers must identify their actual receipt kind/version, exact scene/catalog and view identity, source/dependency hashes, plan file hash, expectation hash, and captured revision where applicable. State/geometry reports cannot satisfy a raster or movie expectation. A file path, nonempty report, metric or catalog admission cannot establish an actual artistic observation. Providers own runtime and artifact validation; the shared coverage evaluator consumes those checks. Consumers must not invent another editable semantic file or infer approval from these identities.

## Coverage and evidence registration

```sh
./ambiance --project PROJECT plan coverage --stage animation
./ambiance --project PROJECT plan coverage --stage export --revision draft-1 --details
./ambiance --project PROJECT plan evidence composition-pixels --view portrait --revision draft-1 --receipt render/paired/render-report.json
./ambiance --project PROJECT plan evidence final-movie --view portrait --revision draft-1 --role silent --receipt revisions/draft-1/editions/portrait-silent.json
./ambiance --project PROJECT iteration preflight iteration.json
```

`production_coverage.evaluate(project, stage='animation', view=None, revision=None, details=False, outputs=None, phase='current')` is the shared decision API. CLI coverage, overview, iteration preflight and delivery scope consume this evaluator. Missing plans, omitted action targets, unmet expectations, contradictory legacy flags and stale/wrong-subject evidence produce `ready: false`, stable `plan.*` issue IDs and actionable gaps. The default result limits blockers to eight and names the durable full report under `.ambiance/coverage/`; use `--details` for every requirement. `--view` evaluates that explicit subset and returns `full_scope: false`.

Saved reports pin the exact scene/catalog/view/asset/fulfillment/evidence-index identities and reject inputs that change during evaluation. `project overview --stage STAGE --view ID --revision ID` selects the same coverage subject explicitly. A plan-aware passing review requires every applicable observed expectation to meet direction; unreviewed entries remain valid in an unfinished review.

Stages include earlier expectations. Animation does not demand future export movies. The `preflight` phase checks the requested scope and intended view/role pairs but lists movie expectations under `future_outputs`, because the iteration will create them. That result is preparation readiness, not completion. Iteration recipes accept `scope: proof|review|final` (default review for compatibility). Proof/review runs remain renderable and presentable with honest gaps; final runs require passing preflight and current export coverage after encoding. New movie evidence is registered against the exact captured plan. Reduced output sets cannot make a final claim complete.

`plan evidence` verifies the provider before saving a sealed `ambiance-plan-evidence` schema 1 wrapper. Its subject pins exact plan, expectation, scene, catalog, view and revision hashes, plus declared source/driver dependencies. Inventory `expectation_evidence` contains only `{path,sha256}` references to these immutable records. It does not duplicate editable requirements. Registration is resumable and preserves the previous inventory bytes.

A smaller proof/review movie remains presentable when it cannot satisfy the planned final dimensions. Automatic registration records `evidence_registration_gaps` in the iteration readiness result; export coverage remains unmet and no final-size evidence is admitted.

Supported picture evidence is an explicit-view `render frame` or synchronized `render views-proof` report. Validation checks exact snapshots/view definitions, hashes and decoded PNG dimensions. Movie evidence must be a canonical captured edition with complete decode evidence, matching view and explicit soundtrack role; actual native decoding is cached by exact movie/expectations for warm readiness checks. Raster generation proves pixels exist; it does not prove that the composition or motion meets direction. Activity receipts are delegated to the activity provider when installed in the codebase; absence remains a gap.

Captured revision review drafts include applicable observed expectations with `status: unreviewed`. A performed observation records its exact view/expectation, named agent or human, note, actual display dimensions, normal-speed flag and typed raster/movie references. Readability records retain observed level separately from the target. Unperformed checks are never filled automatically. Original legacy reviews and editions remain sealed with their old subjects; a new capture binds the new plan instead of retrofitting intent onto an old movie.
