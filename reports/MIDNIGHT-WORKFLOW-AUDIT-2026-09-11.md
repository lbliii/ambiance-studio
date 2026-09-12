# Midnight Reading Room: production workflow audit

Audited September 11, 2026 against checkout `31390fbe7c8039aca9f39ef9695cc9a55a41343a` (0.8.0), including the current motion/style guidance changes. This is an analysis and implementation proposal. The commands proposed below do not exist unless explicitly identified as existing. No film, runtime code, captured revision or review verdict was changed by this audit.

The next investment should make creative decisions easier to test and production state easier to operate. The existing renderer, transactions, revisions, inventory, preparation tools and iteration runner provide a useful foundation. Extend those services in small slices. The strongest new evidence is the excessive curtain motion, the manual feedback workaround, a 1.17 MB status response, and the project-specific scripts needed to reach export.

## What the production and audit establish

| Observation | Evidence and implication |
| --- | --- |
| Curtain motion was judged excessive, with no established draft or haunting. | The authored `curtain-breath` action requests readability level 2 in both views, onset within 2 seconds and rests no longer than 2 seconds. Its expectation asks that it be noticeable. The plan supplies no corresponding cause or acceptable upper emphasis. This was an authored direction problem, not a malfunctioning renderer. |
| General feedback falls outside the supported capture path. | `feedback add` requires role and time; a dual delivery also needs an unambiguous view. The user's untimed curtain feedback was saved to `feedback/curtain-motivation.md`. `feedback list painted-review` returns an empty list. |
| Routine status is too large. | This audit measured 1,173,801 stdout bytes for `project overview`; nested runs account for 867,324 bytes even when serialized compactly. `project latest` returns 18,261 bytes. `plan next` returns 2,668 bytes. Local elapsed times were 13.432, 4.278 and 0.221 seconds respectively; these are one-off observations during other checks, not isolated performance benchmarks. |
| Asset completion obscures the next creative work. | `plan next` reports zero ready items and overview has an empty `ready_work`, although overview also reports nine open gates. Inventory completion and review work are intentionally different, but the primary next-work presentation does not bridge them. |
| Run liveness is detected but poorly presented. | The stopped `first-review` record still says `state: running`. `runs()` adds `process_state: unknown-or-interrupted`. The studio connection indicator checks the former and can keep announcing an iteration in progress. |
| The practical rendering path required a custom optimization. | The selected six-edition iteration took 654.66 seconds. Its two picture-render reports record about 233–234 seconds each, excluding some surrounding work. Each 720-frame picture renders another 720 frames for encoder preroll. The earlier linear-light attempt was stopped as too slow; no reliable full-run speedup ratio is available. |
| The film accumulated twelve project scripts, totaling 753 lines. | Some encode real artistic decisions. Others author manifests, reconcile fulfillment, record checks, optimize atlases or select revisions. Several are tied to a particular preceding scene and are not general replay commands. |
| The foundations already work. | Selected dual views, six decodable editions, exact captured identities, shared readiness, interrupted-step recovery, source mappings, cel registration and soundtrack reuse all exist. The 2026-09-10 audit and earlier roadmap contain historical gaps that have since been addressed. |

Project evidence is retained in the local `projects/midnight-reading-room` directory: the canonical production plan, selected iteration, generation ledger, handoff, render reports, preparation scripts and curtain feedback. The small companion [audit evidence record](MIDNIGHT-WORKFLOW-AUDIT-2026-09-11.json) records the checks and measurements. The large project status dump stays in temporary diagnostic storage.

## Prioritized implementation slices

Priority denotes recommended order, not a claim that every item is a release blocker. Sizes describe integration scope, not calendar estimates.

