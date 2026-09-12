# 04 — Sound as a place and a story

**Input:** creative brief and picture draft when available. **Output:** sound brief, sources, audition notes, circular session, masters/stems, measurement and listening evidence. **Gates:** sound-design and mix.

## Define the listening position

Write an emotional sentence and locate the listener. What is near, what is behind a window, what is across the valley? Choose a musical identity or environmental focus. Decide where to leave quiet. Do not assign a literal sound to every visible object.

The Last Lantern used a small musical identity, muffled hearth, quiet outside air, leaf movement, and one distant bell. The music made the place welcoming; the bell suggested a wider world. That relationship can transfer to other themes without copying the same notes or sound effects.

## Map depth and stereo movement

Make a small sound map alongside the layer plan. Choose whether the listener stays with the camera or occupies another intentional position. Separate local object sounds, diffuse room ambience, and the score: music need not move with an exhibit. Include only cues that serve the scene, with quiet between them.

For each selected cue, record its source/identity, near/middle/far role, screen region or route, timing, and intended obstruction. Visual draw order and painted scale help stage a cue but do not supply physical distances. Keep screen-left and screen-right consistent with the picture. A sound can continue off screen; hiding a sprite does not automatically silence it.

| Decision | Starting treatment | Judgment to check |
| --- | --- | --- |
| Near versus far | Compare the same source: clear direct detail nearby; lower direct level, gentler high frequencies and more room relative to direct sound farther away | Does the object retain its identity? Do not normalize the far version back to the near version's level. |
| Static left/right location | Place the direct cue near its apparent source; choose a restrained stereo width | Does it belong to the visible object without pulling attention away from the main action? |
| Travel | Automate pan smoothly across the actual cue duration; coordinate level, tone and room send when distance also changes | Does the sound follow the route and pace, including offscreen continuation? |
| Glass, wall or doorway | Alter direct level/tone and reflected sound for a plausible obstruction or connected room | Visual overlap alone is not acoustic blockage. Preserve room tails instead of abruptly muting the entire cue. |

