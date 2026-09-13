# Parallel work plan for the first short

Updated September 13, 2026 for [agent-operated traditional animation](AGENT-ANIMATION-VISION.md). This plan decomposes the [first-short roadmap](FIRST-SHORT-ROADMAP.md) into bounded future tasks. No first-short packages have been launched. The [work-package backlog](FIRST-SHORT-WORK-PACKAGES.json) holds package IDs, status, dependencies, acceptance results and task-specific prompts. The roadmap continues to own film milestone status; the research owns the supporting rationale.

**Recommended launch pattern:** a short shared-contract setup, then four concurrent tracks: story/animatic, character tools, finite-shot timing and audio/mouth tooling. The story track can start while the common technical packet is being prepared. Engineering can use independent fixtures before the film's drawings exist. Final production art and performance choices follow the adopted storyboard.

The seven software-development packages are P02–P06 plus P15 animation-convention authoring and P16 visual/listening dailies. They build reusable tools; production packages exercise them with real art and sound. P15/P16 are appended IDs for work that joins P10, not packages after final delivery. Known missing capabilities are implemented upfront, while early reconstruction, voice, gesture and observation trials reveal additional work. The [roadmap's tool-development explanation](FIRST-SHORT-ROADMAP.md) distinguishes this from film-production milestones. P10 is the combined acting/authoring/dailies acceptance test, not the first opportunity to learn from actual artwork.

An observed failure returns to its responsible package with exact source/proof identities, a proposed classification, measured editing effort and the affected requirement. The owner fixes the art, implementation or observation tools, then repeats the failed case and a separate reuse case. Consumers refresh their captured dependency versions and affected checks before resuming dependent work. These follow-ups are a deliberate feedback loop outside the acyclic start/accept dependency graph. A technically accepted package can need further work when real production exposes a new limitation.

The backlog now contains eighteen packages across the whole film; the two additions do not justify increasing concurrency. Several packages are later continuations, and the shot package is a template for a small number of disjoint batches. Use only authorized available worker capacity, including the coordinator in any host/task limit. The coordinating role can remain in the parent task. The lanes below express independent work, not a required number of simultaneously running agents.

| Wave | Packages that can run alongside each other | What unlocks the next work |
| --- | --- | --- |
| Setup | P00 shared contracts/integration baseline; P01 story can begin | Common interfaces and source locations are captured |
| Foundation | P01 story, P02 character tools, P03 finite clock, P04 mouth-cue tooling | Integrated fixture paths and a shot demand list |
| Authoring and observation trials | P15 exposure/pose authoring and P16 dailies after P00, as capacity frees; existing operations/specimens support early trials | Concrete native-operation gaps, animator vocabulary and real artifact observations |
| Assets and assembly | P07H human, P07D dog, P08 sets/props, P09 voices; P05 sequence rendering after P03; P06 film evidence as capacity frees | Selected art/audio plus working sequence/cue paths |
| Acting convergence | P15/P16 integrated acceptance, then P10 acting/authoring/dailies comparison; P06 can finish if still open; P12 sound can prepare | Chosen performance method, observed correction loop and reproducible directing revisions |
| Full film | P11 disjoint shot batches alongside P12 score/effects | Every required shot/action and draft soundtrack exist |
| Edit and finish | P13 one master rough edit, then P14 finishing and final delivery | Complete verified minute and reusable sources |

These waves communicate useful concurrency, not strict global barriers. Start a ready package when its actual dependencies and an owner are available. Reuse a task for a closely related follow-up when that retains useful context. Do not keep an idle implementation task running just to poll another task.

**Shared setup is short but necessary.** P00 establishes interfaces, fixtures and ownership. It should not become a project to build the whole application before anyone else starts.

Use the [studio alignment](STUDIO-PLAN-ALIGNMENT.md) during setup. Align P00/P02 with reusable-model identity, registration and dependency/proof contracts; coordinate workflow adapters around native operations. Keep the existing start/accept graph: a full model-library release is not an extra prerequisite for every narrative package. Shared-file ownership below is a planning boundary to refresh against current command, rendering and evidence adapters before dispatch.

| Shared decision | Required agreement |
| --- | --- |
| Character coordinates | Preserve existing source/reference mappings, full-cell size, padding and pivots; name character, view, part and drawing IDs |
| Model/instance integration | Align stable definitions, nested parts, allowed overrides and immutable dependencies with the model plan; character-specific drawings and controls extend that foundation |
| Time | Frame/sample units, one rounding/conversion implementation, end-exclusive edit ranges, finite end behavior, and legacy loop compatibility |
| Audio and mouth cues | Selected take identity, transcript provenance, cue intervals, drawing-map reference and authored correction ownership |
| Shot/edit selection | Exact shot revision, source in/out frames, edit position, view and soundtrack references |
| Evidence | Receipt identity, dependency hashes, per-shot coverage and aggregate film coverage; which observations remain unperformed |
| Production state | One canonical film address; immutable inputs and exclusive candidate output locations for each worker |
| Animator vocabulary | Model/pose sheets, layouts, key poses/breakdowns, exposure sheets and pencil tests map to native owners; no duplicate editable timeline |
| Dailies | Exact shot/view/audio selection, inspected frame/sample coverage, observer identity, uncertainty and localized findings through existing feedback/review records |

The packet should include tiny test specimens: a registered character with known offsets, two unequal shots, and a selected audio/cue sample with a known edit offset. Specimens expose incompatible assumptions before final art. They do not establish artistic quality.

Changes to a shared interface need an explicit version/diff and a named integration owner. Consumers continue unrelated work, then update together against the revised fixture. “The other task can adapt later” is not a completion condition.

**Four foundation briefs.** The JSON backlog contains fuller dispatch prompts; these are the intended boundaries.

| Package | Own result | Can start with | Does not establish |
| --- | --- | --- | --- |
| P01 Story and animatic | Complete minute, shot list, required-action map, poses/angles/props | Working creative brief and temporary sources | Finished animation or a new runtime sequence feature |
| P02 Character tools | Registered package and source-versus-assembly proof path | Shared coordinate contract and independent fixtures | An aesthetically successful human or dog |
| P03 Finite clock | Deterministic finite sampling and local cycles with legacy compatibility | Shared time contract and unequal-shot fixtures | Encoded movie assembly or final film delivery |
| P04 Speech cues | Saved take → editable mouth intervals → character drawing map | Shared cue contract, fixtures and available audio | A performed laugh or a convincing speaking character |

P04 may implement against a fixed contract specimen while P02/P03 are active. It is accepted only after a real integrated CLI replay consumes their implemented interfaces. P06 has the same relationship to P05's movie receipts. This distinction is recorded as start_after versus accept_after in the backlog.

P15 and P16 may start after P00 with existing operations and independent specimens. P15 acceptance requires integrated P02/P03/P04/P05 authoring/rendering; P16 acceptance requires actual P05 inputs plus performed perception and correction trials. P16 uses existing native correction operations for its own trial, so it does not acquire a circular dependency on P15/P10. P10 combines both packages with real character art and audio. Missing perception capability leaves only its affected observations/acceptance open; unrelated work can continue.

P01's first timed storyboard can use a provisional local slideshow/edit. It must not wait for the new sequence renderer, and must not claim that provisional assembly implements P05. Private source art and voice access are resolved before requesting any dependent generation. Scope and spending authority remain those already recorded for the film.

**Ownership follows actual shared code.** Separate worktrees isolate file edits, but do not prevent two implementations from disagreeing about semantics. The following is an initial ownership map; inspect the actual checkout before dispatch and explicitly lease additional files when needed.

| Owner | Exclusive area during its package | Interface to other owners |
| --- | --- | --- |
| P00 coordinator | CLI parser/command-adapter and command_output.py integration, tools/scene-command.mjs, media_operations.py job registration, docs/CLI.md, docs/CAPABILITIES.json, shared templates/test registration and package-audit integration | Workers provide small hook changes; coordinator installs/tests them early and preserves existing output ownership |
| P02 character tools | New character modules; necessary changes to assets.py, compound_preparation.py, scene_authoring.py and editor/source-placement.mjs; package-specific fixtures/tests | Consume the public evaluator; request evaluator changes from P03 |
| P03 clock | editor/engine.mjs, editor/timing.mjs, agreed common time helpers and finite-clock tests | Publish evaluator/time API consumed by P04/P05; do not change movie assembly |
| P04 speech cues | New take/cue/import/correction modules and their tests | Reuse audio.py/audio_cues.py through existing APIs; request any necessary shared edits explicitly |
| P05 sequence renderer | New sequence modules; render_plan.py/render_execution.py, tools/render modules, native media owners and relevant preview/player integration | Consume P03; preserve compatibility wrappers and shared media operations; emit agreed P06 receipts |
| P06 film evidence | Revision capture/dependency/review and edition owners, coverage context/evidence/records, iteration/delivery owners, required production-plan adapters and evidence tests | Consume the P05 output contract and shared model identities; preserve existing single-scene editions and avoid a second evaluator |
| P15 animation authoring | New authoring/inspection adapters, worked exposure/pose examples and bounded animation methods; proof/preview additions only through explicit leases | P02 owns drawings/controls, P03 time, P04 cues and P05 render/preview; P15 consumes them without independently editable copies |
| P16 dailies | New packet/observation adapters and perception trial inputs/results; narrowly leased proof, packet and feedback hooks | P05 supplies exact media; P06/existing review owners retain evidence/verdict authority; coordinate shared neighboring-frame views with P15 |
| Production workers | Their own immutable candidate asset/audio packages or assigned shot projects | Submit manifests; canonical admission/edit/review belongs to the named integrator |

A listed filename is an ownership boundary, not a requirement to edit that file. Prefer smaller modules and existing library functions. No worker should broadly refactor shared files just to make its package easier.

The public CLI remains the completion path. An internal function and unit tests alone are not an accepted production capability. Workers can prepare their modules and registration hook patches independently; the coordinator integrates hooks early so each package can demonstrate the supported CLI before acceptance. Do not postpone all wiring until the last day.

Public documentation and capability index entries change when a command actually works. Owner-specific design notes can remain in their package directory. Do not rename speculative commands into the current command reference.

**Production media needs different isolation from code.** Worktrees do not automatically carry the private media of an existing project, and different tasks must not independently overwrite its state.

At kickoff, resolve one canonical film project and seed/reference packet. Assign each art/audio worker an exclusive candidate directory or initialized candidate project. Inputs are immutable copies or existing immutable library versions; hashes identify exact sources. Transfer/admit returned packages through the CLI so project-relative paths and dependencies remain valid. Merely symlinking to another task's temporary worktree is not a durable handoff.

One integrator writes the canonical asset catalog, production intent/inventory, master edit, selected voice takes and review records. A lease may transfer that role at a recorded checkpoint. Distinct shot tasks can own their own shot scenes and candidate observations, but cannot change global art versions, timing or the current film selection. Canonical reviews have one writer at a time.

P07H and P07D can be separate art tasks once the common style, character scale and required views are established. P08 needs the same stage/contact conventions. P09 can create/select voice performances independently of final puppets; its actual audio duration returns to the story editor for timing decisions.

**Converge before multiplying animation tasks.** P10 is deliberately one integrated performance owner. It tests the real art, real selected audio, cue tool, clock and renderer together. Its output fixes the production method and identifies defects by responsible owner.

P10 additionally tests familiar exposure/pose authoring and a performed visual/listening correction cycle. It retains before/after media for a dailies correction, delayed reaction and replaced line, plus actual state changes and manual effort. The trial evaluates agent animation under direction; generated-shot comparison is optional and cannot replace this acceptance.

After P10, instantiate P11 as disjoint shot groups, normally two or three shots each. Group related acting/continuity to reduce duplicated setup. Actual shot IDs and batch boundaries come from the adopted P01 shot list; no guessed ranges are dispatched now. Each batch receives:

- Exact character, set, prop and voice-take versions.
- Shot duration/framing and required actions.
- Entry/exit poses, eyelines, screen direction, prop location and lighting state.
- Exclusive scene/output paths and an integration baseline.
- A named director to receive proposed timing or asset changes.

This lets one task animate an investigation while another animates the reveal. Boundary states remain part of the handoff, so individually good shots can form a coherent edit.

P12 can prepare score/effects and a provisional mix against the selected animatic while shots develop. Final conform belongs after the P13 edit selection. P14 may explicitly continue the sound task for that conform while shot owners address their bounded visual notes, but the final edit/review stays with one finishing coordinator.

**Critical convergence points.** Without duration measurements this is a dependency analysis, not a promised schedule.

The integrated acting proof waits for character/art preparation, clock/sequence implementation, voice/cue preparation and P15/P16 authoring/observation acceptance. These can advance concurrently within available capacity; early bounded art/performance checks need not wait for P10. P10 → all P11 shot batches → P13 full rough → P14 finish/delivery is the main production chain. P06 evidence and P12 sound should run before their downstream joins rather than becoming surprises at delivery. P14's fresh directing and second-shot reuse tasks measure effort while preserving the previous accepted film.

A complete-looking engine fixture cannot advance the art milestone. Conversely, useful character/story work need not wait for every evidence adapter. Keep partial progress labeled: planned → active → implementation ready → integrated → accepted. Engineering acceptance means public CLI plus required evidence; artistic acceptance also needs observation of the actual output. Film milestone completion still requires every contributing package and the full stated scope.

**Future dispatch procedure.**

1. Verify that the exact starting commit includes these planning files and the adopted shared interfaces before creating worktrees. Begin from the merged planning baseline, then capture P00's interface packet in the baseline used by engineering tasks. Do not assume future tasks inherit this conversation or uncommitted files.
2. Inspect saved projects and select the correct repository/host. Resolve its worktree support and start from the verified integrated baseline. Record the returned task ID in the backlog after creation; do not pre-invent IDs.
3. Compose each visible task prompt from the common brief, package brief and resolved dispatch context in the JSON. Supply actual absolute project/input/output paths and exact dependency versions. Placeholder paths or an unresolved baseline are not a ready dispatch.
4. As packages integrate, publish a new baseline and launch dependents from it, or explicitly update an existing dependent task. No consumer silently uses only the original baseline after dependencies change.
5. Require a handoff with exact changes/commits, affected interfaces, executable CLI replay, validation results/skips, artifact hashes/paths, issues and downstream effects. Native rendering tests and observations must say whether they actually ran.
6. The coordinator integrates dependency order and runs the affected required suite/package audit on the combined code. Review actual preview/media when behavior changes. A task's green isolated suite does not certify the combined build.
7. Update package status/evidence in FIRST-SHORT-WORK-PACKAGES.json and milestone evidence in FIRST-SHORT-ROADMAP.md. Create further tasks only for the ready packages the user chooses to launch.

The first dispatch group is therefore concrete: P01, P02, P03 and P04, with P00 providing their shared baseline and integration. Later tasks pull from the same backlog as dependencies land.
