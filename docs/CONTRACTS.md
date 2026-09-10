# Contracts for modular production

The existing editor's executable format is described in [SCENE-CONTRACT.md](SCENE-CONTRACT.md). The production records below are handoff conventions and supplied templates. They describe data to retain; they do not imply that every field is already interpreted by the prototype.

## Reference and creative brief

Keep the actual source, a hash, its role, observed visual facts, intended alterations, style constraints, and output settings. Treat style references as versioned inputs. A new reference or changed artistic direction should be reflected in project state and affected reviews.

## Layer-plan object

Each object should describe:

- Stable ID, readable name, focal/supporting role, and whether observed or proposed.
- Source-image bounds and their coordinate system; intended canvas placement.
- Draw order, artistic depth, anchor, parent rig, and attachment socket if any.
- Rigid plate, cel sequence, transform, path, particle system, or combined method.
- Planned cycle and approximate screen size; frame count where relevant.
- Source/reuse plan, clean backing needs, masks, shadows, emissive companions, and dependencies.
- Review notes and unresolved decisions.

Use `templates/layer-plan.example.json` as a small example, not an exhaustive list of objects to copy into every film.

## Asset record

Identity: immutable ID/version, asset kind, content hash, raw source and production derivative paths. Technical: dimensions, color/alpha convention, cell rectangles/layout, frame count, playback metadata, content bounds, pivot, and intended size range. Context: palette, lighting direction, camera angle, texture/edge treatment, subject/season tags, compatibility pack. Provenance: prompt/reference inputs, provider/model as returned, request ID if available, selected take, preparation recipe/version, input hashes, and usage context.

Store an unknown value as unknown/null. Do not invent a seed, model, license conclusion, cost, or exact generation method. A content hash identifies what was used; a prompt alone does not guarantee the same asset can be regenerated later.

## Rig record

A rig names child asset versions, local placements, pivots/sockets, masks, and parent relationships. Expose a small set of useful controls, such as window warmth, smoke rate, or branch sway. Include a preview and safe camera/scale ranges determined by review.

The current editor supports one group level plus nested layer attachments and cel-specific sockets. See the executable scene contract for those fields. Parameterized rig instances, exposed control bindings, and automatic module instantiation remain future features; the rig-record template is still a design/handoff record, not a file the editor loads.

## Motion recipe

Record motion type, coordinate space, anchor, cycle length or integer cycles, amplitude, phase, stepping rate, and random seed if applicable. Define the behavior at boundaries and ensure state can be evaluated at arbitrary time. Include the tested parameter range and the scene/asset context of the review.

A falling leaf can have a periodic path plus rigid spin and a flip sequence. Its emission/death should occur outside the visible region or close coherently. A moving cloud can reuse the same atlas with a distinct phase and route.

## Generation request ledger

Use `templates/generation-request.json` within the project ledger. Record a local request ID/fingerprint before submission, intended asset, provider/capability, exact prompt and references, requested settings, authorized cost scope, status, returned IDs, output paths/hashes, selected take, and known cost. Keep request attempts and retrieval attempts distinguishable.

The record is currently maintained by the agent; no paid request queue is implemented. See [provider operations](PROVIDERS.md) for the state transitions and retry rules.

## Audio session

Record master sample rate/duration, source asset IDs, source trims/offsets, track gains, pan/width, processing and its order, cue times, circular wrap/tails, crossfade choices, and output stems. Keep requested musical direction distinct from measured or heard source properties.

Specify whether stems contain master gain/processing and whether unity summing reconstructs the master. The example session is an editorial record, not a new general mixing engine. Retain the actual DAW or scripted mix source that produces the result.

## Review and release

Use `studio.py review-template` for current criterion IDs. Save observations against exact files and let `record` hash them. Evidence paths must remain inside the project. The recorder also snapshots watched stage paths, so newly added files can invalidate a review even if they were not in its original evidence list.

A release inventory should identify each final file's role, duration, dimensions/sample format, hash, generation/export date, and validation report. Do not mark technical or human checks passed based on a naming convention.

## Versions and changes

Code, schemas/contracts, scenes, and recipes receive ordinary version control. Accepted media receives immutable IDs and content hashes. A derived change creates a new asset version and updates explicit references. Do not silently replace a shared smoke atlas in all existing films.

Changes to a production contract need a migration note and a fixture test. Keep the old record available so past projects remain understandable. Use one renderer implementation for preview and export wherever possible; parity still needs testing after backend/version changes.
