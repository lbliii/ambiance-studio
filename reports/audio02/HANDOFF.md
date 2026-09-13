# AUDIO-02 committed handoff

Implementation commit: `2e7aefb87b3e4911bf19d6117b6cd8e2d9b72cde`. Base: `75d24b85a8977f234d87daa1c18993d394036c1c`.
Task: `01a09b0c-90a8-7613-8e74-3804bbbcafea`; worktree: `/Users/lb/.codex/worktrees/80a1/ambiance-studio`; branch: `codex/wave3-audio02`.

The bounded implementation adds `audio measure` and configurable requested AAC bitrate, preserving the old 256000 default. 320000 was explicitly encoded and decoded. The 384000 trial is unsupported for stereo 48 kHz on this host and now fails before raster output. It is not advertised as supported and no fallback is selected. Native audio samples are decoded as unclipped float32 over the existing presentation interval; the PCM16 playback artifact and its legacy peak/RMS labels remain. Original WAV and prepared/materialized source hashes are unchanged.

## Public replay and exact evidence

`python3 examples/audio-level-replay/replay.py --out .ambiance/audio02/replay-final --native`

Replay: `/Users/lb/.codex/worktrees/80a1/ambiance-studio/.ambiance/audio02/replay-final/replay.json`

SHA-256: `13060f7932bc9a3f2656e444d713735b3b6abd51b0dfa76991ce43ff74dbe6d5`

The replay recorded 18 passing checks and all public argv/exit codes, source/artifact hashes, reference results and negative responses. Source manifest `/Users/lb/.codex/worktrees/80a1/ambiance-studio/.ambiance/audio02/replay-final/source-identity.json` SHA-256 `17f71b568949f705f79083516924471cb7360f3dc507314e5b6bcd97ae3f21e1`; aggregate source identity `f39dab3b4f31377b53d3f357333e0e85d5140d11932a9dac6cc1fcfa2d28a38f`. Meter SHA-256 `de80c3bacffb3f7c6a9a9f0ba2911efc88bf7de4e856781d8182d323b9b09c54`; adapter SHA-256 `dd253cc382d0356554c825275f8d3f78732d4117058a56d8b1d1d72478577c66`; native-source aggregate `cd9b78be4adec9082e83f242271886a54c1226ac2f0b01cc7a176f98cb39051e`.

Each successful two-second audio export contained exactly 96000 presented samples. Simple-tone estimated encoded rates were 26750 and 29824.21875 bps for the requested 256000 and 320000 settings respectively. Requested settings, actual estimate and perceptual quality are distinct.

The original synthetic PCM measured approximately −14.656878 LUFS and −17.955314 dBTP. Decoded 256000 AAC measured −14.658607 LUFS/−17.845125 dBTP; decoded 320000 AAC measured −14.656762 LUFS/−17.845125 dBTP. These are fixture observations, not targets.

Supplemental public 0.2 s high-peak encode on the same frozen source: `/Users/lb/.codex/worktrees/80a1/ambiance-studio/.ambiance/audio02/high-native/high-peak-observation.json` SHA-256 `563c56b7ff04a4ab5272ddf92962e28989776479947135f472951cd746061cf7`. Actual decoded float reached 1.009989619255066, remained unclipped in the retained stream, and measured +3.1122539839 dBTP across 9600 presented samples. Legacy PCM16 clipped at its integer limit. This distinguishes the actual measurement path from the playback copy.

## Frozen validation

`./ambiance test --require-native --artifacts .ambiance/audio02/native-final` exited 0 on the implementation commit above with **528 recorded cases / 513 Python tests / zero skips**. All 17 checks passed, including native encoding/decoding, Node renderer/rig suites, package audit and failure-contract replay. The recorded source hash matches the final public replay exactly; no tracked source changed during this run.

Report: `/Users/lb/.codex/worktrees/80a1/ambiance-studio/.ambiance/audio02/native-final/run.json`

Report SHA-256: `9db12e775179702a3c54c445b61b7597c613f2aae3acfe9ab3e1cbb9519b7225`

Inputs SHA-256: `17f71b568949f705f79083516924471cb7360f3dc507314e5b6bcd97ae3f21e1`

Python report SHA-256: `316a157d314def2f31b3ee241907f465a55d3030275d6d90cadce96d8938c923`

The native slot was explicitly released to the coordinator after completion. This handoff adds documentation/metadata only; the exact fully tested implementation remains the earlier commit. No hosted CI run is claimed.

## Changed paths

- `ambiance_studio/audio.py`
- `ambiance_studio/audio_encoding.py`
- `ambiance_studio/audio_measurements.py`
- `ambiance_studio/editions.py`
- `ambiance_studio/iteration_plan.py`
- `ambiance_studio/iterations.py`
- `ambiance_studio/media_operations.py`
- `ambiance_studio/media_verification.py`
- `ambiance_studio/render_execution.py`
- `ambiance_studio/render_plan.py`
- `ambiance_studio/rendering.py`
- `docs/AUDIO-LEVELS.md`
- `examples/audio-level-replay/README.md`
- `examples/audio-level-replay/replay.py`
- `native/media/compose.m`
- `native/media/encode.m`
- `native/media/media.m`
- `native/media/media_commands.h`
- `native/media/verify_audio.m`
- `reports/audio02/IMPLEMENTATION-NOTES.md`
- `tests/fixtures/cli-options.json`
- `tests/fixtures/cli-outputs.json`
- `tests/test_audio_measurements.py`
- `tests/test_render_services.py`
- `tools/audio-measure.mjs`

## Limits and retained failures

The EBU-defined deterministic signal checks cover integrated cases 1–5 and true-peak cases 15–19. They passed the published ±0.1 LU and +0.2/−0.4 dB tolerances. Official EBU archive retrieval returned 403, so real-programme independent references and full conformance certification remain unavailable. Silence, insufficient duration, gated values and mono cancellation are explicit. 48 kHz mono/stereo is the only metering scope.

Initial restricted media access, the weak writer preflight's 384 kbps runtime rejection, and replay fixture/schema errors remain under `.ambiance/audio02/`; no failure was counted as a pass. Generic revision checking remains input-only. Altering the float artifact blocks the selected edition's export review through `project status`; restoration clears that issue. Source provenance uses existing AUDIO-01 and LIB-01 records, with the fixture library explicitly unaccepted and independently retained outside any checkout/project.

Inspected exact final 320 kbps decoded contact: centered ochre square on dark background, a 32×32 synthetic engineering card. Picture raster/clock semantics were not changed. Original WAV and decoded AAC listening were **unperformed**; numerical checks do not establish audition, comfort, artistic acceptance or release approval. No canonical film, production mix, library promotion, paid generation, publishing or account change occurred. TV-01/02, LIB-02, MIX-01, surround and broader roadmap acceptance remain open. No hosted CI pass is claimed; prior billing-blocked GitHub jobs are unchanged.

Shared leases were approved by the coordinator: extracted native compose/encode/verify_audio plus dispatcher/signatures; audio-only render planning/execution/media verification; edition fields; typed media requests; actual iteration validator/pass-through and execution-only pending audio preflight. No edits were needed in native-process.mjs or revision_dependencies.py. Central capability/backlog/CLI documentation reconciliation remains with the coordinator.

The [measurement contract](../../docs/AUDIO-LEVELS.md) and [public replay](../../examples/audio-level-replay/README.md) document the interfaces and reproduction. [Machine-readable handoff](HANDOFF.json) carries the selected report/artifact identities and all changed paths.