| ID | Priority | Improvement | Scope | Dependency |
| --- | --- | --- | --- | --- |
| MRR-01 | P0 | Carry cause, purpose and appropriate intensity through direction and review | Small initial guidance/example change | None |
| MRR-02 | P0 | Capture untimed feedback and track its resolution | Medium contract/CLI/UI change | None |
| MRR-03 | P0 | Return compact status and useful next work | Small summary projection; medium next-work integration | Feedback integration follows MRR-02 |
| MRR-04 | P1 | Create an early picture-and-sound review packet | Medium orchestration/artifact change | Reuse existing render/audio/review services |
| MRR-05 | P1 | Add render estimates, live progress and safe cancellation | Medium process-control change | None |
| MRR-06 | P1 | Close demonstrated authoring gaps with transactions | Medium, split by operation | None |
| MRR-07 | P1 | Support meaningful alternatives for cel deformation | Medium asset/proof change | MRR-01; reuse comparison engine |
| MRR-08 | P2 | Promote measured render/asset optimizations | Medium to large, profile first | MRR-05 |
| MRR-09 | P1 | Shorten skills around the actual production path | Small, updated with each shipped slice | Start now; command examples follow implementation |
| MRR-10 | P1 | Test operator behavior using contrasting creative cases | Medium evaluation work | Establish baseline before changing skills |

### MRR-01 — Ask why an object moves before targeting its visibility

The plan already has `element.purpose`, `action.description`, and expectation `direction`/`rationale`; use them. The [action schema](../ambiance_studio/production_plan.py) currently describes method, per-view readability and timing. The [observation evaluator](../ambiance_studio/production_coverage.py) checks actual declared observations and minimum readability. Neither is an automatic judge of whether billowing cloth fits a sheltered room.

Start by updating the plan-authoring example and the deconstruct/animate workflow to state, for each selected action: its cause or thematic contribution, the cues that establish it, and the intended limit on emphasis. Keep this as concise authored direction using existing fields initially. A new mandatory metadata schema would add burden without proving artistic judgment. Introduce a structured motivation field only if a concrete query or review feature needs it; preserve version-1 reads and captured identities if that happens.

Treat physical and supernatural causes as legitimate artistic choices. Do not invent broken windows or a haunting merely to justify an animation already produced. Preserve deliberately still objects and revise selected requirements explicitly when user feedback changes the direction. Review both insufficient and excessive motion in context. A higher readability level is not inherently better.

Acceptance: in a sheltered-room case, the operator retains still or credibly restrained curtains without suppressing justified fire/steam/outdoor motion. In separately authored open-window and haunted-room cases, stronger or uncanny cloth behavior can be appropriate. Review records must explain the difference; a nonempty explanation is not an automated quality pass.

### MRR-02 — Make ordinary feedback a first-class project input

The restriction is concrete: [production parser](../ambiance_studio/production.py) lines 27–29 requires `--role` and `--time`; [feedback storage](../ambiance_studio/deliveries.py) lines 409–438 binds a point to one movie and lists only `feedback/movies/*.json`.

Extend the existing feedback contract with explicit subjects: delivery-wide, entry-specific, and optional point/range. Delivery-wide feedback binds the immutable delivery identity; entry feedback binds its exact movie. Unspecified orientation remains unspecified. Preserve who reported a comment separately from an actual viewer when known. Do not assign a fictitious timestamp or multiply one report into six claimed auditions.

Proposed surface: `feedback add ... --scope delivery --note ... --by ...`, optional `--time` or range for a specified entry, optional action/element references, and an append-only resolution event pointing to the revision/delivery that addresses it. Resolving a work item must not automatically approve the movie. Support explicit import of the existing curtain note with its original wording and uncertainty.

Acceptance: the curtain report appears in CLI and studio feedback with no invented time/view; it remains bound to the old review when a new one is selected; a later resolution links to new evidence. Legacy timestamped records retain their meaning and seek behavior.

### MRR-03 — Separate compact query results from detailed evidence

[production.runs](../ambiance_studio/production.py) reads entire run records, and `overview` returns those nested records alongside history, entry checks and the selected delivery. Run step results include large media reports. The routine response consequently contains data the agent should fetch only on demand.

Add explicit summary projections for runs, deliveries and project state. Preserve detailed evidence on disk and expose it through `iteration inspect`, targeted entry queries and a details option. Keep the internal evidence model intact; version any public response shape that existing consumers depend on. Reuse the existing `Fingerprints` request cache before proposing another cache system. Profile remaining hashing/query costs after reducing payloads.

A compact next-work list should combine inventory work, canonical coverage gaps, open feedback and unavailable observations. Each item should identify its subject, why it matters, and a usable next command or requested creative decision. Preserve `plan next`'s documented inventory meaning; expose broader work through `project overview` or a dedicated project query. Reuse existing readiness results rather than adding another evaluator. Review requests remain informational during authorized independent work.

