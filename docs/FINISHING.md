# Painted-image finishing and reusable looks

Finishing adds color adjustments, authored light regions and receiver-bound shadows/reflections to the existing layered scene. Preview, proof and final rendering use the same deterministic evaluator. A scene without `finishing` retains its existing Canvas rendering path; applying an explicit finishing configuration selects the linear-sRGB path. An identity configuration can therefore change legacy blend results, because its compositing space is deliberately different.

```sh
./ambiance --project PROJECT look inspect
./ambiance --project PROJECT look check --time 2 --out reports/look-check.json
./ambiance --project PROJECT look apply look.json --dry-run
./ambiance --project PROJECT look apply look.json --expect-sha256 SCENE_HASH
```

`look inspect` and `look check` return authored settings, shared-engine diagnostics, asset roles and verified dependencies. They do not certify appearance. `apply` replaces the complete finishing configuration in one validated scene transaction, preserving a restorable scene snapshot. A stale expected hash, unknown field, invalid relationship or changed dependency fails without saving. The file argument follows shell-relative CLI path conventions.

## Grades and color space

A look document contains `kind: "ambiance-look"`, `version: 1`, and `finishing`. Set `finishing` to null to remove the configuration. Otherwise the runtime value has this shape:

```json
{
  "kind": "ambiance-look",
  "version": 1,
  "finishing": {
    "version": 1,
    "working_space": "linear-srgb",
    "output_space": "srgb",
    "assets": {"stone-v1": {"saturation": 0.8}},
    "groups": {"display-case": {"exposure": -0.2}},
    "layers": {"cat-statue": {"balance": [0.8, 0.95, 1.15]}},
    "grade": {"contrast": 1.04, "saturation": 0.9}
  }
}
```

Grade order is asset, direct group, layer instance, local lights, compositing, then the scene grade. A group grade affects its explicit members; transform-attached descendants do not silently inherit their parent's color adjustment. Add an explicit instance grade where the same treatment is wanted. Parenting continues to inherit transform, visibility and opacity normally.

| Grade field | Meaning and range | Identity default |
| --- | --- | --- |
| `exposure` | Stops, -8 through 8 | 0 |
| `contrast` | Linear contrast around 0.18, 0 through 4 | 1 |
| `saturation` | Interpolate away from linear luminance, 0 through 4 | 1 |
| `balance` | Three RGB multipliers, each 0 through 8 | `[1,1,1]` |
| `curve` | 2–32 `[x,y]` knots in 0–1, strictly increasing x, spanning x=0 to x=1 | No curve |
| `mask_asset` | Catalog image or single-cel atlas ID | Full strength |

Exposure/balance precede contrast, saturation and the optional piecewise-linear curve. The engine decodes sRGB RGB values to linear light, composites premultiplied contributions, and encodes sRGB output once. Input artwork must already be sRGB; this pass does not perform ICC conversion. Alpha and masks are data. A mask's weight is stored luminance multiplied by alpha, so white opaque pixels select fully and black/transparent pixels select nothing. Masks are bilinearly sampled; values outside their support are zero.

Asset/group/instance masks use the affected layer's full-cell UV coordinates, including padding. A scene-grade mask spans canvas UV. Grading preserves source alpha. The final output clamp is reported as clipped pixels by raster proofs; a structurally valid extreme grade can still clip highlights.

## Light regions and shared signals

Add `lights` and optional `signals` to the finishing object:

```json
{
  "signals": [{"id":"lamp-pulse","layer":"lamp-flame","values":[0.6,1,0.8,0.9]}],
  "lights": [
    {"id":"moon","receivers":["floor","rat"],"rect":[0.55,0.1,0.35,0.8],"color":"#7198ff","gain":0.6,"feather":0.25},
    {"id":"lamp","receivers":["floor","casket"],"anchor_layer":"lamp-flame","rect":[-2,-1,6,7],"color":"#ffad57","gain":0.8,"feather":0.3,"signal":"lamp-pulse"}
  ]
}
```

Each light names explicit receivers. `rect` is `[x,y,width,height]`: canvas fractions for a fixed region, or fractions of the anchor layer's full-cell rectangle when `anchor_layer` is present. An anchored rectangle can extend outside 0–1; a small flame needs a rectangle larger than its own cell to illuminate neighboring objects. Receiver pixels move through the fixed or attached region naturally. Light color is a six-digit sRGB hex value; gain is -1 through 8, and edge feather is 0 through 0.5. An optional `mask_asset` modulates the region in its own normalized coordinates.

The effect multiplies receiver RGB by a colored intensity factor. It does not add geometric light transport, change source alpha or automatically affect every layer. Values are deterministic and sampled from absolute picture time.

