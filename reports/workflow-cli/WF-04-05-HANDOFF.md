# WF-04/05 committed engineering handoff

Implemented native input packets and optional command outcome guidance on isolated branch `codex/wave3-workflow-packets-outcomes`, based on merged main `75d24b85a8977f234d87daa1c18993d394036c1c`. No main push/merge, account change, paid generation or canonical film edit occurred.

Task: `01a09b0c-3462-71c1-9a61-2d7201602138`  
Worktree: `/Users/lb/.codex/worktrees/61c0/ambiance-studio`

The [public contract](WF-04-05-PACKETS-OUTCOMES.md) describes supported inputs, exact-subject handling, native ownership and compatibility. The [machine-readable handoff](WF-04-05-HANDOFF.json) contains the changed paths, artifact/report hashes, native decode facts and retained diagnostics.

## Commits and exact validation identity

| Commit | Change |
| --- | --- |
| `06c1315010f8f8653a96e1073693aeebf177f544` | Immutable native packets, pure intent draft adapter, prepare route, consumption and publication safety regressions. |
| `0ccabe4198d91a3b56afbcd2bbad004b10847d44` | Optional outcome guidance, CLI boundary integration, regression tests, public replay and contract. **Exact frozen tested candidate.** |

The final handoff is a documentation-only successor to the tested candidate. Its code and fixtures remain unchanged. No tracked source changed during the required-native run.

- Tested Git tree: `0efcafae651af6d7399dd91b040c84a451681744`.
- Suite tracked-source SHA-256: `2e1cafa4ceeaede5415e6589131b4aaa273f7fd0a475d130398639844033ccff`.
- Exact source manifest (`inputs.json`) SHA-256: `6b449b1d5d334f9e74562c02b9043badb42e246f491580e3d2e832efef5e3303`.

## Results and reproduction

Required-native validation passed **544 recorded cases / 529 Python tests / zero skips**, exit 0, including the package audit and existing renderer/rig checks. All 544 case statuses are passed. This adds 28 Python cases to the supplied 501-test baseline. The coordinator granted and received an explicit release of the serialized native slot.

Exact command, run from this worktree with local loopback/Core Audio/AVFoundation access:

```sh
./ambiance test --require-native --artifacts .ambiance/validation/w3-native-final
```

Retained report: `.ambiance/validation/w3-native-final/run.json`  
SHA-256: `a80640460ebe7cd636d571c215159fbe4d59e539166d241d4d4924e9b87e42b8`

The exact-source public replay passed **24 CLI calls**, with `source_unchanged: true` at the tested commit:

```sh
python3 tests/replay_workflow_packets.py --out .ambiance/validation/w3-replay-frozen
```

Retained report: `.ambiance/validation/w3-replay-frozen/run.json`  
SHA-256: `4962caa99ea61ef095b8f0044a37c0f441b04477efbaff82606f87de4c352798`

These are the exact commands used; repetitions must select fresh evidence directories. Every resolved public argv, stdout hash, exit code and elapsed time is in the replay report. Evidence paths above are relative to the named worktree and are retained locally, not bundled as large media in Git.

The replay consumed packet outputs through `plan spec apply`, `asset proof`, `review record` with explicitly **unperformed** observations, `iteration preflight` and `iteration run`. The proof-scope preflight correctly returned exit 1 for open readiness while `may_render` remained true; it was not counted as a ready final film. The subsequent native iteration produced and fully decoded both silent one-second movies: six frames at 6 fps, portrait 90×160 and landscape 160×90. The full delivery outcome retained two distinct edition/view identities.

The decisive mutation case is `22-mutation-guidance-failure.json`: native `scene apply` returned exit 0 and its actual new scene hash, preserved the previous scene snapshot, then attached `guidance_unavailable` because a deliberately malformed workflow selector prevented full guidance. No retry occurred and no native success/error or saved report was replaced by guidance.

## Observations and retained failures

The final frozen portrait raster was visually inspected: a uniform ochre/brown field from the supplied synthetic flat-paint fixture, at 90×160. Its SHA-256 is `5a33aa0d629e1514d834053b13b0828a94feb61b1d450476d02d488d9428092f`. Renderer/preview behavior was not changed. Native complete-decode reports are technical evidence; no human playback, listening, phone check or artistic acceptance is claimed.

The first restricted public replay remains at `.ambiance/validation/w3-replay-1/run.json`. Its iteration-run step failed with exit 3 and AVFoundation error `-11834` (“encoder cannot be found”). The original `runtime_error` and exit status survived optional guidance. This diagnostic is not a pass. The authorized native-access replay and then the frozen replay passed without weakening assertions.

Earlier focused nonpassing logs are retained under `.ambiance/validation/w3-focused/`. They exposed fixture assumptions about stage filtering and malformed settings falling back to partial assessment. Corrections were followed by passing focused runs, explicit tests for actual legacy review scope, watched-parent staging and delivery-wide feedback subjects, and the complete frozen required-native suite. Their exact hashes are in the JSON handoff. No known failure or skip remains on the tested candidate.

The documentation-only handoff was additionally checked with `python3 tools/package_audit.py`; its retained output is `.ambiance/validation/w3-handoff-package-audit.json`. Hosted CI is not claimed: the prior wave's GitHub jobs were blocked by billing/spending limits, and no billing or account changes were made.

## Integration boundaries and residual limits

The CLI lease is confined to the root guidance option, filtering that option from native namespaces, optional stdout envelope extension and success/error boundary. Existing output declarations remain authoritative. Native result-file bytes never contain guidance. Only root/workflow option signatures and the new artifact-owned prepare route were updated in the CLI fixtures. M3/T3/A3 registrations and native operation semantics are untouched; the coordinator owns their integration and central roadmap/capability updates.

The three native adapters preserve unresolved creative choices, native validation and exact review subjects. Legacy working gate drafts still cover the whole project and are explicitly labeled even under a workflow view filter. Complete iteration packets expose validated preflight; executing them requires an explicit recorder identity. Full outcome assessment for an iteration without a compatible selected subject stays explicitly unavailable, preserving all native run entries instead of choosing a default. Direct arguments reuse the existing resolver's native contract; there is no new universal recipe, evaluator, census, scheduler or provider operation.

WF-06/07 fresh-operator trials/adoption and model-operation guidance expansion remain open. Synthetic fixtures do not establish whole-scene model coverage, creative completeness, film quality or artistic/audition approval. This handoff stops at the assigned WF-04/05 engineering boundary.
