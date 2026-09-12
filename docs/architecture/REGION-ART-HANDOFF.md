# Region art workbench handoff

Implementation date: September 11, 2026. The five first-release milestones in the [plan](REGION-ART-WORKBENCH.md) have callable CLI/browser paths. See [usage and boundaries](../ART-REGIONS.md).

## Delivered behavior

- Saved source-space regions with additive/subtractive polygons, soft-mask imports, explicit paint coverage, context padding and tight/square/custom framing.
- Uniform padded exports with exact source mappings; scene-bound density measured through the shared evaluator over every selected output frame and intended view.
- Generation packets containing separate clean references, guides, availability/shape/coverage masks, request drafts and return templates.
- Explicit registered returns retaining high-resolution paint and clipped patches. Fixed compiler geometry and typed region provenance survive admission, source placement and revision capture.
- Local visual editing with rectangle drawing, polygon tracing, vertex movement, pan/zoom, sizing controls, comparisons, undo and recipe export. Draft and CLI rasterization use the same implementation.

Existing crop/return recipes, preparation recipes and source placement semantics are preserved. The legacy mask loop was extracted into a shared helper without changing its rasterization. New scene sizing reuses the source-mapping helper and evaluator instead of implementing a second animation clock.

## Agent-operated evidence

The reusable [public-command replay](../../examples/art-regions/README.md) runs with cleared synthetic art. Two additional local studies use copies of existing paintings; their private source and output files remain in ignored project directories:

| Study | Local project | Exercise |
| --- | --- | --- |
| Ornate window | `projects/region-window-reviewed` | A 21-vertex traced opening in the reading-room painting, filled with a crop of existing nighttime city artwork; source frame and neighboring panes remain separate. |
| Newspaper | `projects/region-newspaper-reviewed` | A seven-vertex non-window region in the tram painting, returned from its own reference to inspect retention, mapping and placement. |

Each saves its exact commands in `reports/replay.json`, the packet in `assets/regions/packet`, returned originals/paint/masks/comparison/receipt in `assets/regions/returned`, the compiled insert, `revisions/region-study`, and actual portrait/landscape raster frames. The study views are explicitly centered on the selected component. They are not proposed replacements for the films' accepted compositions. The existing film projects are unchanged.

The ledger path is exercised with actual local image retrieval and selection, without submitting a paid generation. Packet inspection also recovers its recorded request/output state and next action; a regression test confirms that an existing return is found without submission. Return records the chosen image hash and snapshots the request summary. A first engineering replay caught an incorrect example revision-selection schema; the example now uses the public revision contract.

The final observed window packet is 779×779 for an 80×486 source aperture; the newspaper packet is 537×537 for a 344×260 source region. Both report zero missing-paint pixels and full containment in both study views. `reports/observations.json` identifies the exact viewed artifacts and records the agent’s observations.

The window insert keeps the carved border visible and contains the reused moon/city in both views. Its straight-segment trace and continuity with neighboring scenery remain artistic refinement points. The newspaper has no apparent doubled edge or placement jump at the rendered sizes; it retains existing paint rather than creating detail.

## Browser observations

Observed through the actual local browser UI:

- The traced window and separate square generation-frame overlay are visible over the original painting.
- Increasing context padding from 12 to 24 source pixels changes the reference from 779×779 to 816×816 while retaining 1.53 export pixels per source pixel. Undo restores 779×779.
- An oversized padding request is rejected; the prior preview and applied fields remain intact.
- Dragging a rectangle adds a second four-vertex outline, and undo removes it.
- A narrow 493-pixel browser window initially exposed a canvas-driven horizontal overflow. The responsive grid fix keeps the body at 493 pixels and the painting inside its scrollable pane.

The HTTP regression separately compares the browser draft's decoded mask bytes with a CLI build of the same exported recipe. It also verifies origin/path boundaries and that draft evaluation leaves saved artifacts unchanged. The browser viewport previews are reduced for inspection; full-resolution masks and paint remain available on disk.

## Validation status

Eleven focused Python region tests and the six-case shared-transform sizing check pass. The first full suite passed all engine, rig, view, source-placement and package checks; two existing HTTP tests could not bind localhost under the default sandbox. Final `./ambiance test` verification with localhost access passed every check: 327 Python tests ran, with 13 opt-in native-media cases skipped, plus the engine, rig, activity, binding, finishing, source-placement, track, view, package and failure-contract checks. The source-integrity check also passed. Native encoding was not changed by this feature. Exact JSON/JUnit evidence is retained locally at `projects/region-window-workbench/reports/validation/`.

The final browser demonstration is `projects/region-window-workbench`; its PNGs are byte-identical to the inspected window study, and its observation record binds its own receipts. Packet inspection finds its selected ledger output. A copied-project relocation check passed `asset inspect` and `revision check` in a fresh directory. `revision handoff` also produced the expected exact-path report with `release_ready: false`, since this study is not a finished film.

## Limits

These are static component studies. No animated clip engine, automatic segmentation, Bezier/freehand tool, learned registration, perspective warp, expanded-stage outpainting or provider submission was added. The packet may guide an image tool; exact fit comes from local masking and explicit registration.

Visible paint integration remains an artistic observation. Reusing another painting establishes the region/return path, not a promise that its palette, perspective or neighboring scenery matches. No human review, phone review, encoded-film acceptance or measured production speedup is claimed.
