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

Migration requires an authored JSON mapping proposal and explicit original paths. It does not guess typed meaning from prose. The fresh artifact directory contains unchanged original copies, `candidate.json`, and a report/diff; it does not modify the project plan. Review the candidate then apply it. Legacy optional/deferred flags that contradict a plan requirement yield stable `plan.required-contradiction.*` issues and prevent saving until reconciled. Originals and sealed reviews are never rewritten or granted new verdicts.

## Consumer API and evidence identities

`ambiance_studio.production_plan.load(project)` returns validated intent. `load_context(project, revision=None)` returns `{plan, path, plan_sha256, expectation_sha256, revision}`. `plan_sha256` is the exact saved file hash; the expectation map uses the repository's canonical JSON hash. Captured context uses the `production_plan` control role; legacy revisions without it remain legacy. `validate_binding(project, {element_id, inventory_part:{item_id,part_id}}, plan=None)` checks the declared mapping and actual inventory entry. `complexity(plan)` returns separate workload counts.

Evidence providers must identify their actual receipt kind/version, exact scene/catalog and view identity, source/dependency hashes, plan file hash, expectation hash, and captured revision where applicable. State/geometry reports cannot satisfy a raster or movie expectation. A file path, nonempty report, metric or catalog admission cannot establish an actual artistic observation. Providers own runtime and artifact validation; the shared coverage evaluator consumes those checks. Consumers must not invent another editable semantic file or infer approval from these identities.
