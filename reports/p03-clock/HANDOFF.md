# P03 finite clock: technical handoff

Implemented on `codex/wave3-p03-clock`, based on `75d24b85a8977f234d87daa1c18993d394036c1c`. Exact tested commit: **`369546b1533c9b65d3a94ebe9148037b0f492e91`**. The subsequent handoff commit adds only this report and its [verification record](verification.json). Nothing was pushed or merged into main.

## Result

The opt-in shared clock supports finite shots, explicit local cycles and exact frame/sample conversions. One evaluated context drives motion, camera, cels, sockets, attachments, tracks, bindings, finishing and reparenting. The legacy seconds sampler retains its state-array result and prior behavior.

An authored integer duration N is authoritative; `loop_seconds` must equal N/fps. Finite movies contain `[0,N)`. Inspection at or after N holds the authored endpoint, which can differ from the final exported sample N−1. Browser playback stops at N−1 and allows separate endpoint inspection. Exact `--start-frame` and integer count transport prevent seconds-roundtrip errors. Nonzero finite audio ranges reject before work until conformance is implemented.

See the [schema/API and public command guide](../../docs/FINITE-CLOCK.md) and [replay fixture](../../examples/finite-clock/README.md). The exact helpers retain sample-alignment rejection, explicit rounding policies and signed rational residuals; no audio retiming or arbitrary rational native fps is introduced.

## Validation and retained movies

Artifact paths below are relative to the originating worktree `/Users/lb/.codex/worktrees/fc6f/ambiance-studio`. They are retained evidence locations, not bundled checkout files. The adjacent verification index binds their original paths and hashes.

`./ambiance test --require-native --artifacts .ambiance/p03-clock/required-native-2` passed **525/525 recorded cases, 509 Python tests, zero skips and 18 check groups**. All 581 recorded input files were rehashed afterward with zero mismatches, and the source tree was clean. The native slot was explicitly released to the coordinator. Run report (`.ambiance/p03-clock/required-native-2/run.json`), SHA-256 `f3770f39dc3be5f9cd3a97f8a59e925a9c75a418556f3b9e677051d1f75f0599`. Input manifest (`.ambiance/p03-clock/required-native-2/inputs.json`), SHA-256 `12cfa5910961c65735c894151bef5f516e434a8fa3eb50727783a2dc89667a5f`.

All six movies below were freshly encoded and decoded on the tested source. Counts and durations passed, with zero maximum frame-PTS error. Ranges are half-open source-frame selections. The package audit also passed after adding the handoff documents.

| fps | Source range | Decoded frames | Exact retained movie |
| --- | --- | --- | --- |
| 24 | 0–60 | 60 | Watch (`.ambiance/p03-clock/native-369546b/24-60-from-0/picture.mp4`) |
| 24 | 1–60 | 59 | Watch (`.ambiance/p03-clock/native-369546b/24-60-from-1/picture.mp4`) |
| 30 | 0–31 | 31 | Watch (`.ambiance/p03-clock/native-369546b/30-31-from-0/picture.mp4`) |
| 30 | 1–31 | 30 | Watch (`.ambiance/p03-clock/native-369546b/30-31-from-1/picture.mp4`) |
| 25 | 0–7 | 7 | Watch (`.ambiance/p03-clock/native-369546b/25-7-from-0/picture.mp4`) |
| 25 | 1–7 | 6 | Watch (`.ambiance/p03-clock/native-369546b/25-7-from-1/picture.mp4`) |

Proof manifest (`.ambiance/p03-clock/native-369546b/proof-manifest.json`), SHA-256 `53d5efd87ba4718e44d8829d1494897281d468bb88716e94cd7ec9b54b077a6e`, binds all six outputs and their receipts. These are technical review movies; they are not selected production editions.

Actual decoded contacts were inspected: full movie frame 59 (`.ambiance/p03-clock/native-369546b/24-60-from-0/verification/contacts/decoded-0059.png`) and range movie frame 58 (`.ambiance/p03-clock/native-369546b/24-60-from-1/verification/contacts/decoded-0058.png`) show the yellow source-59 cel with its middle-socket marker. The separate endpoint N (`.ambiance/p03-clock/native-369546b/endpoint-24/frame.png`) is blue with its final socket. It was not appended to either movie. Observation record (`.ambiance/p03-clock/native-369546b/observation.json`), SHA-256 `e4bd03cd7a4d2280fbbaa270b7c5a3c78f752349750f21d304589f552690515a`, records these observations and browser provenance.

