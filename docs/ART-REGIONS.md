# Prepare artwork for a traced region

`asset region` prepares a rectangular reference, exact shape masks, output-size guidance and a registered return for an irregular part of a painting. It works before replacement artwork exists. The visible opening, extra paint and surrounding reference are kept separate. The first release creates still inserts and reusable paint/masks for later animation.

## CLI workflow

All command paths are shell-relative; saved references are project-relative. Every output directory must be fresh. Source images are preserved. Initialize with a half-open pixel-edge rectangle or start empty and author polygons:

```sh
./ambiance --project PROJECT asset region init PROJECT/assets/raw/source.png \
  --id window --rect 100 80 240 420 --out PROJECT/assets/regions/draft
./ambiance --project PROJECT asset region inspect PROJECT/assets/regions/draft
./ambiance --project PROJECT asset region edit PROJECT/assets/regions/draft \
  --batch edits.json --expect-sha256 HASH_FROM_INSPECT --out PROJECT/assets/regions/edited
./ambiance --project PROJECT asset region check PROJECT/assets/regions/edited
./ambiance --project PROJECT asset region build PROJECT/assets/regions/edited \
  --out PROJECT/assets/regions/packet
./ambiance preview --region PROJECT/assets/regions/packet --port 8799
```

Add `--base LAYER` to initialization to derive output demand from an existing, source-mapped one-cell scene layer. All intended views are selected by default; repeated `--view` arguments must still cover the complete intended set. The initializer records scene, catalog and project/production-scope identities. An unbound draft uses a labeled native-density assumption until given `sizing.display_size`.

An edit batch is version 1 with 1–64 operations, each `{ "op": NAME, "value": VALUE }`. Supported operations are `set-visible-mask`, `append-polygon`, `set-coverage`, `set-frame`, `set-sizing`, `set-context` and `set-intent`. The `set-*` operations replace their complete field group; copy current values from `recipe.json` before editing. Failed batches leave the prior checkpoint intact.

Example frame and shape edits:

```json
{
  "version": 1,
  "operations": [
    {"op": "set-frame", "value": {
      "aspect": "square", "padding": [12, 12, 12, 12], "rect_xyxy": null
    }},
    {"op": "append-polygon", "value": {
      "operation": "subtract", "points": [[160,80],[168,80],[168,419],[160,419]]
    }}
  ]
}
```

`build` also accepts a directly authored or browser-exported recipe file. `inspect` returns saved dimensions, issues, exact preview paths and working inputs that have changed. For packets and returns, it also looks up the associated generation request, existing returned files and next recovery action so reopening a packet does not suggest a duplicate submission. `check` recalculates the current contract and exits nonzero for incomplete or below-target sizing unless an explicit study is allowed. Framing observations remain issues to inspect rather than automatic artistic failures.

## Contract and sizing

The saved format is `ambiance-art-region`, version 1. Initialize instead of inventing source hashes.

| Group | Fields and behavior |
| --- | --- |
| `visible_mask` | Ordered `polygons` with `add`/`subtract` operations; optional `image` identity for an imported grayscale `L` mask at full source size. Vertices use source pixel centers, as in preparation recipes. Holes and disconnected panes are supported. |
| `paint_coverage` | `bleed: [left,top,right,bottom]` in source pixels, and optional `reveal_xyxy`. With no extension, coverage follows the mask; extensions produce a rectangular required paint envelope. Required paint stays inside the source. |
| `frame` | `aspect: "tight"`, `"square"`, or `[width,height]`; `padding: [left,top,right,bottom]`; optional explicit `rect_xyxy`. An explicit frame must retain requested paint and context and respect the aspect lock. |
| `sizing` | `mode: "manual"` or `"scene"`, optional `display_size`, `quality_multiplier` (default 1.5), optional `export_size`, caller-supplied `allowed_sizes`, and explicit `allow_under_target`. |
| `intent` | `brief`, `preserve`, and optional `asset_id`. No semantic segmentation is inferred from these words. |
| `context` | Optional source-mapped `base`, `views`, `start_frame`, `frames`, and project-relative `{file,sha256}` identities for `scene`, `catalog`, and `scope`. `scope` is the canonical production plan when present, otherwise project settings. |
| `raster` | `supersample: 1/2/4` for vector masks and `resampling: "nearest"/"bicubic"` for images. Imported alpha retains its source detail. Legacy preparation rasterization is unchanged. |

Scene sizing samples every output-frame time in the declared interval through the shared renderer evaluator. It uses the largest directional scale from source pixels to output pixels across all intended views, then applies the explicit quality multiplier. Reports identify the demanding view/frame and whether each view contains or crops the region. The view pictures show the source plane at its demand peak; they are not full-scene renders.

