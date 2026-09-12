# TV quality, compact loops, and a reusable sound library

Planning date: September 11, 2026. Baseline inspected: `31390fb`.

The intended product is a short, high-quality ambiance master built from reusable painted and audio sources, ready for full-screen TV playback and later repetition. Keep everyday production compact. A ten-hour movie is an optional delivery, not the working asset.

This plan consolidates the user's discussion of resolution, scaling, long playback, ElevenLabs quality, spatial sound, and a shared sound library. It is a design and implementation backlog, not a claim of implemented features or approval of existing media. The companion [YAML backlog](TV-QUALITY-AND-SOUND-LIBRARY.yaml) owns task status and dependencies. Existing [production work](PRODUCTION-IMPROVEMENTS.md), scene contracts, revisions, and delivery selection remain authoritative for their current functions.

## Decisions and scope

| Area | Core milestone | Later, separate work |
| --- | --- | --- |
| Picture | Opt-in landscape TV profile: 3840 × 2160, 16:9, 30 fps, SDR/BT.709; source-detail and full-resolution inspection | 8K, HDR, 60 fps, and a generalized larger renderer |
| Other compositions | Preserve each film's declared portrait and landscape scope; use 1080 × 1920 for portrait unless its brief says otherwise | No automatic restaging or resolution migration of existing films |
| Duration | One complete authored picture cycle and a compatible short audio/master cycle; repeat in the preview | Hour-long files, streaming assembly, or publishing integrations |
| Audio | 48 kHz stereo production masters, separate stems, source-format records, loudness/true-peak checks, and actual listening | 5.1, headphone spatialization, and immersive/overhead delivery |
| Sources | Continue evaluating ElevenLabs; retrieve the best practical original format and reuse suitable existing sources | Switch provider only for a demonstrated quality/control gap |
| Library | A small collection of 15–20 selected environmental clips, plus reusable mix recipes | Large speculative generation batches or a universal music library |
| Storage | Short media, small previews, pinned source identities, and explicit portable copies | Automatic duplicate archives or expanded ten-hour masters |

Planning does not start paid generations, upgrade accounts, upload films, or schedule work. During implementation, complete local inventory, preparation, proof, and costing first. If a source gap needs paid generation without existing authorization, present the exact prompts, candidate count, duration, format route, and quoted cost for that batch. A target of 15–20 accepted clips is not authorization for 15–20 generation calls; a provider may return several candidates per call.

## What exists and what remains unproven

| Area | Inspected foundation | Gap this plan addresses |
| --- | --- | --- |
| Rendering | Saved views, deterministic rasterization, 1/2/4× supersampling, native H.264 High with BT.709 tags, configurable video bitrate | Output and internal stage are limited to 4096 pixels per side. A 4K output fitting those bounds is not proof of sufficient source detail or TV appearance. |
| Composition | Encoded picture can repeat without re-encoding; exact PCM selection and complete native media verification | PCM must already match final duration. Current in-memory audio and ordinary WAV handling are unsuitable for a promised ten-hour path. |
| Audio | Mono/stereo integer PCM inputs at the session rate; stereo PCM24 mixes; pans, fades, circular tails, stems, cue binding | No built-in resampling, distance EQ, room simulation, LUFS, or oversampled true-peak measurement. Native mux currently encodes stereo AAC at 256 kbps. |
| Spatial sound | Left/right pan and automation; documented direct/room-return separation and near/far treatment | Two-channel mixer, encoder, and verifier; no implemented surround or calibrated 3D acoustic model. |
| Asset library | Image/atlas lookup and inspection, version identities, source-preserving project conventions | The current visual catalog is not an implemented searchable audio library. |
| Provider access | Connected flow types include Sound Effects v2 and Music v1/v2 | Those flow generation controls do not expose output bitrate/format. API documentation is not proof that this connection or subscription can retrieve every format. |

Implementation anchors: [rendering](../RENDERING.md), [views](../VIEWS.md), [audio sessions](../AUDIO-SESSION.md), [sound workflow](../workflows/04-soundtrack.md), [asset/library adapter](../../ambiance_studio/assets.py), [native media backend](../../native/media/media.m), [revision contracts](../REVISIONS.md).

