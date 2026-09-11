---
name: ambiance-sound
description: "Design, source, edit, and mix a looping ambiance soundtrack with an emotional story and separate stems. Use for music, environmental sounds, cue placement, circular edits, and listening review."
---

# Give the scene a sound story

Read the brief, picture draft if available, and [sound workflow](../../../docs/workflows/04-soundtrack.md). Start sound identity early; a finished animation is not required to sketch it.

Write one emotional sentence and assign near, middle, and distant sound roles. Preserve quiet space. Nostalgia can come from melody, timbre, pacing, and room tone; do not add hiss or crackle by default. The reference film's guiding idea was “A light is still on for you,” not a generic Halloween effects bed.

For spatial storytelling, use the workflow's **Map depth and stereo movement** section. Locate the listener and selected cues; compare near/far and travel treatments before a full mix. Keep direct sound and room return distinct, preserve cue identity in mono, and distinguish measured movement from auditioned distance. Scene draw order is not an acoustic model.

Inspect existing project sound sources before generating replacements; audition and pin reusable candidates. Generate or import music, ambience beds, and isolated events separately. Use the provider's dedicated music/sound-effect tools and skills. Follow the workflow's source-format and reuse guidance: actual connected-tool controls and returned files can differ from public API options. Preserve original quality and document preparation. [Provider operations](../../../docs/PROVIDERS.md) covers route capabilities, spending, uncertain outcomes, and retrieval.

Audition selected sources; note hiss, warble, unwanted voices, harsh attacks and musical restarts. If audition is unavailable, label sources unlistened and continue useful preparation while that observation remains open. Signal plots cannot establish listening quality.

Use the executable [audio-session contract](../../../docs/AUDIO-SESSION.md) and `audio inspect/mix/compare/check` for selected PCM sources, clips, gains, pan automation and circular tails. EQ, convolution and other unsupported processing need preserved external preparation. Keep legacy descriptive sessions intact; `audio import-stems` creates an executable derivative without claiming to reproduce their processing.

Bind picture-linked clips with `audio cue-bind` against a complete stride-one activity receipt. After scene timing, action or loop changes, run `audio cue-check`; explicitly revise affected anchors/session timing and preserve source/PCM identities. Reuse the same soundtrack across compatible views without inventing a new audition. See [activity and cues](../../../docs/SCENE-ACTIVITY.md).

Choose a compact master period spanning whole picture cycles without distracting event repetition; extended viewing is separate from asset duration. Edit compatible musical phrase/harmony positions and retain room tails across the join; requesting matching endpoints does not guarantee continuity.

Measure the actual sources before setting gain. Quiet generated effects can still contain isolated high peaks. Use level, spectral balance, stereo width, and reverberation to imply distance. Protect mono readability and low-volume comfort. The reference's −22.5 LUFS is an artistic result, not a mandatory target for every project.

Export exact-length PCM masters and aligned stems, then inspect sample counts, clipping, peak method, seam, mono compatibility, and reconstruction. Listen with picture across three playback repeats. Current checks measure RMS/sample peaks, not LUFS/true peaks; current export is stereo, not surround. Preserve actual external processing/measurement evidence and leave unavailable observations explicit.

Close `sound-design` after source selection and audition evidence; close `mix` after the circular edit, measurements, and repeated listening. Do not claim that a 24-bit export recovers detail lost in a compressed source.