The browser was checked on runtime-identical `2847b83`: a 31-frame/30-fps scene loaded, seek 31 showed the authored endpoint, and Play restarted before stopping at frame 30. Earlier actual browser checks of the 60-frame moving fixture observed its endpoint/cel/socket changes. These were technical snapshots and playback progression, not human artistic acceptance or a continuous visual-quality review.

Legacy compatibility was additionally checked against base `75d24b8` at 485 sample times, with byte-identical state arrays. Parity record (`.ambiance/p03-clock/duration-repair/legacy-parity.json`). JS tests cover unequal 60/96-frame shots, 7@25, 31@30 and 31@60, out-of-order and subframe sampling, endpoint visibility/cels/sockets, finishing pixels, reparenting, local-cycle closure and rational cue interval/rounding specimens. Public tests cover atomic authoring, stale guards/history, exact ranges, invalid requests without writes and native count/default-verification boundaries.

## Repairs preserved in the evidence

The first full run on `06a5023` failed: 520 of 523 recorded cases passed, with 506 Python tests and zero skips. It exposed prepared-editor module closure and two expected CLI-signature changes. Those were repaired before the successful full rerun. Original failed run (`.ambiance/p03-clock/required-native-1/run.json`), SHA-256 `a70ac99c98fda0e9bbe0103c2c22da46c68c940cd806992e3cff4eb95336370c`.

Further review caught floating reconstruction of authored N for 7@25 and 31@30; `1567a39` fixed the clock and narrow consumers. Actual browser inspection then caught initialization order, repaired in `2847b83`. `369546b` only corrected a new test's positional media-verification argument. Earlier media/observations retain their original identities; the six current movies above bind the successful source.

## Integration ownership

- `editor/clock.mjs` owns evaluated time, local-cycle values and JS exact conversions. `ambiance_studio/timebase.py` supplies arithmetic/CLI adapters, including `scene_frame_count`; `audio_cues.py` changes alignment arithmetic only.
- Engine, finishing, source placement, timing and audit consume the shared context/count. `engine.mjs` also exports existing scaling/rotation helpers in `c6cfbb2`; M3 already consumed equivalent `2ad22e3` separately.
- `scene_commands.py` and `tools/scene-command.mjs` expose clock-file authoring, frame/context sampling and optional local-cycle fields through existing atomic transactions.
- `rendering.py` adds the start-frame parser group. `render_plan.py` carries source start/count and finite range/repeat/audio guards. `tools/render/job-input.mjs`, `raster.mjs` and `outputs.mjs` carry integer frame identity to rendering. A3 retains codec/bitrate fields.
- Receipt additions: `picture_clock`, `clock_engine_sha256`, `endpoint_policy`, `rgba_endpoint_exact`, `last_exported_to_endpoint`, `source_start_frame`, `source_end_frame_exclusive`. Renderer and prepared-workbench copy/serve/identity closures include the new clock dependency.
- The coordinator owns broad CLI/capability/backlog registration and evaluator-source identity lists in `tools/check-scene.mjs`, `tools/activity-scene.mjs`, `ambiance_studio/views.py` and `motion_proof.py`.
- Remaining coordinator count joins: activity-scene `fullLoop` / `saved_segment_is_full_loop` raw fps×seconds comparisons; coverage-evidence `verification.loop_frames` equality; activity default counts, editor activity/region-sizing counts and M3 receiver-envelope counts. Preserve existing circular activity meanings; reading authored N does not establish finite-shot evidence coverage.

All 32 changed runtime/test/doc paths and their exact tested hashes are listed in [verification.json](verification.json). Coordinator integration should retain the tested clock semantics and reconcile separately owned hooks before its combined suite.

## Explicitly open

P00 production seed/story/census/art acceptance, P04 cues, P05 sequences and P06 film-level evidence remain **OPEN**. This handoff does not complete the short film, supply new art or voices, add model transport, conform nonzero audio ranges, enable rational native fps or establish 4K quality. No human audition, phone check, hosted-CI pass, account change or publishing is claimed.
