# Reusable models and complete scene assembly: delivery plan

September 12, 2026 · Proposed plan · Development deferred pending other studio changes

**Expected result:** an agent can inventory an entire seed, find or prepare complete editable models, assemble a living scene from their instances, prove that the scene stands without the seed, and return accepted models to a library that makes subsequent films easier to produce.

This plan sets goals, deliverables, dependencies and acceptance outcomes. Implementation architecture, command names, estimates and development task breakdown remain open until the other planned studio changes settle. The [research and evidence][research] explain the observed failures and candidate technical approaches; those approaches are inputs to the later implementation review, rather than commitments made here. All delivery phases below are planned, not completed.

The [studio alignment](STUDIO-PLAN-ALIGNMENT.md) is the integration map with workflow guidance, narrative character/timing work and quality/library reuse. The [operator audit](AMBERWATCH-GLUE-AUDIT.md) adds capability-selection evidence to the research's art/ownership findings. It does not make source separation equivalent to model construction or turn the research's proposed CLI/schema into a settled design.

## 1. Product goals

| Goal | Expected outcome | How we will know it works |
| --- | --- | --- |
| **G1 — Complete scene ownership** | Every visible element belongs to a model, a nested part or an explicit effect on a receiving model. This includes environment surfaces and deliberately still objects. | Reconstruct the whole scene with the seed and full-scene fallbacks excluded. Review the inventory against the actual image and inspect removal proofs across all contributing layers. |
| **G2 — Editable reusable models** | A model contains its own layers and can contain other model instances. Complete characters retain their bodies; houses can contain windows, doors and lanterns; leaf piles can contain individual leaves. | Inspect the hierarchy, modify an internal part, and rebuild the model without reconstructing its assembly manually. Editable sources and dependencies remain available. |
| **G3 — Predictable scene editing** | Instances can be placed, duplicated, mounted, moved, hidden and varied while retaining their internal relationships and independent controls. | Manipulate two instances independently; verify attachment, draw order, contact, timing and lighting in actual output. Compatible swaps retain intended overrides. |
| **G4 — Useful derived edges** | Each selected pose/variant can produce composite transparency, silhouettes and tight bounds, with solid structure separate from glass, flame, smoke and glow. | Compare derived masks to isolated model rendering, including holes and soft edges. Cropping preserves registration; dependent edits invalidate stale products. |
| **G5 — Coherent living compositions** | Complete models support the chosen story actions, environmental activity and lighting in portrait 9:16 and landscape 16:9. | Observe full compositions at normal speed and intended display size. Required actions are visibly readable and the short loop is complete. |
| **G6 — A library that compounds value** | Accepted models retain editable sources, versions, provenance, dependencies, controls and review evidence. Later films can reuse them confidently. | Build a second composition from library records alone, make ordinary placement/variant changes and preserve the earlier scene's accepted version. |
| **G7 — Reliable agent operation** | The full workflow is available through structured operations and saved state; browser inspection shows the same model and scene state. | An agent completes the representative workflow without bespoke scene-assembly scripts or browser-only production steps, resumes interrupted work, and presents exact review artifacts. |

The main acceptance criterion is: **remove the seed, reconstruct the scene from cataloged components, then move or hide any component without carrying unrelated paint or exposing an unfinished surface within its intended views and action range.** Complete ownership also applies inside nested models. Removing the backmost sky intentionally leaves transparency; that differs from revealing a missing wall behind a lantern.

## 2. Agreed behavior

A **model definition** is an editable assembly with stable identity, local coordinates, parts, nested references, attachment points, variants and exposed controls. A **scene instance** selects a definition version and supplies placement and permitted changes. A **library record** preserves the reusable definition, source art, provenance and evidence. Compiled images, masks and previews are rebuildable products of that source.

Ownership, mounting, painter's order, depth and light relationships stay explicit. Ownership determines what belongs to a model. Mounting determines what follows a movement. Painter's order determines what covers what; depth determines spatial/parallax behavior. Light can be driven by a lantern while remaining painted on the ground receiving it. Grouping objects for selection must not silently change any of those relationships.

Model boundaries follow meaningful editable elements. A sky surface is a valid model, and its paint need not be subdivided into brush marks. A cloud, distant wood, leaf pile or character that is separately inventoried retains that identity. A whole-scene background cannot absorb those elements merely because they are still. Hidden paint is prepared for the chosen staging, overlaps and motion, including the union of both output compositions.

Variants change compatible construction or appearance; animation states change poses, cels or time within that construction. A reusable model exposes a small understandable set of controls. Changing a label must not lose an override. An incompatible replacement must explain which contact, control or relationship needs attention before it changes the scene.

