# Sprite edge inspection and controlled repair

These tools help identify where edge artifacts enter a production. They produce measured pixel facts, explicit-size comparison images, and deterministic derivatives. They do not guess a matte color, remove an opaque checkerboard, reconstruct fur, or give an artistic pass.

## Inspect the sampled edge

```sh
./ambiance --project /path/to/project asset edges /path/to/pack \
  --display-width 60 --magnify 4 --fps 8 --out /path/to/project/proofs/rat-edges-v1

./ambiance --project /path/to/project asset edges rat-run-v1 \
  --display-width 60 --background /path/to/project/proofs/floor.png \
  --context-rect 510 1240 60 40 --out /path/to/project/proofs/rat-floor-edges-v1
```

`PACK_OR_ID` follows the existing asset lookup: either a prepared-pack directory, or a catalog ID with optional `--catalog`. All explicit command file/directory arguments are shell-relative. Pack/cel integrity is checked before inspection; changed metadata or source bytes during output generation abort publication.

`--display-width` is required. It describes the **whole registered cel**, including transparent padding, in intended output pixels. Height follows the cel aspect ratio, rounded to the nearest pixel. Supply the scene's actual displayed cel width, not its visible silhouette bounds. The report records the exact per-axis cell-to-display scale, source/display alpha statistics, nonzero cel border pixels, and available compiler registration scale/mappings. Legacy packs without a registration mapping report that source scale as unknown. Compiler mapping is recorded metadata; this proof does not claim to show the original raw input pixels.

Every cel is extracted **before** premultiplied-alpha Lanczos resizing. This prevents sampling an adjacent atlas cell and avoids transparent-RGB color halos during the resize. Light/dark and optional context PNGs are saved at exactly the selected size. Magnified PNGs use nearest-neighbor enlargement of those sampled output pixels. They expose the actual samples rather than hiding them behind a second smoothing pass. Paginated contacts retain that resolution; no cels are dropped to fit a sheet.

The HTML viewer provides playback, cel scrubbing, background selection, and 1×/½×/¼× speed. At 100% browser zoom the small image uses one CSS pixel per output pixel. Device pixel ratio and browser zoom remain display conditions, not a physical-phone check. The chosen `--fps` is a **uniform review cadence**; it does not infer the production scene's cel tracks, transform motion, or loop closure.

Context must be explicit. `--background` and `--context-rect X Y W H` are required together. The rectangle uses **unscaled decoded background pixels** and must remain inside the image. Its W/H must equal the displayed cel dimensions exactly. No automatic scene fit, crop enlargement, floor-lighting simulation, or duplicate removal is performed. Use a clean background when the source image already contains the same object. The output includes the untouched context image and a full-context first-cel placement, so the location can be checked.

Proofs support up to 512 cels and limit individual side and aggregate pixel sizes. Reduce display width or magnification if the selected proof exceeds those bounds.

## Derive an explicit repair

```sh
./ambiance --project /path/to/project asset edge-repair /path/to/project/art/rat-sheet.png \
  --recipe /path/to/project/plans/rat-edge-repair.json \
  --out /path/to/project/art/rat-edge-repair-v1
```

Example recipe:

```json
{
  "format": "ambiance-edge-repair",
  "version": 1,
  "layout": {
    "columns": 4,
    "rows": 2,
    "cell_width": 256,
    "cell_height": 256,
    "frame_count": 8
  },
  "alpha": {"feather_px": 0, "choke_px": 0},
  "decontamination": {
    "strength": 0.5,
    "matte_rgb": [238, 238, 238],
    "alpha_floor": 0.00392156862745098,
    "color_space": "srgb"
  },
  "padding_px": 2
}
```

Layout is mandatory, uses row-major order, and must exactly match the decoded still-image sheet. The source must contain actual transparency. Opaque RGB/RGBA pictures are rejected. Unknown fields, nonfinite numbers, invalid geometry, and a nonzero correction without a declared matte are rejected before publishing.

All corrections default to zero, preserving the decoded RGBA pixels exactly, including faint whiskers and RGB beneath zero alpha. No byte-identical PNG encoding is promised; the **original file bytes are separately retained** as `source-original.bin` and their original path/hash are recorded. This makes the original recoverable even when the newly encoded derivative has different compression or metadata.

Operations run separately on every active cel in this order:

