# Tool choices and the next engineering investments

> Historical design record from the initial studio passes. For current executable capabilities and engineering direction, use [CLI](CLI.md), [studio library](STUDIO-LIBRARY.md), and [architecture](architecture/CLI-FIRST.md). The future-work lists below are retained as history.

The most valuable change is to make the artistic relationship explicit: “this plume attaches to the chimney” becomes data the renderer preserves. A coordinate grid helps place the first point; a socket removes the need to repeat that placement after each parent edit. Similarly, a registration recipe replaces a series of one-off image adjustments.

## Own a small, portable core

Use PNG artwork, JSON recipes/catalogs, a deterministic scene evaluator, and replaceable provider adapters. These are our design choices, based on the needs of this studio. The v0.3 compiler and rig implement the first part. Build artifacts retain source/recipe hashes so later work can reuse accepted versions without relying on the chat history.

Existing tools remain useful at the edges. Official documentation checked September 10, 2026; these options were researched, not purchased, installed, or benchmarked in this task.

| Tool | Useful existing capability | Decision for this studio |
| --- | --- | --- |
| Aseprite | Named slices can carry pivots and export metadata; the CLI supports batch export of sheets and JSON. [Slices](https://www.aseprite.org/docs/slices/), [CLI](https://www.aseprite.org/docs/cli/) | Optional artist-facing cel correction and pivot authoring. Add an importer when we actually receive Aseprite assets; no importer is implemented yet. |
| TexturePacker | Atlas export can retain trimmed source rectangles and pivot coordinates. [Exporter metadata](https://www.codeandweb.com/texturepacker/documentation/custom-exporter) | Consider when texture memory and many packs become a measured issue. Keep fixed cells now; packing cannot determine the correct semantic anchor. |
| PixiJS | Containers provide hierarchical transforms and scene organization. [Container guide](https://pixijs.com/8.x/guides/components/scene-objects/container) | Candidate rendering backend if profiling shows a Canvas2D bottleneck. Preserve our scene contract and compare rendered frames before switching. |
| Spine | Dedicated skeletal-animation authoring and runtimes. [Runtimes](https://esotericsoftware.com/spine-runtimes) | Revisit for articulated characters or complex deformation. Our immediate task is painted cards and cels, so we have not adopted it. |
| Python + Pillow | Current local compiler decodes, measures, registers, resamples and packs images. | Implemented and exercised on deliberate displacement fixtures and the existing smoke pack. |
| Existing Canvas2D engine | Current studio now owns attachments, absolute-time sampling, and a browser raster check. | Continue with the working evaluator while adding missing production capabilities. |

## What to automate and what to judge

| Repeated work | Implemented in v0.3 | Remaining judgment |
| --- | --- | --- |
| Cut a known grid into cels | Recipe-driven extraction | Identify the correct grid and remove labels or matte contamination first |
| Align cels | Shared scale, fixed pivot or per-cel landmarks; silhouette estimate available | Select a stable feature and distinguish drawing deformation from unwanted drift |
| Keep elements attached | Named static or cel-specific sockets; nested attachments | Choose the right object, socket, and occlusion order |
| Check all times | Every frame sampled; graph, attachment, coverage and preview seam diagnostics | Judge small edge defects, style consistency and the closing gesture |
| Avoid rebuilding unchanged work | Hash-checked asset cache and protected IDs | Decide which version belongs in the accepted library |
| Make another film | Skills, project records, gates, reusable recipes and asset IDs | Produce new art, compose the scene and review its sound story |

## Build next in this order

1. **Landmark and registration panel.** Let an operator step through cels, overlay neighboring drawings, and click a feature once per cel where needed. Show light/dark mattes, displacement arrows and the effect of a common scale. Export the same compiler recipe and socket tracks. Acceptance: recover known fixture displacements, preserve deliberate deformation, and complete a second real pack without ad hoc image code.
2. **One evaluator for preview and final rendering.** Port the missing glow, mist, particles and leaves, add exact-frame export and encoded-media checks, then compare against the accepted film. A live preview alone is insufficient. Acceptance: any frame can be rendered directly; preview/final differences are documented; the actual media passes frame-count and join review.
3. **Reusable rig modules and project loading.** Package “cottage + sockets + lights + smoke” as a versioned module, with attachment names, compatible asset roles, placement presets and a preview. Add project selection, undo/autosave and a discoverable library. The current editor still opens one bundled catalog and supports JSON scene loading.
4. **Audio arrangement and durable jobs.** Preserve separate stems, circular tails and the sound story. Record provider job IDs, generation outcomes, costs and retries before adding a render queue. Paid generation should not happen in local tests.
5. **A second operator, a second scene, then batches.** Give the sister pilot a different reference image and this folder. Measure preparation time, landmark corrections, reuse, review rounds, final quality and interruptions. Only then estimate throughput or a percentage speedup.

The new compiler removes repeated mechanical work; it does not make ambiguous artwork effortless. We have functional tests and a real existing-scene demonstration, but no measured end-to-end time saving, independent operator pilot, or multi-film scale test yet.
