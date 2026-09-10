# Scale the studio by making the next film easier

## Current capability map

| Capability | Status in this package |
| --- | --- |
| Studio guides, stage skills, style language, production templates | Implemented documentation and agent instructions |
| Project initialization, review drafts, hashed receipts, dependency/staleness checks | Implemented and behavior-tested Python tool |
| Existing painted assets and six sprite atlases | Bundled and integrity checked |
| Placement, groups, named/nested attachments, per-cel socket tracks, cel playback, JSON round trip | Implemented rig workbench; tested in browser and Node |
| Registration recipes, fixed-grid packing, light/dark proofs, cache protection | Implemented Pillow compiler; fixture and real smoke-pack exercises |
| Per-frame attachments and coverage, preview seam comparison | Implemented Node state checks and browser pixel checks at preview resolution |
| General image decomposition, matte repair, automatic feature tracking | Guided agent workflow; not automated by the compiler |
| Full-fidelity Last Lantern picture in the shared browser engine | Partial; mist, glow, leaves, and motes remain to port |
| Shared-scene frame/proof/video export | CLI implemented: Node Canvas raster, macOS AVFoundation H.264/PCM mux and actual decoded verification; historical missing effects still require porting |
| Explicit sound arrangement | CLI implemented: source hashes, PCM clips/stems, fades, circular tails and A/B evidence; no synthesis/resampling/automatic normalization |
| Production inventory, source proofs and named anchors | CLI reconciliation, library discovery and HTML proof/anchor authoring; artistic classification and review remain authored |
| Provider request queue, retries, budget enforcement | Contract and workflow only; ledger maintained by the operator/agent |
| Human artistic/phone listening review | Deliberately performed by people and recorded as evidence |
| Another operator creating a new film from scratch with this package | Not yet demonstrated; the next pilot |

The registration/attachment groundwork now exists. See [tool strategy](TOOL-STRATEGY.md) and the [workbench guide](RIG-WORKBENCH.md) for v0.3 scope and the current engineering order.

## First milestone: a faithful production template

Port the missing effects into the same absolute-time scene engine, then implement exact-frame export and final media validation. Retain the original film as a reference. Compare representative frames, motion, and the full loop with documented tolerance; do not demand byte-identical encodes across different backends.

Done means the same scene recipe drives preview and final picture, the loop and attachments hold, and the actual final container passes the expected frame/audio checks. This is a production milestone, not merely a new editor control.

## Second milestone: the sister pilot

Give a new operator this folder and a different reference image, such as a rainy bookshop. Let them use the start prompt without access to the original chat. Observe where they need an undocumented answer, where the agent assumes a missing tool, and where the workflows cause unnecessary interruptions.

Success means a complete first draft, useful quality evidence, a clear final review, and a handoff another person can reopen. Record the operator's effort and support requests. This is the first real transfer test; it has not been performed by preparing the package.

## Third milestone: the asset workbench

Registration, packing, sockets, and preview coverage checks are now implemented. Extend them with a landmark/onion-skin panel, better alpha/edge inspection, and project loading. Exercise those helpers and test them on the original smoke/cloud/flame sources plus a second style-compatible pack. Keep ambiguous art decisions reviewable.

Admit reusable modules by version and hash. Search by lighting/perspective/style as well as subject. Save rigs and recipes, not only PNGs. Prefer a small library of dependable modules over a large unreviewed folder.

## Fourth milestone: reliable orchestration

Add provider adapters with persistent job IDs, cost estimates/reservations, retrieval, and tested failure behavior. Add a shared audio-session engine or supported DAW bridge. Keep paid calls out of ordinary local tests. Persist work so a session can resume without another generation.

Use one queue owner per project initially. Independent asset requests can run concurrently within a known budget, while scene integration and gate recording remain serialized. Multi-agent work is optional and requires authorization in the host/task; these workflow roles do not automatically spawn agents.

## Fifth milestone: batch production

Add project browsing, render queues, templates, seasonal variations, and packaged installation after the pipeline works across distinct scenes. Keep code and lightweight recipes in Git; use a deliberate media store or Git LFS policy when the asset volume warrants it. Separate scratch renders, accepted library versions, and final editions.

A changed shared asset should not silently alter old releases. Pin project inputs and renderer versions. Cache prepared assets and frames by content/recipe/engine hashes. Generate cheap draft previews before full-resolution renders. Mux accepted picture with revised audio when possible.

## What to measure

Track per film: paid generation requests and cost, unknown outcomes, retrieval retries, raw-to-production preparation time, proportion of accepted assets reused, draft/final render time, review rounds, defects by stage, and human effort. Compare quality and effort across films, not just the number exported.

The first project did not keep a complete timing/cost ledger. There is no credible percentage speedup to claim yet. Establish a baseline with the pilot, then optimize the largest measured source of rework.

## Keep the process maintainable

Assign one maintainer to shared contracts and tools; give each project an owner and an identified creative reviewer. These can be the same person in a tiny studio, but the roles should be clear. A new rule should solve an observed problem. Review it after another project rather than accumulating permanent instructions for every one-off issue.

Treat process changes like production changes: a focused revision, example or behavioral check, version note, and a migration plan when existing projects are affected. Improve the documentation where the new operator actually struggled. The process should support taste and reduce rework, while leaving room for each film to have its own character.
