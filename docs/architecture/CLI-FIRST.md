# CLI-first studio architecture

## Product priority: agent operation, human observation

User direction, September 11, 2026: the agent is the primary production operator. Optimize the toolkit for how an agent inspects state, authors bounded changes, runs tools, reads concise results, inspects rendered artifacts and resumes work. The human supplies creative direction and judges the quality of concrete results. Human observability is essential, with implementation priority following the agent's operational capabilities.

Each production capability starts with a saved contract and a callable CLI/tool path. Operations share validation and implementation with localhost. Browser interaction is optional: it can help the human inspect or adjust work, and the agent can use computer control when visual interaction is useful. It must not be the only way to author a mask, configure a look, inspect an intermediate result or advance production.

The default agent loop is inspect → author a bounded change → validate/build → inspect picture or sound artifacts → present a comparison → incorporate feedback. Return compact state, actionable errors and exact artifact paths; keep full evidence available without requiring the agent to read it on every call. Prefer useful batch operations and recoverable state over recreating every GUI gesture as an individual command. Technical evidence supports artistic judgment; the agent also inspects its own visual/listening results wherever its tools permit.

Acceptance requires an agent to run the production path from saved inputs without UI interaction. Test localhost separately for legible progress, version-specific previews, comparison and feedback. A successful browser editing demonstration alone does not establish agent ergonomics.

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

## Studio library in 0.8

The [library contract](../STUDIO-LIBRARY.md) adds a machine-local registry, project discovery across Git worktrees, immutable delivery sets, append-only presentation selections, movie streaming and exact-version feedback. `production.py` composes existing capture/render/compose/verify functions into resumable local iteration runs. `project overview` joins existing review and planning results without redefining readiness. `studio_server.py` serves the library independently of working-scene validity. The editor retains its existing saved-scene boundary.

## Remaining engineering slices

The [cel motion workbench plan](CEL-MOTION-WORKBENCH.md), revised through [web research and agent operation review](CEL-MOTION-RESEARCH.md), adds multiple landmarks and motion rules, localized jitter diagnostics, constrained registration corrections and synchronized comparisons. It is planned, not implemented. Its first release includes source/layer initialization, compact observation packets, validated batch edits, translation-only correction at fixed geometry and optional bounded classical propagation. Learned tracking, scene contact/velocity tools and cloud deformation exploration follow in separate milestones.

The selected [portrait/landscape implementation plan](DUAL-FORMAT-IMPLEMENTATION.md) adds two saved views of one scene, synchronized proofs, view-bound editions and a resumable paired delivery. It is planned, not implemented. Start with its saved-view and picture-proof milestones; retain existing scene and delivery behavior through explicit compatibility adapters.

The [preparation workbench plan](ASSET-PREPARATION-WORKBENCH.md) turns the museum's mask and alignment lessons into an integrated CLI/browser workflow. Its first slice provides saved separation recipes, interactive masks/alignment and shared-engine motion proofs. The next engineering pass improves direct recipe inspection, validation, bounded edits and proof discovery for the agent; a measured agent-operated pilot on a different painting follows.

Version 0.7 adds the [finishing/edge implementation](CLI-FINISHING-PLAN.md), with opt-in shared rendering, reproducible appearance packages, all-cel matte inspection/repair, supersampling and browser look development. Future physical lighting or additional color spaces must extend the explicit contract; existing painted shadows and parallax depths do not establish full scene geometry.

1. Port the remaining historical Last Lantern effects into the supported scene contract and compare raster/encoded proofs; the new exporter only renders authored supported content.
2. Add reusable rig modules, dependency locks and migrations over the working batch interface. Preserve existing releases when library versions change.
3. Extend rendering backends and audio processing only where a new film demonstrates the need. PCM mixing does not imply synthesized acoustics, resampling or perceptual loudness analysis.
4. Add durable provider jobs with request identity, retrieval, uncertain-outcome reconciliation and budget scope. Run an independent second-scene/operator pilot before batch queues.

Each slice needs a usable CLI command, a saved contract/example, meaningful positive/negative checks and a documented capability boundary. Do not add command names that only print a future plan as if they perform production work.
