# mc/1 — definition, instance and proof boundary

This document specifies the meaning of the [packet specimens](../../../tests/fixtures/model-contract/README.md). It is not the validator/schema for a shipped model format. Unknown production fields must fail when implementation lands; the focused specimen checker below is deliberately narrower than that future validator.

## Identity, pins and adoption

Use the existing `record_contracts.identifier` alphabet/length for authored IDs: 1–100 ASCII letters, digits, dots, underscores or hyphens, starting with a letter/digit. IDs are case-sensitive. `model_id` identifies an enduring editable family; `version` identifies one immutable revision of it, and `sha256` pins the **exact definition file bytes**. A version label alone never proves equality. Character definitions set `kind: character`; `character_id` in a consumer is exactly that `model_id`, not a separately mutable alias.

Part, drawing, control, exported socket, variant-set and variant IDs are stable within their owning model. Character-view IDs select registered art orientation; they are unrelated to output framing view IDs. An instance ID is unique in the scene. Re-labeling does not change any ID. Removing an ID makes an incompatible dependency change unless adoption explicitly remaps/resets its consumers.

A part is either a drawing-bearing part or a nested model slot. A nested slot has its own stable part ID and exact `{model_id, version, file, sha256}` pin. Repeated slots may reference the same definition; their identities remain different. A resolved member is addressed by `(scene instance_id, [nested slot IDs..., leaf part_id])`, never by a display-name path or array index. A drawing ID maps to an exact asset pin and zero-based cel index; changing atlas packing is a new pinned mapping and does not rename the semantic drawing.

Do not prescribe a human-readable concatenation as a globally collision-free runtime ID. The construction adapter emits a deterministic, collision-checked tuple → runtime layer/signal/binding mapping and saves it as derived metadata. Rebuilds of unchanged input must reproduce it. That mapping is not another authored assembly graph. Duplicate operations choose a new scene instance ID and derive independent internal IDs, while sharing immutable definition/art bytes.

Definition/file references in specimens are relative to their containing definition or specimen (`path_base: document`); package publication must materialize all nested/art/editable-source dependencies inside its immutable package root and reject escapes/symlink escapes. Existing project metadata remains project-relative, compiler inputs recipe-relative, and CLI arguments shell-relative. Materialization rewrites typed paths deliberately and records source/destination hashes; never silently reinterpret existing fields or retain a mutable worktree dependency. Definition cycles, missing dependencies, duplicate IDs, changed bytes under a version, unpinned art and incomplete closure fail before publication/adoption.

Use `file_identity.digest`, `record_contracts.seal/read_sealed` and the existing revision collector's typed edges. Exact file hashes and a sealed record's `payload_sha256` are different identities; a pin to a file uses its byte hash. Do not add a different cross-language canonical JSON hashing algorithm. Manifests/receipts can be sealed by the existing service; runtime content remains bound to exact files and emitted mappings.

An instance stores its definition pin, placement/mount, selected variant IDs and explicit allowed overrides. Updating a library record never mutates an existing instance. Adoption names old/new pins and expected scene hash, verifies closure, previews affected managed layers and dependent receivers, and reports retained, explicitly reset, remapped and conflicting fields. Changed ranges, absent sockets/drawings/parts, changed registration or uncontrolled layer edits are conflicts, not implicit resets. A compatible label-only definition revision retains overrides by ID. Changed nested pins still require adopting a new parent version; no transitive live upgrade occurs.

The save uses the existing scene transaction and history. Runtime layers, relationships, instance metadata and their source identities commit together after full candidate validation. A failed late operation leaves the old scene intact. Existing direct file edits bypass its lock; do not claim filesystem compare-and-swap. Separate immutable build/publication from scene mutation; an interrupted build is not permission to leave half an instance in a scene. Operation retry must identify the exact prior commit/result or reject occupied instance IDs, never duplicate silently. A future build may reuse validated immutable outputs; accepted originals stay unchanged.

## Local registration and scene placement

A definition has a fixed `local_frame` size, top-left origin, pivot in **local pixels**, and `clip: none` for this slice. The frame establishes scale, not a tight alpha crop or automatic clipping region. No originating scene canvas, output fps or duration is inherited. Cropping a derivative preserves the frame through an explicit crop-to-local affine.