A cel signal requires one intensity value per source cel, including held/repeated cels. It follows the layer's actual cell clock or cell track and multiplies by effective visibility/opacity, so a hidden flame's shared signal becomes zero. Alternatively use closed `keys: [[time,value],...]` plus `interpolation: "linear"`, `"smoothstep"` or `"hold"`, with keys beginning at zero and ending at the picture duration with matching values. Intensities range from zero through eight. A key-based signal is independent of a layer. Shared signal IDs can drive several lights or projected effects without separately authored flicker cadences.

## Source bindings and prepared painted light

[Source bindings](BINDINGS.md) map existing signal intensity, normalized local pose or discrete cel/state to bounded layer channels. `binding inspect/check/apply` uses normal scene transactions. `finishing.illuminations` composites prepared contribution layers over explicit receiving bases, clipped by receiver alpha and receiver-local masks in linear light. Attachment, source response and surface receiving remain distinct. Reusable look/rig packages preserve the binding endpoints, registered masks and painted base/contribution identities.

## Contact shadows and reflections

`shadows` and `reflections` are explicit relationships, painted immediately after their receiver and before later foreground layers. The caster must occur after the receiver in the scene's painter order, and they must be different layers. Receiver alpha clips the projected result; caster and receiver visibility/opacity affect it. An arbitrary depth number does not establish the relationship.

```json
{
  "shadows": [{
    "id":"casket-contact","caster":"casket","receiver":"floor",
    "offset":[0,0.005],"scale":[1,0.2],"opacity":0.55,"color":"#101522","softness":0.003,
    "elevation":{"layer":"casket","rest_y":0.69,"range":0.06,"offset":[0.025,0.018],"scale":[1.3,0.36],"opacity":0.24,"softness":0.018}
  }],
  "reflections": [{
    "id":"casket-floor","caster":"casket","receiver":"floor",
    "offset":[0,0.01],"scale":[1,0.28],"opacity":0.12,"softness":0.006
  }]
}
```

The caster uses its evaluated `ground` socket, including per-cel coordinates, or falls back to the bottom center of its full cell. Author a ground socket for padded sprites; the fallback is reported. The current cel supplies the shadow silhouette and reflection color. The projection follows relative caster/receiver rotation while flattening the image at contact. `mask_asset` can supply explicit painted appearance/coverage instead; that asset is a separately versioned single image. Shadows use `color`; reflections retain the selected source RGB, apply the caster's source grades, and flip vertically at contact.

Offset is measured in canvas-normalized units along the receiver's local axes. Positive scales are relative to the caster dimensions, from 0.001 through 8 per axis. Opacity is 0–1; softness is 0–0.1 of canvas height. Optional `signal` refers to a shared intensity signal. Softness uses a single separable box filter; reflections blur linear premultiplied RGB alongside alpha to avoid transparent-edge darkening. It is an explicit approximation, not a material roughness parameter.

Elevation follows an explicit layer driver's evaluated world anchor y, normalized by canvas height. `rest_y` is its chosen rest anchor, and positive `range` is the displacement that reaches full lift. The clamped lift fraction interpolates offset, scale, softness and opacity from the base values to supplied elevation values. Ground contact compensates for that vertical displacement while retaining the caster's horizontal route and receiver transform. This makes a casket's shadow broaden and fade as it rises. These are authored 2D projections: they do not recover geometry, perspective or material roughness from the painting.

## Export and import a reusable package

```sh
./ambiance --project SOURCE look export --out looks/moonlit-museum
./ambiance --project TARGET look import looks/moonlit-museum --bindings bindings.json --dry-run
./ambiance --project TARGET look import looks/moonlit-museum --bindings bindings.json --expect-sha256 TARGET_SCENE_HASH
```

Export requires a fresh destination and writes `look.json`, `bindings-template.json`, and `report.json`. It preserves the entire finishing configuration, relationship requirements, source layer-art identities and source asset versions. It copies no artwork. The package JSON has `kind: "ambiance-finishing-package"`, `version: 1`, and a canonical payload digest that detects changed contents. Import accepts either the package directory or its `look.json` file.

The binding template has null values to make omissions explicit:

```json
{
  "kind":"ambiance-finishing-bindings","version":1,
  "layers":{"floor":"new-floor","rat":"new-rat"},
  "groups":{},
  "assets":{"soft-mask-v1":"imported-soft-mask-v1"}
}
```

Every required source layer, group and asset ID needs a binding to an existing target ID, even if the name is unchanged. Extra, missing and colliding bindings fail. Relationships include grade targets, cel-signal layers, light receivers/anchors, casters/receivers, and elevation drivers. Signal and effect IDs remain internal to the replaced finishing configuration.

