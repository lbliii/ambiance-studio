# Local model construction C1/C2

This implemented subset of [mc/1](contract-v1.md) builds immutable local packages and static model proofs. It does not implement scene instances, version adoption, finite/local-cycle clocks, Phase 1/P00 or artistic acceptance. [The replay](../../../examples/model-construction/README.md) uses complete geometric raster artwork with a painted root, nested candle/flame, separate glass and two frame drawings. It is explicitly an engineering specimen.

## Public operations and ownership

All paths are shell-relative CLI inputs. All six routes are project-free, including when `--project` is supplied. There is no implicit project/catalog/library mutation.

| Route | Result and `--out` owner |
| --- | --- |
| `model build DEFINITION --source-root DIR --out PACKAGE` | New package directory; service-owned atomic publication |
| `model inspect PACKAGE_OR_ENTRY [--out REPORT]` | Read-only inspection; optional normal JSON envelope file |
| `model lower PACKAGE --state STATE --out PROJECT` | Fresh ordinary scene/catalog project plus mapping and package copy |
| `model proof PACKAGE --recipe RECIPE --out PROOF` | Fresh proof directory, rendered images, exact sealed report and HTML |
| `model check PROOF --package PACKAGE --recipe RECIPE [--out REPORT]` | Read-only exact-input/runtime/output freshness check |
| `model admit PACKAGE --proof PROOF --recipe RECIPE --out ENTRY` | Fresh portable local technical candidate entry; package, proof and recipe copies |

Occupied destinations fail, even for an identical request. Failed validation publishes nothing. Publication uses the existing `fresh_output`/exclusive directory rename; it never replaces an older version or a racing publisher. No lock or mutable “latest” selector is added. Version equality is exact definition bytes within a resolved closure; independently named output locations do not create a global family registry. Adopting versions in a scene remains I2.

## Definition schema

A definition has `format: ambiance-model-definition`, `schema_version: 1`, `path_base: document`, stable `model_id` and `version`, `kind` (`prop`, `environment`, `character`), optional `name`/`notes`, `local_frame`, `root_part_id`, `drawings`, `parts`, `sockets`, `controls`, `variant_sets`, and `paint_order`. Unknown fields fail at each authored level. Authored IDs use `record_contracts.identifier` unchanged. IDs in each typed namespace are unique and case-sensitive. Character-specific view tables remain P02 work.

`local_frame` contains `size: [width,height]`, `pivot: [x,y]` in local pixels and `clip: none`. Its unmounted root is a nonempty drawing leaf. All other parts mount to a declared socket, and every leaf must resolve through that root. The registered root anchor must coincide with the declared model pivot, including nested models. This explicit restriction avoids a silent alternate rotation center. Non-paint carriers, shear, reflection, nonuniform and singular transforms fail. Local frames are bounded to 4096 pixels per side, definitions to 32 nesting levels/128 distinct documents, dependencies to 4096 files.

A drawing is:

```json
{
  "drawing_id": "frame-square",
  "asset": {
    "file": "../packs/frame-square/asset.json",
    "sha256": "EXACT_ASSET_JSON_BYTE_HASH",
    "report_sha256": "EXACT_COMPILER_REPORT_BYTE_HASH"
  },
  "cel_index": 0,
  "material_role": "solid",
  "source_to_local": [1, 0, 0, 1, 0, 0]
}
```

Drawings pin ordinary compiler packs, which may be built with `asset build`. `source_to_local` maps the **whole compiler input image** to the containing model frame; a strip cel's input origin is retained. The compiler's full-cell mapping yields `cell_to_local = source_to_local × inverse(source_to_cell)`. No alpha fitting occurs. `parts` reference drawing IDs and assert that same `cell_to_local`. Compatible drawings retain that mapping, full-cell dimensions, pivot and role. Every declared variant/drawing-control alternative is validated before publication, even if not selected.

A nested part instead has `definition: {model_id, version, file, sha256}`, `local_to_parent` and `mount`. A mount has `part_path` and `socket_id`. Sockets have `socket_id`, a drawing-leaf `part_path` and normalized full-cell `cell_uv`. A parent may export a nested leaf's socket under its own stable ID. Nested slot roots retain their registered rest offset; a named mount does not snap it away. The lowering report exposes actual reparent diagnostics, local offsets and source/rest corners. `paint_order` lists every owned drawing-leaf path once, independent of mount order.

Package paths preserve the source-root-relative layout byte for byte. The copied closure contains root/nested definitions, compiler outputs, portable editable recipes, all original input images and named registration sources. `asset inspect` and file/record identity helpers are reused. Paths escaping the explicit source root, symlinks, missing/changed pins, mixed bytes for the same model/version, cycles, duplicate IDs and incomplete closure fail. Definitions do not retain an absolute worktree reference. Unlisted/changed package sources fail on reopen.

Basic isolated compiler inputs and named landmark registration sources are supported. Project-relative source mappings and region/compound/motion/trim/edge preparation receipts require a future typed package materialization adapter and fail explicitly here. Already isolated art does not pass through source separation. The portable compiler recipe can be rebuilt with `asset build`; atlas bytes and registration are tested against the preserved version. The package records current construction implementation identities; the pinned original compiler report retains its version/cache/source facts. It does not retrospectively assert which unrecorded compiler binary made older art.

