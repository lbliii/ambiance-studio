# M3: independent instances and explicit adoption

The bounded I1/I2 candidate is implemented and passes the full native suite.
Two instances can share exact contained art while retaining independent runtime
identity, placement, static controls, variants, visibility and receiver contacts.
Compatible version adoption is explicit and checks the previous package pin and
managed-state fingerprint. Project selection commits the validated scene/catalog
pair through one atomic configuration-pointer replacement.

Implementation tested: `fe2ab3eeffd587cb41df1dbd7bba9922adb65306`.
Base: `75d24b85a8977f234d87daa1c18993d394036c1c` (PR #33).
Branch: `codex/model-instances-wave3`.
Task: `01a09b0c-4fcf-7542-b921-c1b7aa265a7b`.
Worktree: `/Users/lb/.codex/worktrees/f1b4/ambiance-studio`.
This handoff and its validation index are documentation added after the tested
implementation; no native pass is claimed for a later integrated source tree.

## Interface and integration

The public project-scoped routes are `model instance apply`, `model instance
inspect` and `model instance evidence`. The [recipe and output contract](../../examples/model-instances/README.md)
documents supported operations, units, stale-state checks, adoption compatibility,
receiver bounds, output ownership and interrupted-transaction behavior. The
[capability probe](probe.md) records why standalone lowering needed an adapter.
The implementation uses the existing lowerer, affine constructors,
`reparentAtTime`, shared evaluator and scene validator.

| Surface | Result |
| --- | --- |
| `model_instances.py`, `model_commands.py`, `tools/model/instance.mjs` | Contained packages, independent namespaces, batched placement/update/adoption and inspection |
| `scene_transactions.py` | Candidate validation, dependency recheck, complete generation publication and one selection commit |
| `model_evidence.py`, `revision_dependencies.py`, `coverage_evidence.py` | Exact package re-lowering, complete managed-subject verification, typed model dependencies and wrappers over actual raster receipts |
| `revision_capture.py` | Current selection divergence for configured and historical captures without changing captured revision integrity |
| `kit.py`, `project_commands.py`, `tools/check-scene.mjs` | Explicit selected project asset root for generation catalogs, preserving omitted-root legacy calls |
| CLI/transport/fixture hooks, `tools/model/lower.mjs` | Narrow model routes, shared transport and exported socket mapping |
| `tests/test_model_instances.py`, `tests/test_revisions.py`, example replay | Transaction, identity, tamper, adoption, restore, portability and historical-selection regression coverage |

Integrate the implementation commits in order:

```text
c8a0fe6  Commit model scene and catalog through one active generation pointer
2ab73ac  Pass explicit project asset roots to scene integrity audits
2702829  Add contained independent model instances and explicit version adoption
690318d  Connect model routes and typed revision and raster evidence
70e0937  Exercise model instance transactions and portable adoption through public CLI
92e6448  Normalize optional model state collections and reject unknown instance fields
a65f630  Reuse exact contained packages after restoring pre-instance scenes
cf2c701  Track configured scene selection in revision working comparisons
1458e37  Replay restored package reuse and historical selection divergence
fe2ab3e  Keep same-batch package reuse in staged dependency validation
```

The earlier `2ad22e3` affine-export prerequisite is equivalent to the coordinator's
already-integrated `c6cfbb2`; do not duplicate it. Include all four lifecycle
successors after `92e6448`, particularly the final staged-dependency correction.
The coordinator owns broad documentation/capabilities, legacy literal-path gate
watch integration, and combined finite-clock integration and evidence. M3 did
not import T3's intermediate clock stack. T3's final clock count must come from
`compileScene(...).clock.duration_frames`, not a floating-point seconds product;
the coordinator owns adapting and exercising the combined receiver-frame probe.

## Exact validation

On the clean implementation commit, the granted native run exited zero:

```sh
./ambiance test --require-native --artifacts .ambiance/model-instances/native-final
```

It recorded **531 passed cases**, including **516 Python tests**, with **zero
skips**. All 582 recorded source files still matched after completion, and Git
status was clean. The source tree SHA-256 is
`9d60ee5138a1d621a7cf0b7ca118855dcd0fdfb4f11edb957230ecec1c1cfe46`.
The shared native slot was explicitly released to the coordinator after the run.

Retained native reports are under `.ambiance/model-instances/native-final/`:

| Report | SHA-256 |
| --- | --- |
| `run.json` | `a93b719108ff28640db53968828e73ae28f046f05fe62821c996fff367ad8c1e` |
| `python.json` | `1c42d86062bf9d1f3233d2044f68999aba5c10b0b6dd05135540217e400f212f` |
| `inputs.json` | `22bde2f2b23c6123a9fd06cce0a00a00a540d18190b59ed65a50166786c694a6` |
| `junit.xml` | `6edf30ab4b1012f04c5bc82e32593177164e0f674899242f3931778e1b6a9e6b` |

Earlier focused checks passed: 14 instance tests, 15 revision tests, 27 model
construction tests, 8 CLI contract tests, 3 scene-runtime tests, and the rig,
bindings and source-placement JavaScript checks. The full run supersedes those
as the regression authority. The separately retained complete package audit
`.ambiance/model-instances/package-audit-final.json` passed with SHA-256
`9007e260be960d32822799e6e9e4fd9647bc8cbcc88e6246e4c5be37df1720e1`.
The native runner also passed its package and intentional-failure contract checks.
The handoff documentation package audit also passed (647 local links), retained
as `.ambiance/model-instances/package-audit-handoff.json` with SHA-256
`80233468fdea4bf90195b62d233b5964d643c2fd94ec92ca66f00446cb7d436e`.

## Public replay and observations

The exact implementation commit also ran:

```sh
python3 examples/model-instances/replay.py --out .ambiance/model-instances/public-final
```

Use a fresh destination to reproduce it. The retained run contains 43 actual CLI
exits and 611 hashed artifacts. Its four listed source files and all artifact
hashes were independently checked by the coordinator. Evidence is
`.ambiance/model-instances/public-final/evidence.json`, SHA-256
`14ddc9a1875292fa451c627c972de22220ac6499be32e8b18f5beafe6c81b883`.
Open `index.html` in the same directory for the exact static raster comparisons.
The machine-readable [validation index](validation.json) binds these records.

The replay places two complete five-leaf lanterns, moves/mounts/varies/hides one,
tests its receiver contribution, captures and renders an old revision, explicitly
adopts a compatible version, restores the previous scene, restores a pre-instance
scene and places from its retained exact package, and reopens a portable project.
The original source, both package directories and original project are moved to
unavailable paths before portable inspect/check/render and old-revision rendering.
Working comparison detects active selection changes while revision integrity and
the captured old raster remain exact.

Actual measurements and agent observations:

- Moving, changing the front variant and hiding the left lantern changed 4,527,
  4,536 and 3,700 pixels respectively. The right-instance crop stayed identical.
- Keep-world mounting had maximum measured corner error
  `2.0097183471152322e-14` pixels. Hiding the source set its receiver opacity to
  zero; the unrelated contribution remained 0.8.
- Old captured pixels equal the original baseline. Compatible label adoption
  preserves the revealed raster. Portable reopening equals the restored raster.
- The inspected native PNGs show the complete left housing/candle/flame/front
  moving together, the alternate front and complete disappearance on hide.
  All eight final frame hashes match the earlier inspected frames byte-for-byte.
- The localhost editor displayed the actual portable 13-layer scene. Its frame
  audit checked 48 frames and 11 attachments. Expected exposed canvas in all 48
  frames belongs to this incomplete geometric specimen; this is no stage coverage,
  painted-film, motion, human audition or artistic acceptance.

The earlier raster/browser observations and failures remain in
`.ambiance/model-instances/observations-92e6448.json`; its queued-native note is
historical and is superseded by the exact native results above.

## Corrected failures and remaining limits

Retained failures drove the host-duration static hold adapter, explicit project
asset roots, integral-number normalization for ordinary JS edit/restore,
runtime/compiler identity mappings, complete managed-subject source verification,
configured/historical selection comparisons, and exact retained package reuse.
The first dependency recheck for retained packages incorrectly reopened a package
still staged by the same batch; three focused failures caught it, and `fe2ab3e`
corrected it. Final focused and full-native runs pass. Those failed and corrected
focused logs remain under `.ambiance/model-instances/focused-fe2ab3e/`.
The initial restricted localhost bind failed; authorized escalation succeeded.
The replay retains a Pillow `getdata` deprecation warning without skipping checks.

This supports static C1/C2 controls and conservative metadata/default adoption.
Changed drawing/socket/registration/control interfaces or nested pins conflict;
there is no implicit remapping or transitive live upgrade. Receiver paint remains
receiver-owned with explicit sampled bounds, not automatic spatial light transport
or continuous between-frame containment. Static raster evidence is not motion
evidence. Direct writers bypass the CLI lock; no filesystem compare-and-swap is
claimed. Interruption before selection may retain a complete unselected generation,
and an occupied retry rejects instead of replacing it.

Broader model Phases 4–7, character/view work, nonpaint roots, generalized clipping,
animation controls, whole-scene production and artistic acceptance remain open.
The coordinator's legacy-watch and combined finite-clock work remain separate
integration obligations. Hosted CI has not run for this candidate. No paid
generation, account change, publishing, push or main merge occurred.