Layer bindings and asset-grade targets may intentionally select different artwork. The package records source identities and reports grade-target substitutions. **Mask/painted-appearance dependencies require the same SHA-256, decoded dimensions and atlas shape** under the destination ID. If one source asset serves both as a grade target and a mask, the mask rule wins. A wrong cel count on a rebound signal layer or a different picture duration incompatible with saved signal keys fails shared-engine validation. Import does not resize masks, retime signals, construct missing groups or guess matching objects.

Import is one ordinary finishing transaction, replacing the target configuration. It checks package/binding bytes and target asset/compiler/source dependencies before saving; export checks its source dependencies again before publishing its immutable directory. Shell-relative input files outside the project are identified as absolute command-input dependencies. Runtime scene references remain catalog IDs. This dependency binding establishes reproducibility and stale-input detection, not authorship or artistic approval.

### Optionally include a production rig

```sh
./ambiance --project SOURCE look export --include-rig --out looks/lantern-rig-v1
./ambiance --project TARGET look import looks/lantern-rig-v1 --bindings rig-bindings.json --include-rig --dry-run
```

The optional `rig` section captures finishing-referenced layer definitions, their attachment ancestors and required group definitions. It preserves layer sockets, motion, authored tracks, cel cadence and phase, normalized placement, and relative paint order. For example, a signal referring to an attached flame includes its mount ancestors; a front-rim layer includes its casket parent. Unreferenced neighbors and descendants are not guessed. Explicit finishing relationships define the roots of the package. Asset-level pivots and sockets, including per-cel ground contacts, are pinned as rig metadata alongside image hash, dimensions and atlas layout.

Import of a package containing a rig **requires `--include-rig`**; omitting the flag fails instead of silently discarding or applying geometry. The target canvas width/height, fps and picture duration must match exactly. Every captured layer/group/asset requires an explicit binding to an existing target. Rig images must match the source image and registration/socket metadata; unlike a look-only grade target, an animated rig asset cannot be substituted with another sequence under this mode.

The import batch replaces those layer/group definitions, restores source-relative paint order among their existing target stack slots, then replaces finishing. Unbound layer definitions and stack slots remain in place. **Source normalized placement and motion are deliberately reinstated**; this is not a keep-world reparent or an automatic placement fit. Target camera settings stay unchanged, so another camera can produce another world appearance. Replacing a group can affect its existing unbound members; the dry-run report names those members. Missing attachment closure, incompatible clocks/assets or an invalid resulting target graph fail the whole transaction.

The package's optional `rig` is version 1 with `canvas: {width,height,fps,loop_seconds}`, `layers` in source paint order and complete `groups`. Its contents and expanded requirements are sealed with the rest of the package. The import report exposes replaced IDs, before/after paint order, restored-placement/cadence flags and the unchanged-camera policy. No artwork, catalog admission, historical review approval or encoded media is transferred. Default export/import remains look-only.

## Typed dependencies, proofs and the independent example

Revision capture and scene authoring include assets used solely as grade targets or masks, even when no visible layer uses them. Mask roles distinguish scene/asset/group/instance grades, lights, shadows and reflections. A changed mask makes affected captured picture evidence stale. Unreferenced drafts and arbitrary strings in metadata are not added by a recursive filename search.

Compiled assets can explicitly declare a hash-bound `edge_preparation` report in their recipe. Its typed provenance includes the actual original source, original byte snapshot, preparation recipe and stored recipe snapshot, and repaired atlas used by the compiler. Scene authoring and revision capture verify that closure through the edge-preparation validator. Catalog provenance must match the compiled pack; neither the word “repaired” in a filename nor a neighboring report is treated as a declaration.

Run the self-contained engineering example into a fresh directory:

```sh
python3 examples/finishing/create_fixture.py --out /tmp/ambiance-finishing-demo
./ambiance --project /tmp/ambiance-finishing-demo preview
```

It uses independent geometric art and public asset/scene/look commands: a creature crosses moonlight, a lamp's four cel intensities drive local bounce, and a rising casket changes its contact shadow while retaining its attached rim. It exports both look-only and rig packages, writes explicit identity `rig-bindings.json`, and dry-runs the rig import. This fixture does not modify a film or supply accepted artwork.

Use `render look-proof` for contextual beauty/bypass/effect comparisons and clipping measurements, and `asset edges` for cell-isolated display-size and magnified matte inspection. `asset edge-repair` writes explicit derivatives; `render ... --supersample 2` or `4` addresses sampling separately. Their [rendering](RENDERING.md) and [edge-quality](EDGE-QUALITY.md) contracts describe artifact recipes and limits. A parameter value cannot substitute for normal-speed review of light continuity, contact and edge quality. `tests/test_finishing_cli.py` exercises package integrity, explicit remapping, atomic rejection, mask-only dependency closure and revision staleness; the renderer tests establish pixel behavior separately.
