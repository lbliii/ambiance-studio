# Midnight production implementation

Implementation of the [approved design](MIDNIGHT-PRODUCTION-DESIGN.md), plus the user's subsequent cleanup-cycle and Helm-like configuration requests. The [backlog](PRODUCTION-IMPROVEMENTS.yaml) preserves all 18 original foundation tasks and adds MRR-01 through MRR-12 with explicit remaining review/trial limits. No selected movie, original art, existing capture or historical review in Midnight Reading Room was replaced.

## What is available

| Area | Implemented behavior |
| --- | --- |
| Feedback | Delivery-wide or exact-entry reports, optional point/range, separate reporter/observer, retry IDs and sealed resolution/reopen events. Studio uses the same service. |
| Operator state | Bounded overview schema 2, complete `--details`, actionable `project next`, paginated run summaries and conservative effective run health. Active unmapped assets are distinct from retained unused versions. |
| Authoring | Transactional loop-clock edits, inventory fulfillment patches with source hashes, and atomic iteration initialization over existing validators. |
| Creative comparisons | Held poses and compatible cel selections preserve object geometry and framing. Unsupported crop/socket/cell-companion substitutions fail explicitly. |
| Early review | CLI packet init/run/inspect, exact movies and source auditions, paired movie playback, interval controls and explicit presentation. Creating a packet leaves the current review unchanged. |
| Run control | UUID plus process-start ownership, separate throttled progress/heartbeats, cancellation and reconciliation, native resume and real-resolution benchmarking. |
| Preparation | Common union-cel crop with exact retained RGBA pixels, remapped anchors/sockets and compiler/capture/transaction dependency checks. Finishing/binding participants require coordinated preparation. |
| Configuration | Ordered local JSON/YAML layers, typed literal values, final overrides, origin preview and a saved resolved recipe. Existing execution contracts remain explicit JSON. |
| Cleanup | Storage and duplicate diagnostics, retention/reference checks, sealed cleanup plans, recoverable quarantine and hash-checked restore. New run records reference detailed media reports instead of duplicating them. |
| Skills | Six shorter stage skills route supported commands, establish cause/theme/emphasis, bring sound into early review, and preserve scope, original protection and honest observations. |

Use [production operations](../MIDNIGHT-OPERATIONS.md) for contracts and [the public CLI example](../../examples/midnight-production/README.md) for a runnable fixture. The [capability index](../CAPABILITIES.json) distinguishes implemented and limited interfaces.

## Measured outcomes

- The real room's overview shrank from 1,173,801 to 14,801 bytes. Its first measured query still took 12.2 seconds: reducing output did not remove expensive source/coverage evaluation. Do not claim a latency improvement from payload size alone.
- The synthetic public CLI path produced its first paired movie in 4.55 seconds on the final measured replay (six seconds in the first replay). Nine recorded commands covered creation/resume, packet inspection, untimed feedback, next work, resolution/reopening and selection preservation. No paid generation or clarification was needed. Initial fixture construction is explicitly separate from production operations.
- The same fixture's saved run record decreased from 66,128 to 18,302 bytes when step results retained exact report handles instead of nested sample arrays. Original reports remain available and hash-pinned.
- The real room contains 11,014 files, 582 JSON files and about 4.29 GB. Thirty-one exact duplicate JSON groups account for about 145 MB of extra copies. These are diagnostic counts; distinct captures/evidence are not merged. Under the default 30-day retention period, 24 recognized generated bundles were protected by age and none was eligible. A synthetic cleanup moved and restored one bundle through the public CLI.
- At the actual 1920-square internal stage, portrait 1080×1920 and landscape 1920×1080 sampled median frame times were 0.1334 and 0.1314 seconds, with peak RSS about 356 MB each. The picture-render estimate was 383.6 seconds including both views and full preroll. Encoding/composition totals remain unknown. No new renderer cache or preroll removal was promoted. The selected room uses prepared Canvas lighting; profiling this scene does not justify changing the separate linear finishing path.

## Actual room pilot and review boundaries

The original untimed curtain report is stored against `painted-review`, without an invented viewer, orientation or time. Studio displayed it as whole-delivery feedback. A separate fixture exercised entry-range submission, withdrawal and reopening through the actual browser UI. The original room's feedback remains open.

A copied project, `projects/midnight-curtain-study`, retains three captured drafts: current, still and restrained. Each contains both 30 fps formats at a 320-pixel long edge and the existing 72-second scored PCM; playback questions focus on the first 24 seconds. The still/restrained captures revise the canonical direction explicitly: no established airflow or haunting, cloth subordinate to the refuge, and no requirement to increase minimum curtain activity. Fire, steam and outdoor actions retain their authored state. Geometry/raster study files remain in the original project's `reports/curtain-study-v1/`. No derivative was selected as the user's final film.

The local comparison pages are `projects/midnight-curtain-study/recipes/comparison-portrait.html` and `comparison-landscape.html`; each movie is bound in `comparison.json`. Per-variant packets remain under `recipes/{current,still,restrained}/packet/`. Local project media and detailed command logs are not repository CI inputs.

One held-pose landscape encode failed the native sync-frame preroll check. Resuming the unchanged packet succeeded and reused completed steps; the failed attempt remains recorded. This implementation preserves that boundary check and does not claim the backend's intermittent keyframe behavior is fixed.

Browser media checks must distinguish control behavior from listening. The in-app browser stalled the audible lead movie at zero while its muted follower advanced; muting the lead initially allowed matched clocks at 1×. A later silent comparison also stalled, with all three clocks aligned and an explicit waiting message. The player detects stalled advancement and keeps followers aligned; this does not resolve the browser's playback stalls. Actual listening and reliable full-loop browser playback remain unverified. Native-app fallback could not be inspected while the Mac was locked. A direct local-file browser preview was blocked by browser URL policy, so the no-server fallback remains unverified; no bypass was attempted. Local HTML/MP4 files are retained for ordinary manual opening.

The sheltered/open-window/established-haunting plan examples all passed the public plan CLI. They are contrasting authored inputs, not three completed films. Context-aware work on this known room and synthetic workflow tests do not count as unfamiliar-input autonomous agent trials. The original CI-02/PILOT-01 criteria and new scenario `not-run` states remain honest.

## Validation and recovery

Targeted tests cover legacy feedback and time bounds, sealed event/CAS integrity, query size, clock/fulfillment snapshots, atomic packet initialization, missing PCM, exact source pixels, source tampering, configuration precedence and cleanup/restore. The native packet suite exercised creation/resume, changed media, interruption boundaries and cancellation requested while real render, verification and composition phases were active; completed output identities and selected review were preserved. The public CLI also exposed and fixed an initializer response-envelope bug that API-only tests missed.

The final shared validation command is `./ambiance test --require-native` with a fresh artifact directory; it includes Python, engine/JavaScript, package/capability and failure-contract checks. Compiler and attachment checks also use `python3 tests/test_assets.py` and `node tests/test-rig.mjs`. The task's final response reports the actual final run, including failures or skips rather than treating this command list as evidence of success.

Remaining work is review-specific: source/device listening, local-file playback under an allowed interactive browser, user selection of a curtain direction, and the declared unfamiliar-input trials. Broader cloth companions, automatic segmentation, generalized templating, permanent cleanup/purge and unmeasured renderer caching are outside the implemented capability.