Manual display dimensions are assumptions. Neither a larger pixel grid nor a successful check establishes new detail in old artwork. Returned-image density is checked separately from the resampled output-grid density.

Squaring or fitting a different allowed aspect expands the frame uniformly; it never stretches the source. If context extends past a source edge, transparent padding and `source-availability.png` identify the missing reference. Increasing context also increases required export size so the region retains its detail. Automatic expanded-stage outpainting is not implemented.

Source and export sides are limited to 4092 pixels, source/export area to 8,388,608 pixels, and supersampled mask area to 64M pixels. This reserves two compiler-padding pixels on each side. A larger requirement fails explicitly. Without caller-supplied allowed sizes, provider compatibility remains unchecked; the tool contains no hardcoded provider size menu.

## Packet and return

A packet contains the source/recipe snapshots, clean `reference.png`, separate `guide.png`, native/export masks, source-availability mask, contextual and isolated previews, `sizing.json`, `region-manifest.json`, `prompt.md`, `request-draft.json`, `return-template.json` and a hash receipt. Reference images have no guide strokes. The request draft is compatible with the [generation ledger](PROVIDERS.md); supply actual tool settings and record it before a separately authorized generation. Building a packet never submits a provider request.

After selecting existing or returned artwork, copy the return template and author its alignment:

```json
{
  "format": "ambiance-region-return",
  "version": 1,
  "packet_manifest_sha256": "COPY_FROM_TEMPLATE",
  "expected_edit_size": [1024,1024],
  "registration": {
    "edit_to_export": [1,0,0,1,-8,0],
    "note": "Inspected the return; its architectural landmarks shifted eight export pixels right."
  },
  "request_id": null
}
```

Expected dimensions must match the actual return. An identity matrix requires the same explicit inspection as any other registration. `edit_to_export` uses `[a,b,c,d,e,f]`: `x'=a*x+c*y+e`, `y'=b*x+d*y+f`. Perspective warping is not included. If supplied, `request_id` must identify a ledger entry containing the actual returned image; a request summary is captured with the derivative.

```sh
./ambiance --project PROJECT asset region return PROJECT/assets/regions/packet \
  PROJECT/assets/raw/returned.png --recipe alignment.json --out PROJECT/assets/regions/result
./ambiance --project PROJECT asset build PROJECT/assets/regions/result/compiler.json \
  --out PROJECT/assets/production/window-v1
./ambiance --project PROJECT asset admit PROJECT/assets/production/window-v1
```

The result preserves `returned-original.bin`, high-resolution `paint.png`, aperture-clipped `patch.png`, masks, a native-size `composite.png`, missing-paint and edge previews, source mapping and compiler recipe. The original returned bytes remain intact regardless of their extension. The composite is an inspection derivative; the high-resolution mapped patch is the production input. Missing/transparent paint inside required coverage remains explicit even when original pixels beneath it make the composite look complete.

Compile with the generated fixed geometry. The typed `region_receipt` pins packet, source, masks, return and registration dependencies for compilation, admission, scene transactions and revision/package capture. Source placement uses the existing [mapped placement](ASSET-PREPARATION.md) and `scene place` contract. Return does not mutate the scene. Successful compilation is not artistic approval.

Scene-bound building/returning requires current source and context identities. After editing a working scene or its views, explicitly refresh the context in a new checkpoint. Existing result assets retain captured scene/catalog/scope bytes so later scene edits do not invalidate historical asset sizing. Art and mask changes remain dependency changes.

## Visual workbench

`preview --region` serves a draft, packet or returned artifact on localhost. It supports rectangle drawing, polygon add/subtract, vertex movement, pan/zoom, aspect and padding controls, manual dimensions, source-plane view previews, undo, JSON editing and recipe export. Returned artifacts also show the saved paint/composite/missing-coverage comparison. Preview images are capped at 1200 pixels per side; full-resolution artifacts remain on disk.

Browser changes stay in memory and use the CLI raster evaluator over captured inputs. Export the applied recipe and build a fresh packet to save it. Unapplied fields and unfinished points are excluded. Rejected edits preserve the previous valid preview. Runtime changes require rebuilding before live draft editing.

Static patch alpha moves with its image. For scenery moving behind a fixed window, retain the uncut paint and use an explicit independent foreground/occluder setup and motion proofs. This tool does not add a general animated clipping engine, automatic tracing, freehand/Bezier editing, or automatic registration.

See the [public CLI replay](../examples/art-regions/README.md) and [implementation evidence](architecture/REGION-ART-HANDOFF.md).
