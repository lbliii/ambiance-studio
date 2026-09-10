# Making this repeatable

> Historical design record from the initial studio passes. For current executable capabilities and engineering direction, use [CLI](CLI.md), [studio library](STUDIO-LIBRARY.md), and [architecture](architecture/CLI-FIRST.md). The future-work lists below are retained as history.

## The recommendation

Build a personal **ambiance production kit** around a scene recipe, an asset library, and one deterministic rendering engine. Add a small visual stage for the tasks that are easier to see than describe: placement, anchors, grouping, depth, masks, and timing. Use Python for preparation and inspection, and keep generation services behind replaceable adapters.

The most valuable product is the accumulated library of reusable art, motion, sound, and production decisions. The editor makes that library practical. A prompt box alone would lose much of what made this film work.

## What actually happened

The first version established the art direction and a working vertical loop. Its principal painting carried much of the scene; transforms, leaves, light, and smoke added motion. That was a useful style and composition proof, but depth was limited by objects living in the same painting.

The second version separated sky, moon, clouds, hills, town, woodland, cottage, ground, and foreground framing. It added actual frame sequences for clouds, smoke, flames, windows, and town lights. Shared transforms kept the cottage grounded; separate movement at different depths made the composition feel spatial. The final picture was a 16-second, 1080 × 1920, 30 fps loop.

The last major improvement was sound. The original procedural ambience looped, but its noise and crackle felt staticky and had little emotional direction. The replacement began with the idea **“A light is still on for you.”** An ElevenLabs instrumental, woodland bed, muffled hearth, leaf movements, and distant bell became a layered score. A 48-second soundtrack over three picture cycles made prominent sounds less repetitive. A separate 16-second edit and an ambience-only version were also retained.

These were three distinct design passes: establish the place, give it life, then give it an emotional world. Future projects should preserve those checkpoints while planning all three from the beginning.

## Challenges and lessons

| What made the work difficult | What we learned | What belongs in the kit |
| --- | --- | --- |
| Cutting a house or tree out revealed remnants of the original painting behind it. | A cutout needs a clean background behind it, plus enough overscan for movement. | Layer brief, clean-plate checklist, adjustable camera range, edge-reveal preview. |
| Generated frame sheets needed matte cleanup and alignment; frame contents could drift or include neighboring fragments. | Generated artwork is source material. Alpha, registration, anchors, and cell bounds need a production pass. | Atlas importer, contact sheet, onion-skin view, shared-scale registration, alpha checker. |
| Independent transforms made attached elements risk sliding apart. | The relationship between objects matters as much as their placement. | Groups and named sockets: chimney, window, doorway, branch hinge. |
| Adding bright window cels over already bright windows produced little visible change. | An animated light needs room to change the base image. | Unlit base, emissive mask, glow pass, and a daylight/off-state preview. |
| Scene coordinates, masks, and timing lived in custom Objective-C code. | Every artistic adjustment risked becoming a code edit and another render. | Editable scene JSON and a visual stage; one shared time sampler. |
| The first audio passed seam checks but sounded weak. | Smooth repetition is only one part of good sound. Timbre, contrast, quiet gaps, and narrative matter. | Early audition against the picture; separate sources and stems; an explicit emotional brief. |
| The ElevenLabs browser route had a failing music page, disappearing results, history retrieval, and inconsistent downloads. | A missing result is not evidence that a generation failed. Repeating generation can spend credits again. | Save request receipts and returned IDs, retrieve existing results, verify downloaded files, use a supported API/tool when available. |
| FFmpeg was absent and native macOS codecs needed access outside the sandbox. | Media tooling should be checked before a production run. | A doctor command, pinned production dependencies, and an established export backend. |
| AAC extraction exposed padding beyond the presented audio interval. | Raw decoded length and a video's actual playback timeline can differ. | Validate the final container's presentation duration and sample interval, not only a loose extracted WAV. |

Some original art preparation used bespoke pixel masks and coordinates tailored to this painting. Those scripts are valuable references, but they are not a general automatic scene separator. Turning them into reusable tooling means exposing the decisions and preserving their recipes, not merely renaming the files.

## Reuse at four levels

**Assets:** a cloud sequence, smoke plume, flame, bell, leaf Foley, tree cutout, or architectural element. Store their scale, anchors, lighting, palette, and intended role. A library should help find a compatible object, not just any pumpkin.

