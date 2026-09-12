# Production improvements: from seed to a visibly animated film

Consolidated September 11, 2026 from the A Quieter Tomorrow reviews. This is an implementation plan, not a claim that the proposed commands, schemas or rendering features exist. The authoritative work items, dependencies and acceptance criteria are in [PRODUCTION-IMPROVEMENTS.yaml](PRODUCTION-IMPROVEMENTS.yaml). This document owns the design decisions and rationale; the YAML owns task status. Existing detailed plans remain the specifications for their referenced components.

For the subsequently shipped interfaces and executable validation path, use the [integration handoff](PRODUCTION-INTEGRATION-HANDOFF.md) and [capability index](../CAPABILITIES.json). The starting-point table below preserves historical evidence; it is not the current capability inventory.

The [Midnight Reading Room implementation design](MIDNIGHT-PRODUCTION-DESIGN.md) adds motivated-motion comparisons, ordinary feedback, compact next-work reporting, authoring operations, review packets, and measured run control. Its MRR tasks extend the same YAML backlog without resetting the completed foundation or unperformed pilot criteria.

The September 12 [Amberwatch custom-code audit](AMBERWATCH-GLUE-AUDIT.md) records eight production scripts and separates bypassed capabilities from genuine gaps. Reconciled against fetched main `a7dae5a`, its findings now feed the workflow, reusable-model and quality/library plans rather than a separate backlog. It distinguishes source separation from editable model/instance support and supplies operation-choice, ownership, move/hide, alpha and reuse acceptance cases. The audit does not change roadmap implementation statuses or settle the model plan's deferred architecture.

Use the [studio alignment](STUDIO-PLAN-ALIGNMENT.md) to coordinate those owners and the first-short packages. Existing DATA/ASSET/BIND/MRR capabilities remain foundations; the model plan owns the new definition/instance contract and WF owns guided operation. Outstanding artistic/operator trials should consume the shared cases rather than duplicate a new checklist or pass on structural evidence alone.

## Outcome and failure to correct

Given a seed, an agent should survey the whole scene, identify story opportunities, plan portrait and landscape compositions, prepare independent art and hidden surfaces, assemble readable motion and connected light, inspect the actual result, then produce exact, reviewable movies. Good source fidelity and technical correctness must coexist with noticeable, well-paced animation.

The tram demonstrated four connected failures: the seed's crop became the production format; a paper/mouse prototype became the effective scope; missing art was handled by reducing movement; and technical success was mistaken for sufficient creative progress. The remedy combines explicit expectations, usable production tools and evidence from normal playback. More layer labels or a higher aggregate score alone would not correct it.

The user has authorized parallel implementation tasks to implement, test, open PRs and merge their own passing PRs. This does not authorize paid provider jobs, new subscriptions, film publication or autonomous scheduled work. The [parallel execution handoff](PARALLEL-EXECUTION.md) assigns ownership and integration order.

## Verified starting point (before foundation integration)

