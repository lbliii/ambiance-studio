# Roadmap to the first one-minute animated short

Updated September 13, 2026 for the agent-operated traditional animation direction. This is the implementation and production backlog for the first narrative experiment. It is not an executable scene schema or a production already underway. This document owns milestone status; [the research](NARRATIVE-ANIMATION-RESEARCH.md) explains the evidence and design choices. The [parallel work plan](FIRST-SHORT-PARALLEL-WORK.md) and [work packages](FIRST-SHORT-WORK-PACKAGES.json) define future task ownership, dependencies and dispatch briefs.

Follow the [studio alignment](STUDIO-PLAN-ALIGNMENT.md) for interfaces shared with reusable models, workflow guidance and quality/library work. P00/P02 align character/part identity, local/source coordinates and package/proof dependencies with the model contract before dependent implementations diverge. A specialized character package must not create a competing general assembly system. P03 retains finite-clock ownership and existing-loop compatibility. This coordination does not block story, timing specimens or the lantern experiment on completion of the full model-library roadmap.

The [traditional-animation tool research](../research/animation-tools-2026-09-13/report.md) supplies preliminary convention/API comparisons and a reproducible native timing probe. Its exposure-boundary and 24-fps findings inform P03/P15; editorial and review findings inform P01/P04/P05/P06/P16. It proposes bounded studies within these owners and changes no milestone or package status.

**Aspiration:** extend the painted ambiance studio into expressive 2D storytelling while retaining its art direction and handmade character. Vintage Scooby-Doo and Archer are creative reference points for deliberate poses, reusable drawings, staging and voice-led acting. Reaching that quality is a goal to test, not an established capability. Explore ambiance loops and finite stories as workflows over one shared engine; a separate mode selector is not a prerequisite for the first short.

**Product direction:** [agent-operated traditional animation](AGENT-ANIMATION-VISION.md). Agents use model sheets, layouts, key poses, breakdowns, exposure sheets, pencil tests, dailies and retakes to author editable performances under human direction. Text/reasoning, image generation, audio and vision support that work. The primary path does not depend on generated video clips. The pilot must demonstrate agent animation, observation, scoped directing revisions and reuse as well as a finished minute. These are new acceptance requirements, not demonstrated capabilities.

**Current position:** research is complete; all seven production milestones below remain open. The existing studio supplies asset preparation, registered placement, attachments, cel tracks, PCM arrangement, raster rendering, and exact movie reviews. Narrative clock/sequence support, a character package workflow, and imported editable mouth cues still need implementation and real-art validation. No film project has been initialized for this roadmap.

**This is a tool-development project with a film as its working test.** It has two deliverables: reusable narrative-animation capabilities and a complete short made and revised through those capabilities. Seven engineering packages precede or support the film: P02 character construction/proofs, P03 finite-shot timing, P04 audio/mouth authoring, P05 sequence preview/rendering, P06 film-level coverage/delivery, **P15 animation-convention authoring**, and **P16 visual/listening dailies**. P15/P16 extend native owners and are appended to preserve existing package IDs; they join P10 rather than following P14. P00 coordinates interfaces and a small animator vocabulary. Storyboarding and early art/observation trials can proceed alongside engineering.

| Tool work | Known work to do now | What small production tests must determine |
| --- | --- | --- |
| Character construction, P02 | Package consistent drawings and expose source-versus-assembly/pose evidence using existing mappings | Which failures are registration, source anatomy, missing paint or inadequate pose controls |
| Finite timing, P03 | Add finite shot behavior, local cycles and shared time conversion | Whether authored timing and edits are practical on an actual performance |
| Audio/mouth authoring, P04 | Add take identity, mouth-cue import, drawing mapping and editable corrections | Needed corrections for expressive speech, pauses, a dog muzzle and laughter |
| Sequence editing/rendering, P05 | Add shot selection, cuts, synchronized preview and export | Whether real shot/line revisions preserve intended continuity and sound |
| Film tracking/review, P06 | Bind all shot/edit/audio inputs and aggregate required scope | Whether an actual revised film can be reproduced, checked and presented accurately |
| Animation authoring, P15 | Expose poses, breakdowns, drawing exposures, mixed holds, scoped timing edits and pencil-test inspection through native state | Whether an agent and a human animator can understand and revise the same performance without manual coordinate reconstruction |
| Visual/listening dailies, P16 | Assemble exact playback/frame/audio inputs and retain localized observations through existing feedback/review services | Whether available perception identifies real issues, avoids false alarms and helps an agent correct a shot; uninspected material remains explicit |

