# 05 — Final files, human review, and reusable archive

**Input:** accepted picture and soundtrack master. **Output:** verified editions, creative release record, reusable modules, and handoff. **Gates:** export, release, library.

## Build the actual deliverables

Use a tested export backend appropriate to the host. Keep format settings and tool versions explicit. When picture is already accepted and only the sound changes, copy the encoded picture during muxing where supported instead of re-encoding it unnecessarily.

Name editions by content and duration. Keep final files separate from previews and temporary encodes. Generate a cover from a deliberately chosen frame. Apply only requested publishing overlays or captions. Check current platform UI before treating a guide as an official safe area.

## Decode and inspect

Decode the final file completely. Verify dimensions, frame rate, expected decoded frame count, ordered presentation timestamps, correct number of audio tracks, and intended duration. For repeated picture cycles, verify the assembled master duration rather than assuming repetition succeeded.

Inspect the encoded audio join and its relationship to the PCM master. Account for codec priming, padding, and edit lists: raw extraction may contain samples outside the presented interval. Use a timeline-aware check and record the method. A duration reported by one header is insufficient when another measurement disagrees.

Inspect visible motion and the seam in the delivered file, not only the source canvas. Revisit color, alpha/resampling, and frame pacing if the encoded output differs materially from the preview.

## Human release review

Present the exact final file and a short set of questions: does it preserve the intended feeling, remain comfortable over three repeats, and work on a phone? Record real observations and their source. Existing user feedback can establish a criterion when it identifies the relevant review; do not rewrite it to imply tests that never happened.

The human look/listen and phone checks remain open until observed. This does not stop preparation of a review draft, source archive, or other independent work. A user's decision to deliver with open checks should be documented accurately. Passing a gate is not permission to publish or send the file to somebody else.

## Archive the production

Save the scene and native project, asset catalog, raw/prepared art, generation/preparation recipes, sound sources/session/stems, masters, cover, exports, actual reports, hashes, tool versions, and concise review history. Exclude credentials, cookies, temporary signed URLs, and unrelated account history.

Distinguish source preservation from rebuild portability. A historical Objective-C renderer may be useful and complete but require macOS and native media services. State which commands were tested on which host. A future cross-platform exporter should be demonstrated, not implied by the archive.

## Admit modules to the library

Promote only selected production assets and useful patterns. Assign an immutable version and content hash. Include a preview, subject/style/light/perspective tags, intended size range, pivot/sockets, masks/emissive companions, cycle metadata, source references, and known limits.

Save a rig when several parts should travel together. Save a motion recipe when parameters carry a useful behavior. Save a sound recipe when spatial roles and event timing transfer to another scene. Do not copy every rejected take or finished video into the reusable catalog.

Close `handoff.md` with the final paths, current gate state, open limitations, rebuild route, next actions, and new reusable modules. A new operator should be able to resume from that file and the project data without the original conversation.
