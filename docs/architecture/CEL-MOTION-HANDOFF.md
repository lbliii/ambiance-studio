# Cel motion implementation handoff

Milestones 1–3 are implemented through the CLI and a localhost workbench. [Usage and boundaries](../CEL-MOTION.md) describe the executable contract. Compiler 1.3 supports typed motion correction; the studio's renderer and existing scene interpolation are unchanged. Milestones 4–6 remain planned.

## Evidence from the isolated pilot

The local project `projects/cel-motion-release` contains a synthetic tooling fixture and copies of existing painted inputs. No production project was edited and no artwork was generated through a paid service. The synthetic example is reproducible from [create_fixture.py](../../examples/cel-motion/create_fixture.py).

- Three independent source cels contain known drift: `[0,0]`, `[3,-2]`, `[-2,1]`. The solver recovered `[0,0]`, `[-3,2]`, `[2,-1]` exactly. Corrected planted body pixels match exactly, while the independently moving head retains its different positions. The independent shoulder check was excluded from fitting.
- A one-point tracking seed plus three manually authored independent checks produced two usable foot proposals. Selecting them through a separate CLI batch produced the same corrected atlas as manual annotation. Two target observations were saved, with zero incorrect selected proposals in this small synthetic case. This is a functional fixture, not a general tracker accuracy estimate.
- Contradictory check points, clipping, changed sources, stale views, altered compiler geometry, repeated marks, textureless patches and disappearing features are covered by focused tests. Failed drafts do not produce ready candidate pixels. Browser-origin and draft dependency checks are exercised through localhost HTTP.
- Unequal holds of 0.5 / 1.0 / 0.5 seconds come from the shared scene evaluator. The captured context includes camera movement and a child attached to a layer socket override. The generated adoption transaction applied successfully to the isolated project and retained a restoration snapshot.
- A four-second H.264 fixture contains two two-second loops at 12 fps, 256 × 256. Native verification decoded all 48 frames, found zero timestamp error and identical decoded first/repeated-start frames. The last-to-first difference remains nonzero because the head/cel pose deliberately changes there. Endpoint equality does not mean a motionless or aesthetically approved seam.

## Agent operation and measured costs

Single local runs, not statistical benchmarks:

| Operation | Wall time | JSON result size |
| --- | ---: | ---: |
| Manual batch edit | 0.25 s | 555 bytes |
| Manual source analysis | 0.22 s | 2.1 KB |
| Manual solve | 0.26 s | 494 bytes |
| Candidate compile | 0.22 s | 286 bytes |
| Two-second context proof | 0.77 s | 2.3 KB |
| Cold point tracking via CLI | 0.38 s | 501 bytes |
| Repeated identical tracking request | 0.15 s | 521 bytes |

The tracked study was resumed from its saved artifact and selected in one batch; no source hashes or crop transforms were copied into hand-authored study JSON. This still required inspecting the proposed points and preserving independent manual checks. The browser draft export path and compiler produced equal decoded pixels on the same runtime. Large scene proofs and dense landmark intervals have explicit work limits; these timings do not claim interactive performance for production-sized frames.

## Painted inputs and observations

Copied eight-cel museum rat and flame sequences, plus an eight-cel Last Lantern cloud sheet, were rebuilt/inspected inside the pilot with source ledgers. The cloud's existing prepared sheet was explicitly declared as a new compiler input; no earlier raw-art provenance was invented.

The flame identity correction retained every decoded baseline pixel with its previously recorded wick anchors. The default patch tracker proposed **0 of 7** flame targets: shape/appearance change caused low correlation or propagation stopped after an unresolved match. Those points remained null and the command returned a diagnostic nonzero result. Manual anchors are necessary for this case; no threshold was loosened to manufacture success.

Actual contact-sheet inspection showed flame tips changing height/direction while the dark wick stayed at its base, rat leg extension changing through its run, and cloud curl/silhouette evolution. Rat and cloud changes were not declared unintended drift. The contact sheets were inspected as still evidence, not continuously watched clips.

Browser inspection covered a flagged cel transition, light/dark comparison, a valid tolerance draft, a deliberately incorrect clicked observation, reset, and the actual-cadence scene context. The incorrect point exposed both the shift bound and the independent shoulder conflict. Raster and native decoded contacts were inspected separately; no human artistic approval or continuous encoded-video audition is claimed.

## Remaining boundaries

The tracker searches integer cell pixels and is conservative on changing painted shapes. Manual observations support subpixel coordinates. The optional viewer needs the pinned project inputs for draft evaluation; its captured image proof remains inspectable independently. Layer initialization records display width at time zero; it does not measure animated world contact. Semantic relationships between independent layers are not inferred.

Object-bound grade masks, alternate caster masks and art-bound light rectangles block automatic context/adoption until a separate companion correction is authored. Unmasked grades, ordinary receiving effects and shared renderer behavior remain supported. Learned tracking, contact constraints, continuous curves/velocity checks and cloud deformation remain future work.

## Verification record

Final checks: 207 Python tests passed with six explicitly skipped (213 total), plus the engine, rig, tracks, source-placement, finishing and package checks. The 18 focused motion tests passed. Pre-merge review also corrected weighted patch correlation so mask edges cannot become texture, and snapped odd-length context proofs to the actual output-frame clock. An existing discovery test now selects its fixture by ID instead of assuming it is the first local project. The final captured context proof occupied about 248 KB, took 0.62 seconds internally, and resumed through the CLI in 0.27 seconds on this machine.

The final shared regression result and local artifact identities are recorded in the pilot's `implementation-evidence.json`. Local generated evidence is excluded from source control; the fixture creator and focused tests are tracked. Run `./ambiance test` to repeat the shared checks. A native tooling fixture is not a production film delivery or a selected museum review edition.