**Learning happens before and during production.** Begin with independent technical fixtures and early samples of real character art/audio. Baseline one difficult action with the existing supported tools; record the exact inputs, manual correction effort and visible failure. Classify it as artwork, authoring, renderer/timing, or missing observation evidence. Repair the artwork or implement the smallest reusable operation at the responsible layer, then rerun that case and an independent reuse case. A second angle, line, character or shot tests whether the fix generalizes. Compare actual pixels/sound and edit effort, not just a passing geometric check.

These feedback checkpoints start during character preparation and voice trials; they do not wait until milestone 4 or the full movie. Milestone 4 is the combined acceptance test. Only then expand to parallel shot production. More elaborate deformation, automatic pose inference or general-purpose contact solvers remain evidence-triggered options, with the named owner estimating their impact before adding them. A new drawing can be the appropriate solution to an art problem.

The work-package dependency graph describes dispatch order. Learning loops are follow-up fixes to the owning package, with affected inputs, tests and observations rerun; they do not require circular scheduling dependencies. Tool completion and film completion remain separate. The first short must also demonstrate ordinary revisions and reuse, so it leaves a usable workflow for the next film.

**Working brief:** a complete 60-second vintage-inspired mystery-comedy, provisionally titled The Ghost Light, with an original projectionist and nervous dog in an old cinema. The premise and names remain proposals to develop during milestone 1. The requested TikTok pilot now plans primary portrait 9:16 staging at 1080 × 1920, replacing the earlier landscape-only planning default. Two related sets and approximately eight shots remain proposals; cuts and duration follow the story. Test a 24 fps profile before adopting it. Record the final formats and frame rate in the actual project brief. A landscape companion requires its own explicit staging/scope decision; no existing film is reframed by this roadmap edit.

The film must tell a setup, investigation, discovery and payoff. It must include audible dialogue from both characters, a listening reaction, expressive laughter, a head turn, a short walk, a hand/prop interaction, music and environmental/effect sound. Both complete characters belong to their own production assets/rigs, including still parts. A polished talking head or a collection of unconnected shots does not complete this brief.

| Milestone | Visible result | Depends on | Status |
| --- | --- | --- | --- |
| 1. Story and timed storyboard | The entire minute is watchable as an animatic, with animator vocabulary and action/pose demands | Existing foundation | Open |
| 2. Reliable characters | Whole characters reconstruct correctly and expose the drawings/poses required for acting | 1 | Open |
| 3. Narrative timing and editing | Finite shots cut together with synchronized audio; exposure/timing authoring survives save/reload and revision | 1 | Open |
| 4. Dialogue, acting and dailies proof | An 8–12-second passage speaks, reacts, laughs and handles a prop; agent observes and revises it | 2, 3 | Open |
| 5. Complete rough short | Every shot and required action exists in one full minute animated through supported agent operations | 4 | Open |
| 6. Finished picture and sound | Consistent art, deliberate motion, final dialogue and mix | 5 | Open |
| 7. Verified delivery, directing and reuse | Exact watchable final example, reusable sources and a measured fresh directing/second-shot task | 6 | Open |

Milestones 2 and 3 can advance independently after the story establishes their production needs. Bounded character, clock and mouth-cue engineering can begin with shared contracts and independent fixtures alongside milestone 1; real art and integrated performance acceptance still depend on the adopted story. Technical review does not require pausing unrelated reversible work. An artistic concern should revise its affected shot or asset; it should not erase required scope.

**1. Story and timed storyboard.** Initialize the actual film project at production kickoff and keep its brief, sources, selected cast/takes, storyboard, shot list, inventory and reviews there. Register its address through the existing studio library. Write a roughly 60-second script and stage every shot, including camera angle, character pose, clue visibility, entrances, exits and prop contacts. Build a timed storyboard with temporary sound and complete dialogue.

Keep a requirements-to-shot map so each required action has a place in the film. Mark adopted creative requirements as required in the production inventory. Use the current canonical production-plan contract where it applies; identify the film-level extensions needed for multiple shots instead of inventing unsupported fields.

P00/P01 supply a concise shared animator vocabulary and one worked shot: model/pose references, layouts, key poses/breakdowns, exposure intent, dialogue beats and continuity. Stage the clue, reactions and prop action for the primary portrait composition. This is authored intent; exact exposure and timing state belongs to the native authoring owners.

Completion evidence: one complete animatic, a readable clue/payoff, a shot list, and a complete asset/action inventory. Timing is still revisable. Story clarity must work before detailed lip-sync or final rig polish.

