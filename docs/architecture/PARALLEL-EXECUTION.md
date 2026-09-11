# Parallel execution handoff

User authorization, September 11, 2026: launch five separate tasks, give each a goal, implement and test end to end, open PRs and merge their passing PRs. This document partitions the [roadmap](PRODUCTION-IMPROVEMENTS.yaml); it does not expand generation, account or film-publication authority.

## Verified baseline

This section preserves the pre-integration starting point. The [integration handoff](PRODUCTION-INTEGRATION-HANDOFF.md), current source and source-bound validation receipts describe the subsequently integrated code.

- Fetched `origin/main` is `dae0e18`; this planning worktree is `codex/encoder-loop-recovery` at `c53a5e4`, with additional uncommitted source/document changes.
- [PR #5](https://github.com/lbliii/ambiance-studio/pull/5), head `ca5a6e624033e252a05a5c643515de10d1a52e1c`, implements the dual-format pipeline. All six recorded CI checks passed, but the PR has conflicts against current main. The archived task **Support dual aspect ratios** confirms completion and contains pilot evidence. Main alone was an insufficient capability check.
- Do not rebuild named views, paired previews, iteration v2, view-bound editions or exact orientation/soundtrack delivery. Integrate and extend them.
- Root will preserve a source-only foundation patch and manifest in a temporary handoff directory. It includes the roadmap, local scope/UI/skill changes and the separate encoder checkpoint commit. Private film media and project state are excluded.

## Owners and goals

| Task | Roadmap scope | End state |
| --- | --- | --- |
| Integrate the foundation and strengthen CI | KIT-01, CI-01; adopt existing VIEW-01/DELIVERY-01; shared CI-02/DOCS-01 integration | Existing dual-format work and local foundation integrated, trustworthy failure artifacts/native checks, runnable cross-feature workflow replay and honest evaluation records |
| Enforce production intent and evidence | DATA-01, DATA-02; production-scope remainder of DELIVERY-01; compact readiness portion of PERF-01 | Canonical typed plan, explicit migration, stage-aware coverage, exact evidence identity and one readiness evaluator across CLI/overview/iterations |
| Build agent asset preparation and recovery | ASSET-01, OPS-01 | Practical structured/batch preparation with independent backing/masks, two-view proofs and durable generation-result recording/reconciliation |
| Build coordinated lighting and bindings | BIND-01 | One-way deterministic source/follower bindings, painted receiver illumination and reusable packages with inspectable synchronized proofs |
| Measure motion readability and cue timing | MOTION-01, MOTION-02, AUDIO-01; proof-measurement portion of PERF-01 | Per-view activity/raster evidence, restrained/target/stronger comparisons, honest readability review and explicit affected-sound-cue diagnostics |

Every owner updates its public CLI documentation, focused fixtures and relevant skill reference as part of its feature. The integration owner handles shared templates, instruction consistency, CI infrastructure and consolidated capability/roadmap status. This avoids making documentation somebody else's unfinished follow-up.

## Parallel work and merge protocol

1. The integration owner first resolves PR #5 against main, runs affected checks, pushes the resolved head, waits for its current CI and merges it without bypassing checks. It then integrates the source-only local foundation, preserving both sets of skills/editor/template behavior, tests and merges that PR. Notify the other tasks when the common baseline is available.
2. Other owners may inspect the roadmap, current and PR #5 code, design interfaces and write isolated modules/fixtures immediately. Do not implement replacement view APIs or merge a feature against the stale baseline. Fetch integrated main before full integration and before merge.
3. The production-intent owner publishes a small schema/API contract early and merges DATA-01 before DATA-02 if that unblocks consumers. Other tasks refer to semantic IDs; they must not invent competing editable census or expectation files. Runtime data remains owned by the scene.
4. The lighting owner owns changes to runtime binding evaluation in `editor/engine.mjs`/`editor/finishing.mjs`. The motion owner reads that evaluator through a documented sample interface. Coordinate necessary shared-file changes rather than creating a second clock or driver evaluator.
5. Every task owns its focused CLI parser/handler where possible; change central registration narrowly. Production-intent owns shared readiness/revision plan identity. Lighting adds its dependency identities through that contract. Rebase/merge deliberately and preserve both changes when shared files overlap; never resolve by replacing a file wholesale.
6. Use one or more focused `codex/` branches and PRs per stream. Review the final diff, run `./ambiance test` and affected native/browser/package checks, wait for checks on the exact current head, then merge without force pushes, protection bypass or overwriting others' work. Recheck after a substantive conflict resolution or new upstream interaction.
7. Each task reports its public interface, evidence paths, PR/merge SHA and remaining roadmap acceptance criteria to the coordinating task. Task messages may coordinate code and interfaces; no third-party messaging is authorized.

## Shared acceptance and boundaries

Use existing CLI transactions, strict validation, snapshots and nonzero failures. Keep ordinary scratch drafts possible and label incomplete production scope accurately. Do not introduce universal minimum layer counts, aggregate artistic scores, fake review observations, or arbitrary report files that satisfy creative requirements.

Readability targets are per action and per intended view. Character, environment, depth, cadence and stable-light classifications must result in useful authoring or evidence checks. Source attachment, driver coupling and receiver registration are separate relationships. Preserve source paint and accepted versions; moving a cutout over its still-baked original is not reconstruction.

Use local synthetic or repository-cleared fixtures by default. Source-backed private pilots stay local and are excluded from CI uploads and repository patches. Do not generate paid media, change accounts, publish films or create scheduled work. Existing tool outputs can be recorded without inventing provider IDs or prices. Explicit user direction overrides quiet-motion and two-format defaults.

Full artistic PILOT-01 remains a subsequent production run after the tools integrate. These tasks must supply executable feature proofs and integration replay, but a synthetic fixture is not a completed tram film or proof of autonomous artistic quality. FOLLOW-01/02 remain evidence-triggered follow-ups. CI-02 trial infrastructure and observed bounded trials can land now; unavailable or unperformed observations remain open.
