# Narrative animation research and first experiment

The [first-short roadmap](FIRST-SHORT-ROADMAP.md) owns the implementation/production milestone sequence and status. This research remains the supporting rationale.

September 12, 2026. Research and proposed design, not an implemented narrative mode or a completed animation test. Code inspected at revision 23f9ca7d8ecb89708520a7b9042b09640eeb623c. The working tree was clean before this research. User direction: explore vintage television-style 2D storytelling, ElevenLabs character acting, and a roughly one-minute mystery; explicitly investigate earlier failures involving body-part proportions and placement.

**Assessment.** A bounded short is a credible development experiment. The current studio has a useful rendering, asset-preparation, registration, sound-arrangement, and review foundation. Its missing narrative capabilities are finite shots, a sequence edit, reusable character performances, and an audio-to-mouth authoring path. Consistent character drawing and readable acting remain artistic work. Neither published provider features nor geometric checks establish that our results match Scooby-Doo or Archer.

Archer's animation leads describe separately illustrated body parts linked into 2D puppets, elaborate reusable heads, and an animatic with recorded dialogue feeding animation. They also describe revising boards when the actor's delivery changes the intended timing. This supports investigating our approach and putting selected audio early in the process. It does not establish equivalent tooling or production quality here. [Production-team interview](https://www.awn.com/animationworld/animating-archer).

**One studio with two workflows.** My recommendation is to keep a shared evaluator, asset library, preparation tools, sound pipeline, and delivery system. “Ambiance” and “Story” can be authoring presets with different timing and review needs. A character workbench is a reusable workspace within either workflow.

| Workflow | Timeline behavior | Main review question |
| --- | --- | --- |
| Ambiance | Periodic scene, reusable cycles, deliberately circular audio | Does it remain alive and resolve naturally across the join? |
| Story | Finite shots assembled into an edit, dialogue and event cues | Does each performance and cut communicate the intended story? |
| Character workbench | Isolated poses, expressions, actions and audio takes | Is the character consistent, expressive and reusable? |

Keep presentation format independent of workflow. A narrative project should declare its own outputs; this proposal starts with landscape 16:9. A later portrait version needs its own staging decision. The ambiance studio's dual-output defaults should not accidentally double the experiment's scope.

A proposed hierarchy is Film → Sequence → Shot → staged character/set instances. A set contains reusable artwork; a shot contains a particular framing and performance. Two shots can use the same set and different poses. Rain and a walk cycle can still loop locally inside a finite shot. This hierarchy is a proposal, not current scene JSON.

The present evaluator wraps time modulo the picture duration. Tracks close or use an explicit hidden reset, and interpolation is linear, smoothstep, or hold. Smoothstep stops at each key. Source cels can already have deliberately unequal holds. Paint order is fixed; attachment order does not determine compositing order. These details are implemented in [engine.mjs](../../editor/engine.mjs) and documented in the [scene contract](../SCENE-CONTRACT.md).

For production, add a versioned finite-clock policy that leaves existing loop scenes behaving identically. A shot should clamp/hold or end at its boundary, while cyclic sub-actions retain their own phase. Add a sequence manifest with exact shot revisions, source in/out frames, edit start frames, camera/view selections and audio offsets. Preview and export must evaluate the same selection. Shot edits should invalidate only affected renders and dependent sound/beat evidence. Merely concatenating existing movies can make an early assembly, but does not provide this editable contract.

**Mapping voices to characters is practical.** There are three distinct layers of information: speaker identity, the timing of audible speech, and a performance interpretation. They should be saved separately.

| Input or tool | Verified capability | Implication for our design |
| --- | --- | --- |
| ElevenLabs TTS with timestamps | Returns audio plus original and normalized character timing | Useful alignment evidence; letters are not phonemes or mouth shapes |
| ElevenLabs dialogue with timestamps | Returns character alignment and timed voice segments tied to dialogue input indices | Can associate spoken segments with a cast member |
| ElevenLabs forced alignment | Aligns supplied audio and transcript at character and word level | Useful for final audio from another route; no documented phoneme/viseme output |
| Eleven v3 direction tags | Supports expressive delivery and nonverbal events such as laughter; results vary | Audition/select the performance before final mouth timing |
| ElevenLabs Voice Changer | Designed to preserve emotion and delivery from an existing performance | A recorded acted take can guide a difficult laugh, hesitation, or emphasis |

These are direct documented capabilities. See [TTS timing](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps), [dialogue timing](https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert-with-timestamps), [forced alignment](https://elevenlabs.io/docs/api-reference/forced-alignment/create), [expressive dialogue](https://elevenlabs.io/docs/overview/capabilities/text-to-dialogue), and [Voice Changer](https://elevenlabs.io/docs/overview/capabilities/voice-changer). The dialogue endpoint currently defaults to eleven_v3. Do not extrapolate its timing behavior to every model exposed by a connector.

Read-only inspection of our connected ElevenLabs tools confirmed speech generation models including eleven_v3 and a Voice Changer node. The exposed creative speech/status return schemas do not promise detailed alignment or mouth cues. Direct API documentation describes additional endpoints; that is not proof that the connected generation tool returns those fields. Our adapter should accept saved final audio and optional alignment, using an explicit API integration or local analysis when needed. [Inspection record](../../reports/narrative-animation/2026-09-12-capabilities.json).

Use stable cast IDs mapped to voice IDs, dialogue input indices, and selected take hashes. A voice ID alone is insufficient if reused for several roles. For the first test, prefer separate clean takes for each character. A combined dialogue response is not documented as isolated speaker stems; overlapping voices complicate subsequent lip analysis and editorial replacement.

The proposed path is:

Selected performance → preserved audio/transcript → timed mouth-cue draft → character-specific drawing substitutions → authored eyes, head, body and prop beats → synchronized shot review.

Rhubarb is a particularly suitable first adapter: it is a CLI that reads recorded audio, can use a transcript, and exports time intervals with mouth-shape IDs as JSON. It supports six basic shapes and three optional additions. This is a compact match for our existing cel hold tracks. Its documentation links the basic shape vocabulary to Hanna-Barbera production. Treat its output as a draft requiring review. It was not found on this session's PATH and was not installed or run. [Rhubarb documentation](https://github.com/DanielSWolf/rhubarb-lip-sync).

Adobe Character Animator provides an independent workflow reference: audio plus transcript produces editable visemes, and lip-sync takes can be exported to After Effects. That supports retaining both computed cues and manual corrections. It is an optional comparison tool, not a required dependency for this studio. [Adobe transcript-based lip sync](https://helpx.adobe.com/au/adobe-character-animator/desktop/behaviors/learn-more-about-behaviors/body-directly-controlled.html).

The proposed importer must preserve the original cue output, selected audio hash, transcript and recognizer settings. Convert clip-relative time into shot time using explicit offsets, then quantize once to the output frame grid. Report short cues lost to sampling, collisions, and missing mouth drawings. Retain deliberate pauses and important closures; avoid rapid chatter caused by every tiny analysis change. Corrections should be editable intervals and should become stale when the selected audio changes.

Our audio backend currently requires already prepared PCM at the session's rate. Any decoding, resampling, trimming or voice conversion should produce an identified derivative before final alignment. Check synchronization against decoded delivery audio as well as the local WAV. These are proposed adapter requirements using the existing [audio](../AUDIO-SESSION.md), [timing](../SCENE-TIMING.md), and [cue](../CLI.md) foundations.

**Speech timing is only one part of acting.** For a line such as “Wait. These footprints are painted,” the semantic performance could be:

| Beat | Mouth | Other performance |
| --- | --- | --- |
| Notice the clue | Rest | Eyes move to floor, then head follows |
| “Wait.” | Timed speech shapes | Brief hand arrest; companion stops |
| Inspect during the pause | Rest | Brow narrows; gaze stays on clue |
| “These footprints…” | Timed speech shapes | Point toward the actual clue |
| “…are painted.” | Timed shapes with emphasis | Look to companion; hold the discovery |
| Companion responds | Speaker's mouth rests | Listening reaction continues |

This is an authored example, not measured timings or a universal acting formula. I can propose these relationships from the script and express them as saved cues. Exact timing needs the selected performance and visual iteration. Tools should make uncertain assumptions inspectable, rather than assign an invented confidence score to “good acting.”

For Scooby-like laughter, a speech recognizer should not be trusted to invent ordinary word timing. Mark the laugh interval from actual audio; use its audible pulses as candidate jaw accents, then author the anticipation, eyes, cheeks, head movement and recovery. Volume can suggest emphasis, but should not directly wag every body part. A dog needs muzzle-specific drawings and poses; a human mouth sheet pasted onto its face is inadequate. Start in one approved angle, then supply distinct registered drawings for a turn. A laughing head and a walking body can require a coordinated replacement pose.

Voice Changer provides a second performance route: someone records the intended delivery, then the selected character voice is applied. Analyze and audition the returned audio, since preserving expressive intent does not establish sample-exact identity. This can be useful when text prompts do not reliably produce a particular rhythm.

**The earlier puppet failure should shape the experiment.** The user reported wrong proportions and placement in prior assembled puppets. Those assets were not located or visually re-audited during this research, so the exact historical cause remains unverified. The current code does, however, address several relevant sources of error:

| Current tool | What it actually protects | Remaining limit |
| --- | --- | --- |
| Compiler registration mappings | Records crop, scale, padding and reference-to-cell transforms | A mapping cannot fix a badly drawn limb |
| Compound preparation | Parts share a reference canvas and fixed registration | Hidden surfaces need real reconstructed artwork |
| Native source placement | Derives a one-cel cutout's intended dimensions from its mapping | Multi-cel sprite placement still needs explicit full-cell size |
| Reparent with keep-world | Preserves evaluated geometry at a stated time | Does not preserve an entire animated trajectory; child transform tracks have restrictions |
| Cel sockets and motion studies | Maintains declared attachments; can correct bounded translation drift | No automatic anatomical reasoning, deformation or in-betweening |
| Raster/rig proofs | Shows isolated subjects, joints, backing and poses | Must actually be inspected; a passing graph is not a pleasing character |

Evidence is in [source placement](../SOURCE-PLACEMENT.md), its [implementation](../../editor/source-placement.mjs), [compound preparation](../AGENT-PREPARATION.md), and [cel motion](../CEL-MOTION.md).

My proposed remedy begins with a complete approved character drawing in a known pose. Extract derivatives from that common coordinate system, reconstruct the original pose automatically, and compare the assembled result against the source before animation. Preserve original proportions throughout cropping and atlas packing. Scale the character as one instance when placing it in a shot.

For replacement drawings, retain a canonical character-space registration, named landmarks, the intended view/angle, and the supported action range. Never infer body-part proportions from each part's alpha bounds. A correctly sized transparent canvas also does not prove that generated paint stayed registered.

Toon Boom's rigging guidance makes a related distinction: a permanent parent pivot stays consistent across substitutions, while the replacement artwork must be drawn to fit it. Its substitution guidance also calls for matching line style and the rig's existing masking/separation. This reinforces the need to prepare compatible drawings rather than compensate with arbitrary scene transforms. [Pivot guidance](https://helpcentre.toonboom.com/hc/en-ca/articles/41016209632531-What-is-the-difference-between-a-peg-pivot-and-a-drawing-pivot), [drawing substitutions](https://helpcentre.toonboom.com/hc/en-ca/articles/41014001536275-How-do-I-add-a-substitution-drawing-while-animating-a-rig).

A character observation packet should show the source beside the reconstructed neutral pose, a transparent overlay/difference, landmark residuals, full silhouettes, enlarged joints, and normal-speed rest/extreme/transition clips. Include ordinary poses as controls, not just automatically ranked problem frames. Check feet or paws against the floor and hands against props at relevant times. A perfectly attached wrist can still belong to an anatomically wrong arm.

This packet is an extension of existing proof tools, not a currently implemented character quality judge. It should return bounded actionable findings—wrong registration, missing paint, incompatible pose, unsupported contact—plus exact image/clip paths. I can then adjust a bounded recipe and compare again. That gives visual judgment better evidence and reduces repeated coordinate guessing.

**Use a hybrid representation.** Choose the animation method per action:

| Method | Best initial use | Main risk to test |
| --- | --- | --- |
| Whole pose replacement | Strong silhouettes, turns, recoil, foreshortened hands | Pose continuity and more drawing preparation |
| Limited articulation | Head tilt, arm gesture, prop movement | Seams, incorrect pivots and mechanical movement |
| Facial substitutions | Speech, eyes, brows, expression accents | Incorrect register or excessive mouth chatter |
| Authored cel sequence | A specific walk, broad laugh or unusual action | Temporal consistency and registration |
| Generated performance video | Optional reference or finished-shot comparison | Local editability and stable artwork/backgrounds |

A universal articulated puppet is not a prerequisite. Begin with complete pose drawings, a small face package and only the joints a shot needs. Add smooth curves, contact solvers or mesh deformation when an actual shot shows a limitation. Existing tracks can already express pauses and simple coordinated gestures.

Runway Act-Two is a credible alternative to evaluate separately. It takes a driving performance video plus a character image/video and can transfer expressions, with support described for nonhuman characters. Its documentation says image inputs add environmental motion and that more expressiveness can produce artifacts. My inference is that it could supply acting reference or a comparison shot, while requiring separate tests for stable painted lines, precise prop contact, and editability. It does not document an export of our reusable rig controls. [Runway performance capture](https://help.runwayml.com/hc/en-us/articles/42311337895827-Performance-Capture-with-Act-Two).

**Proposed experiment: The Ghost Light.** An original vintage mystery-comedy with a projectionist and a nervous dog investigating a “ghost” in an old cinema. They find painted footprints and expose a projected silhouette; one final sound leaves the dog unconvinced. This is a proposed brief, not approved artwork or a production already started.

The intended deliverable is a complete approximately 60-second landscape short with two characters, two related set paintings, about eight shots, a clear clue and payoff, dialogue, a laugh, one short walk, one prop interaction and a head turn. These requirements remain in scope even while testing a smaller passage.

| Approximate edit range | Story purpose | Capability exercised |
| --- | --- | --- |
| 0–6 s | Establish closed cinema and strange sound | Ambiance/set reuse |
| 6–14 s | Introduce investigators and ghost silhouette | Staging and readable reaction |
| 14–22 s | Projectionist notices painted footprints | Gaze, pointing and clue delivery |
| 22–29 s | Dog gives nervous reply/laugh | Nonhuman speech and nonverbal acting |
| 29–39 s | Follow the clue to the projector | Short locomotion and continuity |
| 39–48 s | Handle a control and expose the trick | Hand/prop contact and cause/effect |
| 48–56 s | Relief and comic exchange | Listening poses and timing |
| 56–60 s | A final unexplained clap | Held reaction and ending |

These are draft editorial allocations, not audio durations. Revise the animatic around selected takes.

1. Build the whole-minute rough animatic and declare its required actions. Use temporary voices or existing audio first. Judge clarity and pacing before detailed rig work.
2. Prepare one approved human model and one dog model. Reconstruct their neutral poses, then inspect the planned view and action extremes.
3. Produce an 8–12-second dialogue/reaction passage from the intended short. Compare a whole-pose/facial-substitution version with a version adding selective limb articulation, holding artwork, dialogue, framing and intended beats as constant as practical.
4. Use the preferred approach for the full minute. Preserve all required actions; do not replace the film with the easier close-up test.
5. Present the exact complete review movie and record changes needed for a second short.

A 24 fps experimental output can test two-frame drawing holds with selected faster accents. The renderer accepts positive integer frame rates, but this narrative profile has not been validated through a full delivery. Keep mouth timing and motion sampling explicit; changing the output rate alone does not supply new drawings or better spacing.

Success means the clue is understandable, each character stays on-model through poses and cuts, speech closures and pauses look credible, the laugh involves a readable performance, and contacts do not slide. A reviewer should understand the scene at normal speed without annotated arrows. Technical checks should cover all presented frames, audio offsets, changed-source invalidation, missing drawing IDs, pose registration and the encoded movie. Actual artistic observations remain separate.

Measure first-character preparation effort, setup effort in a second shot, manual cue corrections per ten seconds, visual defects, revision rounds, render latency, and any actual generation cost. Attempt two concrete revisions: delay a reaction by a few frames and replace one line. Those reveal whether the tool supports direction efficiently. Do not estimate series throughput from a single successful shot.

**Development order.** Build the smallest CLI operations that make this experiment repeatable, using existing evaluator and proof functions.

| Slice | Proposed operation | Completion evidence |
| --- | --- | --- |
| 1 | Character registration manifest and reconstruction/pose proof | Real character retains proportions through compile, placement, reparent and chosen poses |
| 2 | Audio take record, cue import, mouth-map validation and corrections | One saved take drives a talking head; missing/stale cues fail clearly |
| 3 | Finite shot clock and sequence assembly | Two unequal shots cut correctly with aligned dialogue and no visible reset |
| 4 | Named acting beats and coordinated pose packages | Speaking and listening reactions can be revised without moving unrelated layers |
| 5 | Complete short, exact review presentation and reuse trial | Sixty-second story plus a second shot/line revision with measured effort |

The order is a dependency guide, not a demand to stop reversible storyboarding while tools develop. Slice 2 can use a clearly labeled local test scene before finite narrative rendering exists. Future schemas and operations must be documented as implemented only after executable CLI examples and tests pass.

For shared-code changes, use the repository's required suite and package audit; include the existing rig/compiler tests for attachment or registration changes. Add meaningful finite-clock, edit-boundary, cue-offset and stale-input failures. Inspect actual browser and encoded output when preview/render behavior changes. No tests or generations were run during this research because it changed only research artifacts.

The immediate next useful work is a character reconstruction proof and the rough full-minute animatic. This tests the user's reported weakness early while preserving the storytelling objective. The project can earn more articulation through evidence; the goal is a character whose decisions read on screen and whose performance remains easy to revise.