**2. Reliable characters.** Design whole-character models in the angles actually needed by the shots. Start with a reference pose, extract derivatives in the same coordinate system, and reconstruct it using recorded mappings, shared scale and pivots. Prepare missing paint beneath overlaps. Preserve complete body ownership when the scene reference is removed.

Use existing preparation, placement and rig proofs first. Add a small character manifest and a reconstruction/pose observation packet only where current tools lack needed information. Include reference/assembly overlays, silhouettes, landmark residuals, joint crops, and normal-speed pose transitions. Check intended proportions after packing, placement and reparenting.

Build a hybrid package: complete pose substitutions, facial drawings, and selective articulation. Prepare each species' own mouth artwork. Keep character placement/scaling separate from part registration. A pose with unsupported perspective or missing anatomy calls for a new drawing.

Expose the character's supported views, named drawings, poses and controls so P15 can author a readable performance. A human-readable model/pose sheet must resolve to the same versioned drawings used in the shot. Broader automatic in-betweening or deformation remains evidence-triggered work.

Completion evidence: both characters reconstruct their reference poses; their planned turns, gestures and extremes remain visually coherent; isolated character removal leaves no duplicate bodies in the background. Record actual observations and exact artifacts. Mathematical socket agreement alone is insufficient.

**3. Narrative timing and editing.** Implement the minimum story path over the shared evaluator: a finite shot clock, local reusable cycles, a sequence edit, explicit source/shot/edit time conversion, and synchronized audio preview/export. Keep existing loop behavior intact.

A sequence must select immutable shot inputs with exact in/out frames and audio offsets. Establish film-level revision and delivery evidence that binds every shot, the edit, and the final mix. Current single-scene coverage/review records must not be presented as certifying an entire multi-shot movie. Preserve per-shot plan checks and add an explicit aggregate readiness path.

Start with two unequal-length shots and a known sound cue. Verify ordinary frame order, out-of-order seeks, shot boundary frames, final-frame behavior, and audio offsets. If the experiment adopts 24 fps, validate it through native encoding and playback. Camera and character drawings need the same authored clock in preview and export.

P15 adds author/inspect/revise operations for key poses, breakdowns, mixed drawing holds and exposure sheets over P02/P03/P04 state. Show animation on ones/twos and longer holds independently of output fps; save/reload, change one hold and render the affected interval. Exposure inspection and pencil-test flipping/onion skins must correspond to the evaluated frames. P15 does not create a competing timeline or change P03's clock ownership.

Completion evidence: an agent-operated CLI replay renders the two-shot example, seeks accurately, and revises one shot duration with correct downstream sound/cue handling. No visible loop reset, missing boundary frame, or silent fallback to stale media is acceptable. These operations are development work, not existing commands.

**4. Dialogue and acting proof.** Select actual character voices and takes for a passage from the animatic. Record voice/take identities and save the final audio. Import a mouth-cue draft through a local analyzer such as Rhubarb, with optional provider alignment. Build explicit mouth-map validation and editable timing corrections over existing cel tracks. Character/word timestamps do not substitute for mouth cues.

Author gaze, brows, head, body and contact beats around the selected performance. Treat laughter as a separately observed audio event. Include a brief speaking turn from each character, a listening reaction, and a visible prop gesture in the 8–12-second proof. Use voice conversion of a recorded performance if it proves useful for delivery.

Compare whole-pose/facial-substitution animation with a version adding selective articulation. Keep dialogue, framing, intended action and artwork as consistent as practical. Record what each version takes to correct. If both look poor, revise the source pose, mapping or performance; do not add joints indiscriminately.

Completion evidence: a convincing short acting passage at normal speed, with correct pause/closure behavior, coherent proportions, readable laughter and credible contact. Demonstrate delaying a reaction by a few frames and replacing one line without manually rebuilding unrelated animation. The remaining film stays required.

P10 also integrates P15/P16: the agent authors the passage through animation conventions, examines exact picture/audio, records a localized finding, makes a bounded correction and inspects the new result. Retain before/after media and the actual state diff. P16's clean/defective controls and held-out case report misses, false alarms and inspection coverage; a packet existing is not a performed observation. Any unavailable motion or listening capability remains explicit. This adds observed correction acceptance to milestone 4 without turning model analysis into automatic artistic approval.

**5. Complete rough short.** Build every shot using the proven approach. Put all required dialogue and actions on screen, including the walk and head turn. Assemble the full minute with rough score and effects. Check screen direction, eyelines, prop state, character scale, and causal continuity across cuts.

