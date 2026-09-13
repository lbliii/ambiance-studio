# Agent-operated traditional animation

September 13, 2026. Product direction adopted from the pilot discussion. This document explains the direction and acceptance changes; package status remains in [first-short work packages](FIRST-SHORT-WORK-PACKAGES.json), film milestone status in the [roadmap](FIRST-SHORT-ROADMAP.md), and shared ownership in [studio alignment](STUDIO-PLAN-ALIGNMENT.md). It describes planned work, not new executable capabilities.

## Purpose

Build a studio where agents carry out traditional animation production under human creative direction. The human directs the story, appearance and performance; agents prepare artwork, stage scenes, animate, inspect results and carry out revisions using durable, editable production files.

Animation conventions supply a language shared by agents and human animators: model sheets, storyboards, layouts, key poses, breakdowns, exposure sheets, drawing substitutions, pencil tests, dailies and retakes. The CLI should make meaningful production changes available in batches. Browser inspection and optional editing use the same saved work.

Text/reasoning, image generation, visual understanding, and audio generation/understanding have complementary roles. The shared engine executes authored drawings, timing, transforms and compositing. Shot lengths follow the story. A reusable character and its performances should make later scenes easier to produce and revise.

Generated video is an optional, explicitly scoped source or reference. The primary development path is agents authoring animation with text, image, audio and vision capabilities. A comparison against generated shots is not a prerequisite or the success criterion for this roadmap. Existing ambiance films and local cycles remain first-class uses of the shared foundations.

## What changes in the roadmap

The existing character, finite-clock, mouth-cue, sequence and film-evidence work remains necessary. Two additional packages make the animator's work and observation loop explicit. Revision and reuse acceptance is strengthened in existing production packages. No additional scheduler, model graph, timeline evaluator or review authority is introduced.

| Epic | Change and owner | Observable result |
| --- | --- | --- |
| Familiar animation authoring | **New P15**, with P00 terminology/contracts and P02/P03/P04/P05 native owners | An agent authors and revises a performance through exposure, pose and timing operations that a human animator can inspect |
| Visual and listening dailies | **New P16**, consuming existing proof, media, feedback and review services | An agent examines exact rendered material, records localized findings, makes a bounded correction and reviews the changed result |
| Character construction and finite editing | Keep **P02–P05** as native owners; P15 demonstrates their combined authoring path | Whole characters, selected drawings, local cycles, dialogue and cuts share an explicit authored timeline |
| Direction, continuity and reusable performances | Strengthen **P10/P11/P14**; use model/library owners for portable reuse | Ordinary directing notes produce scoped revisions; a second shot reuses the character without reconstructing unchanged parts |
| Complete pilot | Preserve **P01/P07–P14** and all required story actions | A full editable 60-second film, with measured production effort and exact review media |

P15 and P16 are appended to the backlog to preserve existing package identities; their numbers do not imply that they follow P14. Their integrated demonstrations join P10. Early art, animatic, performance and observation experiments can proceed before that join. An 8–12-second acting proof remains a useful calibration, while the complete minute remains required.

## Animation vocabulary and native ownership

P00 records the minimum shared vocabulary and a small worked shot. P15 implements only the missing authoring/inspection operations after exercising the closest current CLI contracts. Existing identities and editable state stay authoritative.

| Animator's concept | Studio meaning and owner |
| --- | --- |
| Model sheet and expression/pose sheet | Character references, view/drawing identities and supported poses; P02 and model definitions |
| Layout | Framing, character scale, eyelines, floor/prop contact and entry/exit state; P01 and saved scene/views |
| Key pose and breakdown | Authored drawings or rig poses defining the action and its path; P15 uses P02 controls and P03 timing |
| In-between | A deliberately supplied drawing or supported interpolation between poses; new paint uses source/art preparation, evaluated motion uses the shared engine |
| Exposure sheet / X-sheet | Frame-addressed drawing holds, substitutions and dialogue cues; a view/edit interface over canonical tracks and P04 cues, with no independently editable duplicate timeline |
| Animation on ones or twos | Explicit drawing exposure durations, separate from the output frame rate; mixed holds must survive edits and export |
| Pencil test, flipping and onion skin | Fast motion review, exact-frame comparison and neighboring drawing overlays built from the shared renderer; P05/P15 |
| Dailies and retake | Review an identified render, describe the visible/audible issue, author a scoped revision and compare again; P16 and existing feedback/review owners |

Prioritize clear silhouettes, anticipation, spacing, holds, arcs, overlap and readable reactions in agent methods and examples. These are artistic decisions to inspect, not universal formulas or automatic aesthetic scores. Begin with complete pose substitutions, facial drawings and selective articulation. More joints, automatic in-between drawing or general deformation require a demonstrated production need.

Round-trip acceptance means author, inspect, save/reload, revise and render through the same native state. A human-readable exposure sheet must describe the frames actually evaluated. P15 cannot silently change a selected take, character version, finite duration or unrelated track. P03 remains the only owner of shared time conversion; P04 owns cue correction semantics.

## Multimodal responsibilities

These are capabilities, not a requirement for four providers or four agents. Use the available model/tool that can actually perform each operation. Record missing perception capabilities and continue other useful work.

