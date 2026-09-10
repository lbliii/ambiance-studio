# Finishing and edge quality — implementation plan

Status: implemented in CLI 0.7.0. See the [handoff](CLI-V07-HANDOFF.md) for tests, independent trials and precise capability boundaries.

The museum trial showed that a correctly registered and animated sprite can still feel separate from its painting. Static color, insufficient light response, receiving shadows, and edge sampling require explicit production controls.

## Delivered scope for this pass

1. Add an opt-in `scene.finishing` contract to the shared browser/offline evaluator. Preserve legacy rendering when absent. Support ordered asset/group/instance/scene grades, curves, painted masks, soft scene-anchored light zones, shared cel/keyframe intensity signals, and explicit shadow/reflection receiving surfaces.
2. Use linear-sRGB arithmetic for the opt-in compositor with explicit sRGB inputs/output and alpha-safe operations. Report the selected pipeline and limitations; do not infer physical light or recover unlit material from painted art.
3. Author and inspect looks through validated, hash-checked CLI scene transactions. Export/import reusable packages with explicit destination bindings and versioned mask dependencies. Revision captures include every finishing input.
4. Add a browser look workbench with synchronized comparisons, grade and light controls, pass inspection, playback/seek, editable full recipe, and downloadable scene/transaction. Saved artifacts carry the actual shared renderer and dependency identities.
5. Add all-cel edge inspection at intended display size, light/dark/context proofs and playback. Add explicit nondestructive alpha and matte-color cleanup recipes. Preserve source pixels and use identity defaults.
6. Add true supersampling to frame/proof/video rendering, followed by one reduction to the requested output size. Preserve aspect ratio. Compare moving edges and decoded media; do not mistake larger output dimensions for recovered source detail.
7. Exercise the interfaces in an isolated creature/moonlight, lamp/receiver, and casket/elevation fixture plus museum-derived comparisons. Leave active museum scenes, accepted art, sound, reviews and editions untouched.

## Architecture and boundaries

Finishing data is inline in the versioned scene; painted masks use catalog asset IDs. The shared JavaScript module owns sampling, field validation, compositing and diagnostics. Python commands reuse that contract and own files, locks, source identities and immutable artifacts. Effects are authored 2D relationships: receiving alpha clips shadows/reflections, paint order governs occlusion, and elevation response is an explicit curve rather than inferred geometry. No paid generations are needed.

A single final grade cannot fix mismatched local light; a floor shadow cannot recolor an animal. The inspection workflow separates baseline correction, light contribution, shadow/reflection contribution, alpha quality, and final encoding. Numerical checks produce evidence, not aesthetic approvals.

## Acceptance

- Legacy sampled states and unmodified raster outputs remain stable.
- Invalid fields, mask assets, signal cycles, receiving surfaces and package bindings fail before scene publication.
- Light response changes continuously across a zone and follows declared scene anchors. Grade changes preserve alpha; mask pixels are data, not display-transformed color.
- Shadows/reflections follow the specified receiving surface, are clipped and occluded, and respond to authored lift without drifting with a lifted body.
- All-cel edge operations preserve sheet registration and originals; identity recipes are pixel-exact; deliberate bad mattes and stale inputs have regression coverage.
- Supersampling renders at larger internal dimensions and emits the original requested dimensions and frame count, including native encoded verification.
- Actual browser inspection covers comparison, sliders/recipe import, pass views, playback, seeking and saved transaction use.
- `./ambiance test`, native media checks, and package audit pass. Evidence and limitations are recorded in the handoff.
