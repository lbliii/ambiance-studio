# Preparing one movable part

The preparation workbench brings source paint, replacement backing, three separate masks, alignment and a movement proof into one local workspace. It uses existing images; it does not generate missing paint or infer an object boundary.

## Agent operation

The agent's primary interface is the saved JSON recipe and `asset prepare`. Author or revise masks, the backing affine and proof motion directly in that recipe, then build into a fresh directory. Read the command's facts, warnings and artifact paths, inspect the resulting PNGs, and use the existing render commands for rest, movement and hidden-part proofs. This path requires no browser session or recipe download.

Localhost is the observation and optional visual-editing surface over the same operation. It helps the human judge the prepared parts and movement; the agent may also use it when computer-driven visual inspection is useful. The [agent operation pass](AGENT-PREPARATION.md) adds dedicated inspect/check/edit/build/proof/place commands, compound cutouts and shared backing/companion dependencies. The legacy browser remains a one-part draft workbench.

## Start and rebuild

From an initialized project, provide a source painting and replacement backing already inside that project:

```sh
./ambiance --project PROJECT asset prepare PROJECT/assets/raw/source.png \
  --backing PROJECT/assets/raw/backing.png --out PROJECT/assets/prepared/part-v1
./ambiance preview --prepare PROJECT/assets/prepared/part-v1 --port 8785
```

The first command writes `recipe.json` for direct agent editing and rebuilding with `--recipe`. The second command optionally opens the observation/editing surface at the returned local address. The initial masks are empty and the alignment starts at the explicit identity matrix, unless supplied through `--backing-to-source A B C D E F`. This is a starting draft; inspect the registered backing before choosing a replacement region. Empty masks create a usable workspace with warnings, not a prepared object. Preserve the generated artifact; save recipe changes to a separate working file before rebuilding.

Choose a mask, click around a source-image region, and close the polygon. Add and subtract regions, undo an applied edit, or clear the selected mask's polygons. Inspect the cutout on dark, light and checker backgrounds. An existing grayscale mask can supply soft alpha beneath polygon edits. Clearing polygons preserves that imported base mask.

- **Removal:** where backing paint replaces the old painted object and its remnants.
- **Cutout:** the original paint retained on the moving part, excluding neighboring fixtures.
- **Occluder:** original foreground paint that stays above the moving part.

Alignment controls expose the backing-to-source affine. Movement controls expose a source-pixel pivot, translation, rotation and duration. The preview holds at rest, moves to the maximum halfway through its period and returns to rest. The fixed foreground remains independent. Use the object-hidden view to find old paint in the backing, and foreground-hidden view to inspect overlaps. This is a standalone three-layer proof, not a modification of an existing film's rig.

**Export recipe** downloads the currently applied recipe as JSON through the local server. Unapplied numeric fields and unfinished polygon vertices are not exported. The same JSON is available under **Recipe and rebuild**. Browser edits never save over project files. Rebuild a new version explicitly:

```sh
./ambiance --project PROJECT asset prepare --recipe preparation-recipe.json \
  --out PROJECT/assets/prepared/part-v2
```

Input and output command paths are shell-relative. References inside the recipe are project-relative, with exact image hashes and decoded dimensions. Altered inputs fail before publication. Occupied destinations are rejected, including concurrent claims. The complete output is staged and atomically published using the existing macOS/Linux preparation helper.

## Recipe contract

The version-1 document uses `format: "ambiance-asset-preparation"`, `version: 1`, `path_base: "project"`, a `title`, `source`, `backing`, `backing_to_source`, `resampling`, `masks` and `motion`. Start from the generated recipe rather than inventing hashes.

Each image identity is `{ "file": "assets/raw/source.png", "sha256": "ACTUAL_HASH", "width": 384, "height": 512 }`. Inputs are still images, no larger than 4096 pixels per side or 8,388,608 pixels each. They are treated as sRGB; there is no automatic ICC conversion. Imported masks must be grayscale `L` images with the full source dimensions.