| Capability | Production use | Boundary |
| --- | --- | --- |
| Text/reasoning | Script interpretation, acting choices, tool operation, continuity and correction planning | Authored intent does not establish what the render communicates |
| Image generation/editing | Source drawings, missing poses, expressions, backgrounds and cleanup | Outputs require registration and visual review before production use |
| Vision: still-image understanding | Reference interpretation, suggested parts/landmarks, pose/model comparison, silhouettes and visible seams | A proposal is not an exact mask, a measurement or evidence of invisible paint |
| Vision: temporal understanding | Observe pencil tests, action readability, continuity and apparent contact | Sparse samples can miss fast events; observations must disclose the frames and intervals actually inspected |
| Audio generation/understanding | Voice takes, effects/music, speech/nonverbal timing and listening | Transcript/word alignment is distinct from mouth shapes; rendered audio is not an audition |
| Deterministic tools | Geometry, frame/sample conversion, masks, tracking where supported, rendering and integrity checks | Numerical validity is distinct from apparent contact, expressive acting and listening judgments |

Specialized segmentation, tracking or pose tools may help after a concrete gap is demonstrated. They are not mandatory infrastructure before the pilot. An inferred contour must be inspected; an obscured body part needs prepared artwork. Agent reasoning chooses corrections, while the native tools validate and execute them.

The capability distinction is supported by the existing [narrative research](NARRATIVE-ANIMATION-RESEARCH.md) and provider documentation for [image understanding](https://ai.google.dev/gemini-api/docs/image-understanding) and [video understanding](https://ai.google.dev/gemini-api/docs/video-understanding), consulted September 13, 2026. These sources describe possible inputs and analysis, not measured reliability on our painted characters or an installed studio adapter.

## P16: dailies as a production loop

The intended loop is: plan an action, author it, render a pencil test, inspect picture and sound, write a specific correction, revise, then inspect again. Use ordinary isolated image review while the richer temporal packet is being developed. P16 supplies the missing packet/observation adapters; the agent supplies the artistic interpretation and tool decisions.

Build on actual rig proofs, activity proofs, frame renders, media verification, early review packets and feedback records. A dailies packet selects an exact shot/revision/view and soundtrack. It provides the reference/model sheet, the intended action, normal-speed playback, relevant consecutive-frame windows, neighboring drawings, contact crops and selected audio. It exposes frame/sample mappings and the actual sampling used by any model. Do not require all optional diagnostics for every shot.

Each finding records the inspected artifact and interval, expected versus observed behavior, an actionable location/subject, uncertainty or uninspected material, and a proposed responsible owner. Preserve the observer/model/tool identity and the actual supplied inputs where applicable. Attach findings through the existing feedback/review contract or a narrow typed extension; avoid a second verdict or correction database. Human-required criteria remain human-required. Model analysis does not automatically pass a gate or establish a human audition.

An agent may notice that the dog retreats before its freeze reads, request a longer hold, modify that interval through P15/native tools, and compare the new pencil test. Geometry diagnostics can independently measure a paw's motion. Vision can assess whether the paw appears planted in the painted result. Neither substitutes for the other's observation.

Validate on clean and deliberately defective controls plus an unseen shot or character angle. Include a brief defect between sparse sample times, a false apparent contact, registration drift, and a cue offset. Keep defect labels out of the observer's inputs. Report misses, false alarms, inspected coverage and correction effort; do not invent an automatic quality threshold. A real find/fix/review example and a held-out case are required in addition to synthetic checks. If an available model cannot inspect motion or listen, leave those observations explicitly open rather than claiming complete dailies.

## Milestones and production order

The seven film milestones retain their existing IDs and statuses. The following are added exit criteria within them, not a second status ledger:

1. **Milestone 1: animation brief and animatic.** Add the animator vocabulary, complete action/pose demands, continuity notes and format-specific staging. For the requested TikTok pilot, plan a primary 9:16 composition. The actual project brief records the final format and frame rate.
2. **Milestones 2–3: editable character and exposure proof.** Reconstruct the character, author mixed drawing holds/key poses/breakdowns, inspect the exposure sheet, save/reload and make a timing revision. The same state must drive preview and output.
3. **Milestone 4: observed and revised acting.** P10 integrates P15/P16 with art/audio/timing. Show the speaking/listening/laugh/prop passage, a dailies-driven correction, a reaction delay, and a line replacement. Keep exact before/after media and affected-state changes.
4. **Milestone 5: complete agent-animated minute.** Every required action exists and shot continuity holds. The agent uses supported animation operations; record any custom-mechanics gap and human intervention instead of hiding it behind a completed movie.
5. **Milestones 6–7: direction and reuse.** Finish the film, then give an agent a fresh directing note and a second-shot task using the saved character package. Record adaptation, revised line/timing, scope preserved, and reproducibility of the earlier version. Use existing model/library acceptance where applicable.

Next implementation should join P00's small vocabulary/contracts packet and P01's full-minute story with P02/P03/P04 foundations. Start P15/P16 bounded proofs against existing operations and shared specimens; integrate with P05 before P10 acceptance. P06 proceeds against actual sequence output. This order does not require finishing every workflow, model-library or TV-quality task before acting tests. Existing workstream statuses and dispatch authority remain with their owners.

Measure initial artwork preparation, first-shot authoring, second-shot setup, directing-note correction time, manual coordinate/cue repairs, agent tool calls/retries, human interventions, provider/model usage and actual review rounds. Separate art quality, technical correctness, continuity and observed performance. Measure both first construction and subsequent revisions/reuse; report unknowns explicitly. The first pilot establishes a baseline, not a percentage speedup or a promised production schedule.
