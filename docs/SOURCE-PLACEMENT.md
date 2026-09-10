# Source placement and reference-pose parenting

`scene place` turns recorded reference coordinates into ordinary scene layers and sockets. `scene reparent --keep-world --at` changes an attachment while preserving its evaluated appearance at one time. Both use the same batch engine, scene history, stale-input check and dry run as `scene apply`. They do not edit source images or existing asset packs.

## Placement manifest

```json
{
  "kind": "ambiance-source-placement",
  "version": 1,
  "placements": [
    {
      "id": "body",
      "asset": "body-cutout-v1",
      "base": "room",
      "mode": "native",
      "reference": {
        "file": "assets/source/reference.png",
        "sha256": "replace-with-the-reference-file-sha256",
        "width": 941,
        "height": 1672
      },
      "order": {"before": "fixed-glass"}
    }
  ]
}
```

The hash placeholder must be replaced with 64 lowercase hexadecimal digits. Run `./ambiance --project PROJECT scene place placement.json --dry-run` to inspect the proposed scene, source anchor, derived dimensions, world corners at zero, inherited appearance, paint index and pinned dependencies. Remove `--dry-run` to save; `--expect-sha256 HASH` checks the scene used to author the change. A batch uses the same placement fields plus `"op":"place_from_source"`.

`base` identifies an existing one-cell painted plane. The reference image is the coordinate frame, which can differ from a repaired clean plate. File identities include decoded dimensions and SHA-256, not a filename alone. Manifest references are project-relative, including explicit mapping files. The manifest argument itself follows the CLI's usual shell-relative convention. Absolute references, path escapes, incorrect dimensions and changed dependencies fail. Dependency results include `resolved_path` and `path_base: "project"`.

Two modes deliberately use different size contracts:

| Mode | Required authoring information | Size calculation |
| --- | --- | --- |
| `native` | Verified reference-to-cell mappings for the base and one-cell cutout | Invert the cutout's recorded crop/return/compiler mapping; retain its full-cell size, including padding |
| `sprite` | Verified base mapping, `source_anchor: [x,y]` and positive `source_size: [width,height]` | Explicit intended dimensions of the full compiled cell in reference pixels; never inferred from alpha bounds |

`anchor` optionally overrides the asset pivot; its components are normalized full-cell coordinates. For native placement the source anchor follows from that pivot and the recorded mapping. An explicitly supplied native `source_anchor` must agree; `source_size` is forbidden. Native sequences with multiple cels are outside this first slice. Use sprite mode with an intended full-cell size for generated gestures, rats or flames.

`order` accepts exactly one existing `before` or `after` layer. Omit it to append the layer to the front. No depth sorting occurs. `values` accepts name, opacity, visibility, blend, cycle/phase, motion, tracks and track-loop policy. Placement derives the reference-aligned **base pose**; intentionally supplied motion/tracks then run normally, so sampled corners at zero can differ from the base pose. Geometry fields cannot be overridden inside `values`.

## Mapping and preparation

New compiler packs contain `registration_mapping` version 1. Each cel records its source index/rectangle, raw-cel-to-cell affine and whole-input-image-to-cell affine. Shared scale, padding and full cell dimensions are explicit. When a hash-bound source mapping is supplied to the compiler, the result also includes the original reference identity and `reference_to_cell` per cel. See [asset preparation](ASSET-PREPARATION.md) for crop, enlarged edit return and explicit registration correction. A same-sized returned image is not proof that its painted landmarks stayed in place.

Affines are six numbers `[a,b,c,d,e,f]` in the renderer convention: `(x,y)` maps to `(a*x+c*y+e, b*x+d*y+f)`. Placement composes cell-to-reference, reference-to-base-cell and base-cell-to-scene geometry. It then attaches the new layer to a deterministic source socket on the base. The base's camera, group, scale and rotation are inherited once. Width and height encode differing axis scales; shear, reflection and singular mappings are rejected.

Immutable legacy packs can use explicit `mapping` and/or `base_mapping`. The value is an inline record below or `{"file":"assets/mappings/base.json","sha256":"..."}`. The CLI verifies the file hash and resolves its references before the bridge runs.

```json
{
  "version": 1,
  "asset_sha256": "replace-with-the-atlas-or-image-file-sha256",
  "cell_size": [945, 1676],
  "reference": {
    "file": "assets/source/reference.png",
    "sha256": "replace-with-the-reference-file-sha256",
    "width": 941,
    "height": 1672
  },
  "reference_to_cell": [1, 0, 0, 1, 2, 2]
}
```

This record is an explicit authored geometric assertion. It cannot certify registration visually. Existing compiler-backed metadata must still match its pack and recipe; an explicit mapping does not bypass integrity checking. The Python adapter checks the selected reference, atlas, catalog, compiler records, recipes, prepared inputs and source-mapping records, then checks pinned bytes again immediately before saving. The JavaScript bridge validates geometry; it does not read files independently.

## Preserve one evaluated pose when reparenting

```sh
./ambiance --project PROJECT scene reparent accepted-hand --to mummy-body --socket wrist --keep-world --at 1.25 --dry-run
```

The corresponding batch operation is:

```json
{"op":"reparent","layer":"accepted-hand","to":"mummy-body","socket":"wrist","preserve":"world_at_time","at_seconds":1.25}
```

At that time, the engine samples the old child and new parent/socket matrices, solves the new local transform, and verifies all four transformed child corners. It also preserves effective visibility and multiplicative opacity. The report includes before/after matrices, corners, inherited appearance, changed fields and maximum corner error. Exact-time checks use a maximum corner tolerance of `1e-7` canvas pixels and opacity tolerance of `1e-10`.

The operation retains the asset, cell clock or cell track, per-cel sockets, dimensions, anchor and paint order. Existing sinusoidal offsets are subtracted when solving the new base x/y/rotation at the reference time. Their later motion remains in the new parent's local axes. A newly moving casket therefore carries its accepted hand and front rim; fixed glass stays independent. This preserves the chosen pose, not the previous world trajectory or every later inherited opacity/visibility state.

Child x/y/scale/rotation tracks are rejected because rebasing their future values is a separate authoring operation. Opacity or visibility tracks can remain only when their sampled local value needs no change. A visible child cannot be preserved under a hidden parent; nonzero effective opacity cannot be preserved under a zero-opacity parent; required local opacity above one fails. No clamping is used. Cycles, missing sockets, singular matrices, shear/reflection and unsupported nonuniform matrix scale also fail without saving.

## Runnable proof fixture

```sh
python3 examples/source-placement/create_fixture.py --out /tmp/ambiance-placement-demo
./ambiance --project /tmp/ambiance-placement-demo scene timing --layer gesture
./ambiance --project /tmp/ambiance-placement-demo preview
```

Choose a fresh output directory. The fixture compiles geometric art, places a native body and generated gesture/rim/glass, reparents the gesture and rim, then lifts the body. `scene/before-reparent.json` and the final `scene/scene.json` should produce the same raster at zero. At two seconds, the body/gesture/rim rise while glass stays fixed. `transaction-report.json` records the actual operation diagnostics. These are engineering assets, not changes to any film.

`node tests/test-source-placement.mjs` exercises geometry, timing and rejected contracts. `python3 tests/test_scene_authoring.py` checks real compiler metadata, legacy mapping, dependency changes and the project-check timing adapter. Browser/raster inspection remains a separate proof of overlap and visual continuity.