Also distinguish active runtime assets from retained intermediate/source versions. This project's inventory warning names 25 older/unmapped catalog assets. Preserve those versions while making an unused retained source informational and an unaccounted-for active layer actionable.

Acceptance: a synthetic project with large frame/sample reports still produces a bounded default overview, with an initial target of 16 KiB for a small project like this one. Detail retrieval stays complete. With assets complete and curtain feedback open, next work identifies the curtain decision. A projection test should catch response growth; use descriptive latency benchmarks rather than fragile CI timing thresholds.

### MRR-04 — Make the first useful review easy to produce

The [producer skill](../.agents/skills/ambiance-produce/SKILL.md) already asks for a combined motion draft before polishing, and the [sound skill](../.agents/skills/ambiance-sound/SKILL.md) already asks for early sound and source audition. My incomplete normal-speed viewing and listening were execution gaps, not missing instructions. A convenient artifact path would make compliance easier.

Reuse `render views-proof`, `render proof`, `audio mix/compare`, `media compose`, captured reviews and the studio player to assemble a bounded early review packet. It should present the intended compositions, one selected audible soundtrack, clear looping/seek controls, source-take audition links and the specific open creative questions. Pick preview duration around the actions being judged; a two-second clip cannot establish a 24-second cadence or a musical join.

The [studio already has a movie player and approximate version comparison](../studio/studio.mjs). Extend that surface instead of building another editor. Its comparison currently matches one orientation/role across versions; add the requested paired-view review mode with a shared timeline and only one audible soundtrack. Identify whether playback is approximate movie synchronization or exact rendered-frame proof. Playback telemetry may establish that media played; it cannot certify that someone watched, listened or approved it.

Provide direct local artifact paths as a fallback when the app browser cannot open localhost. Treat the in-app browser block and Messages authentication error as integration limits; do not work around them by weakening server origin checks or changing release semantics. A local share-package operation can provide descriptive filenames, selected identities and size information without implementing a messaging service.

Acceptance: through a public CLI path, produce an early paired review with source audition and exact feedback targets; open/play/seek it in a real browser and inspect it. Include a portable/local-file fallback. No paid generation or automatic creative approval is required to exercise the mechanism.

### MRR-05 — Observe and control expensive work before it becomes a surprise

[rendering._json_command](../ambiance_studio/rendering.py) waits on a captured subprocess result. The [renderer](../tools/render-scene.mjs) records elapsed time at completion, and [iteration](../ambiance_studio/production.py) checkpoints at stage boundaries. Add a bounded benchmark using representative source times at the actual planned internal stage resolution. Include initialization, finishing, preroll, both views, native encode and verification in the estimate, and report uncertainty.

Add throttled progress records with completed/expected frames, current phase, recent throughput and heartbeat time. Keep the final JSON result on stdout compatible with current callers; use a progress file or separate structured event channel. Extend the existing iteration runner with cancellation/reconciliation rather than adding a new scheduler. Cancellation must identify the owned process tree, preserve completed editions and record interrupted state. Do not signal a PID solely because a stale record contains it.

Use effective run state in both CLI and studio. [studio/studio.mjs](../studio/studio.mjs) lines 189–194 currently considers any saved `state === 'running'` active even when `runs()` has detected an absent owner. Show interrupted/unknown explicitly and provide the existing resume route.

Acceptance: benchmark and progress records bind the actual render recipe; cancellation leaves the current review unchanged; resumption reuses completed work; a dead or reused PID is handled without killing an unrelated process. Cover these with synthetic runs and the existing native recovery lane.

### MRR-06 — Replace repeated manifest surgery with narrow authoring operations

At the time of this audit, the project-local art preparation script, `projects/midnight-reading-room/tools/prepare_art.py` (not distributed with the repository), directly changed `canvas.loop_seconds` because the supported transaction operation list had no canvas-clock mutation. The corresponding implementation was in [tools/scene-command.mjs](../tools/scene-command.mjs) lines 26–29. Its other preparation steps used existing CLI/compiler services.

