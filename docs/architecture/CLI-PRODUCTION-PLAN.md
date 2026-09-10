# Production CLI design and implementation plan

Status: implemented and verified in CLI 0.5.0, 2026-09-10. Scope follows the museum pilot's six requested improvements. The commands, saved contracts, independent fixtures and validation below are executable; further provider orchestration and historical effect ports remain outside this release.

## Design

Keep `./ambiance` as the entry point and preserve its JSON result envelope, exit codes, project discovery and immutable source policy. Split new capabilities into Python modules and reuse the asset compiler and shared JavaScript scene evaluator. Commands that create artifact directories own their `--out` destination; the top-level CLI must not replace those directories with a report file.

| Workstream | Contract and commands | Acceptance |
| --- | --- | --- |
| Production inventory | Versioned project inventory; `plan inspect/check/next` reconciles declarations with files, catalog and scene | Missing parts and stale evidence are visible; intentional static/deferred objects remain valid; dependencies resolve without cycles |
| Asset proofs and discovery | Extend `asset inspect`; `asset proof`, `library find/inspect`; named landmark file input | Actual contact sheets, onion skins and fixed-anchor previews; distinct cel counts do not imply artistic quality; source hashes and originals preserved |
| Scene transactions | Versioned batch of explicit operations; `scene apply --dry-run --expect-sha256`, full inspection and track authoring | All-or-nothing validation/save, one lock/snapshot, stale-input rejection, reversible edits and explicit paint order |
| Authored movement | Optional versioned keyframe tracks in shared evaluator | Position, scale, heading, opacity/visibility and cel holds at absolute time; loop/hidden reset validated; existing scenes retain their sampled behavior |
| Rendering and verification | `render frame/proof/video`, `media verify`; scene/catalog/run provenance | Real image/proof/video outputs, independent second fixture, actual encoded inspection; runtime/backend availability explicit |
| Sound | Versioned explicit source/clip/stem arrangement; `audio inspect/mix/compare/check` | Missing or changed selected sources fail; cue positions, fades, circular tails and sample counts checked; preserved sessions and short A/B outputs |

The inventory records planned work and links to execution evidence; it does not certify that the image has no overlooked objects. Asset method declarations distinguish isolated objects, painted/interpolated poses and light patches. Production completion and creative review remain separate. Static drawing is a legitimate scoped choice.

The asset compiler remains the only registration/atlas compiler. The proof tools read its outputs and source recipe. A named landmark file maps one named source-pixel anchor across cels; the compiler still uses one shared scale. A visual proof allows landmark editing without modifying accepted packs; a new recipe/version is needed for rebuilding.

Batch scene operations act on an in-memory clone before validation and saving. Attachments define transform inheritance; authored layer order defines overlap. Camera depth must not be repurposed as automatic sorting. Near and far rat instances with fixed route occluders are sufficient for this release. New motion semantics live in the evaluator shared with the browser and renderer.

Rendering starts from the existing scene contract. Final video supports only backends actually available on the host; the proven macOS encoder is a supported initial backend, with no cross-platform claim. Frame output must have deterministic sampling and provenance, but encoded byte identity across operating systems is not promised. Preserve the observed raster-padding, startup-texture and AAC presentation-timing failures as verification cases.

Audio sources and session versions are immutable inputs. A render must not silently replace a missing source, normalize a deliberately quiet mix upward or overwrite the previous session. Technical measurements inform comparison; listening and phone observations remain explicit review evidence.

## Implementation sequence

1. Establish this design and bounded module interfaces. Preserve existing uncommitted guidance changes.
2. Implement independent inventory/assets, scene/tracks, renderer/media and audio modules with focused tests.
3. Integrate parsers, dispatch, runtime reporting and top-level error/output behavior. Update command and contract docs with only working interfaces.
4. Run `./ambiance test`, including compiler, engine, rig and package checks. Exercise invalid inputs, source changes, existing destinations and stale writes.
5. Produce independent fixture proofs and a short museum proof using existing assets. Inspect the actual browser renderer and output images; verify native encoded media when available. Keep all experiments separate from the delivered museum files.
6. Record results, known limits and concrete commands in the handoff. No paid generation, publishing, provider queue or generalized rig-version migration is included.

## Validation record

`AMBIANCE_TEST_NATIVE=1 ./ambiance test` passed **80 Python tests without skips**, the existing engine checks, rig checks, nine authored-track behavior suites and the package audit. The native-enabled run required host macOS media-service access; its restricted-sandbox attempt failed explicitly at encoder initialization and was retained as diagnostic evidence.

The native fixture rendered and encoded an independent scene, trimmed only after a verified sync frame, repeated its picture and muxed known PCM. Complete decode verified 24 video frames and 192,000 presented audio samples per channel, plus repeated-frame equality. Wrong expectations and changed/missing sources fail. Verification also checks contiguous PCM presentation, final video sample/track timing and pre/post input identity.

Browser inspection used an actual CLI-authored traveling-subject fixture, not only static sample matrices. All 40 frames had zero uncovered pixels at 135×240 and an exact raster seam. The corrected 360×640 museum comparison played at actual speed; seeking and half-speed controls worked. Browser testing found and fixed a negative initial animation-frame timestamp in the proof viewer. The rejected first proof remains clearly separate from the corrected version.

The flame proof was inspected as light/dark contact sheets and in the browser. Playback, source-cel selection and clicking the source anchor worked. The exported named-landmark contract was compiled and checked in regression fixtures. A 12-second museum sound comparison was generated from existing rendered stems; reduced-room variant B changes only explicit relative gains/mutes, and both versions reconstruct from their stems. No listening or physical-phone approval is claimed.

Local project evidence is preserved under `projects/the-midnight-collection/reports/cli-v05/`, including `full-regressions-host.json`, `browser-render-checks.json`, `render-media-regressions.json` and the implementation handoff. Working projects are excluded from Git; reusable examples and test fixtures remain checked in. The delivered museum assets, source scene and original audio session were preserved.