Affines use the existing `[a,b,c,d,e,f]` convention and column points: `x' = a*x+c*y+e`, `y' = b*x+d*y+f`. Use the current engine's `multiply`, `inverseMatrix`, `point` and compiler mapping records. For mapped source art:

```text
reference_to_cell = source_to_cell × inverse(image_to_reference)
cell_to_local = reference_to_local × inverse(reference_to_cell)
cell_to_scene = instance_local_to_scene × cell_to_local
```

`source_to_cell` acts on the whole input image; `raw_cel_to_cell` acts on the extracted cel. A grid cell's origin must not disappear. Preserve compiler `cell_size`, `shared_scale`, padding, per-cel pivots and source rectangles. Width/height and normalized sockets refer to the full output cell, not alpha bounds. Character drawings use one declared registration basis and compatible shared scale; a cel's deformation is not independently fitted to fill its box.

The character specimen has reference 200×300, `reference_to_local = [1,0,0,1,-40,-30]`, model frame 120×220 and pivot `[60,210]`. Its head's 40×40 padded cell has `reference_to_cell = [.5,0,0,.5,-30,-15]`. Cell center `[20,20]` maps to reference `[100,70]` and local `[60,40]`; its full cell spans local `[20,0]` through `[100,80]`. The body retains its whole 70×120 padded cell and extends beyond the design frame; it is not clipped. Mouth drawings retain separate stable drawing IDs even when stored as neighboring atlas cells.

Registration is not scene placement. Instance placement applies positive uniform scale and clockwise rotation to model-local pixels, then converts to current canvas-normalized anchor/size/track fields. A mount is an explicit socket and parent-local offset. Camera/parallax applies once. Current `scene place` can prove source-backed one-cell registration; it requires a painted reference base and emits attachments. That base is not automatically a production model root. A model may use already-isolated registered art without compound source separation. Its chosen painted root must belong to the model, and its mapping must be known.

Specimen `cell_to_local` matrices are rest-placement assertions in the containing model frame; a nested slot's `local_to_parent` maps its model frame into the containing frame. The named mount adds following behavior without snapping away that recorded rest placement. Lowering derives/reports the parent-socket offset using the child's registered pivot (the nested model pivot for a slot), or rejects missing registration. Socket coincidence is required only for an explicitly zero-offset contact. Source placement/reparent-at-time supplies the existing preservation pattern; model construction must make each pivot/offset inspectable.

Reuse current restrictions: native placement supports one-cell cutouts; sprites require explicit full-cell source size; per-cel sockets select the actual evaluated cel. Reject unrepresentable shear, reflection, singular transforms and unsupported preserve-world rebases instead of approximating. Reparent-at-time preserves one sampled pose, not the future world trajectory. New character multi-drawing registration validates every drawing; it must not invoke the one-cell native route and claim it supports sequences.

## Construction, controls and relationships

The first definition slice requires one drawing-bearing root. Every internally mounted member resolves to that root through existing sockets; nested definitions attach their painted roots. A still character body is owned and included. Definitions lacking a suitable painted root return an unsupported-case diagnostic; transparent carrier rasters are not an implicit workaround. Nonpaint roots require a separately reviewed engine change only after a concrete failing representative case.

| Relationship | Meaning and lowering |
| --- | --- |
| Ownership | Exactly one technical owner for each part/nested slot; whole-model selection, copy, isolation and removal expand this set. Collections organize instances and change no transforms/paint. |
| Mount | What follows a parent/socket. Uses existing `attach`, including inherited visibility and multiplicative opacity. A scene-owned lantern mounted on a fence retains its own identity; detaching need not change ownership. |
| Paint order | Definition back-to-front leaf path sequence; one contiguous scene block per instance initially. It must contain each owned drawing leaf exactly once. The flame can precede the front frame while being mounted to the candle. External pumpkin order is explicit. |
| Depth | Parallax only. Instance root uses independent/group depth; attached descendants inherit depth today. Independent child-depth overrides fail. No automatic depth sort. |
| Receiver light | Fixture owns luminous art and emitter output. Receiving surface owns contribution paint/mask and an explicit external source link. Receiver paint mounts to receiver, never to the flame. |

