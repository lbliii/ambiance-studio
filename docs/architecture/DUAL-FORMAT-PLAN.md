# Portrait and landscape from one production

Analysis and proposal, September 11, 2026. This document proposes an extension; the commands and view contract below are not implemented. Existing project scenes and accepted deliveries were left unchanged.

The user subsequently delegated the approach choice and implementation planning. The selected architecture, concrete contracts, milestone order and acceptance criteria are now recorded in the [implementation plan](DUAL-FORMAT-IMPLEMENTATION.md). This analysis remains the rationale; the implementation plan takes precedence where it narrows or settles an earlier option.

The recommended product is one scene, one animation clock, shared artwork and sound, and two named views produced by the same iteration. Plan and inspect both compositions from the beginning. Begin with static framing; add limited layout overrides only where a crop cannot preserve the intended subject and action.

The intended outputs are portrait 9:16 at 1080 × 1920 and landscape 16:9 at 1920 × 1080. These have equal pixel counts. YouTube documents 16:9 desktop video and 1920 × 1080 in its [aspect-ratio guide](https://support.google.com/youtube/answer/6375112?hl=en); TikTok's [creative checklist](https://ads.tiktok.com/business/library/Top_Tips_One_Pager_SMB.pdf) describes full-screen 9:16. These are proposed studio output presets, not a complete platform upload or safe-area specification.

**What the current implementation supports**

| Area | Observed behavior | Consequence for two formats |
| --- | --- | --- |
| Scene evaluation | `editor/engine.mjs`, `compileScene`, multiplies positions, destination sizes, motion and group offsets by the single scene canvas width/height. | Replacing the dimensions changes geometry. A separate framing transform is needed. |
| Camera | The same evaluator applies depth-dependent oscillation and overscan about the canvas center. | This camera describes scene motion; it is not a named output crop or an independent output viewport. |
| Rendering | `ambiance_studio/rendering.py` and `tools/render-scene.mjs` both reject output dimensions with a different aspect ratio. | `--width` and `--height` currently control resolution within the authored ratio. |
| Preview | `editor/editor.mjs` draws one stage through the shared evaluator; the renderer's motion proof compares same-size variants. | A synchronized two-format proof can reuse timing and drawing infrastructure, but requires output-view support. |
| Finishing | `editor/finishing.mjs` creates canvas-sized buffers, sets its own transforms, and computes some light, elevation and softness parameters in canvas units. | Changing only an outer Canvas transform is insufficient. Framing must preserve finishing coordinates and effect support. |
| Audits | `editor/audit.mjs` checks plate coverage against the single canvas and audits composite pixels. | Each requested view needs coverage and seam evidence across the loop. |
| Iterations | `ambiance_studio/production.py` renders one picture, then sequentially composes soundtrack editions from it. | Extend the recipe and run state to create one picture per view, with resumable results per view. |
| Delivery | `ambiance_studio/deliveries.py` keys entries by `score`, `effects`, or `silent`, with each role allowed once. | A delivery cannot presently hold both portrait-score and landscape-score under their true soundtrack roles. |
| Revisions | `ambiance_studio/revisions.py` captures one scene/catalog and binds verified media to that captured input. | Preserve that identity model and include the selected view definition and any overrides in render/edition evidence. |

Both registered projects currently author 1080 × 1920 scenes: Last Lantern has 16 layers and a moving camera; The Midnight Collection has 48 layers and a stationary camera. Those are configuration observations, not a visual judgment that either composition will survive a landscape crop. Project discovery used `./ambiance project list`; canonical files were read from the registered project locations.

Two bounded checks confirmed the constraint:

- Running `render frame --width 1920 --height 1080` against The Midnight Collection returned exit code 2 and `Render dimensions must preserve the authored aspect ratio.` It produced no render.
- An in-memory fixture evaluated through the actual `compileScene()` showed a 100 × 100 square becoming 177.78 × 56.25 after only swapping canvas dimensions. This demonstrates the distortion risk, not a fault in the existing aspect-preserving renderer.

**The options**

| Approach | Suitable use | Effort and limitation |
| --- | --- | --- |
| Crop a finished wide movie | Fast adaptation when the subject and all essential action fit a narrow strip | Smallest adaptation, but a full-height 9:16 crop retains only 31.64% of a 16:9 picture's width. It cannot recover missing art or relocate a subject. Evidence must identify the cropped derivative. |
| One expanded scene with two saved views | Default for new productions | Moderate, cross-cutting tooling extension. Assets, rigs, timing and sound remain shared. Composition and visible coverage are checked twice. |
| Shared scene with a few view-specific layout overrides | Subjects spread across the landscape, or a phone composition needing a larger focal object | More authoring and review. Move complete rigs and preserve associated occluders, contact, shadows and reflections. Do not automatically pack independent objects into a new layout. |
| Two separately authored scenes using one asset catalog | Strongly different compositions that cannot share staging | Possible as an explicit fallback, but animation and fixes can drift. It gives up much of the desired single-workflow benefit. |

Simple cropping can be an initial view mode inside the recommended architecture. A later need for selective restaging should not require duplicating the project.

**Which composition comes first**

Choose both target frames before committing to the source painting and layer boundaries. Plan the environment for the union of both visible regions plus the intended camera, rig, shadow and reflection extents. Use the tighter portrait frame to test focal-action readability, and the landscape frame to test the broader arrangement and environment. This reconciles the different demands without declaring one finished format the master.

A 1920 × 1920 painted stage can contain centered 1920 × 1080 and 1080 × 1920 windows at native scale; it still needs motion margins. A square is an example, not a requirement or a reason to repaint accepted scenes. A wide source can work well when it contains the needed portrait detail. A 3840 × 2160 wide raster, for example, supplies a 1215 × 2160 portrait crop that can be reduced to 1080 × 1920. Cropping a 1920 × 1080 wide raster instead supplies only 607.5 × 1080 source pixels, requiring enlargement for that output. Render from adequately resolved layered sources when possible.

Existing portrait work should retain its authored coordinate basis. First inspect a landscape framing proof; then explicitly plan background extension, a wider stage, or limited restaging if needed. A format change creates new visible areas and may require new painted derivatives. This analysis does not establish that usable side artwork already exists.

**Proposed implementation boundary**

Keep authored scene coordinates stable. Add named views with an explicit scene-space rectangle and output pixel dimensions. The rectangle must have the requested output aspect ratio; map it to the output with uniform scaling and translation. Missing view configuration resolves to the current full-canvas behavior.

Illustrative data for an already authored 1920-square stage:

```json
{
  "views": {
    "portrait": {
      "rect_scene_px": [420, 0, 1080, 1920],
      "output": {"width": 1080, "height": 1920}
    },
    "landscape": {
      "rect_scene_px": [0, 420, 1920, 1080],
      "output": {"width": 1920, "height": 1080}
    }
  }
}
```

This is a proposed contract fragment, not a file the current CLI accepts. `rect_scene_px` is `[x, y, width, height]`. Initially support static view rectangles; shared scene motion still runs normally. Separate output framing from the existing depth-driven camera. A later animated crop must be deterministic, loop closed, and included in visibility/coverage checks.

The simplest correctness-first implementation can composite a bounded shared stage with the existing finishing semantics and extract both views before final output encoding. This allows image decoding, animation samples, and potentially the composite to be shared when views differ only by crop. It also incurs full-stage raster and memory cost and cannot reveal anything already clipped at the stage edge. Direct rasterization into each output view is a later optimization requiring consistent mapping of lights, masks, shadows, reflection extents, blur radii, sockets and editor hit testing. Do not introduce a second implementation of rig motion to perform conversion.

The current per-side limit is 4096, including supersampling. A 1920-square stage at 2× fits that dimensional limit, but finishing allocates additional buffers. Benchmark representative scenes before promising concurrent encoder speed or increasing stage limits.

Expose the production path through the CLI before requiring UI authoring. Proposed operations are `view inspect/apply/check`, selecting a view on existing `render frame/proof/video`, and selecting multiple views in `iteration run`. A comparison proof should show both formats at the same source time with one scrubber. The exact CLI names and persisted schema should be finalized during implementation.

Capture the scene, requested views, any layout overrides, selected assets, and shared audio inputs into one immutable production revision. Editions identify both `view` and soundtrack `role`; render receipts also pin the exact framing configuration. Delivery selection, feedback, posters, stable/current watch routes, and release checks must identify that pair. Existing deliveries and their links should retain their meaning through a versioned contract and explicit legacy default view.

**Producing both together**

One iteration should capture inputs once, render a picture per view, compose the selected soundtracks onto each picture, fully verify every movie, and present one delivery containing both views. Retain independent success/failure records so a portrait failure can be retried without regenerating a completed landscape output. Present the requested complete pair together; any partial presentation should be explicitly labeled.

Sound design and a matching-duration PCM master can be shared. Picture rendering/encoding must produce two different image streams; soundtrack-only edits can reuse each view's compressed picture. Different video lengths or different screen-relative panning would become separate editorial choices, not automatic consequences of aspect ratio.

"Together" should first mean synchronized authoring, one command and one delivery. Actual concurrent work is an execution policy: cap raster/encode workers according to measured resources, use separate immutable output directories, and have one coordinator write iteration state and selection/review records. The current runner is sequential. Parallel native encoding is plausible but has not been benchmarked here; it should not be sold as free or necessarily faster. Shared assets and audio avoid rebuilding two productions, but extra painting, composition review and picture work remain.

**Suggested rollout and acceptance**

1. Add static view resolution, shared-stage crop rendering, and CLI paired still/short-loop proofs. Preserve legacy default output. Establish the two compositions before any expanded art production.
2. Extend revision evidence, per-view iteration steps, delivery/watch selection and feedback. Produce both verified movies from one saved CLI recipe, then expose the same result and synchronized preview in localhost.
3. Add bounded per-view layout overrides only after actual scenes demonstrate the need. Treat complete rigs, receiving effects and stationary occluders explicitly. Benchmark and introduce limited render concurrency separately.

Acceptance should demonstrate: unchanged legacy raster output; preserved object proportions, sockets, cel timing and appearance in both views; coverage and motion extremes in each frame; full encoded decode, expected dimensions and loop timing per movie; view-specific review freshness; retry of one failed view without rebuilding the other; and exact/current watch links that distinguish orientation and soundtrack. For shared renderer changes run `./ambiance test`, including the existing rig and packaging checks, and inspect browser and encoded picture behavior. Geometry checks alone cannot establish artistic quality.

This is a moderate product extension touching rendering and delivery identity, with a small first milestone available. The potentially expensive part is art and composition when a single portrait painting lacks the environment needed by a wide view. No complete render benchmark, raster comparison, encoded-media test, or human composition review was performed for this analysis.