**Rigs:** a cottage with windows, smoke, doorstep, and a warm light pool; a town with separately controlled lights; a branch with a hinge and leaf attachment points. Each rig keeps spatial relationships and exposes a few useful controls.

**Motion recipes:** slow cloud drift, quantized cel playback, flame flicker, falling leaves, pendulum sway, and breathing light. Give each a duration, amplitude, phase, seed where relevant, and safe parameter range. Preserve deterministic behavior at arbitrary timestamps.

**Scene templates:** woodland cottage, rainy train window, seaside lighthouse, snowy bookshop, nighttime greenhouse. These reuse composition and depth relationships while allowing new art, weather, motion, and sound. Sound recipes can be shared separately: near shelter, quiet outside bed, occasional distant event, small recurring motif.

Reuse must respect style and perspective. A beautiful cutout painted from the wrong viewpoint or lit from the wrong side will still look pasted in. Tags should include lighting direction, camera angle, palette, and edge treatment as well as subject names.

## When to use cels

Use painted frame sets for **changes in shape or internal detail**: smoke curling, fire deforming, curtains moving, a cat breathing, changing window silhouettes. Use transforms for **rigid motion**: a moon drifting with the camera, a branch swinging, a leaf rotating, a cloud crossing the sky. Combine them when useful.

Keep stable architecture fixed and animate its windows or overlays. Regenerating an entire building for every frame invites structural wobble and makes the asset harder to reuse. Generate a clean master pose first, then variations with fixed framing and a clear invariant list.

Start with a small sequence sufficient for the motion. The successful film used, for example, 12 smoke cels over two seconds and eight cloud cels over four seconds. More frames are not automatically better; consistent registration and an expressive cycle matter more.

## The repeatable workflow

| Stage | Saved output | Review before proceeding |
| --- | --- | --- |
| 1. Creative brief | Mood, place, viewpoint, focal point, style references, sound story, target format, generation budget | Can we describe the feeling and main visual idea in one sentence? |
| 2. Style and composition proof | One approved still and a rough depth layout | Does the phone-sized image already work without motion? |
| 3. Asset breakdown | Asset list, layer groups, motion types, masks, clean plates, sockets | Is everything that will be revealed by movement actually painted? |
| 4. Generate and prepare | Raw sources, chosen takes, registered cels, production PNGs, receipts | Are alpha, framing, scale, pivots, and style consistent? |
| 5. Assemble a short draft | Scene JSON and a low-resolution loop | Is depth readable, are attachments stable, and is movement restrained? |
| 6. Sound sketch | Music identity, selected beds and one-shots, cue plan | Does it tell the same story as the image at low listening volume? |
| 7. Finish the master | Full-length circular mix, aligned stems, final picture | Do three repeats remain pleasant? Is any event becoming conspicuous? |
| 8. Export and inspect | MP4, cover, WAV, stems, technical report | Decode the actual deliverable; inspect on a phone and listen in mono/headphones. |
| 9. Catalog | Reusable assets, rig/template, prompts, hashes, notes | Can a new project find and reuse the good pieces without reading this chat? |

Stages are checkpoints, not a rigid waterfall. Sound should be sketched early enough to influence rhythm. A matte issue should return to asset preparation instead of being disguised with ever more compositing code.

## The tools I would use

For this personal kit, keep a narrow stack:

