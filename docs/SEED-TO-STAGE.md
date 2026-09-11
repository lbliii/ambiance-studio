# Build a production scene from a seed

The studio's default for an end-to-end seed film is an independently staged, visibly animated scene with full-frame portrait (1080 × 1920) and landscape (1920 × 1080) compositions. Follow a user's different output or scope instruction. A seed supplies design, identity, atmosphere and spatial relationships; its exact crop and baked object boundaries are not automatically the production layout.

This direction follows the user's repeated review of A Quieter Tomorrow: clean assets and technically valid movies were too still, and the near-square seed was preserved instead of developing the intended output compositions. Existing instructions mentioned layering, but the authored brief reduced the work to tiny, infrequent gestures and deferred much of the environment. The correction belongs in scope, art preparation, creative review and CLI completion checks together.

## Start with the whole scene

For a new contract, start from the [unplanned template](../templates/production-plan.json), author its story, sources, elements, actions, requested outputs and expectations, then use `plan spec apply` with the appropriate predecessor hash. The template intentionally has no scope and cannot establish readiness. The [single-format example](../examples/production-plan.json) demonstrates an explicit nearly-still direction; do not copy its creative choices into another seed.

Before prioritizing a few easy assets, inspect the whole reference and author its semantic census in the canonical [production plan](PRODUCTION-PLAN.md), `plans/production-plan.json`. Inventory meaningful object families, including partially visible framing, characters and their action parts, environmental surfaces, and all light sources. Group repeated leaves/windows where they have one role; a census need not name every pixel or identical leaf. Use stable IDs and distinguish observed objects from proposed additions. Preserve existing census notes as migration inputs; do not maintain a second editable census that can disagree with the plan.

For each entry record its story role, visible relationships, possible actions, chosen treatment and reason, required production parts, and inventory IDs that carry the work. Deliberately still objects also need a decision: framing, structure, a resting pose, contrast to nearby movement, or another artistic purpose. Include both foreground and distant activity when the scene supports it. Choosing a story hierarchy happens after this survey.

Write one emotional/story sentence and a small set of observable beats. Ask what a viewer should notice, when, and what that contributes. For the tram: the outside world travels past while the passengers linger; the paper and loose cloth respond; the mouse attends to something; connected candlelight keeps the foreground alive. These are authored possibilities, not mandatory content for other seeds.

## Design the two compositions and asset boundaries together

Save target formats and composition decisions in `plans/layout-notes.md` and the brief. Produce small portrait and landscape blocking proofs before detailed cel cleanup or a complete film render. Both should show the intended focal subjects and actions at useful viewing sizes. Inspect the whole composition at normal display size; a detail crop cannot establish readability in either output.

Plan a shared stage for the union of both visible regions plus motion margins. Preserve proportions, contact, perspective and the reference's identity. Reposition complete rigs where the compositions require it, and plan their receiving surfaces and overlaps accordingly. Missing side scenery, headroom, floor, object backs and new poses are production assets to make. A crop or dimension swap is sufficient only when the actual composition proof shows it works.

The selected [dual-format implementation](architecture/DUAL-FORMAT-IMPLEMENTATION.md) from [PR #5](https://github.com/lbliii/ambiance-studio/pull/5) provides named views, synchronized proofs and paired deliveries; see the callable commands in [views](VIEWS.md). The [integration evidence](architecture/FOUNDATION-HANDOFF.md) identifies the tested baseline. Saved crops do not reconstruct missing scenery or establish composition quality. A fallback using separately staged scenes requires explicit shared-asset/timing records and its own coverage review.

Use [layer and light planning](LAYER-AND-LIGHT-PLANNING.md) to distinguish depth families, independently controlled action parts, foreground occluders and receiving surfaces. Prepare production versions of every component needed for the chosen staging and actions. Extract suitable paint; reconstruct hidden areas; generate new poses or expanded environments where needed. Choose generation extent from the production need and available authorization. Reuse a good cutout without forcing it to carry missing geometry.

## Commit scope before polishing

Record selected expectations in the production plan and their realization parts in the [production inventory](PRODUCTION-INVENTORY.md). Inventory entries retain `required: true` and tracked `required_parts`; they describe fulfillment, while the plan owns intent. Include the requested composition proofs, necessary extraction/backing, selected character and environment actions, and source/receiver light proofs. Reconcile `plan next` with story priority: the easiest ready asset is not automatically the most important artistic task.

Separate a prototype's scope from the full film's scope. It is useful to test one animal or a page hinge first; that proves that component. The remaining required scene work stays open. A missing source, preparation difficulty or unavailable capability should name the work still needed and its next action. Record any consequential reduction with reason and impact; do not silently relabel a requested feature optional to make the plan appear complete. Ask only when a real scope/authority decision requires the user's input, while continuing independent work.

Use `plan coverage --stage animation` for stage-specific readiness and the stable blocked expectation IDs shared with overview and iteration preflight. Future export evidence does not block animation; final export checks the intended view/role set. Register actual provider evidence through `plan evidence`; observed readability still requires an observation of exact artifacts. For an unmigrated legacy inventory, `plan check --require-complete` remains an inventory-only completion check; ordinary `plan check` is an integrity check. Neither can discover omitted objects, enforce an unwritten intention, or judge appeal.

## Prove the intended experience early

Make the first combined motion draft ambitious enough to test the film's intended life. Include the selected story actions, environmental depth/movement and representative lighting in both compositions, using provisional art where necessary and labeling it. A narrowly scoped component proof may precede this draft, but it does not replace it.

Apply [motion direction](MOTION-DIRECTION.md) to distinguish size, speed, noticeability and cadence. Compare a readable target with quieter/stronger variants at the same cadence. Judge event frequency separately. Quietness should come from coherent pacing, stable references and an attention hierarchy; it does not imply every action is tiny, rare or hidden. Use project-specific viewing targets rather than a universal animation count or fixed pixels-per-second rule.

Record what was actually noticeable in each view at normal speed, including any long spans that felt still and whether the principal action worked without a pointer or crop. Then inspect edges, registration, contacts, reveal limits and loop seams. Passing stability checks does not answer whether the film meets the creative brief. A still, a difference image and a timing report provide different evidence from normal playback.

Before calling the requested production scope complete, run coverage for the applicable stage and attach its exact input-bound report to the picture review alongside actual visual observations and every requested composition. Use explicit review scope for partial iterations and final scope when the full intended output set is required. Unfinished work can still be shown as a clearly scoped review draft; presentation is useful progress and does not remove outstanding requirements. Keep final human checks truthful and preserve the user's existing authorization.

## Agent decision discipline

Keep concise consequential decisions in the project: chosen direction, reason, tradeoff, what evidence could change it, and affected requirements. Useful questions are: Am I preserving identity or just preserving coordinates? Have I scoped the whole scene before selecting a first asset? Is missing art a preparation task? Does the draft actually show the intended action in both views? Have I changed the scope to suit what I already finished?

The next autonomous production is the behavioral test of these changes. File/skill validation and fixture tests establish structure and specific CLI behavior; they cannot prove an agent will make good artistic choices. Judge the actual paired composition and motion drafts against the recorded brief before extending the process with more rules.

The [consolidated engineering plan](architecture/PRODUCTION-IMPROVEMENTS.md) describes typed intent, stage-aware expectations, semantic layer roles, coordinated lighting, activity diagnostics and CI/behavior trials. Its [YAML backlog](architecture/PRODUCTION-IMPROVEMENTS.yaml) owns implementation status and dependencies; it is not an executable project recipe.
