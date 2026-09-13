# Stream M first-assignment handoff

Base: `00c64436543d0252fc0850f3ef58e686badda1b6`. Branch: `codex/model-character-contract`. Worktree: `/Users/lb/.codex/worktrees/174e/ambiance-studio`. Packet: **mc/1**. The coordinator receives the exact delivery commit with this handoff; nothing is pushed, merged or published.

Delivered paths are this `docs/architecture/model-contract/` packet, `tests/fixtures/model-contract/`, `tests/test-model-contract.mjs`, and a two-line packet link in the reusable-model plan. No engine, production runtime, central CLI/output/bridge, backlog status, canonical media or review was edited. The development test is automatically registered through `diagnostic_commands.test()` → `checks.run_suite()` and its `.mjs` glob.

The [decision table](README.md#decision-table) and [implementation slices](implementation-v1.md) resolve the shared identity/pin/adoption, registration/local coordinates, clock consumption, ownership/mount/order/depth/light and derived-evidence boundaries. These are selected contract meanings pending coordinator integration, not implemented model or narrative capabilities. P02 specializes the common registered model/drawing foundation; P03 can proceed with current flat scenes and the pinned time vectors without waiting for the model library.

## Executed validation

| Check | Result |
| --- | --- |
| `node tests/test-model-contract.mjs` | 10 grouped positive/negative specimen checks passed |
| `node tests/test-source-placement.mjs` | 8 current registration/timing checks passed |
| `node tests/test-rig.mjs` | 7 current attachment/graph checks passed |
| `python3 tests/test_assets.py` | 10 compiler checks passed |
| `python3 -m unittest discover -s tests -p test_roadmap.py -v` | 2 actual discovered tests passed |
| `python3 tools/package_audit.py` | Links, capability routes, owning roadmap and bundled source/scene integrity passed; exact final count is in the check record |
| Current public CLI timing and reparent dry-run | Passed; world-corner error `5.684341886080802e-14` pixels at time zero |

See [checks.json](evidence/checks.json), [the focused output](evidence/contract-check.json) and [the artifact manifest](evidence/artifacts.json). The manifest records exact packet/specimen bytes, and selected replay artifacts with SHA-256. Raw package/CLI stdout and stderr remain at `/private/tmp/ambiance-mc1-validation-20260913/`; the small generated source-placement project is `/private/tmp/ambiance-mc1-placement-20260913/`. These local replay outputs are supplemental evidence, not dependencies of the committed specimens.

The initial direct roadmap-file invocation did not run unittest cases; the final discovery invocation above ran both. An initial contract negative case targeted a nonexistent path; it was corrected to an existing escaped path and rerun. No unresolved focused-test failures remain. Full/native tests were not repeated: the coordinator explicitly refined this design-only assignment and owns validation of the unchanged runtime baseline. No native encode/decode, browser/raster inspection, human audition or artistic review is claimed here.

## Replay

Choose a fresh fixture output directory; the following uses a new example name rather than overwriting retained evidence:

```sh
node tests/test-model-contract.mjs
python3 examples/source-placement/create_fixture.py --out /tmp/mc1-handoff-replay
./ambiance --project /tmp/mc1-handoff-replay scene timing --layer gesture
./ambiance --project /tmp/mc1-handoff-replay scene reparent gesture --to body --socket hand --keep-world --at 0 --dry-run
python3 -m unittest discover -s tests -p test_roadmap.py -v
python3 tools/package_audit.py
```

This is an existing public CLI registration/transaction replay. There is no new `ambiance model` command or finite-scene route in this delivery.

## Remaining acceptance and next dependency

Coordinator review/integration of mc/1 is the next dependency. Then C1/C2 can construct one local immutable lantern package and I1/I2 can introduce independent instances/adoption over existing services. P03 can start independently from the integrated clock packet; P02 uses the same IDs/registration and P04's acceptance still requires actual P02/P03 integration. Public hook/typed evidence changes require their named owners and new runtime acceptance evidence.

Production seed selection, canonical film address, complete full-scene census, required actions, hidden surfaces, receiver needs, portrait/landscape compositions, storyboard, real art/takes and observed acceptance remain unresolved. Phase 1 and P00 are not complete. The next model runtime, typed evidence adapter, full scene and second-scene trials are still required; geometrical fixtures and silent PCM do not reduce their scope. Stream M stops after this first assignment and awaits an explicit continuation.
