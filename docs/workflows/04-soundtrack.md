# 04 — Sound as a place and a story

**Input:** creative brief and picture draft when available. **Output:** sound brief, sources, audition notes, circular session, masters/stems, measurement and listening evidence. **Gates:** sound-design and mix.

## Define the listening position

Write an emotional sentence and locate the listener. What is near, what is behind a window, what is across the valley? Choose a musical identity or environmental focus. Decide where to leave quiet. Do not assign a literal sound to every visible object.

The Last Lantern used a small musical identity, muffled hearth, quiet outside air, leaf movement, and one distant bell. The music made the place welcoming; the bell suggested a wider world. That relationship can transfer to other themes without copying the same notes or sound effects.

## Source and audition separately

Request music, continuous beds, and isolated events separately. Record the exact prompt, loop control if present, requested duration, provider/model returned, file format, request ID, and selected variation. Current provider support must be checked at use time; the original production used a browser fallback because callable ElevenLabs tools were unavailable in that session.

An instrumental request and a sound-effects loop switch solve different problems. Generated music still needs phrase/harmony review and editing. Keep enough source duration around a proposed join to overlap compatible material.

Audition at sensible levels. Listen for static-like hiss, artificial shimmer, unwanted voices/music, relentless noise, repeated attacks, and sharp peaks. A very quiet effect may still have a large isolated transient. Measure before normalizing. State whether a source was actually heard or only analyzed.

## Arrange a circular session

Give music, beds, and one-shots their own tracks. Place events on an explicit timeline. Use a longer master when a unique event would otherwise recur too often. Avoid a start-up gesture or closing cadence that announces the loop boundary.

Edit music at compatible rhythmic and harmonic positions. Overlap the continuation and opening without producing an audible dip or doubling. Carry room/reverb tails through the circular boundary. Do not fade the entire film to silence just to avoid a click.

Use level, spectral balance, width, and room/direct balance to suggest distance. Keep phone/mono readability. Tame harshness at the responsible source; preserve enough space that subtle sounds can be heard without forcing the whole mix louder.

Save source offsets, cue times, gains, pan/width, processing, master duration, and overlap method in `audio/session.json`. This record describes the arrangement even if the chosen editor or mixer uses another native project format. Keep that native session too.

## Measure and listen

Measure actual sample counts, clipped samples, loudness with method, peaks with true-peak/oversampling method stated, seam deltas, mono behavior, and aligned stem duration. Compare stem reconstruction where the delivery promises it. A PCM master preserves the edited mix but cannot recreate information lost in a lossy source.

Listen to at least three consecutive repetitions with picture. Check for a click, gap, obvious musical restart, repeated-event fatigue, pumping, harshness, or a distracting change in distance. Human final review includes the actual phone speaker and intended crop. Keep those observations distinct from measurements.

The reference's −22.5 LUFS and generous headroom are examples of its quiet artistic direction. Do not automatically impose a platform loudness claim or a fixed target on every film.

## Export evidence

Store masters and aligned stems separately from original sources. Identify whether master gain/processing is included in the stems and whether unity gain reconstructs the master. Record exactly which file was auditioned. Check the AAC/MP4 version after encoding, because the final container and its presentation timeline can introduce different constraints than the WAV.