Accepted versions remain reproducible. Updating a library model creates a new version; adopting it in a scene is explicit and reviewable. Compilation, library admission, model acceptance and acceptance in a particular scene are distinct facts. The library records actual observations and supported use, rather than promising that one review establishes quality everywhere.

## 3. Delivery phases

The sequence is based on evidence, not calendar dates. A phase ends when its stated result is demonstrated. Preparation can overlap where dependencies allow, but an unresolved acceptance condition remains visible.

| Phase | Goal and deliverables | Exit outcome | Depends on |
| --- | --- | --- | --- |
| **1. Define the whole-scene contract** | Agree model/instance/library terminology; survey one complete seed; record the ownership hierarchy, actions, hidden surfaces, light relationships, reuse candidates and both composition plans. Produce a model description checklist and review scorecard. | Every meaningful visible element is accounted for, required creative work is explicit, and another agent can identify what must exist before assembly. | Restart alignment below. |
| **2. Establish model construction and library entry** | Prepare one complete layered model with a nested subassembly, compatible variants, local frame, attachment points and exposed controls. Preserve sources and provenance; produce masks, bounds, previews and an inspectable library record. | The model can be opened, edited, rebuilt and inspected independently of its originating scene. Its registered parts and derived outputs agree. | Phase 1 model contract. |
| **3. Establish composition from instances** | Place, duplicate, mount, move, hide and vary instances; organize the scene hierarchy; control painter's order and source/receiver lighting. Provide structured operations and matching browser inspection. | Two instances remain independent, their internal parts follow correctly, and saved/reloaded state preserves the result. Changes are reviewable and restorable. | Phase 2 construction contract and first model. |
| **4. Prove representative models and failure handling** | Complete the lantern/pumpkin demonstration, then exercise trees, nested architecture, leaf piles, a complete character and transparent effects. Produce visual and motion evidence plus edit/recovery/version checks. | The workflow works across materially different model types and detects the known crop, ownership, rig and stale-evidence failures. | Phases 2–3. |
| **5. Reconstruct one complete seed scene** | Prepare all remaining required models/backing, assemble both compositions, add selected story actions and coordinated light, and produce compact paired review movies. Return accepted models to the library. | The entire inventoried scene works without seed/fallback paint; move/hide proofs are clean; required motion reads in both formats. | Phase 4, plus complete art coverage for the selected seed. |
| **6. Demonstrate reuse in a second scene** | Start a separate composition using accepted library models across props, environment and nested assemblies. Exercise compatible variations and a reviewed model update. Record what was reused, adapted and newly made. | Reuse preserves editability, looks coherent in the new setting and avoids rebuilding known assemblies. The first scene remains reproducible. | Accepted models and evidence from Phases 4–5. |
| **7. Adopt the workflow as the studio default** | Update production guidance and agent-facing operations; provide one worked example; establish selective migration and library maintenance practices; run an agent-operated production trial. | A fresh run follows inventory → reuse/prepare → assemble → compose → prove → library return with actionable saved state and exact review delivery. | Phases 5–6 demonstrated; restart decisions resolved. |

### Phase 1: the planning packet

Use the existing canonical production plan and inventory rather than a second editable census. Each model family needs: identity/story role, visible members, internal components, overlaps, intended actions or reason for stillness, hidden-paint needs, receiving surfaces, local contacts, view/detail requirements, library match or missing-art decision, and required proof. Mark selected creative requirements `required: true`.

The model checklist must cover editable parts, nested dependencies, local frame/pivot, sockets, controls, variant compatibility, paint order, material roles for masks, motion/reveal limits and source provenance. Choose a representative seed when production resumes; the current research examples do not select or modify an active film.

### Phases 2–4: the representative proof set

First demonstrate one layered lantern, then broaden the proof set before treating the workflow as general. Temporary geometric fixtures may establish editing behavior; accepted painted models must establish artistic quality.