## Static states, controls and variants

A state has `schema_version: 1`, `pose_id`, `controls` and `variants`. Overrides are arrays of `{model_path: [...nested slots], control_id, value}`. Variant selections are `{model_path, variant_set_id, variant_id}`. No arbitrary layer patch is accepted. Models store no source-film canvas, fps or duration. The emitted one-second/one-fps compatibility scene holds every cel constant; its clock is explicitly labeled static in derived metadata. Animation/cycle/track fields are unsupported and rejected, including phase/rate controls. P03 remains the only planned shared clock owner.

Controls have stable IDs, type, default and `target: {part_path, channel}` or `{part_path, control_id}` for forwarding to a nested model. Supported channels:

| Channel | Type and unit | Application relative to registered rest |
| --- | --- | --- |
| `visible` | boolean | Set local visibility; engine descendants inherit |
| `opacity` | number, `ratio`, range within [0,1] | Set local opacity; engine multiplies ancestors |
| `scale` | number, `multiplier`, positive range | Multiply the rest scale |
| `rotation` | number, `radians` | Add to local rest rotation |
| `x`, `y` | number, `local-pixels` | Add a parent-local offset before engine evaluation |
| `drawing` | drawing, explicit allowed drawing IDs | Select a registered cel; preserve its contacts |

Numeric controls need finite `min`/`max`. A forwarding chain has one effective value; ranges/types/units must fit its target. A forwarded control cannot also receive a direct override. Multiple forwarders, cycles, multiple channel writers and competing drawing controls/variant sets fail before publication. Defaults never mask a competing authored writer. Unknown state fields or duplicate override identities fail.

A variant set declares its default and variants with drawing replacements. Variants use stable part/drawing IDs. Compatible drawing changes do not rename runtime leaves. Runtime layer/asset/socket IDs derive from typed tuple hashes and are collision-checked. The mapping is derived, never an independently edited authored graph. This is one local model identity, not the future scene instance namespace.

## Lowering and proof boundaries

`tools/model/lower.mjs` uses the existing engine affine functions, compiler source registration and `reparentAtTime`. It produces ordinary layers/catalog, resolves mounts through the real evaluator, verifies all four rest corners against registration, then applies allowed controls. Existing scene validation determines inheritance, cel selection and paint order. It implements no second evaluator.

A proof recipe has `schema_version: 1`, one to 32 explicit static `states`, unique `roles` chosen from `solid`, `glass`, `flame`, `smoke`, `glow`, and integer `threshold` in [1,255]. It produces one native-size sample set per state, with a 64-million aggregate role-pixel bound. Raster frames must have integer dimensions. Output framing is the local frame with identity crop-to-local mapping; content outside that explicit viewport is not claimed. `clip: none` defines the model geometry, not infinite output pixels.

Proofs exercise `prepareRaster` and `renderRigProof`, using `drawScene` for original-source comparisons and role passes. Role passes filter already evaluated leaves, so excluding a solid parent does not lose a mounted flame's transform. Original-source views use the compiler's exact source rectangle and source-to-cell affine over the same evaluated transforms, then the same drawing path; they are not another compositor. Source-versus-compiled RGBA differences are diagnostics. Fresh canvases isolate each role; the ordinary repeated raster path must still pass its real endpoint check.

`composite.png` and each role PNG preserve soft RGBA. Corresponding `*-mask.png` files encode binary coverage at the explicit threshold; bounds are pixel-edge/end-exclusive, and an empty mask is transparent with `bounds: null`. Role classification is authored, never inferred from alpha. A proof records:

- Exact root/closure bytes, package hash, recipe bytes and values, effective controls, variants and drawing/cel choices.
- Ordinary scene/catalog, deterministic mapping, mounts/rest offsets, selected and hidden leaf IDs, explicit static clock and source rectangles/transforms.
- Actual role-included/excluded/visible sets, resolution, threshold, crop/bounds policy, and every output hash.
- Construction/compiler/engine/source-placement/binding/finishing/drawing/renderer source identities and Node/Canvas runtime identity.

`model check` recomputes the resolved state, verifies package closure, recipe, implementation/runtime and every output byte. Changed pose, override, variant, source, role policy or implementation is stale even if filenames or pose labels are unchanged. The sealed local entry copies the exact package/proof/recipe and rechecks after materialization. `model inspect ENTRY` verifies that entry and its current proof.

Technical admission never records artistic acceptance. The proof is not a coverage provider or a revision adapter and is not relabeled as one. There is no receiver paint in the local package: `source_receiver_links: []` and the proof limitation state this explicitly. Receiver removal, contamination in other scene contributors, normal-speed motion, both film compositions, production paint and human observations remain separate acceptance gaps.

## Observed capability gap

Before implementation, the public source-placement fixture and `scene reparent --keep-world --at 0 --dry-run` preserved corners within `5.68e-14` pixels. The mc/1 specimen tests passed. That operation requires an existing reference plane and has no immutable nested-definition closure, control resolver or library-entry record; C1/C2 add only those missing adapters. Source placement and rig proof remain the geometry/raster authorities. The first actual transparent model proof exposed retained-canvas accumulation; its captured failing replay was sent to D2 rather than changing renderer semantics in this package service.