Completion evidence: one end-to-end review movie of approximately one minute, with no storyboard placeholders standing in for required animation. Every declared action is visible and every story beat is understandable. Label remaining art, timing and sound issues explicitly. This is a rough film, not a release claim.

Record the agent's supported operations, custom-mechanics gaps and human interventions across all shots. Dailies and correction notes identify the exact artifacts inspected, including continuity at cuts; unresolved perception limitations remain visible. The complete minute must be editable as authored animation and must not be counted complete through unrelated generated replacement clips.

**6. Finished picture and sound.** Refine drawing consistency, articulation seams, pose transitions, motion spacing, facial timing, camera staging, edges and light. Polish the shots in story priority. Prefer well-chosen drawings and holds over increasing movement everywhere.

Finalize voice takes and rebuild affected cues; finish the score, effects and mix against the captured edit. Preserve clean dialogue/music/effects stems. Retain at least the final minute and complete source cycles needed to reproduce it. Freeze final audio timing before export verification.

Completion evidence: the full film has no known required placeholder work; normal-speed picture and listening reviews address the actual chosen files. Character and sound revisions return through the checks they affect. Exact 60-second duration is the delivery target; any deliberate change belongs in the recorded brief.

**7. Verified delivery and reuse check.** Render and fully decode the final movie at the recorded dimensions (primary pilot plan: 1080 × 1920), check picture/audio duration and synchronization, and inspect the complete delivered film. At 24 fps, an exact minute contains 1,440 picture frames; a 48 kHz master contains 2,880,000 audio sample frames. Use the final selected rate if it differs.

Run existing complete-plan checks for each applicable project/shot and the new aggregate sequence coverage check from milestone 3. Verify all required actions and assets against the full film. Distinguish technical success, agent observations, and any unperformed human review.

Bind the final sequence and soundtrack to exact revision/delivery evidence. Present it explicitly in the studio with exact/current watch links. Preserve the script, shots, character versions, selected takes, cue corrections, mix/stems and reproducible render selection.

Completion evidence: one complete, watchable, verified minute; its source package; exact review links; and honest remaining review notes. A final-movie label must not depend on the newest filename. As a reuse check, place an accepted character in a second shot and revise a line without proportion drift or rebuilding the character.

Give an agent a fresh directing note, such as making a reaction more hesitant while keeping the selected line and prop contact intact. Resolve it into explicit intended edits, preserve the prior accepted version, and inspect the resulting performance for regressions. Run the second-shot reuse task from saved production material with a different line or action; a fresh operator context tests the saved handoff without requiring a separately spawned task. Record setup/correction effort and human intervention. The test may establish a baseline even when no time saving is yet demonstrated; it must show the actual revision and reuse working.

**Scope and spending.** This roadmap authorizes no provider spending, installation, account change, publishing or sending. At production kickoff, preserve the user's existing authority and record any authorized generation envelope. Prepare the script, art requests and concrete comparison before seeking any newly necessary spending decision. Reuse existing source media and completed results where possible. Local preparation and technical work can continue while a genuinely dependent generation waits.

**How to track progress.** Each completed milestone gets exact evidence paths, an observation, remaining issues and measured effort in the film project; update only the status and evidence link here. Do not mark milestones complete based on code existing. Track artwork preparation, first/second-shot setup, directing-note correction time, manual coordinate/cue edits, agent calls/retries, human interventions, perception misses/false alarms, revision rounds and actual provider/model usage or costs. Separate initial construction from later revisions/reuse. Use milestone 4's results to estimate the remaining production schedule; no savings claim is implied by a successful encode.

For shared-code changes, run ./ambiance test and the required package audit. Registration/rig changes also require python3 tests/test_assets.py and node tests/test-rig.mjs; include the affected existing placement/timing checks and inspect real rendered output. Add targeted positive/negative tests for finite boundaries, sequence edits, cue offsets, missing drawings and stale evidence. Documentation-only roadmap edits do not require the shared-code suite.

**Resume here:** start with P00's shared contracts, small animator vocabulary and integration baseline, alongside P01's full-minute script, shot list and timed storyboard. Continue P02 character tools, P03 finite timing and P04 mouth-cue tooling against that baseline; start bounded P15 authoring and P16 perception trials using native operations/specimens and integrate them with P05 before P10. P06 retains film-evidence ownership. The character reference and reconstruction plan give the work concrete production cases. All packages remain planned; this direction update launches no tasks. Follow the parallel work plan for resolved paths, ownership and later dependencies.