| Demonstration | Expected result |
| --- | --- |
| **Lantern with nested candle/flame** | Two instances share one model definition and offer two compatible frame variants. Flame motion stays behind front bars; candle, flame, frame and handle remain attached when either instance moves. |
| **Independent pumpkin and receiving ground** | One lantern sits behind the pumpkin. Hiding the pumpkin exposes a complete lantern. Hiding the lantern removes all of its paint and its light contribution while leaving ground and other lighting intact. |
| **Tree family and environment** | Several tree instances use a small coherent set of models. Moving/hiding one carries no sky or neighboring tree paint; canopy holes and root contacts remain clean. Sky, clouds and distant woods retain separate planned ownership. |
| **House with nested windows, doors and lanterns** | A whole-house edit carries mounted children; an individual nested model can be selected and changed. Intended opening/reveal actions expose finished interior/backing paint. Authored overlaps remain correct across nesting boundaries. |
| **Leaf pile with leaf instances** | Whole-pile edits and selected individual-leaf actions coexist. Loose leaves do not drag ground paint, and moving a leaf reveals a finished underlying pile/surface. |
| **Complete character with an articulated part or held prop** | The still body belongs to the character. Whole-character movement and internal action preserve attachment, contact and foreground occlusion. No residual body remains in the environment. |
| **Glass, flame, smoke and glow** | Separate role masks retain translucency and soft edges. Solid silhouettes do not expand to glow extents or fill glass openings. Composite visual alpha matches the isolated assembly at the recorded state. |

Across this set, verify isolation against contrasting backgrounds, all relevant animation cels/extremes, local registration after a tight crop, variant changes, nested dependency changes and actual playback. A changed pose or model version must not silently reuse a mask or review that describes a different result. A sampled motion envelope identifies its sampled range; it does not claim all possible poses.

Exercise duplicate operations, interrupted preparation, reload/resume, missing dependencies, invalid nesting, incompatible replacements and conflicting edits. Expected outcomes are understandable failures, preserved prior scene state, useful next actions and recoverable work. Exact implementation tests will be chosen once the updated system is known.

### Phase 5: full-scene acceptance

The full-scene review package must contain the canonical inventory/coverage report, model/version list, paired composition previews, ownership isolation/removal evidence, internal rest/extreme proofs, normal-speed motion observations and exact current review movies. Every reviewed artifact identifies the scene/model version it represents. Preserve complete short picture/audio cycles and source-quality assets; long playback duration does not require long repeated production files.

Completion requires all of the following:

- Every inventoried visible element has a realized owner, and a fresh whole-image review finds no meaningful omissions.
- Production rendering excludes the seed and any full-scene fallback. No model is merely an unexamined renamed crop carrying other subjects.
- Moving/hiding top-level and relevant nested components leaves no unrelated paint, duplicate remnants or unfinished newly exposed surfaces within the specified range.
- All selected required actions and light relationships work, including foreground/background activity where chosen. Normal-speed observations describe what is actually noticeable in each composition.
- Portrait and landscape retain the intended identity, contacts, focal subjects and action readability at their target size. Native-detail inspection also supports the source-resolution claim.
- Required coverage passes, including `plan check --require-complete` and applicable stage checks available at implementation time. These checks accompany visual evidence; they cannot certify an incomplete inventory or aesthetic quality.
- Accepted models are discoverable in the library with editable sources and exact review evidence. Unresolved findings remain open and the delivered review scope states them accurately.

The lantern demonstration can complete Phase 4's core experiment. It cannot satisfy this full-scene acceptance.

### Phase 6: the reuse experiment

The second scene must obtain models from their library records and dependency packages, without relying on the first scene's mutable working directory. Reuse at least one prop family, one environment family and one nested assembly. Stage them differently enough to exercise hidden paint, placement and variations. Make one compatible model update and demonstrate both adoption in the new scene and retention of the old accepted version in the first scene.

Record reused definitions/instances, adaptations, new art requests, assembly repairs, unresolved compatibility issues and hands-on effort. Success means a coherent editable result with no reconstruction of unchanged model internals. The first run establishes a baseline for later time/cost improvement; this plan makes no unsupported percentage-savings promise.

### Phase 7: default workflow and migration

Adopt the proven sequence in the relevant production guidance and examples. Agent operations should expose a compact hierarchy, current state, missing work, conflicts and direct proof/review paths. Browser controls should operate on the same saved model/scene semantics, after the structured path works.

Existing films retain their originals and accepted editions. When a film needs revision, classify its assets as reusable as-is, recoverable with documented preparation, or needing replacement. Convert selected families on derivatives and repeat affected evidence. A cropped object does not gain acceptance through metadata migration. Library maintenance distinguishes candidate, compiled, reviewed, accepted and superseded versions without discarding provenance.

## 4. Evidence and progress scorecard

Report these measures at each milestone; use “not yet demonstrated” where evidence is missing.