Level, tonal balance and the contrast between direct sound and reflections can suggest front-to-back placement. Use a coherent room response for objects sharing a room; distance need not create a different cathedral-sized reverb for every prop. Longer pre-delay can separate a close source from its reverberation, so it is not a universal “farther” control. These are mix decisions to audition, not calibrated meters. See [iZotope's explanation of mix depth](https://www.izotope.com/community/blog/what-is-mix-depth-how-to-create-front-back-space).

For a clean mono object cue, equal-power panning is a useful starting point for continuous left/right motion; [MDN documents this panning model](https://developer.mozilla.org/en-US/docs/Web/API/StereoPannerNode). Preserve intentional stereo sources when appropriate: balancing a stereo recording is not the same as positioning one mono object. Avoid opposite-polarity widening as the main spatial cue. Use smooth automation rather than channel jumps. Do not add Doppler pitch shifts to slow motion merely to advertise movement.

Keep direct-source motion and the room return separate. Pan or route the signal entering the room effect, then let already-emitted reflections decay; moving the entire finished reverb tail with the current source position can make the room appear to move. Use a shared room bus or a documented equivalent in the actual mixer. A connected gallery can have its own response if the picture and listening support that choice.

Record pan keypoints against cue times, depth treatment, direct gain, EQ, room send/return, and any obstruction in the sound plan and `audio/session.json`'s arrangement/processing notes. Keep the native session or script that implements them. These are editorial records within the existing session convention, not new executable fields. The studio's evidence CLI does not automatically turn layer depth or a written sound path into spatial audio.

Before a full remix, render a short controlled study: the same isolated cue nearby, farther away, and traveling. Keep relative levels intact and leave gaps for tails. Check measured left/right energy at the cue's starting and ending windows, then audition whether its movement and distance are convincing. The study is useful evidence of a treatment, not approval of the full soundtrack.

## Source and audition separately

Inspect existing film source/retrieval records before requesting new sounds. Resolve actual files and audition candidates; a prompt or filename does not establish availability or quality. Current visual `library find/inspect` commands are not an audio catalog. Record reuse with hashes and preparation notes in the existing source ledger/session while the [audio-library work](../architecture/TV-QUALITY-AND-SOUND-LIBRARY.md) remains planned. Materialize pinned sources within the target project for portable sessions and handoffs.

Request music, continuous beds, and isolated events separately. Record the exact prompt, loop control if present, requested duration, provider/model returned, file format, request ID, and selected variation. Current provider support must be checked at use time; the original production used a browser fallback because callable ElevenLabs tools were unavailable in that session.

Separate generation quality, download format and mix processing. Check the selected route's actual model/format controls, entitlement, and returned codec/rate/channels; public API options may not be exposed by the connected tool. Preserve the best practical original. Decode/resample through explicit preparation when needed; the mixer does not resample. Compare formats using the same take where possible, and different models/takes at documented audition levels. Change provider to address an audible or control limitation, not merely a larger format label.

An instrumental request and a sound-effects loop switch solve different problems. Generated music still needs phrase/harmony review and editing. Keep enough source duration around a proposed join to overlap compatible material.

Audition at sensible levels. Listen for static-like hiss, artificial shimmer, unwanted voices/music, relentless noise, repeated attacks, and sharp peaks. A very quiet effect may still have a large isolated transient. Measure before normalizing. State whether a source was actually heard or only analyzed.

## Arrange a circular session

Give music, beds, and one-shots their own tracks. Place events on an explicit timeline. Use a longer master when a unique event would otherwise recur too often. Avoid a start-up gesture or closing cadence that announces the loop boundary.

Keep picture period, soundtrack/master period and viewing duration separate. Choose a compact audio master spanning whole picture cycles; audition with playback repetition. `media compose --repeats` repeats picture and requires audio already matching the final duration. It does not extend sound. Hour-long assembly is a separate requested delivery; the current in-memory/ordinary-WAV path does not establish support for it.

Edit music at compatible rhythmic and harmonic positions. Overlap the continuation and opening without producing an audible dip or doubling. Carry room/reverb tails through the circular boundary. Do not fade the entire film to silence just to avoid a click.

Use level, spectral balance, width, and room/direct balance to suggest distance. Keep phone/mono readability. Tame harshness at the responsible source; preserve enough space that subtle sounds can be heard without forcing the whole mix louder.

Save source offsets, cue times, gains, pan/width, processing, master duration, and overlap method in `audio/session.json`. This record describes the arrangement even if the chosen editor or mixer uses another native project format. Keep that native session too.

## Measure and listen

Measure actual sample counts, clipped samples, loudness with method, peaks with true-peak/oversampling method stated, seam deltas, mono behavior, and aligned stem duration. Compare stem reconstruction where the delivery promises it. A PCM master preserves the edited mix but cannot recreate information lost in a lossy source.

Executable audio checks currently report RMS and sample peaks, not LUFS or oversampled true peaks. Use an identified external measurement backend or leave those measurements unavailable; never relabel existing results. Current mixing/export is stereo. Depth treatment and pan movement do not establish surround, binaural rendering, or overhead placement.

Listen to at least three consecutive repetitions with picture. Check for a click, gap, obvious musical restart, repeated-event fatigue, pumping, harshness, or a distracting change in distance. Human final review includes the actual phone speaker and intended crop. Keep those observations distinct from measurements.

For spatial cues, audition stereo on headphones and the intended phone, then a mono fold-down. Check individual cues as well as the master so a surviving room bed cannot hide a disappearing event. Left/right travel will be reduced by close phone speakers and disappears in mono; timing, identity and useful near/far contrast should remain. Ordinary stereo does not promise reliable behind-the-head or overhead placement. Confirm the actual encoded deliverable rather than inferring playback from the WAV or device specifications.

Inspect moving-cue automation at the circular join: active sources must continue coherently, or reset during a silent gap without cutting off their room tails. Check cue direction, smooth gain changes and clipping numerically, but do not label distance, mono readability or comfort as heard when only measurements exist.

The reference's −22.5 LUFS and generous headroom are examples of its quiet artistic direction. Do not automatically impose a platform loudness claim or a fixed target on every film.

## Export evidence

Store masters and aligned stems separately from original sources. Identify whether master gain/processing is included in the stems and whether unity gain reconstructs the master. Record exactly which file was auditioned. Check the AAC/MP4 version after encoding, because the final container and its presentation timeline can introduce different constraints than the WAV.

## Select reusable ingredients

Favor isolated object cues, simple beds, complete tails and a few variants of noticeable events. Label baked-in distance, room sound and unrelated events; do not assume they can be removed. Preserve relatively dry direct sources where useful. Keep music tied to the film's identity; pitched loops need harmonic/tempo context before combining them.

Promote only auditioned, useful versions with source identities, loop/tail notes and known limits. Save recipes as source references plus editable gains, pan and cue timing; these adjustments do not require duplicate source files. A starter-collection target is a curation plan, not a requirement for each film or generation authority.
