# Plan layers and light before animation

The A Quieter Tomorrow review exposed a production failure: a clean background with a few moving cutouts left the exterior and characters largely still. Small brightness changes did not replace missing depth, cloth animation or connected illumination. Use this workflow during reference deconstruction and focused revisions to make the intended controls explicit.

This is an authored planning and review workflow. It adds no scene schema, automatic extraction, light detector, cloth solver or new approval gate. Keep decisions in the project's layer plan/layout notes and actual parts in the [production inventory](PRODUCTION-INVENTORY.md). Record target motion using [motion direction](MOTION-DIRECTION.md).

## Three related maps

1. **Depth:** what lies nearer or farther, and how it responds to camera or world movement. A stationary camera can still see a moving exterior through fixed window openings.
2. **Parts and overlap:** what needs independent movement, changing cels, surface treatment or foreground coverage. Two parts can share depth while having different controls and draw order. A seated character belongs to its own rig, with the bench behind it and selected seat/arm edges in front where the painting requires that overlap.
3. **Light:** where illumination originates, how the source behaves, which surfaces receive it, what blocks it and where it is reflected. Draw order and depth do not automatically calculate these relationships.

The historical analogy is Disney's multiplane camera: separated painted planes supplied depth while character animation supplied changing poses. The Walt Disney Family Museum describes glass paintings and independently staged foreground/middle/background planes in [Pinocchio's multiplane work](https://www.waltdisney.org/blog/machine-imagination-walt-disneys-pinocchio-and-multiplane-camera). The related 2D game technique moves background layers at different rates, as illustrated in [Godot's parallax documentation](https://docs.godotengine.org/en/4.5/tutorials/2d/2d_parallax.html).

## Layer and extraction pass

List the back-to-front spatial families, then split each family only where intended action, overlap or lighting requires independent control. Include explicitly requested exploration even if its first pose is still. Name the source painting, cutout/removal masks, clean backing, foreground occluders, attachments, contact surfaces and maximum reveal for each moving part.

| Planning field | Answer required before claiming the part is ready |
| --- | --- |
| Source and identity | What observed paint is being retained? What hidden paint or new pose must be inferred? |
| Independent action | Rigid motion, changing cels, world travel, illumination change, or deliberately still? |
| Depth and overlap | What moves with it, what covers it, and what becomes visible behind it? |
| Envelope and contact | Largest intended pose/travel; fixed hinges, feet, seat contact and shadow/reflection receivers. Record unproved limits as proposals. |
| Production state | Planned, prepared, compiled, placed, or actually reviewed, with real artifact references. |

Test a mover hidden and at its extremes. A cutout over the same object still baked into the background fails separation. For cloth, translating a rigid sheet cannot supply changing folds; plan suitable painted cels or supported deformation. Keep weight-bearing folds stable while free fabric can change. A floor is a receiving surface, not a single flat depth shared automatically by every object standing on it.

## Light-source pass

Inspect the whole frame, including partial fixtures at its edges. Inventory every visible source or plausible offscreen source, and distinguish observed appearance from a proposed explanation. A bright reflection, white fabric or a dark phone is not automatically an emitter. Assign stable IDs that can be referenced by assets, signals and observations.

For each source record:

- **Identity and mounting:** observed region, proposed mechanism, fixed/attached/world position, color and relative strength.
- **Behavior:** steady, combustion, electrical interruption, atmospheric occlusion or another explicit mechanism. Position, intensity, color and shape can change independently. Give each intended change a readability target and cadence; keep target and observed result separate.
- **Visible source:** fixture/body, luminous region and any changing flame/glow art. Identify the reference, dim and off appearance that must exist.
- **Influence:** explicit receivers, painted masks/falloff, blockers, contact shadows and reflected images. Keep reflected surface movement distinct from emitter flicker.
- **Coupling:** name the source signal and the responses it drives. The flame, nearby illumination and its reflection should agree in time, while water can distort the reflected shape independently. Separate sources need independent behavior unless there is a shared cause.
- **Evidence/state:** assets that exist, missing paint and the proof needed. A still reference establishes neither a flicker frequency nor an off-state image.

Use a project table with columns `ID | observed source | proposed behavior/cadence | source art | receivers/blockers/reflections | signal | state/proof`. Sources deliberately kept steady still belong in the table.

Keep moon illumination steady unless cloud cover or another cause changes its visibility. Treat distant twinkling as a considered direction, not a preset applied to all city/bridge lights. A candle can have continuously changing shape/intensity without requiring the pumpkin body to move. An electrical dropout requires the fixture and affected surfaces to dim together; a global exposure dip is not a substitute.

### Prepare the light range

Painted illumination can be a separate production element: preserve the surface base and author the source's highlighted tile edges, wet patches or cloth folds as a mask or painted contribution. Give it a receiving surface, bounded appearance/movement and explicit source relationship. A painted overlay needs suitable compositing and foreground occlusion; naming it a lighting layer does not supply those behaviors.

Keep three relationships distinct: **attached to** inherits object transforms; **driven by** maps a source state to a response; **received by** registers/clips the response to a surface. A flame may attach to a pumpkin while its floor light stays registered to the floor and follows candle strength/pose. Start with explicit one-way drivers and bounded follower mappings. Light changes share source time; temporal lag belongs only where the intended response calls for it. [Source bindings](BINDINGS.md) implement bounded one-way response on the existing clock, with explicit off values and conflicting-writer rejection.

The reference already contains painted illumination. Identify each contribution that must diminish, preserve a dim/base version and use receiver masks to restore or modulate its contribution. Preserve light from other sources. Turning a signal to zero while the painted bulb and bright floor remain unchanged does not establish an off state.

The current [finishing engine](FINISHING.md) supports explicit receiver masks, closed/cel-driven signals and authored 2D shadow/reflection projections. Receiver lights multiply RGB; they do not automatically reconstruct an unlit painting, cast geometric occlusion, simulate bouncing light or create missing emissive artwork. Source appearance needs its own supported track/grade/art treatment. Use `binding inspect/check/apply` for supported intensity, pose and cel response; unsupported effects still require separately authored work.

## Evidence before another full film

1. Save the maps and reconcile required parts through `plan check/next`. A ready plan is not an extracted scene.
2. Prepare source-bound derivatives through `asset crop/prepare/return` as appropriate. Compile/admit real assets and place them through scene transactions. Preserve the reference and reviewed editions.
3. Use `render rig-proof` for hidden-part/rest/extreme views and `render look-proof` for reference/dim/bright variants with individual lights and receivers isolated. Inspect actual pixels for duplicates, holes, mask leaks and unrelated surfaces changing.
4. Make a short combined normal-speed proof at the intended viewing size. Judge readable cloth/environment movement and source/receiver timing together; stationary source bodies may still light moving receivers. Record actual observations separately from numerical checks.
5. Update affected reviews and capture/encode the selected revision after the proof resolves the issues. These are readiness checks, not a new permission request.

For an agent, the useful output is an actionable inventory: which control is missing, what source/backing supplies it, what depends on it and where the proof lives. Layer counts and light counts alone cannot establish readiness. A visual review must still show that the intended movement and illumination read in the full scene.
