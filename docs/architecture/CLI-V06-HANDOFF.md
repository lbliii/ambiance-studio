# CLI 0.6 implementation handoff

The museum production trial exposed repeated coordinate reconstruction, fallback-clock timing reports, and reviews that could watch legacy folders instead of the selected media. Version 0.6 addresses those problems and implements the inspection and picture-reuse helpers from the next-pass plan.

## Delivered behavior

| Area | Result |
| --- | --- |
| Timing | `scene timing` and project checks distinguish regular clocks, cell tracks, holds, inherited visibility and output-frame sampling; overridden legacy `cel_fps` is null |
| Revisions | Capture mutable control documents and pin typed art/audio dependencies; distinguish working divergence from stale revision evidence |
| Reviews/editions | Reuse the existing criterion validator with exact revision/edition subjects; retain legacy records and never transfer a pass automatically |
| Placement | Place native cutouts using compiler/crop mapping or generated sprites using explicit intended size; reparent at a chosen time without changing the reference pose |
| Preparation | Decode alpha facts, export source crops and return explicitly registered edits as immutable derivatives |
| Rig proofs | Save rest/extreme/hidden-part samples, context/detail comparisons and actual-speed playback; report selected sample coverage explicitly |
| Media | Reuse identical compressed picture samples for alternate PCM editions, completely decode outputs and extract requested action frames |

Exact interfaces live in the [CLI reference](../CLI.md), [revision contract](../REVISIONS.md), [placement contract](../SOURCE-PLACEMENT.md), [timing contract](../SCENE-TIMING.md), [asset preparation guide](../ASSET-PREPARATION.md), and [rendering guide](../RENDERING.md).

## Validation

The complete native-enabled `AMBIANCE_TEST_NATIVE=1 ./ambiance test` passed 127 Python tests without skips, the engine, rig, authored-track and source-placement Node suites, and the package/link audit. Native execution used actual macOS media services; it was not inferred from capability discovery. Focused review found and fixed a capture race that could validate different bytes from those saved, and a catalog/pack mapping mismatch that could lose a source dependency.

The [public CLI pilot](../../examples/revisions/README.md) ran 21 commands in a fresh synthetic project. It placed prepared parts, reparented the gesture and rim, and preserved the reference-pose RGBA pixels exactly. It produced a rig inspection matrix, two explicit PCM mixes, a frozen revision and two encoded editions from the same picture. Both editions fully decoded to 240 video frames and 384,000 presented audio samples per channel. Compressed video sample payloads were preserved. A requested 3.67-second contact came from the actual movie.

The pilot then changed the working scene and confirmed the captured revision stayed valid, changed a pinned body atlas and received a nonzero integrity failure naming it, restored that atlas and passed again. It used saved placement manifests and public commands rather than project-specific coordinate calculations or direct native-binary invocation. Synthetic audio and geometric art are engineering fixtures, not creative examples or film approvals.

Local evidence is kept under `work/cli-v06-operator-pilot/` (command receipts, summary, proof images, encoded editions and revision records) and `work/cli-v06-regressions-final.json`. Working evidence is excluded from Git; the reusable pilot scripts and regression fixtures are included as repository source. The prior bundled engine also retained exact sampled state in 487 baseline comparisons.

Actual browser inspection passed in Chrome for Testing through the native CUA controls: the attached body/gesture/rim lift, fixed glass, hidden descendants, detail/difference images, playback, pause, seek and half-speed selection worked. The evidence at `work/cli-v06-operator-pilot/reports/browser-review.json` binds the exact saved scene/catalog, HTML and inspected images and verifies all 131 PNG receipt hashes. It identifies the later report-metadata correction, which changes no inspected HTML or pixels. A desktop browser inspection does not establish a physical-phone, listening, artistic or full-loop review.

## Boundaries and adoption

- Binary dependencies remain pinned to existing project paths. Preserve those versions; a changed pinned WAV, movie, image or source is detected rather than silently replaced.
- Reparenting preserves one specified world pose. Existing sinusoidal motion continues in the new parent's axes. Child transform tracks require an explicit authored revision; full trajectory rebaking is not implemented.
- Generated sprites need an intended size and anchor. Image dimensions or alpha bounds cannot determine their physical scene size. Crop return requires explicit registration.
- Native composition supports the documented CFR H.264/macOS/48 kHz PCM boundary. It does not add another rendering platform, processing workstation or provider queue.
- An externally prepared master needs declared source/recipe/output identities. Recording those identities does not execute or certify an external processor.
- Captures, proofs and catalog admission do not pass aesthetic gates. Existing feedback applies only to the exact subject and criteria it addresses.

No active museum scene, artwork, soundtrack, review or deliverable was migrated or edited by this implementation. An operator can adopt the revision commands explicitly after finishing their chosen production state. The broader audio-preparation adapter, provider orchestration, rig-package migrations and historical effect ports remain deferred as planned.
