# Scene and asset contract, version 1

The scene is the recipe. The catalog describes ingredients. Both are readable JSON so a person, a visual editor, and an assistant can make the same change without rewriting rendering code.

## Coordinate system

- A portrait canvas is 1080 × 1920 pixels in this example. Coordinates start at its top-left.
- `x` and `y` locate a layer's **anchor**, in fractions of canvas width/height. `0.5, 0.5` is the canvas center.
- `width` and `height` are the destination image size, also in fractions of canvas width/height. These use the full atlas cell, including transparent padding.
- `anchor` is a pair of fractions within that destination rectangle: `[0,0]` is its top-left, `[0.5,0.5]` its center, and `[0.5,1]` its bottom-center.
- `scale` multiplies the layer's size around its anchor; `rotation` is radians clockwise in the screen coordinate system.
- The order of `layers` is back to front. **Draw order and depth are separate.** Depth controls camera response; it does not automatically reorder the painting.
- `depth` is an artistic parallax multiplier, not meters. A value near zero barely moves with the camera; a higher value moves more. Values from 0 to 2 are exposed in the editor.

This is a stack of painted cards in depth, not a per-pixel depth image or full 3D reconstruction. It suits gentle camera movement. A large move can reveal missing artwork; that requires a clean background plate or further scene construction.

## Groups and attachments

A layer may supply `group` instead of `depth`. The group contains shared depth, position offset, scale, and pivot. Groups remain one level; the v0.3 evaluator additionally supports nested layer attachments.

Groups first receive the depth-based camera transform, then their own offset and scaling. Their layers use the same canvas coordinate system. Thus the cottage, ground, and smoke can share a movement while preserving their relative placements. Named sockets now implement object-level relationships, such as `chimney`, `windows`, and `branch-hinge`.

The editor always changes a grouped object's depth through its group. The “Move / scale the whole group” control also applies position and scale edits to that group. Anchor edits remain specific to the selected image.

### Named sockets (v0.3 extension to scene version 1)

A layer or catalog asset can declare `sockets: {"chimney": [0.58, 0.13]}`. Coordinates are fractions of the full, untrimmed cell rectangle, independent of the layer's anchor. Layer entries override asset entries with the same name. A moving architectural feature can use `{"frames": [[u0,v0], [u1,v1], ...]}` instead of a pair; provide exactly one pair per source cel. The UI places static sockets; tracks are authored in JSON.

A child supplies `attach: {"layer": "cottage", "socket": "chimney"}` and omits both `group` and `depth`. Its `x` and `y` are offsets from that socket, measured in canvas-normalized units along the parent's local axes. Width/height use the usual canvas units; the parent matrix then scales/rotates them. At zero offset and without translation motion, the child's anchor coincides with the socket. Parenting inherits transform, depth, visibility and multiplicative opacity. Blend mode and paint order remain independent. Hiding the parent hides descendants.

The parent matrix is applied once; children never receive a second camera transform. Graph evaluation follows dependencies, not paint order, and rejects cycles/missing sockets. Moving the whole group still moves all its contents. Moving a cottage layer alone now moves its socket-attached smoke, while ground remains in the shared group. Large house moves can still expose missing background artwork.

`coverage_layers: ["sky"]` identifies individual plates intended to cover the entire canvas throughout the loop. Node checks their transformed rectangles; the browser additionally checks actual composite alpha. This list is not for partial terrain layers.

## Timing

`canvas.loop_seconds` is the picture loop. `canvas.fps` is the export clock, currently 30. The browser preview uses elapsed time; it is not an export recorder.

For a sprite with N frames and cycle C seconds:

```text
wrapped_time = time modulo picture_loop
cell = (floor(wrapped_time / C × N) + phase_frames) modulo N
```

Every cel cycle must divide the picture loop. An 8-frame sheet played over 4 seconds has 2 new cels per second, while the picture can still export at 30 fps. Motion is computed from periodic functions with whole-number cycles over the picture duration. Rendering a frame does not depend on which frame was rendered previously.

`engine.mjs` is the executable contract for the prototype. `compileScene()` validates and snapshots a scene once and exposes `sample(time)` for repeated evaluation. `sampleScene()` is a convenience wrapper. Sampled state includes source/destination rectangles, matrices, cel indices and local/world socket coordinates; `drawScene()` paints that state. All preview controls use those functions.

For production, export the samples at `frame / fps` for frames **0 through N−1**. The state at time T must equal the state at zero, but do not append time T as an extra frame. The last exported frame should advance naturally into frame zero, rather than be a duplicate.

## Assets

Each catalog entry has a stable `id`, relative file path, dimensions, SHA-256 digest, type, and provenance. Historical entries also include source byte counts. Compiled packs add their registration pivot and recipe reference. Atlas entries also describe rows, columns, fixed cell dimensions, frame count, and optionally a default cycle. Frame order is row-major.

The present catalog records source attribution and reuse status, but is not a full licensing database. It does not invent missing provider model IDs, job IDs, seeds, or generation costs.

A production asset record should additionally retain:

- A preserved raw source and separately versioned production derivative.
- Generation request ID, model, exact prompt, references, seed if supported, settings, timestamp, and cost if returned.
- Alpha convention, color profile, content bounds, anchor, attachment sockets, and any mask or emissive companion.
- A recipe for registration/matting/packing, including its version and input hashes.
- Intended size range, lighting direction, palette, season, and compatible style pack.
- Review status for art, matte edges, frame stability, loop behavior, and applicable usage terms.

Do not normalize every cel independently to fill its box: doing so changes the apparent size of a flame or smoke plume. Register against a shared pivot and consistent sequence scale; preserve intentional deformation.

## Audio

The example contains reference metadata for a 48-second soundtrack over three picture cycles. It is not an executable audio arrangement. A future `audio-session.json` should hold source IDs, offsets, gains, pan, filters, event times, crossfades, and circular tails, with separate processed stems and master outputs.

The shared master duration should be a deliberate multiple of the picture duration. Long music and event cycles reduce obvious repetition while shorter visual motions keep the image alive.

## Validation boundaries

`kit.py check` verifies declared geometry, references, PNG headers, file hashes, and cycle arithmetic. `verify-engine.mjs` checks deterministic state sampling and attachment behavior. The browser decodes actual PNGs and checks their dimensions on load.

The compiler inspects alpha bounds and creates visual proofs. The browser checks composite alpha and adjacent/seam pixel differences at preview resolution. The Node scene audit checks geometric coverage and all-frame socket attachment with input hashes. Still needed for production: detailed alpha/cell-content inspection, full-resolution edge and loop review, encoded-video decoding, exact audio presentation length, audio level/seam checks, and human visual/listening review. Passing one layer of validation never implies the others passed.
