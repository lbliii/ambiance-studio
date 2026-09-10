# CLI-first studio architecture

## Decisions implemented in 0.4

The CLI is an adapter over the existing tools. It emits structured results, selects a project explicitly, and calls the shared JavaScript evaluator for scene validation and sampling. It does not recreate motion math in Python. The browser reads the same saved scene/catalog through a read-only project server.

A project owns references, prepared assets, scene, sound records, checks and review history. A repository owns code, reusable example assets, templates and workflows. The historical session archive is retained alongside the repository but excluded from Git and from preview HTTP routes.

Scene changes validate before writing, preserve the previous content by hash and use one project lock. Project initialization builds in a temporary directory, then promotes a complete workspace. `project check` checks that project's catalog rather than the bundled one. Blank projects do not claim a passing picture check. Template projects start with no accepted quality gates.

The initial source launcher needs no installer. Distributable packages will require moving runtime resources into a deliberate package/resource layout; an incomplete wheel is not offered as an installation path.

## Production additions in 0.5

The [production design](CLI-PRODUCTION-PLAN.md) adds inventory reconciliation, actual asset proofs/library lookup, named landmark files, atomic scene batches, authored tracks, shared-engine raster proofs, macOS encode/verify and explicit PCM arrangements. The [command reference](../CLI.md) links each saved contract and its executable interface. The museum pilot and independent fixtures exercise different aspects; neither mathematical sampling nor a catalog entry implies creative approval.

Inventory checks and asset proofs live in focused Python modules. The scene bridge owns mutation semantics and validates final candidate snapshots. New tracks live in the shared evaluator rather than a second timing engine. Render commands call that evaluator and its drawing implementation; native encoding is an explicit backend. Audio is a separate versioned sample-frame arrangement whose outputs can be muxed as selected PCM. The top-level CLI preserves errors, locks and snapshots, and distinguishes report-file outputs from immutable artifact directories.

## Production corrections in 0.6

The [next-pass design](CLI-NEXT-PASS.md) is implemented: shared timing reports, explicit captured revisions and edition-bound reviews, source-coordinate placement/reparenting, crop/return mappings, compound-rig proofs, and picture composition with requested decoded contacts. The [handoff](CLI-V06-HANDOFF.md) describes the independent CLI pilot and validation. Revision receipts extend the existing review validator; their typed dependencies replace folder watches only in explicitly captured scopes. Legacy review behavior remains available.

## Remaining engineering slices

Version 0.7 adds the [finishing/edge implementation](CLI-FINISHING-PLAN.md), with opt-in shared rendering, reproducible appearance packages, all-cel matte inspection/repair, supersampling and browser look development. Future physical lighting or additional color spaces must extend the explicit contract; existing painted shadows and parallax depths do not establish full scene geometry.

1. Port the remaining historical Last Lantern effects into the supported scene contract and compare raster/encoded proofs; the new exporter only renders authored supported content.
2. Add reusable rig modules, dependency locks and migrations over the working batch interface. Preserve existing releases when library versions change.
3. Extend rendering backends and audio processing only where a new film demonstrates the need. PCM mixing does not imply synthesized acoustics, resampling or perceptual loudness analysis.
4. Add durable provider jobs with request identity, retrieval, uncertain-outcome reconciliation and budget scope. Run an independent second-scene/operator pilot before batch queues.

Each slice needs a usable CLI command, a saved contract/example, meaningful positive/negative checks and a documented capability boundary. Do not add command names that only print a future plan as if they perform production work.