Controls have stable IDs, explicit type/unit/default/range and declared existing-channel targets. mc/1 permits boolean visibility/source-on, bounded scalar opacity/rotation/scale/position, discrete registered drawing selection and local-cycle phase/rate where supported. Numeric values must be finite, scales positive, opacity within [0,1]. Position uses model-local pixels before lowering; rotation uses radians, phase uses **turns**, period uses positive rational seconds. Shot fps converts these through P03. Model defaults never store phase in an originating film's frames.

An instance may override only declared controls and opted-in part channels; no arbitrary runtime-layer patch is an override. Each channel has one writer: direct override, track, binding or drawing control conflicts must be rejected under existing binding rules. Variant selection substitutes explicitly compatible drawings/construction and retains stable contacts/controls/registration. Flame cels are animation states, not frame-style variants. A new viewing angle requires registered art and an explicit compatibility decision. Hidden is separate from unlit; inherited opacity is multiplicative and is not group compositing.

An exposed parent control may forward to a named nested control (`part_path`, `control_id`) rather than also writing its underlying layer channel. The lantern's `source-on` forwards to the candle's `flame-on`; this creates one effective control value/writer after defaults and explicit overrides resolve. Competing direct/forwarded overrides of that same effective control fail; arbitrary expression graphs are outside mc/1.

Instance signal/binding IDs are namespaced in the derived mapping. New relationships merge with unrelated existing scene entries through one validated batch; current `look import` replaces complete binding configuration and requires the source canvas/clock for rig adoption, so it is not a general instance import API.

Use existing cel signals/bindings to turn source-hidden/off into receiver `off: 0`. Other illumination and receiver geometry remain unchanged. Prepared illumination attaches directly to a receiver and is composited after it under current finishing rules. A moved source may drive a supported anchored zone or a bounded receiver-local mapping; outside its declared valid envelope it must report reauthoring/review required. No automatic transport or inferred unlit paint is promised. The lantern specimen records a receiver effect separately from the lantern's ownership tree.

## Derived outputs and evidence

Derived alpha, material coverage, solid silhouettes and bounds are disposable outputs of a resolved state, never editable substitutes for the model. Composite onto transparency using the existing evaluator/drawing code. Preserve soft alpha and holes; material roles are authored (`solid`, `glass`, `flame`, `smoke`, `glow`), not inferred from alpha. Solid masks exclude the other roles and external receiver paint. Record threshold, resolution, crop-to-local mapping and empty-mask behavior. Bounds are pixel-edge, end-exclusive. A thresholded silhouette is coverage, not collision geometry.

Every derived product/proof must bind:

- Exact root and transitive definition/art/source/compiler identities, selected variants and effective allowed overrides.
- Pose ID **and resolved pose values**, character-view/drawing/cel selections, instance/mount state when relevant, full evaluated clock/local-cycle sample (or an explicit static pose), and sampled range for envelopes.
- Actual included/excluded runtime leaf IDs and source-receiver links; output framing view/hash and resolution; threshold/role policy; relevant engine, binding, finishing, drawing/compiler/adapter version hashes.
- Actual output files/hashes, reference-to-local/crop mappings and limitations. A scene-context proof additionally binds scene/catalog and captured revision/edition/plan subjects through existing services.

Any changed bound input makes that product stale. Model-local masks can be reused across scene placement only when their declared subject excludes placement and the exact local state is unchanged. A scene-space mask includes placement/view. A motion envelope states its sample list/range and never promises unsampled poses. Variant, override, dependency, role policy or renderer changes cannot reuse an old result merely because its filename or pose label is unchanged.

Extend `revision_dependencies.Collector` and `coverage_evidence.ProviderVerifier` with typed adapters under their owners; reuse `render rig-proof`, frame/views proofs and activity observations. A rig-proof report is not currently an accepted raster provider receipt. Do not relabel it or infer pass verdicts. Removal proof records the effective hidden owned set plus affected receiver contributions and inspects **all** remaining contributors for duplicates. Geometry, hashes and alpha cannot recognize a baked lantern in planter RGB, judge restored hidden paint, or replace normal-speed observation. Library admission, compilation, model acceptance and scene acceptance stay separate records.
