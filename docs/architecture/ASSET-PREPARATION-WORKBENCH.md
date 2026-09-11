# Asset preparation workbench

Status: first implementation slice and agent operation pass implemented. Steps 1–5 have callable interfaces; see [agent preparation](../AGENT-PREPARATION.md). Following explicit user direction, the next priorities are the agent operation pass in step 5 and the agent-operated fresh-painting pilot in step 6. See the [implementation handoff](PREPARATION-WORKBENCH-HANDOFF.md) and [user guide](../PREPARATION-WORKBENCH.md).

## Problem and intended result

The museum production repeatedly needed separate background-removal and object-alpha masks, source-coordinate alignment, and movement/hidden-object inspection. Existing preflight, crop/return, compiler and rig-proof commands supply the foundations, but preparing their inputs still requires project-specific scripts.

The primary operator is the agent. It must be able to inspect the original, replacement backing, masks and fixed foreground; author masks/alignment directly; generate motion proofs; and build fresh derivatives through structured tools and saved recipes. Localhost makes this work observable and provides optional visual editing for the human or agent. Browser-authored recipe downloads are an interchange option, not a required production step. Original paintings and accepted projects remain protected.

## Implementation sequence

1. **Saved preparation contract and CLI.** Add `asset prepare` to create a workspace from existing source/backing images or rebuild an exported recipe. Pin input identities, keep removal/cutout/occluder masks distinct, use source-pixel polygons and optional existing grayscale masks, and reuse Pillow registration. Publish complete immutable output directories, preserving source snapshots and source mappings. Supply compiler recipes for the resulting layers.
2. **Interactive inspection.** Add `preview --prepare DIR`. Show original and candidate, isolated parts, contrasting backgrounds, changed-pixel overlays, alignment controls, polygon add/subtract/undo, and recipe import/export. Compute edited masks through the same Python implementation as saved outputs. The loopback server performs bounded preview calculations on captured inputs; browser edits do not write project files.
3. **Movement proof.** Generate a normal scene/catalog using the shared evaluator and draw code. Preview rest, maximum movement and object/foreground-hidden views, with play/pause/seek. Save an isolated preview project so existing frame/proof/video commands work without another rendering implementation. Keep the preview movement explicitly separate from an existing film's authored rig.
4. **Verification and first handoff.** Exercise mask separation, alignment, source preservation, recipe rebuilds, rejected input changes, output collisions, browser editing and actual rendered pixels with an independent fixture. Run `./ambiance test` and package audit. Present the running workbench and document current limits.
5. **Agent operation pass — next engineering priority.** Make recipe inspection, validation without building, bounded mask/alignment/motion edits and proof discovery convenient through structured CLI/tool inputs. Reuse the current recipe evaluator and immutable build path. Keep normal responses compact, expose artifact paths and source coordinates directly, and preserve clear input identities across edits. Check what direct JSON authoring already handles well before adding commands; avoid a command for every browser gesture. The public interfaces are documented in [agent preparation](../AGENT-PREPARATION.md).
6. **Agent-operated fresh-painting pilot.** Have the agent carry an object from a different painting through preparation, compilation, scene placement and an encoded review movie using public commands and saved recipes, without a required browser edit or download. Present intermediate/exact-version results on localhost for human observation and quality judgment. Record active preparation time, repair attempts, manual workarounds, agent context/output burden and review rounds. A synthetic fixture does not satisfy this artistic pilot. Select existing suitable art/backing first; do not assume new paid generation authority.

## Boundaries for the first slice

- One moving cutout, one repaired backing and one fixed foreground layer per workspace. Compound articulated rigs remain in the scene tools.
- Inputs are existing sRGB still images. Preparation does not generate missing paint, infer segmentation or infer registration.
- Polygon masks support additive/subtractive regions; existing grayscale masks retain soft edges. The initial editor does not replace a pressure-sensitive paint application.
- Pixel coordinates and a full affine registration are explicit. Full reference-sized derivatives preserve placement even when masks change.
- Preview and rebuild use the same mask rasterizer; animation uses the existing shared engine. Technical success does not establish artistic acceptance.
- Browser changes are drafts. Export the recipe and run the CLI with a new output directory to save a reproducible version.
- Agent-authored recipes use the same build directly. No browser session or download is needed to create, revise or render the prepared parts.

## Completion evidence

Record commands, fixture input/output identities, meaningful positive/negative tests and actual browser observations in the implementation handoff. Establish the agent's complete CLI path separately from the UI inspection path. Report the fresh-painting pilot separately until performed. Evaluate time savings only against measured work.