The affine is `[a,b,c,d,e,f]`, mapping backing pixels to source pixels: `x' = a*x + c*y + e`, `y' = b*x + d*y + f`. It must be finite and invertible. `nearest` and `bicubic` use the existing premultiplied-alpha resampler. Cropped/enlarged backing can be aligned with this transform; use the existing [crop/return workflow](ASSET-PREPARATION.md) to establish its source mapping.

Each of the three required masks has `polygons: []` and an optional `image` identity. Polygons are ordered `{ "operation": "add" or "subtract", "points": [[x,y], ...] }` records. Vertices use source **pixel centers**, within `[0, width−1] × [0, height−1]`; they round to the nearest integer with halves rounded up. Pillow fills polygon boundaries inclusively. This differs from the crop workflow's half-open pixel-edge rectangles. Add fills alpha 255; subtract sets alpha 0. Existing soft-mask pixels outside these regions remain intact. Limits: 128 polygons per mask, 3–512 vertices each, and 8192 vertices overall.

`motion` contains `pivot: [x,y]`, `delta: [dx,dy]`, `rotation_degrees` and `seconds`. The loop is 1–30 seconds at 30 fps with an even whole frame count, so its midpoint maximum lands on an output frame. The generated scene authors closed smoothstep tracks. The browser and existing CLI renderer evaluate those tracks through `editor/engine.mjs`; preparation does not introduce another animation evaluator.

## Saved results

Each artifact contains:

- The exact recipe, byte-preserved source/mask snapshots, and an identity receipt.
- Full source-sized PNGs: registered backing, repaired background, cutout, fixed foreground, three masks, assembled rest and changed-pixel overlay.
- `compiler/*.json` recipes and source mappings. Full source canvases preserve alignment when a mask changes; alpha bounds never redefine the origin. Compiler padding is normally two pixels; sources at the 4096 limit are scaled to fit the compiler's cell limit with its recorded mapping.
- `preview-project/`: a render-only scene/catalog using the exact prepared parts.
- Captured browser UI and shared renderer modules.

```sh
./ambiance asset build PROJECT/assets/prepared/part-v2/compiler/cutout.json \
  --out PROJECT/assets/production/cutout-v2
./ambiance --project PROJECT/assets/prepared/part-v2/preview-project render frame \
  --time 2 --out PROJECT/proofs/part-v2-maximum
./ambiance --project PROJECT/assets/prepared/part-v2/preview-project render video \
  --out PROJECT/proofs/part-v2-movie
```

Empty parts cannot be compiled into useful packs. Admission and placement in the production scene remain deliberate existing CLI operations. The source mapping pins the original painting and derivative; it does not extend the compiler/revision dependency schema to every separation input. Preserve the complete preparation artifact for the backing, masks and recipe provenance, and explicitly include that evidence when capturing a production revision.

The local preview verifies all receipt-listed bytes and evaluates draft edits from captured source bytes in memory. Later changes to working sources do not alter that captured workspace. Different source/mask identities require a fresh CLI build. Live editing also checks the preparation module and Pillow versions against the receipt; rebuild the artifact after updating those implementations. A single preview calculation runs at a time. The service binds to loopback, restricts paths and origins, and performs no project writes or provider calls.

## What the numbers establish

Changed-rest pixels compare Pillow's prepared assembly with the original source. The other counts flag cutout pixels outside removal and removal regions lacking opaque backing. These are useful inspection prompts, not automatic mask or artistic verdicts.

Saved and live mask rasters use exactly the same Pillow implementation. Browser Canvas and native Canvas render the scene separately; their sampling and antialiasing can differ at edges, even at identity size. The changed-pixel overlay is a preparation diagnostic, not a browser/native parity certificate. Inspect actual rendered movement and encoded frames as well.

The [independent fixture](../examples/preparation-workbench/README.md) exercises this workflow with synthetic art. A measured pilot on a different painting remains the next production milestone; no preparation speedup or artistic acceptance is claimed from this fixture.