- **Image generation:** continue the reference-led image workflow that established this painted style. Save prompts, references, and actual returned art. Treat models as replaceable suppliers, because a later generation is not guaranteed to reproduce the original.
- **Python:** file inventory, atlas registration/packing, alpha and edge reports, contact sheets, audio analysis/mixing, and batch orchestration. A production environment should pin its image/audio dependencies; the current starter needs only the standard library.
- **A browser stage and shared renderer:** the starter uses Canvas 2D. Keep preview and export drawing from the same scene/time functions. If measured scene complexity justifies it, PixiJS offers containers for shared transforms and ordered child objects; that matches the rig structure we need. [PixiJS container documentation](https://pixijs.com/8.x/guides/components/scene-objects/container).
- **FFmpeg/ffprobe for production media:** standardize encoding, muxing, and container inspection. Copy the encoded picture when only audio changes, as we did with the native helper here. FFmpeg documents stream copying as a separate path from decoding and encoding. [FFmpeg documentation](https://ffmpeg.org/ffmpeg.html#Streamcopy).
- **ElevenLabs for separate audio sources:** the sound-effects endpoint supports a loop option on its v2 sound model; music supports prompt/composition-plan generation and an instrumental control. Keep editing and loop validation in our own audio stage. [Sound effects](https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert), [music](https://elevenlabs.io/docs/api-reference/music/compose).
- **Git for code, recipes, and manifests; an asset store for media:** start with local versioned folders. Add Git LFS or content-addressed storage when the library warrants it. Avoid checking every draft render into ordinary Git history.

Remotion is a possible render orchestration layer if we decide to use React-based compositions. Its renderer exposes still, frame, and media rendering APIs. I would evaluate it against our shared Canvas/Pixi engine before adopting it, so we do not maintain two different scene implementations. It is optional, not a prerequisite for the kit. [Remotion renderer](https://www.remotion.dev/docs/renderer).

The current machine did not have FFmpeg available; the completed film used Core Graphics and AVFoundation. No new production dependencies or provider connections have been installed for this starter.

## What makes this easy for an assistant

Provide a **small, explicit contract** and stable tools. A named asset, a saved pivot, a documented coordinate system, and a command with machine-readable errors are more useful than a long explanation of how the composition looked last time.

The eventual assistant workflow should be:

1. Read the brief, scene, asset catalog, and current review notes.
2. Choose a compatible template and reuse known assets first.
3. Produce a missing-asset plan with prompts, sizes, expected cost, and attachment requirements.
4. Generate only the missing pieces; retain receipts and verify the returned files.
5. Modify scene and sound-session data through supported parameters.
6. Run draft rendering and focused checks; inspect the contact sheet and looping preview.
7. Present meaningful creative choices and carry the chosen direction through final export.

A future project instruction file or personal skill can describe these steps and command names. The actual project state should live in files, so a fresh session can continue without reconstructing the work from conversation history.

## Efficiency rules

Cache by input asset hashes, recipe version, scene settings, and renderer version. Keep raw sources immutable. Generate low-resolution previews before full exports. Preserve selected takes rather than regenerating a whole set to fix one object. Cache decoded images and atlas crops. Render picture and audio separately, then mux. Store a rejected candidate's reason, so the same mistake is not repeated.

Before a paid request, record its request fingerprint and budget reservation. Where a provider supports idempotency, use it. Where it does not, an uncertain response becomes a retrieval/reconciliation task, not an automatic resubmission. Keep credentials out of manifests and never treat a disappearing UI card as permission to generate another take.

Measure generation cost, retries, preparation time, draft render time, final render time, and review rounds. We did not record a complete timing/cost ledger for this film, so a claimed percentage speedup would be invented. The next project should establish that baseline.

## What to build next, in order

**Milestone 1 — faithful template.** Port the remaining Last Lantern mist, glow, leaves, and audio cues into the shared scene engine. Add exact-frame export and a container validation command. Finish when the new pipeline recreates the complete scene within a documented visual tolerance, preserves loop quality, and produces the expected frame/audio counts. The existing final MP4 and validation records are the reference.

**Milestone 2 — second-scene proof.** Build a different environment using the same commands and renderer. New art and scene data are expected; duplicating the renderer is a sign that the abstraction is incomplete. This is the best test of whether the kit is reusable.

**Milestone 3 — asset workbench.** Add registration, onion skins, matte inspection, atlas export, attachment editing, and metadata search. Save reusable rigs and motion presets from both films. Expose background-reveal checks and editable portrait guides; verify current publishing UI before calling any overlay a platform safe area.

**Milestone 4 — provider and audio workflow.** Add supported generation adapters, a persistent job ledger, retrieval, budgeting, audition comparisons, circular audio arrangements, and per-stem exports. Preserve a manual source-import route so service changes do not stop production.

**Milestone 5 — convenience.** Add batch variants, render queue, thumbnails, project browser, and packaged installation after the creation pipeline works across several distinct scenes. A large dashboard will not solve weak asset contracts or inconsistent art.

The immediate next investment should be the faithful template and a second scene. Those two steps will tell us which tools deserve to become permanent.
