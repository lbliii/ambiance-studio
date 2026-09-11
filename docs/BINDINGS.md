# Source bindings and painted illumination

`binding inspect/check --time SECONDS` samples the same absolute picture clock as preview and export. `binding apply FILE --dry-run` validates a complete binding document; save with the returned `--expect-sha256`. Both apply and the `bindings` scene operation use the ordinary atomic transaction, dependency check and restorable history. `--out FILE` on inspect/check saves the JSON result. Checks establish state and file identity, not visual quality.

```json
{
  "kind": "ambiance-bindings",
  "version": 1,
  "bindings": {
    "version": 1,
    "links": [{
      "id": "candle-floor-strength",
      "source": {"signal": "candle-strength", "range": [0, 1]},
      "target": {"layer": "floor-paint", "channel": "opacity", "range": [0, 1]},
      "map": {"interpolation": "linear", "keys": [[0, 0], [1, 1]]},
      "off": 0
    }]
  }
}
```

`bindings: null` removes bindings. `scene apply` accepts `{"op":"bindings","value":CONFIG_OR_NULL}` for an atomic combined rig/look/binding change. IDs are stable, unique within their collection and case sensitive. The production plan can refer to `binding:ID`, `signal:ID` or `illumination:ID` without relying on array indices.

## Inputs and mappings

Each source is exactly one of these forms:

| Source | Meaning |
| --- | --- |
| `{"signal":"ID","range":[min,max]}` | Existing finishing intensity signal. Closed keys or actual cel selection supply the value; no new clock. Range lies within 0–8. |
| `{"layer":"ID","channel":"rotation","range":[min,max]}` | Evaluated local pose: `x`, `y`, `rotation` or `scale`. This includes that source's tracks, periodic motion and incoming bindings before its parent/camera matrix. |
| `{"layer":"ID","channel":"cell"}` | Actual zero-based cel/state after the source's track or binding. Images have one state (0). |

Continuous ranges require finite `min < max`. Normalize and clamp `(raw-min)/(max-min)` to 0–1 before mapping. Continuous maps have 2–64 ordered `[input,output]` keys covering exactly 0–1; interpolation is `linear`, segment `smoothstep` or `hold`. A held knot takes effect at the knot, including input 1. A discrete source instead requires `{"values":[...]}` with exactly one output per source cel. Tables do not invent between-cel poses.

Every output and the explicit `off` value must fit the declared inclusive target range. Output channels are `x`, `y`, `rotation`, `scale`, `opacity`, `cell`. Position uses canvas width/height fractions along the layer's parent axes; rotation is clockwise radians; uniform scale is dimensionless (0.001–100); opacity is 0–1. Cel outputs require an atlas, integer indices and held interpolation for a continuous source. All ranges and values are finite. A response may travel a different distance or direction from its source.

Bindings replace their target's authored scalar or fallback cel cycle. A track on the same channel or a nonzero periodic-motion amplitude on a bound translation/rotation channel is a conflicting writer and fails. Other tracks and motion channels remain active. Attachment then applies the parent transform and inherited visibility/opacity exactly once. Scale bounds describe the local scale; parent and camera transforms still affect final size. There is no expression language, feedback, state accumulation or temporal lag.

A layer source is inactive when effective visibility is false or effective opacity is zero. An intensity source is inactive when its effective signal is zero; cel signals already multiply by source visibility and inherited opacity. Inactive sources use the required `off` value without evaluating a nonzero map endpoint. Pose/state sources otherwise retain their actual values (partial opacity does not shrink a pose). Use `off: 0` for illumination opacity. For a key-based power signal that must also dim the visible source, bind the luminous artwork's opacity to that independent signal. A cel signal cannot drive its own source layer; that is a cycle. A separate driver/fixture can feed both luminous art and receivers.

Dependencies combine source layers, cel-signal layers and attachments. Missing endpoints, cycles (including mixed attachment/binding cycles), duplicate IDs, multiple target writers and incompatible tables fail before mutation/render. The conservative graph is layer-level: it rejects self-dependencies even if two particular channels could be ordered. Hidden-reset source tracks become inactive during their authored hidden interval. Every seek wraps to picture time, including negative times; output frame N is never appended to the loop.

