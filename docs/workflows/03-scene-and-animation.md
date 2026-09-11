# 03 — Assemble, animate, and close the picture loop

**Input:** prepared asset pack and layer plan. **Output:** scene recipe, rigs/motion settings, low-resolution draft, and loop/coverage evidence. **Gate:** animation.

## Assemble the still first

Match the reference with movement disabled. Establish layers, anchors, groups, masks, and base lighting. Align the window overlay with its architecture and the smoke with its chimney. Make the foreground/middle/background readable with overlap and contrast as well as parallax.

Use the [scene contract](../SCENE-CONTRACT.md) for the existing editor. Named and nested sockets, cel-specific socket tracks and preview loop checks are implemented; use the [workbench guide](../RIG-WORKBENCH.md). Richer particles and sound sessions are described in [contracts](../CONTRACTS.md) but remain to implement. Do not silently put unsupported settings into JSON and claim they render.

## Add a motion hierarchy

Use [source-coordinate placement](../SOURCE-PLACEMENT.md) when cutouts share a reference image. Use `scene reparent --keep-world --at` to preserve a chosen pose while attaching existing parts; later parent motion deliberately changes their world movement. Keep the recorded mapping and transaction diagnostics instead of repeating crop/padding calculations in project scripts.

Choose a primary motion, supporting cels, and quiet background movement. Use phase offsets so repeated assets do not move in lockstep. Keep structural motion small enough that the painted perspective remains convincing. Use separate camera response for depth, with shared transforms for attached elements.

For multiple candles, vary compatible shape sequences, cadence and phase rather than merely shifting one identical brightness pulse. Choose periods that close over the picture loop; do not choose arbitrary rates and assume they loop. Judge the combined pattern at actual speed: distinct local flames should remain attached to their wicks, and shared light response should make sense for the room. Independence does not require animating every practical light equally strongly.

Give every motion a duration or integer cycle count, amplitude, phase, and anchor. Seed any particle variation and define a circular birth/death schedule. Use absolute-time evaluation so frame 240 can be rendered directly without first simulating frames 0–239.

Choose picture and sound master periods intentionally. In the reference: a 16-second picture accommodates 2-, 4-, and 8-second cel cycles; a 48-second sound master repeats the picture three times. Other durations are valid when the motion periods and exported sample count agree.

## Make the loop test concrete

Run `scene timing` to identify the active cel driver, authored holds and frame-sampled visibility before judging cadence. An inactive fallback cycle is not the played sprite rate. Use `render rig-proof` for saved rest/extreme/hidden-part comparisons when motion exposes overlaps; the result supplements the full-scene loop review. See [timing](../SCENE-TIMING.md) and [rig proofs](../RENDERING.md).

- Check state at time zero and exactly one period. They should agree for an exact loop.
- Inspect frame N−1 flowing into frame zero. Those frames normally differ; the change should be consistent with nearby motion.
- Export N frames, sampled at `frame / fps`, with no duplicated endpoint frame.
- Inspect all major camera extremes and border regions. A perfect endpoint can still reveal an empty strip halfway through the loop.
- Inspect the focal object and group attachments across the full duration.
- Inspect compound objects and crossings at their motion extremes: front rims still occlude the correct parts, stationary frames remain stationary, and shadows/reflections keep the intended contact or separation.
- Watch the draft three times at phone size. Look for distracting synchronization, short repeated gestures, cel jitter, and excessive motion density. Check that the intended supporting action is noticeable without a label pointing to it. If uncertain, compare it enabled/disabled or at two proposed strengths while preserving the primary action. Record the actual observation; if continuous viewing is unavailable, keep that check open and present the short proof for review.

Keep state checks, rendered-image checks, and encoded-video checks separate. Report the actual scene/asset hashes and engine version. The bundled example's Node check covers its own state only; a new scene needs its own inputs and suitable assertions.

## Repair at the responsible layer

When a moving cutout does not fit its surroundings, use [finishing](../FINISHING.md) to separate baseline asset correction, local illumination, contact/cast shadow and final scene grade. A receiving shadow cannot recolor the caster. Use declared surface relationships and inspect overlap at rest and extremes. Keep the original look as a comparison; attach light masks to their intended source coordinates and drive flame/light response from the same cel or closed key signal.

Use `render look-proof` for actual-size comparison, isolated contributions and saved variants. Apply exported transactions with the expected scene hash. `look export/import` reuses explicit relationships with destination bindings; inspect the new composition before treating a reused look as accepted.

For rough edges, first compare source cel, compiled atlas, output raster and decoded movie at the same intended display size. Use [edge proofs](../EDGE-QUALITY.md) to distinguish cutout damage, sampling, atlas bleed and encoding. Preserve delicate alpha by default; test repair recipes across all cels. Supersampled rendering is an option after source/matte problems are understood, with one reduction to the requested portrait output size.

If a roof ghost appears behind the cottage, repair the clean plate or separation. If smoke floats off the chimney, repair its group/socket. If a bright border flickers, inspect alpha and resampling. If a wrap is visible, repair the periodic path or cel sequence. Do not add broad blur or more particles as a default concealment strategy.

Render a small draft after the repair. Reuse accepted cached layers and source files. Increase resolution for final inspection only after layout, motion, and coverage are stable.

For requested portrait and landscape outputs, use `view apply`, `view check`, then `render views-proof --view portrait --view landscape` through the CLI. The saved proof and editor panes sample one scene clock. Inspect raw-alpha coverage, finishing, attachments, camera extremes and the join independently in both crops. Render final pictures with explicit `--view` and bind them to the captured revision. Guide overlays are inspection aids and are excluded from output.