Add a clock operation through `SceneTransaction` and the shared scene validator. Make timing consequences explicit: changing a loop duration is distinct from stretching tracks or retiming sound. Preserve snapshots and report affected tracks, bindings, cues and captured subjects; do not silently retime everything.

Add bounded fulfillment updates for stable inventory parts and a recipe initializer for capture/iteration selection. Reuse the canonical plan, inventory validator, preparation receipts and edition contracts. Keep intent, fulfillment, runtime and observations as distinct authorities, while deriving duplicate factual summaries such as the layer-plan table. Updates should validate references and show diffs rather than marking every item complete merely because a mapping dictionary exists.

Acceptance: recreate this film's setup/fulfillment/capture recipe through public operations in a small fixture without directly overwriting canonical JSON. Invalid references, stale expected hashes and interrupted saves preserve the previous state. Test clock changes against real cel-track precedence and audio cue invalidation.

### MRR-07 — Compare reduced deformation without shrinking the object

[activity.variants_from_recipe](../ambiance_studio/activity.py) lines 70–115 already separates strength from cadence. Its strength variants allow motion amplitudes, width, height and scale; they do not support changing a cel-deformation range or substituting a registered alternative atlas. That distinction matters for curtains: shrinking the entire cloth does not reduce billowing while preserving its ties, size and weight.

Extend comparisons with explicit held-pose and registered cel alternatives. Keep the same camera, object size, anchors, lighting and cadence where applicable. Reuse existing motion studies and asset registration. State which property changed. A still variant must retain the curtain's painted presence; hiding the layer is a useful diagnostic but is not the artistic alternative being judged.

Acceptance: show current, restrained and still cloth with stable attachments in both views. A whole-object scale change cannot masquerade as reduced deformation. Atlas substitutions must pass registration, source identity, contact and contextual raster checks. Let the reviewer choose based on the established cause/theme.

### MRR-08 — Promote optimizations only after profiling and fidelity checks

The full-resolution production used project-local `bake_fixed_look.py` and `trim_runtime_cells.py`. The latter crops the union of alpha bounds across every cel and remaps geometry/anchors/sockets. That is a useful candidate for the existing compiler/preparation layer. Preserve the source mapping and static/dynamic companion rules; do not copy a script that assumes this room's predecessor state.

The light bake is more constrained. Its saved notes explicitly call Canvas transparency an approximation to the earlier linear-light composite. It should not be marketed as an output-equivalent fast renderer. First profile [drawFinished](../editor/finishing.mjs): repeated scratch allocation, per-pixel grades/masks and repeated static surface work are concrete candidates. It already caches source pixels/cells, so a proposal to add generic image caching alone would miss existing work.

Consider bounded caches for invariant transforms/masks and discrete receiver appearances, keyed by all scene/look/view/source dependencies. A separate prepared-look recipe may intentionally trade appearance for cost, but needs explicit comparison and immutable source provenance. The two picture jobs currently redraw the stage separately, and preroll adds one loop per picture; investigate shared-stage fan-out or bounded frame reuse only after measuring memory and fidelity. Preserve preroll unless encoded-boundary tests justify changing it.

Acceptance: retain baseline and candidate timing/memory reports at intended resolution, plus edge, occlusion, light-state, both-view and encoded-loop comparisons. Distinguish exact, tolerance-bounded and intentionally approximate paths. Cache invalidation must survive a mask/source/view change.

### MRR-09 — Shorten the route through the skills

Keep the six stage skills. Give each a short operational opening: inputs to inspect, the normal command path, the artifact to present, and the creative decision to judge. Put uncommon recovery details in linked references. Preserve the strongest existing instructions: user scope, original protection, real backing, meaningful cels, exact versions and honest observations.

Make cause/purpose part of action selection before readability targets. The existing guidance correcting the under-animated tram remains useful, but must coexist with the curtain lesson. Avoid replacing a minimum-motion bias with a universal stillness bias. Bring sound into the first motion review. The normal milestones should be a composition proof, a motion-and-sound draft and an exact review movie, scaled to user scope and autonomy.

Keep [CAPABILITIES.json](../docs/CAPABILITIES.json) and current contracts as the capability sources. Older audits/roadmaps are evidence of past states, not a list of still-missing features. Add a small executable example for each newly shipped route; do not make link/frontmatter checks stand in for an operator trial. Update skill examples only when their proposed commands exist.

