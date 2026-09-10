# Rig workbench — from repeated adjustments to reusable rules

Version 0.3.0 introduces working tools for cel registration, named attachments, and loop inspection. The originals and the finished film are preserved. The new default scene is a rigged variation of the placement study.

## Try it in five minutes

From the studio folder, run `python3 kit.py serve` and open `http://127.0.0.1:8781/editor/`.

1. Select **Cottage**. Change its position, rotation, or scale. The smoke follows the chimney. Select **Town** and the window overlay follows it. Reset the study afterward.
2. Turn on **Sockets**. Select a parent layer, enter a socket name, click **Place socket**, then click the desired point in the painting. Select a child layer and choose that named attachment. Its anchor snaps to the socket. The child's position fields become local offsets.
3. Click **Check all frames**. The workbench checks all 480 samples, attachment coordinates, declared background coverage, and actual composite alpha at 135 × 240. It compares the final-to-first image change with ordinary adjacent changes. **Preview the join** starts playback one second before wraparound. It continues playing until paused.
4. **Export scene** exposes copyable JSON and a download link. Load that JSON to resume. No edits are saved to disk automatically. Reset restores the bundled example. The report also exposes its exact scene snapshot as copyable JSON; edits invalidate its displayed freshness.

Depth groups still help move a house and its surrounding ground together. Sockets serve a different purpose: a child follows one object, including that object's rotation, scale, visibility, opacity, and inherited camera movement. Keep paint order separate: smoke may be drawn behind the house while remaining its child.

## Prepare an asset once

The asset compiler requires Python with Pillow; the stage itself needs no Python image packages. The tested dependency is in `requirements-assets.txt`. Install it into a project virtual environment if needed.

```sh
python3 tools/asset_tool.py build assets/recipes/smoke-v1.json --out assets/compiled/smoke-v1
python3 tools/asset_tool.py admit assets/compiled/smoke-v1 --catalog assets/catalog.json
```

The included pack already exists; an identical build returns **cached**. Changed inputs, compiler code, Pillow version, settings, or output bytes require a new output directory. `admit` makes an asset available in a catalog and protects existing IDs; it does **not** pass an artistic or library quality gate. Reload the editor after catalog changes.

For a new pack, copy the recipe, use a new asset ID and output directory, and supply either an exact input grid or an explicitly ordered list of PNG frames. Three registration modes are implemented:

| Mode | What the operator supplies | Appropriate use |
| --- | --- | --- |
| `fixed` | One source-pixel `point` shared by every cel | Already aligned source canvases; preserve existing registration |
| `landmarks` | One source-pixel entry in `points` for each cel | A known base, hinge, or stable architectural feature that shifted between drawings |
| `bottom-center` | Alpha threshold and destination pivot | A first estimate for a simple upright silhouette; review it before acceptance |

All modes require a normalized destination `target`. The compiler calculates **one scale for the whole sequence**, fits all nonzero alpha into padded fixed cells, and resamples premultiplied color. It preserves intentional size variation. Bottom-center follows a bounding box, so changing wisps or asymmetry can move the estimate; it is not feature tracking. Use explicit landmarks when the estimate is wrong.

Outputs: `atlas.png`, runtime-compatible `asset.json`, portable `recipe.json`, `report.json`, a light/dark `contact-sheet.png`, and `preview.gif`. The report records input hashes, per-frame content bounds, source and destination pivots, translations, shared scale, output hashes, and warnings. The catalog's `provenance.sources` paths are relative to its referenced recipe. Keep the source tree with the pack if you want to rebuild it; the atlas itself can render independently.

The included smoke pack demonstrates the compiler, not a newly improved production selection. Inspection found cut-off wisps in some **source** cells, which remain visible in its proof. The compiler reports edge contact and does not invent missing artwork. The default scene continues to use the original smoke artwork. Repairing those wisps is a separate asset revision.

## Run checks without opening the editor

```sh
node tools/check-scene.mjs scenes/last-lantern-rigged.json --out reports/rig-check.json
python3 kit.py check scenes/last-lantern-rigged.json
python3 tests/test_assets.py
node tests/test-rig.mjs
```

The Node command accepts `--catalog path/to/assets/catalog.json` for another library; asset files are relative to the directory above `assets`. It records the actual scene/catalog/engine/audit hashes and verifies referenced asset bytes. It samples every output frame, validates the graph, rejects cycles or missing sockets, and measures attachment and geometric coverage errors. It does not decode raster alpha or encode a video. The browser's separate pixel check uses decoded images.

A declared `coverage_layers` entry should be a plate intended to cover the **entire** canvas at every time. Do not put partial hills or foreground cutouts in that list. A transparent or hidden sky can still look plausible over the canvas fill; the pixel check clears that fill to detect the gap.

## What is still manual

Choosing a correct chimney point, judging style/edge quality, repairing fake transparency or clipped artwork, and judging the closing gesture need inspection. Per-cel socket tracks can follow a changing feature, but their coordinates must be authored in JSON. The UI places static sockets; it does not yet provide a landmark table, onion-skin editor, or automatic tracking.

This is a working rig and asset compiler, not the complete production renderer. Final video export, the remaining full-film effects, and the audio arrangement are separate stages. Browser reports are evidence to attach to a review; they do not automatically close any studio gate.