`scene timing` labels a bound cel channel `binding` and marks fallback cadence inactive. Its sampled intervals are exact at export-frame times. Authored continuous/subframe binding transition intervals are unavailable rather than inferred from a nominal cel rate. Preserve-world reparenting refuses bound child transform/opacity channels; an explicit coordinate/binding revision is required.

## Prepared painted light

Prepare a dim/base surface and separate source-shaped highlight paint or highlight cels. The renderer does not recover an unlit painting. Keep unrelated source light in the base deliberately. Add this relationship to a linear-sRGB finishing recipe:

```json
{
  "illuminations": [{
    "id": "floor-glow", "layer": "floor-paint", "receiver": "floor",
    "mask_asset": "floor-mask", "mode": "add"
  }]
}
```

The contribution layer must attach directly to a socket on its receiver. Its normal layer geometry, cels and bindings determine its shape and bounded motion. It is composited immediately after the receiver, before the receiver's shadows/reflections and later foreground artwork; it is not painted again at its layer-list location. Receiver must precede the contribution in the layer list. A layer can contribute to one receiver; contributions cannot receive other contributions. Their authored blend field does not override the explicit illumination mode.

The receiver's decoded alpha clips the contribution. Optional `mask_asset` is a single image/cel, sampled in the receiver's full-cell UV including padding; it stays on a moving/rotating/scaling receiver. White opaque pixels select fully; black or transparent pixels select nothing. The contribution inherits receiver opacity once through its attachment. Foreground painter order provides occlusion; no geometric shadow transport is inferred.

`add` adds premultiplied linear-sRGB contribution to the already painted base. Supply highlight-only paint, including zero/transparent areas where nothing is added. `mix` uses ordinary premultiplied alpha over the base in linear light; use a separately painted lit appearance when replacing a region. Both preserve the base surface's shape. The scene grade follows compositing and clipping is reported by the existing renderer. The `illuminations` drawing pass isolates contributions over black while retaining foreground occlusion; the look workbench exposes it for inspection.

The source flame may attach to a pumpkin while floor paint attaches to the floor. Bind source intensity to floor-paint opacity, source lean to a smaller receiver-local shift, and source cel to explicit highlight cels. These are three distinct relationships. Stable or muted light may remain constant; combustion can change shape and intensity; industrial light may have authored outages. None requires universal twinkling.

## Identity and review

Look and rig packages preserve `scene_bindings` and remap every explicit layer endpoint. Signal/binding IDs remain internal. A package with bindings replaces the complete binding configuration on import. Packages preserve exact painted base/contribution and mask versions; a rig also pins all rig image/socket identities. Compiler registration metadata is captured with images and masks. When receiver and mask share a source reference, their normalized reference-to-cell mapping must agree for every receiver cel. A lone correction fails until a matching companion is supplied. Independently correcting object-bound contribution art through cel-motion adoption is rejected until its companion relationship is explicitly revised.

Source and mask dependencies remain in the existing asset/compiler/revision closure; no arbitrary strings become dependencies. Captured binding recipes stay fixed when working drivers change. Package admission and hash validation do not approve artwork.

Run the [synthetic fixture](../examples/bindings/README.md) through the public CLI. Inspect low/high/off, left/rest/right, hidden-source, moving-receiver and fixed-occluder states. Use synchronized portrait/landscape proofs at normal speed, the isolated contribution pass, arbitrary seeks and the final-to-first transition. Record actual observations with exact artifact identities separately from structural/raster results. The fixture is an engineering demonstration, not a completed film or a physical-phone/human review.

For consumers, `compileScene(scene,catalog).sample(time)` remains an array of states. Each state adds `channels` (local evaluated values) and `bindings` (responses). `compileScene(...).inspectBindings(time)` returns `{version,time,bindings,samples}` with wrapped time, authored configuration, and samples `{id,source:{kind,raw,value,active},target,value}`. `source.value` is normalized input or the discrete cel. Hash `engine.mjs`, `bindings.mjs` and `finishing.mjs` when attributing runtime evidence.
