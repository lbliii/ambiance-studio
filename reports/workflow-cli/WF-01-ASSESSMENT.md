# WF-01 assessment service and replay

Implementation boundary: shared coverage computation, scoped input reads, and explicit report persistence. The owning [WF-01 acceptance](../../docs/architecture/WORKFLOW-CLI.yaml) and [workflow design](../../docs/architecture/WORKFLOW-CLI.md) remain authoritative. No workflow catalog, guidance action system, scheduler, or artistic acceptance is introduced here.

## Interfaces

- `production_coverage.assess(project, stage, view, revision, *, details, outputs, phase, assessment, verifier)` reads coverage without creating reports, decode caches, native binaries, or writer locks. Its readiness fields come from the same policy as explicit coverage. It adds `assessment` containing component states, relevant input fingerprints, changed-input diagnostics, exact subject, completeness and a query identity. The identity is a freshness aid, not a saved review receipt.
- `production_coverage.evaluate(...)` remains the explicit persistence entry point used by `plan coverage`, `iteration preflight`, and iteration execution. Its immutable report path, compact/full projections, stage/phase semantics and exit behavior remain compatible. `coverage_records.format_report` is pure; `save_report` owns the saved report.
- `coverage_context.AssessmentInputs(project, revision)` lazily reads selected components through `get(name)`. Plan schema, inventory data and pipeline criteria can be inspected without loading scene/catalog/runtime. `finish(names)` checks the selected components and their input dependencies for changes. Components are query-local; reuse them within one assessment, then create a fresh instance to reassess. Unknown values are `None` with diagnostics. Parsed scene/catalog documents remain separately inspectable when runtime view validation fails.
- Captured controls use their exact manifest pins. Missing or stale captured material never falls back to working files. A stale captured scene does not make the captured plan or pipeline unreadable. Plan/source validity and runtime/view validity remain separate components. Full coverage retains the existing captured dependency integrity requirement as a separate `revision_dependencies` component; independent material reads do not acquire it.
- `project overview` and `project next` use pure assessment. Overview carries `subjects.working` and `subjects.selected_movie` separately; the latter preserves each selected entry's revision, edition, view, role and movie identity. Existing current selection, working hashes and review fields remain available.
- Delivery `production_scope` uses pure assessment and returns per-revision `assessments`. Its retained `reports` field is empty because this read does not create reports. Explicit report consumers should use `plan coverage` with the desired revision.

Pure reads consume exact existing movie decode evidence. Missing cached decode evidence is unknown and names an explicit acquisition route. Registration and explicit coverage retain their existing decoder acquisition behavior. No cached receipt or raster fixture establishes an artistic or human observation.

## Public replay

Run from the repository root, choosing a fresh disposable directory:

```sh
python3 tests/replay_coverage_assessment.py --out /tmp/wf01-replay
python3 tests/test_production_coverage.py
```

The replay constructs a small supplied-art fixture, then invokes the actual CLI for all assessment, explicit coverage, raster proof and evidence registration operations. It records argv, exit codes, response bytes/hashes and unchanged project snapshots for pure reads. It exercises report reuse, portrait-only evidence versus landscape, a held writer lock on a non-writable project, stale raster evidence and malformed working scene input. Exact outputs and project files are retained in `replay.json` and its adjacent files.

Focused tests additionally cover missing runtime, independent pipeline/inventory inspection, stale captured controls, absent files appearing, concurrent plan/raster changes, selected movie versus working identity, and cold/warm/tampered movie caches. Synthetic movie-cache fixtures test identity/routing only; existing required-native tests exercise actual codecs. Run the shared `./ambiance test --require-native --artifacts /tmp/wf01-suite` once the final source tree is stable. The full run includes studio, CLI, editor and package checks.

WF-02/03 can build subject-aware stage inspection and prerequisite-aware action projection on this service after integration. Guided operations, adoption trials and full-film artistic approval remain separate work.