1. **Declared matte decontamination:** for partially transparent pixels, recover foreground color using `F = clamp((C - (1-alpha)*matte) / max(alpha, alpha_floor))`, then blend the result with C by `strength`. The declared model is compositing in encoded sRGB. It is suitable only when the source actually matches that matte model. Alpha, opaque RGB, and zero-alpha RGB remain unchanged. There is no inferred contamination detector. A higher floor bounds amplification but changes the correction for very faint pixels.
2. **Transparent padding:** add equal, isolated margins to every cell. New margins contain zero RGBA. Existing hidden RGB is copied intact. Padding changes cell dimensions; the report supplies each raw-cel-to-output-cell translation. Recompile and register the derivative before placing it in a scene. Padding does not alter the current renderer or an accepted atlas in place.
3. **Choke:** opt-in integer-radius minimum filtering erodes alpha against a transparent outside boundary. Radius is 0–8 source pixels. It can erase thin tails or whiskers and should not be a default fix.
4. **Feather:** opt-in Gaussian alpha blur, radius 0–8 source pixels, against transparent outer pixels. Newly visible pixels borrow color from a premultiplied blur of retained paint, avoiding black or stored matte color in newly exposed padding. RGB in previously visible pixels is retained. Feathering can soften or clip the edge; enough authored padding and visual comparison are needed.

All unused sheet slots are copied unchanged with the same padding; they are not accidentally repaired or discarded. The report records before/after alpha facts, changed-RGBA pixel counts, hashes, layout, settings, and explicit limitations. It includes all-cel before/after light/dark proofs and separate viewers with matching proof cadence. The default repair proof width is a bounded diagnostic view, clearly recorded; use `asset edges` on the compiled derivative for the intended production scale.

Outputs are staged off-path, dependencies are rehashed, and the completed directory is published using an atomic **no-replace** rename on macOS or Linux. Existing or concurrently claimed destinations are not overwritten. Other hosts fail with an explicit unsupported-publication message. Neither command modifies or admits an accepted pack or edits a scene.

## Carry preparation provenance into the compiler

To compile a repaired sheet, add an explicit reference to the compiler recipe:

```json
"edge_preparation": {
  "file": "../art/rat-edge-repair-v1/report.json",
  "sha256": "ACTUAL_REPAIR_REPORT_SHA256"
}
```

Like `source_mapping`, this reference is **compiler-recipe-relative** and becomes relative to the saved pack recipe when compiled. The compiler requires this report to identify its exact single sheet input and the same columns/rows/frame count; it never guesses a nearby report filename. The packed recipe and asset provenance both retain the reference. Current compiler version is 1.2.0; changed compiler code gives a new build key and leaves accepted old packs intact.

The repair report's typed `provenance` has `path_base: "report"` and five explicit relative `{file, sha256}` identities: `source`, `recipe`, `original_snapshot`, `recipe_snapshot`, and `atlas`. Snapshot hashes must match the recorded originals. The stored recipe must agree with reported settings, output cell geometry, and decoded output dimensions. The compiler, scene authoring, and revision capture share the same verifier for this chain. They follow only these declared dependencies. A changed authored recipe, raw source, original snapshot, repaired atlas, or report invalidates the chain, including a cached compiler build. Studio scene/revision use additionally requires these paths to stay inside the selected project.

The report also identifies the repair algorithm, Pillow version, and Python version. Keep the report and its declared sources together when moving the project; report-relative identities remain portable. Original absolute paths in diagnostic metadata describe where the operation ran and are not used as dependency resolution rules.

## Diagnose the production path

Compare original raw cels, the compiler output, rendered PNGs, and decoded movie frames at the same intended display size. This command supplies the compiled-cel stage and controlled repairs; scene renders and `media verify` supply the downstream stages. Use source preparation/registration reports to align raw inputs honestly. A clean atlas alone does not prove that a moving sprite or encoded video will look clean.

Hard stair steps, a colored fringe, neighboring-cell bleed, temporal sparkle, and compression artifacts have different causes. Make one bounded variant per suspected cause, inspect the full sequence on light/dark/context backgrounds, then compare a short scene motion proof and the decoded export. Lighting and final grading belong after source-edge diagnosis; grading cannot restore lost detail.

Run the [independent example](../examples/edge-quality/README.md) and `python3 tests/test_edge_quality.py` for repeatable technical evidence.
