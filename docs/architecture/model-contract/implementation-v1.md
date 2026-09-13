# mc/1 — smallest construction and consumer slices

These slices map to current owners at `00c6443`; they do not change phase/package statuses. C1/C2 are now implemented as the [bounded static construction contract](construction-v1.md), with [public replay](../../../examples/model-construction/README.md) and exact [artifact observations](../../../reports/model-construction/observations-v1.json). I1/I2 remain planned; broad phase/package statuses do not change. The coordinator owns central CLI/output/bridge hooks and shared evidence/media integration. Request a narrow lease before editing those hooks.

| Slice | New work and existing owner to reuse | Completion evidence |
| --- | --- | --- |
| C1: immutable local construction | New model-definition service validates stable identities, registered parts, exact local dependencies, allowed controls and variants. Reuse `tools/asset_tool.py` build/inspect, `assets.py` raster inspection and `record_contracts.py`/`file_identity.py`. Optional source separation stays in `compound_preparation.py`; already-isolated art bypasses it. | Build/reopen one painted-root lantern with nested candle/flame and two compatible frame drawings. Reject wrong/missing pins, cycles and invalid registration before publishing; preserve old output and editable sources. |
| C2: resolved local proof/library entry | One model lowering adapter produces ordinary scene/catalog data, tuple-to-runtime mapping and source identities; use `editor/engine.mjs` evaluation and existing `tools/rig-proof.mjs`, `tools/render/raster.mjs` and `tools/render/outputs.mjs` paths. Add transparent composite/role-mask output through the existing renderer, not a second rasterizer. A typed local model record binds sources and observed evidence. | Inspect alpha/solid/glass/flame at named rest/extremes and both variants; rebuild matches registered geometry. Dependency/pose/override changes reject stale products. Geometric fixture status remains separate from art acceptance. |
| I1: independent scene instances | New instance adapter creates one complete candidate, lowers model-local placement/controls via existing engine/source-placement primitives and emits all relationships. `scene_runtime.py` transports it through coordinator-owned `tools/scene-command.mjs`; `scene_commands.py` and `scene_transactions.SceneTransaction` validate/save. | Public CLI dry-run/save/reload for two independently moved/hidden/varied lanterns. Late invalid operation/stale input saves nothing. Existing bindings/order remain intact. A retry identifies prior result or rejects duplication. |
| I2: explicit adoption and evidence | Validate previous instance pin/managed-layer fingerprint; preview retained/reset/conflicting fields. Extend `revision_dependencies.Collector` typed edges and `coverage_evidence.ProviderVerifier` through their owners. Use `revision_capture`, `revision_reviews`, existing `views`/activity providers and immutable library entry. | Old scene/revision remains on old version; new adoption is restorable and reopens affected evidence. Reject drift, changed socket interface, wrong drawing map and swapped nested dependency. Reconstruct from a self-contained local package, not a disposable worktree. |

The render bridge is `tools/render-scene.mjs`; extracted `tools/render/raster.mjs`, `outputs.mjs`, `receipt.mjs` and `source-identity.mjs` own its corresponding work. These are integration boundaries, not a request to edit all files. Before I1, exercise a construction lowering dry run on the actual lantern specimen and return any unrepresentable transform to the contract owner. Do not solve that by inventing another evaluator, attaching the model to a seed plate, or raising unrelated preparation limits.

## P02 specializes; P03 remains independent

P02 adds character view/drawing tables, source/compiler registration, complete-character reconstruction and joint/pose diagnostics to C1's identities/local geometry. A registered body, head, mouth and optional held prop remain ordinary model parts/nested slots. Character controls reference stable drawing IDs and contacts; character-view compatibility is explicit. P02 can first demonstrate the existing source-placement/rig path on isolated art while C1/C2 are implemented. It must retain the complete body and detect scale/offset mismatches, hidden duplicates and inconsistent pose registration through actual source-versus-assembly, isolate/removal and extreme proofs. Atlas indices alone are not the drawing interface.

P03 needs only the [time specimen](clock-v1.md), the current flat scene API, and independent scene fixtures. It owns `editor/engine.mjs`, `editor/timing.mjs` and common conversion helpers, coordinating changed reparent/finishing/binding consumers and receipt clocks. It can implement/test finite endpoints, local cycles, attachments and random seeks without waiting for C1–I2 or a model catalog. Preserve legacy `sample(seconds)` result shape. P04 develops selected-take/cue/drawing-map validation against pinned specimens and then demonstrates actual P02/P03 integration. P05/P06 retain their sequence/movie and aggregate-evidence ownership; this packet does not certify those formats.

## Acceptance matrix

| Check | Fixture/owner | Limit |
| --- | --- | --- |
| Definition pins, stable IDs, allowed overrides, distinct instance tuple identities | `tests/test-model-contract.mjs`; future C1/I1 public CLI | Focused specimens, not a production schema/resolver |
| Padded source → local mapping, full body, drawing identity | Character specimen; current `referenceMapping` and shared affine functions | Source/compiler visual registration still needs P02 actual raster proof |
| Mounts preserve candle/flame/frame, source hiding disables receiver contribution, front-frame order, second instance unchanged | Current evaluator state fixture | State only; no claim of clean pixels or source/receiver appearance |
| Pose/variant/override/dependency proof subject differs | Exact specimen subject comparisons | Does not implement a typed evidence provider |
| Unequal shots, end-exclusive edit/cue offsets, collapsed mouth interval | Fixed rational/integer expected tables | Finite runtime/encoding and cue importer still absent |
| Unsupported registration/mount/writer conflict rejected | Existing engine/source-placement through focused checks | No new runtime behavior |
| Real compiler/transaction path and required regressions | Public existing CLI replay below; focused contract/roadmap/package checks for this design-only handoff; `./ambiance test` for downstream shared implementation | Native skipped/failing checks must be reported when run; no artistic approval |

Current public replay (fresh output directory required):

```sh
node tests/test-model-contract.mjs
python3 examples/source-placement/create_fixture.py --out /tmp/mc1-source-placement
./ambiance --project /tmp/mc1-source-placement scene timing --layer gesture
./ambiance --project /tmp/mc1-source-placement scene reparent gesture --to body --socket hand --keep-world --at 0 --dry-run
python3 -m unittest discover -s tests -p test_roadmap.py -v
python3 tools/package_audit.py
```

The original contract-packet assignment added no `ambiance model` command. Its replay above demonstrates existing registration/evaluation/transaction capability. The later C1/C2 implementation has the separate model build/inspect/lower/proof/check/admit replay linked above; finite scenes and instance adoption remain unimplemented. The new test is automatically discovered by the existing `tests/test-*.mjs` suite rule; no central test registration patch is needed.

Discovery is verified through `diagnostic_commands.test()` → `checks.run_suite()` → the sorted `tests/test-*.mjs` glob. The coordinator explicitly refined this first assignment to focused contract/roadmap/link/package checks; it separately validates the unchanged runtime baseline. Downstream shared implementation still runs `./ambiance test` and affected native/browser checks, with actual execution/skips reported.

## Inputs still needed for full acceptance

Select the actual production seed/project, survey every meaningful visible element, preserve required actions in canonical inventory, plan portrait and landscape, and identify all backing/reveal and receiver-light needs. Choose actual art, character views, storyboard and selected takes under existing authority. Then conduct the lantern/pumpkin, tree, complete-character and second-scene reuse trials with exact raster/playback observations. These are remaining Phase 1/P00/production requirements, not implied by a committed contract or green tests.
