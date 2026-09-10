# 03 — Assemble, animate, and close the picture loop

**Input:** prepared asset pack and layer plan. **Output:** scene recipe, rigs/motion settings, low-resolution draft, and loop/coverage evidence. **Gate:** animation.

## Assemble the still first

Match the reference with movement disabled. Establish layers, anchors, groups, masks, and base lighting. Align the window overlay with its architecture and the smoke with its chimney. Make the foreground/middle/background readable with overlap and contrast as well as parallax.

Use the [scene contract](../SCENE-CONTRACT.md) for the existing editor. Named and nested sockets, cel-specific socket tracks and preview loop checks are implemented; use the [workbench guide](../RIG-WORKBENCH.md). Richer particles and sound sessions are described in [contracts](../CONTRACTS.md) but remain to implement. Do not silently put unsupported settings into JSON and claim they render.

## Add a motion hierarchy

Choose a primary motion, supporting cels, and quiet background movement. Use phase offsets so repeated assets do not move in lockstep. Keep structural motion small enough that the painted perspective remains convincing. Use separate camera response for depth, with shared transforms for attached elements.

Give every motion a duration or integer cycle count, amplitude, phase, and anchor. Seed any particle variation and define a circular birth/death schedule. Use absolute-time evaluation so frame 240 can be rendered directly without first simulating frames 0–239.

Choose picture and sound master periods intentionally. In the reference: a 16-second picture accommodates 2-, 4-, and 8-second cel cycles; a 48-second sound master repeats the picture three times. Other durations are valid when the motion periods and exported sample count agree.

## Make the loop test concrete

- Check state at time zero and exactly one period. They should agree for an exact loop.
- Inspect frame N−1 flowing into frame zero. Those frames normally differ; the change should be consistent with nearby motion.
- Export N frames, sampled at `frame / fps`, with no duplicated endpoint frame.
- Inspect all major camera extremes and border regions. A perfect endpoint can still reveal an empty strip halfway through the loop.
- Inspect the focal object and group attachments across the full duration.
- Watch the draft three times at phone size. Look for distracting synchronization, short repeated gestures, cel jitter, and excessive motion density.

Keep state checks, rendered-image checks, and encoded-video checks separate. Report the actual scene/asset hashes and engine version. The bundled example's Node check covers its own state only; a new scene needs its own inputs and suitable assertions.

## Repair at the responsible layer

If a roof ghost appears behind the cottage, repair the clean plate or separation. If smoke floats off the chimney, repair its group/socket. If a bright border flickers, inspect alpha and resampling. If a wrap is visible, repair the periodic path or cel sequence. Do not add broad blur or more particles as a default concealment strategy.

Render a small draft after the repair. Reuse accepted cached layers and source files. Increase resolution for final inspection only after layout, motion, and coverage are stable.