| Measure | Completion target |
| --- | --- |
| Inventory coverage | All required entries realized, plus a visual review for omissions. No completion claim based only on authored counts. |
| Ownership/reveal quality | No unresolved contamination, residual duplicate or unfinished reveal in the reviewed scope. |
| Model editability | Hierarchy, nested parts, sources and controls survive rebuild, save/reload and library retrieval. |
| Instance behavior | All representative move/hide/mount/duplicate/variant cases pass with independent instances. |
| Derived masks | Correct recorded pose/variant, role separation, soft alpha, holes, registration and dependency freshness. |
| Artistic result | Actual observations support required actions, contacts, light behavior, loop continuity and both compositions. |
| Reuse | Second-scene demonstration passes for props, environment and nested assemblies; original versions remain reproducible. |
| Agent operation | Representative production and recovery use supported structured operations and durable state, with exact delivery links. |

Structural validation, image inspection and normal-speed observation answer different questions. Keep their findings separate and bind each to the actual reviewed version. Changes reopen only the evidence they affect. Review readiness is a production state, not an additional permission flow.

## 5. Restart alignment after the other changes settle

At development restart, inspect the settled system and map this plan onto existing work. Produce a short reconciliation note identifying what is already delivered, what can be extended, what still needs design, and the revised work packages/dependencies. Keep the goals and acceptance outcomes stable unless a deliberate product decision changes them.

The alignment note records the initial reconciliation at `a7dae5a`; refresh it against the actual implementation baseline. Resolve shared identity, local/source coordinates, clock consumption and proof/dependency ownership with the first-short P00/P02 interfaces before dependent code diverges. A character package is a specialized use of the shared model/registration foundation, not a competing general object graph. This does not require completing narrative finite-shot or dialogue features before the two-lantern experiment.

The [mc/1 model and character contract packet](model-contract/README.md) reconciles that shared technical subset against `00c6443`, with versioned specimens, focused checks and bounded construction/instance slices. It implements no model runtime and does not complete Phase 1 or P00: production seed selection, the complete scene census and production inputs remain outstanding.

| Adjacent work | Integration outcome to preserve |
| --- | --- |
| [Production intent and coverage][production-plan] | One authoritative inventory/requirement model with model ownership and exact evidence references. |
| [Workflow guidance](WORKFLOW-CLI.md) | Native model operations own assembly and recovery; workflow resolves their inputs, exact subjects and continuations. Share the operator/model acceptance case without a second census, resolver or run journal. |
| [First-short packages](FIRST-SHORT-WORK-PACKAGES.json) | Align model/character/part IDs, registration, overrides, local-cycle time and typed proof identity through P00/P02. Preserve independent story/clock work and existing loop behavior. |
| [CLI-first architecture][cli-plan] and [scene transactions][transactions] | Structured, resumable edits; reviewable changes; saved state and browser behavior agree. |
| [Seed-to-stage composition][seed-stage] and [layer/light planning][layer-plan] | Full-scene scope, both formats, finished backing and distinct ownership/mounting/lighting relationships. |
| [Studio discovery and review delivery][studio-library] | Find the actual project/current review; model versions and proof artifacts connect to the selected revision. The film library and model library have distinct roles. |
| [Output quality and sound-library work][quality-plan] | Preserve source quality, compact cycles and compatible version/provenance practices; use the settled audio/mix and export workflow for scene reviews. |

Defer schema/storage choices, exact CLI syntax, renderer/compiler boundaries, automatic contour implementation, packaging transport, migration tooling, detailed test lists, performance budgets and estimates to that reconciliation. Establish resource budgets from representative art and target outputs. Nested clipping, interleaved paint handling and roots without paint should be resolved according to the demonstrated model needs; the product acceptance remains correct visible composition and predictable editing.

The first implementation work package should deliver an independently inspectable layered model and its library record, followed by the two-lantern composition experiment. The entire roadmap remains open until full-scene reconstruction, second-scene reuse and the agent-operated adoption trial are demonstrated.

The shared operator trial must use supported operations or demonstrate a specific capability mismatch before custom mechanics, while still identifying contaminated paint and unmounted parts. Use `asset prepare` for an actual source/backing separation problem; clean isolated parts can use current compiler/scene operations directly. Neither instruction compliance nor a structural independence pass replaces the model's visual move/hide, reveal and reuse criteria.

[research]: ../research/clean-components-2026-09-12/report.md
[production-plan]: PRODUCTION-IMPROVEMENTS.md
[cli-plan]: CLI-FIRST.md
[transactions]: SCENE-TRANSACTIONS.md
[seed-stage]: ../SEED-TO-STAGE.md
[layer-plan]: ../LAYER-AND-LIGHT-PLANNING.md
[studio-library]: ../STUDIO-LIBRARY.md
[quality-plan]: TV-QUALITY-AND-SOUND-LIBRARY.md
