# WF-04/05 native packets and command outcomes

Bounded Wave 3 implementation based on `75d24b85a8977f234d87daa1c18993d394036c1c`. This contract covers input preparation and optional command outcomes. WF-06/07 operator trials/adoption, model-operation guidance and artistic acceptance remain open. The coordinator owns central capability and roadmap registration.

## Public contract

```sh
./ambiance --project /absolute/project workflow prepare ACTION_ID \
  --expect-assessment ASSESSMENT_SHA256 --inputs /absolute/project/authored.json \
  --out /absolute/project/fresh-packet
./ambiance --project /absolute/project --guidance auto scene check
./ambiance --project /absolute/project --guidance full scene apply /absolute/project/change.json
```

`workflow prepare` accepts the same subject/revision/edition/view/stage selectors as `workflow explain`. The exact action ID and assessment are resolved again using WF-03. An unavailable or changed selected entry never falls back to the working scene or the default entry. A stale token reports the current assessment identity, as the existing explain contract does; an opaque hash alone does not reconstruct an old assessment's file differences. Changes during preparation report the tracked file/directory differences. The saved `assessment-inputs.json` retains exact fingerprints for comparison.

The output parent must already exist inside the selected project. Output and input paths reject symlinks and escapes. A new sibling temporary directory is promoted with the existing macOS/Linux atomic no-replace publisher. Occupied destinations, write failures, changed inputs and a concurrent destination owner preserve prior files. No output directory is reserved for a future production operation. Completed packet files are never updated by re-preparation; select another directory.

`packet.json` is sealed and records exact subject, action, assessment, catalog and implementation identities, input fingerprints, native file hashes, field origins, effects and the next native argv when ready. `README.md` explains open choices. Draft wrappers use `ambiance-workflow-input-draft`, contain `values` and `missing_inputs`, and are explicitly not executable native recipes. A completed draft wrapper or native JSON object may be supplied through `--inputs`; it is copied into a fresh packet. No arbitrary scripts or universal recipe language are accepted.

| Adapter | Native owner and behavior | Readiness |
| --- | --- | --- |
| Intent | Small pure `production_plan.draft` helper; complete values pass `production_plan.validate` and native contradictions. The current plan hash binds `change.supersedes_sha256` and the emitted apply command. | Null creative choices remain missing. Explicitly authored empty collections retain native meaning. Complete values emit `plan spec apply`. |
| Gate review | `studio.review_template` with the exact native working or captured review context. The native draft retains `not-run`, blank recorder/observer names and its default revise state. No supplied observations are accepted by prepare. Working legacy gate drafts cover the whole project even when workflow has a view filter; the packet labels this native scope explicitly. | Always unperformed and `ready_to_run: false`. Complete an observed derivative and use native `review record` separately. |
| Iteration | `iteration_recipes.build` and its validators produce `iteration.json`, capture selection, exact inputs and job plan. Explicit request JSON, native views, audio and dependency checks apply. | Missing IDs, soundtrack, default pair and scope remain explicit. A complete request emits a runnable **preflight** command. Actual `iteration run` still requires the operator's explicit `--by`; no recorder is inferred. |
| Direct arguments | Existing `workflow_operations.Operations.resolve` supplies the native argv and its existing checks. | Ready only when that adapter resolves all arguments. Missing-file/decision actions remain unresolved; there is no generic file adapter. |

The intent helper closes an observed native gap: `plan spec --help` exposed inspect/check/apply/migrate, with no blank initializer. Existing iteration `build`, native `review_template` and the exclusive edge-output publisher were inspected and reused. Preparation performs no capture, admission, render, selection change or provider call. Native operations still revalidate their inputs at consumption.

## Outcome compatibility

Global `--guidance off|auto|full` defaults to `off`. An optional top-level `guidance` uses `ambiance-operation-guidance` schema version 1 beside unchanged `data` or `error`. Native success, failure and exit codes remain authoritative. The option is removed from native dispatch namespaces so it cannot enter a scene transaction or recipe.

The CLI writes its ordinary report envelope **before** adding stdout guidance. Native files/artifact directories retain their declared ownership and bytes. Guidance never enters sealed receipts, saved recipes, run checkpoints, native report files or dependency hashes. An adapter, import, reassessment or serialization failure becomes a bounded guidance diagnostic; an already successful operation remains successful and must not be retried because guidance failed.

Auto adapters cover project init, asset build/proof, scene apply/check, review record, iteration init/run and delivery present. They use returned operation facts and explicit arguments only. No coverage, recursive next-work evaluation, catalog read, runtime query or library scan is performed by auto guidance. Gate criteria are not named without compatibility binding; operation success does not imply an observation or a gate pass. Structured native failure codes receive bounded hints, while unmapped failures retain an explicit non-causal fallback.

Full mode requests fresh WF-03 assessment where a compatible project subject is available, retaining assessment/catalog identity, completeness, exact subjects, scope and pagination/retrieval argv. A presented delivery is pinned to the returned selection before and after assessment and retains each entry. Captured review records use their native revision/edition/view. Project-free operations remain artifact-local. Iteration run outcomes may be unpresented/multi-entry, so full reassessment explicitly remains unavailable rather than substituting a working/default subject; native run and exact delivery inspection remain available. Unsupported routes return explicit help and do not perform full assessment. Parse errors before a valid namespace retain the legacy envelope. Each optional guidance block is bounded to 16 KiB.

## Verification entry points

- [Packet regressions](../../tests/test_workflow_packets.py): native intent/review/iteration consumption, unresolved and partial inputs, origins, source hashes, immutable re-preparation, exact multi-revision entries, stale tokens, symlink/escape rejection, partial-write cleanup and concurrent publication.
- [Outcome regressions](../../tests/test_workflow_outcomes.py): legacy off mode, report ownership, no broad auto reads, supported continuation parsing, structured failures, dry runs and successful native scene mutation followed by guidance failure.
- [Public argv replay](../../tests/replay_workflow_packets.py): actual packet consumption, native asset build/proof, unperformed review recording, paired iteration encode/decode, full exact delivery assessment, stale preparation and mutation/guidance failure. The intentionally non-ready preflight exits 1 while its proof-scope `may_render` remains true; the subsequent native iteration is separately exercised.
- [Existing CLI contract checks](../../tests/test_cli_contract.py): only root/workflow signatures and the new artifact-owned prepare route are updated in their fixtures.

Run the bounded replay with `python3 tests/replay_workflow_packets.py --out FRESH_RETAINED_DIRECTORY`. Native media access is required for the movie steps. Retain restricted failures honestly. A native encode/decode or synthetic identity test is not a human playback/audition or artistic acceptance.

Exact final commit, retained report paths/hashes and local observations are recorded in the task's committed handoff after frozen-source validation.