### MRR-10 — Evaluate creative decisions and production effort

The existing [agent scenarios](../tests/agent-evaluations/scenarios.json) explicitly remain `not-run`; synthetic CLI replays establish mechanics, not autonomous artistic behavior. This film is useful observed production evidence, but it is not a controlled pass of those declared trials.

Add contrasting sheltered/open-window/haunted cases to evaluate motivated motion, plus general feedback with no timestamp and continuation after interruption. Use supplied existing art and declared local resources for the initial trial. Compare whether the operator preserves the intended theme, proposes appropriate alternatives, reaches an actual picture-and-sound review and uses the public CLI without avoidable manual edits. Record interventions, custom script volume, response bytes, time to first useful review, unnecessary questions and unresolved observations. Avoid an aggregate aesthetic score.

Extend existing tests with the implementation they protect: feedback subject/lifecycle compatibility; bounded status projection; dead-run state; clock transactions; cel-alternative proofs; optimization fidelity; and actual studio playback/seek/sound behavior. The current JavaScript/raster checks and source inspections do not claim a browser-engine playback test. Keep native media tests in the existing macOS lane rather than creating another generic test runner.

## Script refactoring boundaries

| Existing project work | Destination |
| --- | --- |
| Room-specific polygons, desired folds, palette and composition choices | Remain authored project recipes/data; no attempt to infer artistic decisions from a generic helper. |
| `record_image.py`, source identity and retrieval bookkeeping | Thin use of the existing generation ledger; reduce duplicate adapters. A submission queue is not justified by this audit. |
| `author_intent.py`, `reconcile_production.py`, `capture_review_setup.py`, parts of `select_fast_build.py` | Validated plan/fulfillment/iteration authoring operations and derived summaries. |
| `trim_runtime_cells.py` | Reusable source-mapped compiler/preparation transform with registration tests. |
| `bake_fixed_look.py` | A constrained preparation recipe or measured renderer optimization with explicit fidelity limits. |
| `prepare_audio.py` | Preserve take selection as a creative decision; reuse the existing PCM session/mixer and consider a narrow native decode/import adapter. Do not grow a DAW or normalize to an invented universal target. |
| `record_first_reviews.py` | Bounded updates to actual review observations; retain unperformed fields and exact subject checks. |

Extract pure preparation/domain functions before replacing scripts with wrappers. Keep imports free of production side effects. Prefer direct domain-service calls within Python orchestration over recursively reparsing CLI arguments, while keeping public CLI replay tests. Make this a touched-code refactor: [production.iteration.step](../ambiance_studio/production.py) currently invokes `cli.run(parser().parse_args(...))`, and preparation has its own subprocess wrapper. There is no evidence supporting a wholesale rewrite, new database or separate orchestration platform.

## Delivery order and evidence

1. Ship compact status/effective run state and ordinary feedback capture; integrate open feedback into next-work reporting. These have direct reproductions and limited artistic uncertainty.
2. Use a curtain revision as the pilot for motivated direction, meaningful static/restrained cel alternatives and an early paired picture-and-sound review. Keep adding draft artifacts distinct from changing current review selection.
3. Add render benchmarking/progress/cancellation and the clock/fulfillment authoring primitives. Measure how much project scripting disappears.
4. Profile and promote only the demonstrated optimization work; update skills/examples with the supported path and run the contrasting operator trials.

Use the existing production backlog as the implementation task home when work is selected. This report supplies new evidence and proposed slices; it does not reset completed foundation work or silently mark historical trial criteria complete. Defer broad provider queues, physics systems, new editor frameworks and social-messaging integrations.

Audit verification: `./ambiance doctor` found Python/Pillow, Node/Canvas and the native macOS backend available; it did not exercise native media services. `./ambiance test` discovered 316 Python tests: 301 passed, 13 native tests skipped, and two localhost server tests failed at sandbox socket setup. Those exact two tests passed when rerun with localhost access, yielding 303 executed Python tests passing across the runs. All nine JavaScript check groups, package audit and failure-contract probe passed. The original aggregate test report remains a failed invocation and has not been relabeled. No fresh native-media suite, browser playback session, complete movie audition or controlled agent trial was performed in this audit.
