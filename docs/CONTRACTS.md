# Contracts for modular production

The executable [production-plan contract](PRODUCTION-PLAN.md) owns typed creative intent and semantic references. Its strict CLI and consumer API are implemented; legacy narrative layer notes remain useful explanation, with explicit migration rather than automatic rewriting.

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

Compound preparation recipes and typed compiler receipts are documented in [agent preparation](AGENT-PREPARATION.md). They preserve separate source/backing/cutout/occluder/companion identities, canonical production bindings, saved view envelopes and immutable rebuild dependencies.

The executable [local model construction contract](architecture/model-contract/construction-v1.md) adds immutable nested definitions, registered static controls/variants, exact role proofs and portable technical entries. It lowers through the existing scene evaluator; scene instances/adoption and artistic approval remain separate.

## Rig record

A rig names child asset versions, local placements, pivots/sockets, masks, and parent relationships. Expose a small set of useful controls, such as window warmth, smoke rate, or branch sway. Include a preview and safe camera/scale ranges determined by review.

The current editor supports one group level plus nested layer attachments and cel-specific sockets. See the executable scene contract for those fields. Parameterized rig instances, exposed control bindings, and automatic module instantiation remain future features; the rig-record template is still a design/handoff record, not a file the editor loads.

## Motion recipe

Record motion type, coordinate space, anchor, cycle length or integer cycles, amplitude, phase, stepping rate, and random seed if applicable. Define the behavior at boundaries and ensure state can be evaluated at arbitrary time. Include the tested parameter range and the scene/asset context of the review.

A falling leaf can have a periodic path plus rigid spin and a flip sequence. Its emission/death should occur outside the visible region or close coherently. A moving cloud can reuse the same atlas with a distinct phase and route.

## Generation request ledger

Use `templates/generation-request.json` within the project ledger. Record a local request ID/fingerprint before submission, intended asset, provider/capability, exact prompt and references, requested settings, authorized cost scope, status, returned IDs, output paths/hashes, selected take, and known cost. Keep request attempts and retrieval attempts distinguishable.

The executable `asset request record/reconcile/inspect` commands preserve managed requests and returned local image identities in the existing ledger; they do not submit requests or implement a paid queue. Legacy records are retained unchanged. See [provider operations](PROVIDERS.md) for the state transitions and retry rules.

## Audio session

Record master sample rate/duration, source asset IDs, source trims/offsets, track gains, pan/width, processing and its order, cue times, circular wrap/tails, crossfade choices, and output stems. Keep requested musical direction distinct from measured or heard source properties.

Specify whether stems contain master gain/processing and whether unity summing reconstructs the master. The executable [audio-session contract](AUDIO-SESSION.md) supports PCM arrangement, mixing and comparisons. Preserve separate external processing recipes for operations it does not implement.

The [typed audio library](AUDIO-LIBRARY.md) preserves immutable originals and preparations, separate listening/decision records, and project-contained materialization. Its typed revision adapter pins contained source files and archived provenance without retaining live dependencies on an earlier project.

## Review and release

Use `./ambiance --project PATH review draft GATE --out FILE` for current criterion IDs. Save observations against exact files and let `record` hash them. Evidence paths must remain inside the project. The recorder also snapshots watched stage paths, so newly added files can invalidate a review even if they were not in its original evidence list.

A release inventory should identify each final file's role, duration, dimensions/sample format, hash, generation/export date, and validation report. Do not mark technical or human checks passed based on a naming convention.

Movie discovery, delivery sets, current selections, local iteration recipes and timestamped feedback are executable contracts described in [the studio library](STUDIO-LIBRARY.md). A delivery references existing movie/review evidence; it does not create an approval.

## Versions and changes

Code, schemas/contracts, scenes, and recipes receive ordinary version control. Accepted media receives immutable IDs and content hashes. A derived change creates a new asset version and updates explicit references. Do not silently replace a shared smoke atlas in all existing films.

Changes to a production contract need a migration note and a fixture test. Keep the old record available so past projects remain understandable. Use one renderer implementation for preview and export wherever possible; parity still needs testing after backend/version changes.
## Production-operation extensions

See [current operation contracts](MIDNIGHT-OPERATIONS.md) for feedback schema 3, bounded overview schema 2, cel comparison recipe 2, packet/recipe initialization, run ownership/progress, trim provenance, layered iteration configuration and cleanup plans/receipts. Scene, inventory, canonical plan, capture, edition and delivery schemas retain their existing ownership. Legacy feedback is read through adapters; sealed records are not rewritten. Resolution and cleanup never certify artistic readiness.
