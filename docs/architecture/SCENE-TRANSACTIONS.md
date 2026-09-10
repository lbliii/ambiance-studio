# Scene transactions and authored tracks

A transaction makes a complete scene change reviewable before it is saved. The Python CLI acquires the project lock, checks an optional expected scene hash, and preserves the previous scene before replacing it. `tools/scene-command.mjs` edits a private JSON copy and validates the result with the same `editor/engine.mjs` used in preview and rendering. A rejected operation or final graph produces an error and no candidate scene.

## Batch contract

```json
{
  "version": 1,
  "operations": [
    {"op": "socket", "layer": "casket", "name": "bed", "value": [0.5, 0.5]},
    {"op": "attach", "layer": "mummy", "to": "casket", "socket": "bed"},
    {"op": "order", "layers": ["room", "casket", "mummy", "front-rim", "fixed-glass"]}
  ]
}
```

The bridge receives `{"action":"apply","scene":...,"catalog":...,"args":{"batch":...}}` and returns `{"ok":true,"data":<complete scene>}`. Opting into `args.report: true` instead returns `data: {scene, operations}`; `operations` contains geometry diagnostics from placement/reparent operations, not a second copy of every requested edit. `inspect` with `args.full: true` returns the whole editable scene, including groups, camera, coverage and metadata. The default inspect summary remains compatible.

Operations run in listed order. Graph validation runs on the final result, so a child can attach to a parent added later in the same batch. Targets being edited must already exist. Unknown operation and authored-field names fail, rather than accepting a misspelled setting silently.

Source placement and preserve-world reparenting additionally evaluate geometry at their operation point. All their dependencies and a valid scene graph must therefore exist at that prefix of the batch. Put them after ordinary structural edits resolve any forward references. Any failure discards the whole candidate; no partial prefix is saved.

| Operation | Fields and behavior |
| --- | --- |
| `add` | `asset`, `id`, optional `values`. Creates an instance with default pivot, aspect ratio, and timing, then applies the supplied layer fields. New ID must be unique. Grouped/attached values omit independent depth. |
| `set` | `layer`, `values`, optional `unset`. Updates authored fields. `unset` can remove optional `depth`, `group`, `attach`, `sockets`, `cycle_seconds`, `phase_frames`, `motion`, `tracks`, or `track_loop`. A field cannot be set and unset together. |
| `replace` | `layer`, `value`. Supplies a complete valid replacement layer with the same ID. |
| `remove` | `layer`, optional `cascade: true`. By default, attached descendants block removal; reparent/detach them first. Cascade explicitly deletes the subtree. Coverage references must be removed with an earlier `coverage` operation. |
| `order` | `layers`: every resulting layer ID exactly once, back to front. Does not change depth or parenting. |
| `group` | `id`, `value`: complete group fields excluding ID (`x`, `y`, `scale`, `depth`, `pivot`, optional `name`). Creates/replaces a group. `value: null` removes it; surviving references must be fixed in the batch. |
| `camera` | `values`: a partial update of `overscan`, `x_amplitude`, `y_amplitude`, `zoom_amplitude`. |
| `socket` | `layer`, `name`, `value`: `[u,v]` or `{"frames":[[u,v],...]}`. `null` removes the layer override, allowing an asset-level socket of the same name to apply again. Exactly one coordinate pair per source cel is required for a track. |
| `attach` | `layer`, `to`, `socket`, optional `offset_x`, `offset_y`. Assigns the parent, clears independent group/depth and sets local offsets (default zero). Other authored motion remains. |
| `place_from_source` | `id`, `asset`, `base`, `mode`, hash-bound `reference`, optional mappings, source anchor/size, layer anchor, paint-order target and appearance/timing `values`. Derives reference placement and adds a named socket plus attached layer. See the [placement contract](../SOURCE-PLACEMENT.md). |
| `reparent` | `layer`, `to`, `socket`, `preserve: "world_at_time"`, finite `at_seconds`. Solves and verifies new local base fields and effective appearance for the sampled pose. Cel clocks and paint order remain; child transform tracks fail. |
| `coverage` | `layers`: unique IDs of plates intended to cover the whole canvas. Allows an explicit coverage change during a deletion or replacement. |

Layer values expose `name`, `asset`, `x`, `y`, `width`, `height`, `anchor`, `scale`, `rotation` (radians), `opacity`, `visible`, `blend`, `depth`, `group`, `attach`, `sockets`, `cycle_seconds`, `phase_frames`, `motion`, `tracks` and `track_loop`. Existing one-operation CLI commands remain compatible. Use a batch to change structural fields together—for example, unset `attach` while setting an independent `depth` and world position. Detachment does not reconstruct world coordinates automatically.

## Movement design

[The scene contract](../SCENE-CONTRACT.md#authored-keyframe-tracks-v04-extension-to-scene-version-1) defines tracks. They are absolute values sampled at absolute time, with no simulation history or playback-dependent state. Holds and repeated values provide pauses; scheduled source cels can hold an idle pose or select run frames. Existing periodic motion remains additive.

A near rat and a distant rat should usually be two separately authored instances with their own route, size, cadence and fixed paint order. Put the distant pass behind the arch or pedestal cutout; put the near pass behind the selected foreground obstruction. Hide each instance before its reset. This preserves explicit painted overlaps and does not pretend that a depth number provides collision, occlusion or path finding.

A moving casket can parent the body and front rim through sockets, while the hand attaches to the body. Place the front rim after the body in paint order. Keep display glass and stationary floor shadows independent. The evaluator supports these transforms; it cannot supply missing backing art, judge a physical pivot, or certify that glass/reflections were correctly separated.

## Examples and checks

[The rat batch](../../examples/scene-transactions/rat-route-batch.json) demonstrates two routes, visibility windows and scheduled run cels. [The casket batch](../../examples/scene-transactions/casket-rig-batch.json) demonstrates nested movement with independent front-to-back painting. Both are **four-second geometric fixtures**, use the placeholder catalog IDs `paint` (one image) and `gait` (four-cel atlas), and expect an empty scene. They are not replacements for the accepted museum artwork. Supply prepared assets and the intended picture duration when adapting them.

Run `node tests/test-tracks.mjs` for deterministic interpolation, hidden-reset rejection, scheduled socket sampling, operation validation, nested overlap ordering and saved-example checks. Existing rig tests still cover all-frame attachment and camera behavior. Browser inspection and rendered normal-speed proof remain necessary: matrix tests cannot establish that an overlap or seam looks correct.

The [source-placement fixture generator](../../examples/source-placement/create_fixture.py) compiles independent geometric art and saves actual placement/reparent output for browser inspection. `tests/test-source-placement.mjs` verifies source geometry, exact-time inheritance, additive-motion rebasing and [timing reports](../SCENE-TIMING.md); `tests/test_scene_authoring.py` verifies compiler linkage and pre-save dependency changes. Source manifests run through `ambiance_studio/scene_authoring.py` before the bridge, and the CLI rechecks those pinned dependencies before replacing the scene. Direct bridge calls alone do not validate file identities.