| Area | Current capability | Remaining gap |
| --- | --- | --- |
| Agent workflow | Local AGENTS/produce/deconstruct/assets/animate edits now require a census, both compositions, story actions and scope evidence | Changes need consolidation; behavioral effectiveness has not been demonstrated on a fresh autonomous film |
| Inventory | Existing parts/stages/hashes/dependencies; local `required: true` and `plan check --require-complete` implementation | No typed semantic census, stage-aware creative expectations or automatic linkage to exact view/proof evidence; completion is only declared inventory completeness |
| Layer engine | Explicit painter order, artistic parallax depth, groups, nested attachments, sockets, deterministic tracks | Five-field semantic description is proposed; classification does not presently affect checks |
| Asset preparation | Source crop/return mappings; separate removal/cutout/occluder masks; backing alignment; compiler and movement proofs | Direct agent inspection/editing/batch preparation needs work; compound and dual-format staging still requires substantial manual assembly |
| Cel stability | Cel-motion milestones 1–3: observations, bounded patch tracking, fixed-geometry translation correction and contextual proofs | World contacts, continuous curves, broader tracking and cloud deformation remain future work; existing tracker is limited on changing shapes |
| Lighting | Masked receiver RGB modulation, shared intensity signals, explicit shadows/reflections, look proofs | Painted illumination as a first-class reusable component and general source-to-follower channel mappings are not implemented |
| Output formats | Named views, synchronized proofs, view-bound editions and paired delivery are implemented in [PR #5](https://github.com/lbliii/ambiance-studio/pull/5), head `ca5a6e6`; all six recorded CI checks passed | The PR is open and conflicts with current main; integrate and revalidate it. Expanded art and composition are still production work |
| Evidence/delivery | Captured revisions, exact editions, feedback and current selections; PR #5 adds resumable paired iterations | New plan/semantic/driver evidence must join the existing view identity model; full versus partial production scope still needs enforcement |
| CI | `.github/workflows/ci.yml` already runs `./ambiance test` on Linux Python 3.12/3.14 and macOS with native media enabled | Add targeted cross-feature/adversarial fixtures, retained failure artifacts and a behavioral evaluation path; another generic test runner is unnecessary |

The last local baseline ran 216 Python tests with six native tests skipped, plus Node and package checks. CI's macOS job enables native tests, but this plan does not claim a fresh remote CI result. The current skill validators establish syntax, not artistic behavior. The small group-control UI fix and scope checks remain working-tree changes; the export-checkpoint improvement is a separate local commit. This paragraph preserves the starting-point evidence. See the [foundation integration record](FOUNDATION-HANDOFF.md) for the subsequent reconciled code and validation.

## Decisions: plan format, expectations and scores

**Use YAML for this implementation backlog, Markdown for rationale, and canonical JSON for executable project data.** The repository already uses JSON for scenes, inventories, recipes and evidence. The backlog is not a scheduler and contains no executable shell instructions. Validate its task IDs, dependency graph and referenced paths. A future YAML authoring import can be added if actual use warrants it; it must normalize through the same strict schema to JSON, reject duplicate keys and unsupported values, and preserve one authoritative saved representation. Do not maintain independently editable YAML and JSON copies of a production plan.

**Use explicit expectations tied to the intended scene.** A universal minimum of ten layers or three character actions is easy to satisfy without improving the picture. Require the independently controlled parts, depth relationships, actions, light responses and output compositions that the brief selected. Count only useful declared separations backed by actual art/control/proof evidence. Deliberate stillness remains a valid artistic choice with a reason.

**Use a complexity profile for workload and coverage, not a quality score.** Report object families, independent depth/control groups, deforming parts, unique cels, occlusion/reconstruction obligations, source/receiver links, requested views and unresolved work. Keep counts separate; do not reward adding layers, duplicate cels, invisible movements or unnecessary dependencies. Estimate effort bands only after measured production runs provide calibration.

**Use a composition/motion review rubric without a single averaged score.** Review reference identity, focal hierarchy, framing in each view, depth/overlap, motion readability/cadence, source/receiver coherence and painted integration. Each dimension records `unreviewed`, `revise` or `meets-direction`, observer, exact subject and an observation with evidence. Existing 0–4 motion readability levels may be used per action as target/observed judgments. An excellent palette cannot average away a cropped-off main subject or a missing required action. Automated metrics describe behavior and support review; they do not produce an authoritative aesthetic grade.

## One production intent model

Implement a versioned `plans/production-plan.json` as the canonical statement of creative intent. It should contain the story, source identities, element census, intended outputs, explicit expectations and mappings to actual production work. Keep runtime geometry and drivers in `scene.json`, physical assets in the catalog, production stage/evidence in the inventory, and observations in existing review records.

The new plan consolidates the semantic information currently spread through authored census/layer notes. Import existing records explicitly, keep their originals and show a migration diff. New plans own expectations; inventories own fulfillment state. Do not duplicate editable cadence, depth or required flags across three files. Where legacy inventory `required` remains, report contradictions rather than letting a weaker flag erase a plan expectation. Narrative layout notes explain decisions and link IDs instead of becoming a second machine contract.

Each element has five semantic dimensions:

| Field | Initial vocabulary and purpose |
| --- | --- |
| `kind` | environment, structure, character, prop, effect |
| `depth_band` | far-background, background, midground, foreground, near-foreground; an authored spatial family, not meters or painter order |
| `motion_role` | primary, supporting, ambient, stable |
| `cadence` | continuous, recurring, occasional, still, plus explicit authored timing targets where needed |
| `readability_target` | 0–4 using the existing motion vocabulary; actual observation stays in a review |

Also retain ID, observed/proposed origin, story purpose, selected action/method, source strategy, required backing/occluders, and references to inventory parts and scene layers. Allow a logical character to realize as several layers and a deliberately static group to remain one plate. Represent `baked`, `cutout`, `rig`, `mask` and `painted-effect` realizations explicitly. One root painting cannot fulfill an expectation for two independently deforming characters merely by listing two semantic IDs.

Depth bands do not assign motion automatically. A near pole fixed to the camera's carriage may remain still while a distant bridge passes outside. A floor spans perspective depth even when its current 2D representation is one surface. Use actual scene transforms, mounting and world/camera motion rules for behavior. Relations for attachment, occlusion, receiving surfaces and light sources reference stable IDs; they supplement the five fields rather than inflating the kind enum.

Expectations have an ID, rationale/direction source, required stage, applicable view(s), required elements/control relationships and evidence type. Some are structural (both views exist, a required part is independently controllable); some require measured thresholds authored for this project; some require a real visual observation. Keep proposed, user-directed and observed facts distinguishable. Record revisions to expectations with reason and impact. A change is visible and restorable without creating a routine permission request.

Add typed capture roles for the production plan and its actual dependencies. A scope/semantic/view/driver edit must invalidate affected evidence. Reviewers must see the exact captured expectations that applied to an edition. Never retrofit a changed expectation onto an old movie's pass record.

## CLI and completion behavior

The following is a proposed command surface. Finalize strict argument/schema details with DATA-01; only existing `plan check --require-complete` is available now.

| Proposed capability | Result |
| --- | --- |
| `plan spec inspect/check/apply` | Inspect/validate/edit the intent model with dry run, expected hash, project lock and restorable history |
| `plan coverage --stage layout|assets|animation|export --view ID` | Reconcile expectations against actual parts, runtime controls and identity-bound proof/review evidence; return actionable gaps |
| `scene profile` | Compact semantic/depth/control/complexity profile with planned-versus-realized differences |
| `scene activity --view ID` | Shared-clock action windows, measured travel/cel changes, projected/visible support and unreviewed readability claims |
| `binding inspect/check/apply` | Author and inspect explicit source-to-follower relationships through ordinary scene transactions |
| `asset prepare inspect/check/edit/proof` | Structured recipe inspection and bounded changes with saved source mappings and reproducible proofs |
| `view inspect/apply/check`, view-selecting renders and `render views-proof` | Adopt the already selected dual-format command design |
| `iteration run` with explicit proof/review/final scope | Preserve resumability while requiring the applicable expectations and requested view/role set for a full completion claim |

Keep `plan check` as an integrity check and the current completion flag backward compatible. Stage-aware coverage must not demand final encoded deliverables before an animation draft can exist. Empty or missing requirements are `unplanned`/`unreviewed`, never a vacuous pass. A declared primary action with no actual control/proof is a gap. A requirement cannot be fulfilled by an arbitrary nonempty report file: validate receipt kind, IDs, source/scene/view/driver hashes, rendered dimensions and review subject as appropriate.

Technical invalidity remains a nonzero error. Honest missing work produces a nonzero readiness result with next actions, while valid plan inspection may succeed. A review draft remains renderable/presentable with explicit outstanding scope; full production completion and release cannot silently use that draft's reduced requirements. Do not block ordinary scratch renders or hide useful incomplete results.

Use one readiness evaluator in the CLI, `project overview`, iteration preflight and delivery summaries. The current overview duplicates some ready-item selection instead of reusing `plan next`; remove that divergence. Default results should contain status, gaps, next actions and artifact paths, with full arrays/pixel/timing evidence in saved reports. Add deterministic filters/pagination/detail modes where necessary rather than dumping every sampled frame into the agent context.

## Staging, extraction and two views

Integrate the existing named views and paired picture proofs from PR #5; do not reimplement [DUAL-FORMAT-IMPLEMENTATION.md](DUAL-FORMAT-IMPLEMENTATION.md) milestones 1–2. Preserve its shared scene clock, full-stage finishing and uniform crop/scale behavior. Prove the two compositions before detailed asset production. Expanded sides/headroom/floor and sufficient source resolution are art requirements, not automatic consequences of adding a view rectangle.

Develop the preparation agent pass already specified in [ASSET-PREPARATION-WORKBENCH.md](ASSET-PREPARATION-WORKBENCH.md). A batch should be able to inspect sources, select/correct masks, register backing, declare overlaps, compile pieces, place them and save rest/extreme/hidden-part proofs through CLI operations. Share backing repairs and overlapping masks instead of generating conflicting replacements per object. Preserve subpixel mappings, delicate alpha, contact points and accepted versions. Asset regeneration should answer a stated geometry/pose/style need.

A shared stage and two crops are the first implementation. If actual paired blocking shows that full characters/actions cannot fit both, retain view-specific restaging as an explicit required capability or an explicitly recorded two-scene fallback with shared assets/timing. Do not silently declare a technically valid crop artistically sufficient. Any later rig override must include its occluders, receiving effects and contacts; it needs the same per-view evidence.

PR #5 also implements dual-format milestones 3–5: view-bound revisions/editions, separate `(view, soundtrack-role)` identities, resumable paired iterations, exact feedback and current/watch routes. Reuse these and add production-plan scope/evidence integration in DATA-02. A failed second orientation preserves a successful first artifact and the previously selected review; retain this tested behavior.

## Painted illumination and coordinated motion

Prepare a surface base with the selected light contribution reduced, plus source-shaped illumination masks or painted highlight cels. Keep tile edges, wet patches, perspective and foreground blockers. Choose compositing explicitly in the shared linear-light renderer; existing receiver lights multiply RGB, so they do not automatically supply arbitrary additive painted highlights or recover the unlit source.

Three relationships stay distinct: transform attachment, source driving and surface receiving. A flame mounts inside a pumpkin; its intensity/pose drives glow and floor light; floor-light position/masking belongs to the floor. The source's lean maps to an authored response, which need not move in the same direction or at the same scale. Light response uses the same source time. Different timing for cloth or other reactions is an explicit artistic mapping, not a universal follower delay.

Start with one-way acyclic drivers over a small channel set: scalar intensity, normalized pose parameter or discrete cel/state into opacity, bounded translation/rotation/scale and cel selection. Reuse existing shared signals and evaluator time. Define units, source/receiver coordinate spaces, interpolation, range/loop behavior, hidden-source behavior and precedence with ordinary tracks. Reject cycles, missing endpoints, multiple writers and unsupported combinations. Do not evaluate arbitrary expressions or introduce feedback physics. Prefer explicit mappings and predictable errors.

Add inspection showing which followers each source drives and how their values resolve at a chosen time. A proof should show source plus receivers, isolated contributions, left/rest/right or low/high/off states, occlusion and actual normal-speed playback. Renderer, compiler corrections, captured dependencies and reusable rig/look packages must preserve the same bindings; do not silently move art-bound masks when cel registration changes.

## Motion measurement and artistic review

Implement activity reporting in two layers:

1. **Deterministic state evidence:** reuse `scene timing` and the evaluator for actual cel holds, action windows, onset/repeat/rest, transformed painted bounds, displacement relative to object/frame, speed, opacity and shared driver values. State changes are not necessarily new pixels or visible motion.
2. **Rendered/view evidence:** sample the actual view at stated display sizes, compare isolated/disabled elements, report visible painted support, temporal difference maps and candidate quiet intervals. Account separately for camera/world movement, occlusion, duplicated cels, low contrast and global light changes. Use ID/alpha contribution passes where they make attribution possible. Label unresolved/translucent attribution and expensive checks honestly.

Every threshold records units, view/display size, sampling rate, measured source and scope. Calibrate on held-out examples of visible, invisible, barely visible and excessive motion. Do not use global image difference as an engagement score: a whole-frame exposure pulse can dominate the number while the main action is absent. A tiny moving asset or offscreen animation cannot satisfy a visible environmental requirement.

Use matched quieter/target/stronger proofs at the same cadence, then test cadence separately. Avoid a combinatorial comparison of every view, effect and amplitude. Review the primary and environmental actions in each full composition at normal speed, without a pointer, before close-up defect work. Record unknown when that observation has not occurred.

For this tram, retain the current proposed targets as a pilot profile: both output views; independently controlled exterior sky/cloud/city/bridge/water roles; visible environmental life across ordinary five-second viewing spans; an early obvious cue around the first two seconds; readable ghost/mouse activity, featured paper motion and coupled practical light. These are provisional direction and review targets, not universal thresholds or a declaration of physical phone review. A one-way traveling exterior must not reverse a landmark just to hide a short loop reset.

## CI and evaluation

Extend the existing Linux and native-macOS lanes; add tests with the feature they protect. Keep generated-film quality approval outside ordinary pull-request CI.

| Lane | What it should establish |
| --- | --- |
| Contract/unit on Linux | Strict schemas and units, migration/read compatibility, dependency cycles, semantic mappings, requirement contradictions, stable issue IDs, empty/unknown handling and atomic transactions |
| Deterministic raster fixtures | Known crops/proportions, independently controlled parts, hidden backing and occlusion, receiver masks/driver states, loop/time sampling and legacy pixels; use controlled tolerances where resampling differs |
| Native media on macOS | Real encode/decode, per-view identities/dimensions/timing/audio, saved evidence, failed-job recovery and exact loop boundaries; missing native capability fails the required native lane rather than silently skipping it |
| Browser/CLI parity smoke | Same edited scene, source clock, selected view and driver values; actual raster comparisons with declared tolerances, functional controls and asset loading; preserve a playable proof on failure |
| Recorded workflow replay | Bounded public CLI path from saved inputs through plan, preparation, paired proof, capture, encode, delivery and resume; corrupted/stale/partial inputs fail at the responsible stage |
| Agent behavior trials | Agent receives unfamiliar seed/brief and tools, then produces and explains artifacts; measure actual completeness/readability, scope reductions, unnecessary questions and recovery effort. Run explicitly with bounded permitted resources; do not trigger paid/live generation on every PR |

Add adversarial cases that specifically defeat superficial proxies: many duplicate/static layers; different semantic IDs mapped to one baked actor; identical repeated cels; motion hidden behind a foreground mask; a light-only whole-frame pulse; a primary gesture cropped out only in portrait; absent clean backing; two independent pulses that drift apart; incompatible source/follower clocks; changed proof/view/expectation identities; and a completed first encode followed by a failed second format.

CI should save compact JSON/JUnit summaries and bounded proof artifacts on failures. Use synthetic or repository-cleared fixtures; private project media is not an automatic CI artifact. Record skipped capability tests explicitly. Run expensive benchmarks on deliberate changes to the affected renderer/preparation path; do not add flaky wall-time assertions to the fast suite.

Upgrade [skill scenarios](../../tests/skill-scenarios.md) into executable/observable trials gradually. The current list is a plan, not passed behavior evidence. Include a quiet seed that nevertheless needs visible activity, an explicitly nearly-still brief, a one-format override, a strong portrait/landscape conflict, reactive candle lighting and continuation after interruption. Judge outputs and decisions rather than matching instruction wording. Use a second unfamiliar, non-Halloween scene to test whether the workflow generalizes.

## Repository, kit and operations

Consolidate the already tested local guardrail/UI work first, preserving unrelated changes and reviewed artifacts. Update capability status from code and handoffs: CLI-FIRST currently calls all cel-motion work planned even though milestones 1–3 are implemented. Maintain one capability index with implemented/planned/limited states, public command and evidence links. Add a check for missing references and contradictory declared status, without claiming that a document parser proves implementation.

Keep AGENTS short: product direction, authority and consequential invariants. Stage skills link the authoritative production workflow and executable contracts. Avoid adding the same detailed checklist to every skill. Update new-project templates and reusable examples when the corresponding feature lands. Existing copied pipelines/records keep their original meaning; adoption of new requirements is explicit and versioned.

Package reusable modules with intended layer roles, safe source/display scale, sockets, masks, drivers and receiver dependencies. Reuse remains conditional on matching perspective, light, style and output size. A catalog admission is availability, not artistic acceptance. Round-trip tests must preserve rig, illumination and source-bound correction companions.

Give external generation requests durable identity and reconciliation through the existing ledger: pending/submitted/uncertain/retrieved/selected states, source hashes, output identity and authority/cost fields only when known. Record/reconcile tool-produced assets even when a provider cannot be called directly from the CLI. Do not pretend a provider adapter exists or retry a charged uncertain request automatically. Use explicit authorized generation scopes; no new provider queue is required before existing-file pilots.

Measure agent effort and renderer cost: calls/turns, JSON volume, manual masks/landmarks, missing undocumented steps, correction rounds, interrupted-run recovery, single/paired proof latency, peak memory and achieved playback rate. Prototype at bounded resolution while preserving output geometry and motion speed; use full detail for edge judgment. The full-stage dual-view renderer remains the correctness reference for later ROI/direct-view optimizations.

## Sequence and definition of done

1. **Foundation:** consolidate local changes; establish the typed plan/expectation contract and CI fixtures. Keep the current reviewed movie and all captured identities intact.
2. **First visible improvement:** implement paired framing/proofs and the agent preparation pass. Produce the tram's two blocking compositions before detailed art. This is a reviewable increment, not completion of both movie outputs.
3. **Readable coordinated animation:** add driver/painted-light support, scene activity diagnostics and measured view proofs; evaluate the existing and proposed stronger actions.
4. **End-to-end enforcement:** integrate exact plan/view/driver evidence with reviews, paired resumable delivery and concise next-work reporting. Ship compatibility adapters with the features.
5. **Behavioral demonstration:** run the corrected tram and an unfamiliar seed through the public agent path. Inspect actual paired movies and record limitations. Expand tracking, contact continuity or deformation only where these runs justify it.

Workstreams can proceed independently where YAML dependencies permit; that graph is a planning aid, not authorization to spawn agents or schedule work. Each feature lands with its own schema/fixture/CLI/docs checks. Relative size estimates are integration risk, not calendar promises.

The core improvement set is complete when an agent can read a seed and saved brief, retain all chosen requirements, prepare the required independent art, show readable and coherent motion in both intended compositions, resume interrupted work, and deliver exact verified movie pairs with honest artistic observations. CI must catch the known structural failures; the actual film must demonstrate the creative result. A larger layer count, passing schema, impressive atlas or new unplayed movie file cannot substitute for that demonstration.