The read-only survey found potential sources in the registered `the-midnight-collection` and `midnight-reading-room` projects: room air, flame/fire, cloth, metal, wind, and paper gestures. These are candidates, not newly auditioned library approvals. The historical [pilot ledger](../../reference/audio-generation-log.json) records woodland, hearth, leaves, bell, and Music v1; a ledger entry does not establish that its original file is available in this checkout. Locate projects through `project list/overview`, resolve retrieval records, and verify actual files before reuse. Do not regenerate a missing-looking result before checking its existing location/history.

## 1. Define output quality before preparing artwork

Add an opt-in `tv_4k_sdr` output profile resolved into existing saved-view and render settings. The name is proposed, not a currently accepted CLI flag. Preserve the authored scene and previous editions when applying it. Do not globally change every project's defaults.

The initial profile uses 3840 × 2160 at the existing 30 fps clock, H.264 High, and BT.709 SDR. Use 40 Mbps as a starting upload-master setting, then inspect the actual encode. YouTube recommends 35–45 Mbps for standard-frame-rate 4K SDR; this is an upload recommendation, not a guarantee of delivered playback quality. [YouTube encoding recommendations](https://support.google.com/youtube/answer/1722171?hl=en)

Use the shared view planner to check both output size and internal full-stage size before rendering. A 1920-square stage enlarged 2× fits within the current limit; a narrow crop or 4K plus 2× supersampling may not. Report the calculated dimensions and explicit remedies. Do not silently lower resolution, discard requested composition, or simply remove the 4096 limit.

If a real required composition cannot fit, benchmark it and plan a bounded renderer change with the same evaluator and finishing behavior. Tile-based or view-local rendering must account for blur, shadows, reflections, and other effects crossing tile/crop boundaries. This is conditional work, not a prerequisite for scenes already supported.

### Effective source-resolution report

Extend asset/view preflight to report, for each visible layer and cel:

- Native original dimensions, prepared dimensions, crop/registration transform, padding, and recorded enlargement history.
- Maximum displayed pixel footprint across the camera, parent rigs, tracks, rotations, and each requested view.
- The worst source-to-output enlargement and its view/time/cel, with source mapping marked unknown when unavailable.
- Whether a previously enlarged derivative masks an undersized original; prepared dimensions alone cannot establish native detail.
- A concrete remedy: better existing source, less magnification consistent with the brief, additional art, or an explicitly reviewed upscale derivative.

Use the existing transform evaluator and preparation mappings. A source pixel budget guides art preparation; it is not an aesthetic pass/fail score. A deliberately soft distant layer and a sharply featured foreground object need different judgment. Small props do not each need 4K source files. Never upscale every asset merely to satisfy a dimension label.

Inspect full-resolution stills at useful camera extrema, then a short motion segment, then the full authored cycle when the staging is stable. Review cutout halos, sprite registration, shimmering, dark-gradient banding, compression, and actual visible life. Supersampling improves raster edges; it cannot reconstruct missing paint. Keep low-resolution previews for daily iteration.

## 2. Keep three clocks separate and files short

| Clock | Owner | Meaning |
| --- | --- | --- |
| Picture cycle | Existing `canvas.loop_seconds` and frame clock | The authored motion returns coherently after this period. |
| Sound/master cycle | Existing sample-frame audio session and selected edition | Music, ambience, and sparse events may span several picture cycles. |
| Requested presentation duration | Preview or future delivery recipe | How long the viewer watches; it does not stretch the motion or alter the source asset. |

For example, a 24-second picture can accompany a 120-second soundtrack. The compact audiovisual master is two minutes, with five picture repetitions. This is illustrative; choose durations from musical phrasing and event cadence rather than imposing those values on every film. Repeated playback of that master requires no ten-hour working file.

Existing `repeats` controls picture composition and still requires matching final-length audio. Use it for short compatible masters. Record the picture's exact frame count, audio sample count, valid loop boundaries, and any deliberate tail/crossfade recipe. Do not duplicate frame T after frames 0 through N−1. A partial-loop proof is not evidence that its arbitrary restart is seamless.

A later duration convenience setting belongs in a delivery recipe, not on each source asset. Specify whether duration must be an integer number of complete master cycles; reject incompatible requests unless a deliberate non-looping ending is authored. Validate finite counts and show an output-size estimate before materializing repetition. A metadata instruction changes playback only in tools that understand it; YouTube does not interpret our project JSON.

YouTube documents a TV/console Repeat control for short uploads. Its editor documents trimming and related edits; the research did not find a supported extend-by-repetition editor operation. A literal ten-hour upload should be assembled externally when required. [YouTube Repeat](https://support.google.com/youtube/answer/10788593?hl=en), [YouTube editor](https://support.google.com/youtube/answer/9057455?hl=en)

The external handoff can supply one good cycle and an editing recipe. Adobe documents looping a single footage cycle; FFmpeg supports input looping and compatible packet copying without another encode. Audio joins and codec padding still need verification; do not offer an untested blanket copy-all-streams recipe as sample-accurate. [Adobe looping workflow](https://helpx.adobe.com/after-effects/desktop/work-with-footage-items/manage-footage-items/footage-items.html), [FFmpeg stream copy and looping](https://ffmpeg.org/ffmpeg.html)

## 3. Preserve source audio quality and measure the mix

### Provider selection and retrieval

Retain ElevenLabs as a candidate supplier. For new music comparisons, explicitly select the available Music v2 model rather than relying on a legacy default. API model IDs and connected-flow model IDs differ; record the actual route and returned ID instead of interchanging them. Keep instrumental selection explicit.

Music v2's documented automatic format is 48 kHz/192 kbps MP3, with 240 and 320 kbps options. Prefer an original 320 kbps download when supported, or genuine uncompressed output when the selected route provides it. Sound Effects v2 has duration, prompt-influence, and loop controls; the overview specifically documents WAV at 48 kHz for non-looping effects and MP3 for all effects. Its API describes additional format options and subscription restrictions. Verify route, entitlement, and actual bytes before promising a lossless looping export. [Music formats](https://elevenlabs.io/docs/changelog/2026/6/22), [sound-effects overview](https://elevenlabs.io/docs/overview/capabilities/sound-effects), [sound-effects API](https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert)

Implement a small local import/preparation path before a provider queue. Probe container, codec, sample rate, channels, bit depth where meaningful, duration, and compressed bitrate. Preserve the original file unchanged. Record source hash, provider output/request identity, chosen candidate, actual model, requested/returned format, source terms reference, and preparation recipe. Do not retain credentials or signed download URLs.

Decode compressed sources and resample once to 48 kHz through an explicitly selected, tested backend. Preserve channel layout; mono object cues can stay mono as source assets. Wrap raw PCM only with known sample format/channel information. A 24-bit production WAV is a working derivative, not evidence of a 24-bit or lossless original. Discover backend availability with `doctor`; do not assume FFmpeg is installed or silently install a tool.

### Acceptance by listening and measurement

Separate two comparisons: format comparison of the same underlying take, and matched-loudness comparison of different model/take results. Comparing two independently generated performances cannot isolate codec quality. Retain audition-only gain offsets rather than destructively normalizing source assets.

Listen for warbling, metallic high frequencies, hiss unrelated to the scene, unwanted voices/music, smeared attacks, abruptly cut tails, repetition, and long-listening fatigue. Review isolated cues as well as the mix at a comfortable low level. Add a recorded natural-source alternative only when it solves an audible problem; the library can contain imported or generated audio. Keep scores specific to the film until reusable musical material has proved useful; pitched loops require key/tempo/harmonic metadata before layering.

Extend the existing measurement reports with a tested implementation of LUFS and oversampled true peak, recording algorithm/backend/version, units, and scope. ITU-R BS.1770 specifies the relevant loudness and true-peak algorithms. Keep current RMS/sample peaks correctly labeled and retain mono, reconstruction, exact duration, and seam checks. Very short or silent clips may have unavailable/gated loudness values; do not invent meaningful numbers. [ITU-R BS.1770-5](https://www.itu.int/rec/R-REC-BS.1770-5-202311-I)

Use a proposed −1 dBTP ceiling as the initial encoded-delivery headroom check, with more headroom when listening or encoding warrants it; this is our provisional engineering choice, not a claim about required YouTube loudness. Do not impose −14 LUFS or the pilot's −22.5 LUFS on every ambiance film. Choose loudness from comfort and creative intent and record the decision. Check the decoded AAC presentation interval separately from the source WAV.

Expose audio bitrate in the edition/export path instead of the current hard-coded 256 kbps. Trial 384 kbps AAC stereo for the high-quality upload profile, matching YouTube's published recommendation; retain a compatible setting when the actual encoder cannot support a requested format and report that incompatibility before rendering. No silent fallback or quality claim based solely on bitrate. [YouTube audio recommendations](https://support.google.com/youtube/answer/1722171?hl=en)

## 4. Build the first sound collection by selection

Collection: **Quiet interiors and nearby nature**. Target 15–20 accepted clips, with 18 as the initial planning inventory below. Counts are a useful size boundary, not a reason to accept weak material or generate missing categories prematurely. Audit current projects first. Add only gaps useful to the selected pilot; a missing category remains visibly deferred.

| Family | Planned assets | Target selected clips | Preparation intent |
| --- | --- | ---: | --- |
| Background beds | Quiet room air, gentle outdoor wind, light rain, small hearth | 4 | Approximately 15–30 seconds each initially; complete natural loops, restrained dynamics; no unrelated events baked in |
| Small movements | Page turn, cloth movement, dry leaves, wood creak | 8 | Two distinct usable variations per action; usually 1–6 seconds plus complete decay; relatively dry and isolated |
| Water | Gentle stream, isolated drip, small ripple | 3 | One bed and two events; choose only where they broaden likely scene use |
| Distant events | Bell, bird call, soft thunder | 3 | Full decay; record whether distance/room sound is baked in; sparse placement recipes |
| **Total** | | **18** | Promote reviewed sources; candidates and rejected takes are separate records |

For each source, prefer independent control. Rain, fire, and paper should be independently mixable. Use relatively dry object sources where feasible; preserve useful distant or reverberant recordings with explicit limitations instead of pretending they can become close/dry. Keep direct sound and room return separate where motion requires it. A stereo bed may already establish a space; adding several unrelated wide/reverberant beds can obscure the scene.

### Library contract and storage

Add a versioned audio catalog alongside the existing visual library through the same CLI entry point. Do not place audio fields into the strict image schema or make current image commands pretend to validate WAVs. Proposed operations are audio-aware search/inspect, local import, short audition/compare, accepted-version promotion, project materialization, and recipe application. Final command spelling belongs to implementation; all mutations need a real CLI path before optional browser controls.

Each record contains:

- Immutable asset ID/version; original and prepared file identities; real byte counts and preview reference.
- Codec/container, rate, channels/layout, meaningful source bit depth, exact frame count/duration, and any lossy-origin flag.
- Loop start/end sample indices and closure recipe, or event tail/silence information; never only a `seamless: true` assertion.
- Role, family, material, intensity, tonal character, near/far suitability, dry/room treatment, channel behavior, and pairing notes.
- Measurements with method, suggested mix gain as a starting point, and audition observations bound to exact files.
- Source/generation provenance, terms reference, preparation recipe, acceptance state, and known limitations.

Use candidate → prepared → auditioned → accepted states, with rejection/revision notes and unknown observations retained. Technical validation cannot assign an auditioned state. One operator owns promotion/review records at a time.

Keep shared media local and out of Git, with small tracked contracts/examples. Select a stable media root explicitly; do not tie the only copy to a disposable worktree. Source hashes and catalogs are not backups. Preserve one managed canonical original and reusable derivative per version; use content hashes to recognize duplicates. Do not delete project originals or accepted versions while organizing the library.

Current sessions require project-contained paths. On use, materialize a pinned copy or safe copy-on-write clone under the film's audio directory with a provenance receipt; keep session paths local. Do not bypass this rule with external symlinks. A portable handoff must include the selected bytes even when the local library is unavailable. Exclude bulk private media from the distributable code package; packaging changes require its audit.

### Reusable recipes

Start with two recipes built from accepted ingredients: **sheltered reading room** and **quiet garden exterior**. Each specifies source versions, intended listener position, relative gains, pan, event times/cadence, available variants, and preserved external processing. Apply into a new editable session; do not overwrite an existing film mix.

Existing executable sessions provide exact placement, repeats, gains, pans, fades, and circular tails. Start with these deterministic features. If later adding randomized event selection, use a saved seed and render the chosen schedule into explicit sample-frame clips; a recipe must reproduce its output. Do not play every library sound in every scene or create copies for every gain/pan adjustment. Preview looping is a playback behavior, not a request for duplicated audio files.

## 5. Make stereo depth convincing; retain a path to surround

For the core milestone, locate the listener and selected sound sources, keep screen-left/right coherent, and use prepared direct/room signals to suggest depth. Preserve cue identity and useful timing in mono. Scene draw depth, sprite visibility, and visual overlap do not supply physical distance or acoustic obstruction.

Make a short near/far/travel study from one source. Record prepared EQ/reverb, direct/return gains, automation, and the exact files auditioned. Compare with the picture and across the join. A room tail already emitted should not move wholesale with the source's new pan position. Existing external preparation remains acceptable; a generalized acoustic engine is outside this milestone.

Store independent source identities and spatial intent so a later mix can route them differently. Do not invent executable XYZ fields in the current stereo session. Version a real spatial-routing contract only when its renderer is implemented.

The later 5.1 phase must extend source layout, bus routing, mixing, encoding, decoded verification, edition identity, and downmix checks together. Speaker channel layout must be explicit; a six-channel count alone is insufficient. Use discrete channel-identification fixtures and an actual supported playback chain before claiming surround. Preserve a stereo edition. 5.1 does not itself supply overhead audio; binaural headphones and immersive formats are separate targets.

YouTube documents 5.1 playback on compatible TV/devices, while its 360/VR spatial-audio path has separate Ambisonics/metadata requirements. Neither establishes that our current stereo movie is spatially encoded. Recheck platform support before selecting a future delivery format. [YouTube 5.1](https://support.google.com/youtube/answer/11904456?hl=en), [YouTube 360/VR spatial audio](https://support.google.com/youtube/answer/6395969?hl=en)

## 6. Prove a compact complete delivery

Select one existing film only after inspecting current project state and a representative source-resolution report. Preserve its current delivery. Use one coordinator for its review records. A small engineering fixture proves API behavior; a real painted film proves the creative workflow. Do not automatically treat a historical review as approval of the new 4K edition.

The pilot delivers:

1. A low-resolution working preview and a source-resolution report for every requested view.
2. Full-resolution stills and short encoded motion proofs, followed by one complete 4K landscape picture cycle once those pass.
3. A compact stereo master spanning whole picture cycles, selected source originals, prepared sources, aligned stems, and an editable session.
4. Both library recipes demonstrated with accepted source versions, without duplicating a long soundtrack.
5. A captured revision and exact view/soundtrack editions verified through existing render/compose/media commands.
6. A labeled delivery presentation with exact and current watch links, actual file sizes, rebuild/import instructions, and open observations.

Keep all existing requested portrait outputs and artistic actions in scope. Full resolution, complete coverage, and a clean encode do not substitute for visible life. Run current canonical coverage checks and, where applicable, `plan check --require-complete`; review actual motion in each declared composition.

Review local encoded picture at 1:1 detail and normal viewing size, then listen to at least three master repetitions using playback repetition. Check TV speakers or the intended soundbar, headphones, mono, and existing required phone checks. Record device, playback path, observer, timestamp, view/role, and movie hash. Leave unperformed checks open while presenting the review movie.

A separate, explicitly authorized upload can later check YouTube's processed 4K picture, audio, and Repeat behavior on the actual TV. A local TV test does not prove YouTube transcoding, uninterrupted playback, or device loop smoothness. Publishing and account operations are not part of this planning task.

## Storage and resource boundaries

| Example | Approximate payload, before container overhead |
| --- | ---: |
| 30-second picture at 40 Mbps | 150 MB |
| Two-minute audiovisual picture payload at 40 Mbps | 600 MB |
| Ten-hour picture at 40 Mbps | 180 GB |
| One-minute stereo PCM24 at 48 kHz | 17.28 MB |
| One-minute MP3 at 320 kbps | 2.4 MB |

These are arithmetic estimates, not observed encoder sizes. Higher source quality costs some storage; avoid multiplying it by hours during production. Keep accepted originals, active derivatives, short proofs, and pinned editions; report storage by category. Scratch retention or deletion must be explicit and must never remove dependencies of accepted editions. Existing immutable snapshots can be necessary duplication; deduplication must preserve their independence and portability.

Do not make all sources 96/192 kHz or force every original into a huge interchange video format. Keep source-native originals and the practical 48 kHz working audio standard. Avoid making full-resolution PNG sequences for long repetition when a short picture cycle and encoded reuse suffice.

Ten-hour PCM24 stereo would contain 10.368 GB of samples, exceeding the ordinary WAV size fields used by the current writer. Float64 mixing buffers and the native verifier's 32-bit WAV counters also need attention for long runs. If long export is later requested, use bounded streaming/chunks and a large-file-capable format or direct encode, preserving exact sample counts and codec delay handling. Verify start, joins, end, timestamps, decode completeness, and resource usage. YouTube's current upload ceiling is 12 hours or 256 GB, whichever is reached first; check it again at delivery time. [Upload limits](https://support.google.com/youtube/answer/71673?co=GENIE.Platform%3DDesktop&hl=en-GB)

## Sequence and completion criteria

| Phase | Outcome | Finish condition |
| --- | --- | --- |
| 0 — Inventory | Locate existing art/audio, current editions, formats, and usable provider routes | Candidate/gap list with verified paths, identities, and explicit unreviewed states; no replacement generations |
| 1 — Quality foundations | TV profile, source-resolution audit, compact clock policy, source import/preparation, loudness measurements | CLI fixtures prove both successful work and explicit failures; one high-resolution proof fits the budget |
| 2 — Sound library | Typed audio catalog, first selected collection, two recipes, stereo depth study | Sources can be found, auditioned, pinned into another project, and reconstructed; gaps remain explicit |
| 3 — Film pilot | A complete short 4K/stereo review delivery with source and loop evidence | Exact verified files, required compositions/actions, current watch links, and honest device-review state |
| Later — Surround | Optional 5.1 with stereo fallback | Actual channel/layout, downmix, encode, and device proof |
| Later — Long delivery | Optional duration expansion or external-editor handoff | Bounded resources, validated joins/duration, size estimate, and tested playback path |

Implement one bounded task at a time from the YAML dependencies. Relative sizes indicate uncertainty, not dates or paid generation estimates. Source generation and listening availability can affect elapsed time, so avoid inventing a delivery date before the inventory and first proof.

For shared code, run `./ambiance test`, the relevant native-media checks, and the renderer/editor checks when behavior changes. Use actual edited scenes in browser checks. Add meaningful negative cases for undersized originals hidden by upscales, oversized internal stages, invalid clocks, wrong-rate/channel sources, changed hashes, broken catalog references, unsupported formats, and unavailable measurements. A portable library import must survive removal of the original library from the test environment. Packaging changes need the package audit. Keep fast tests small; run the 4K/long-media resource tests deliberately, not on every minor change.

The core milestone is complete when the agent can make and present the short TV-quality film through the CLI, reuse accepted sounds in another project without losing provenance, and report what was actually seen/heard. It does not require a ten-hour file, a provider switch, a surround mix, or a platform upload.
