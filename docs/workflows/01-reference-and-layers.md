# 01 — From one image to a production plan

**Input:** the user's image and creative intent. **Output:** preserved reference, brief, object/layer plan, clean-plate plan, and proposed motion/sound roles. **Gates:** intent and layout.

For a complete seed film, start with [seed-to-stage production](../SEED-TO-STAGE.md): whole-scene census, story choices and requested output compositions before narrowing asset scope. Portrait and landscape are the studio defaults unless the user specifies otherwise. Full-frame staging may require expanded paint and independent objects; preserve identity while adapting composition.

## Inspect before inventing

Read the image at its native framing and at a small portrait preview. Identify focal subject, horizon/perspective, major light sources, warm/cool relationships, depth cues, and foreground silhouettes. Record observations separately from additions. If the image contains no city, a hilltop city is a creative proposal, not an extracted fact.

Keep the source unchanged. Copy it into project inputs and record its hash. Record reference provenance/usage context when known. Ask only for missing decisions that would materially change the result; infer routine production details and label the assumptions.

Complete the [layer-and-light planning pass](../LAYER-AND-LIGHT-PLANNING.md): distinguish depth planes, independently controlled parts and light-source/receiver relationships. Inventory steady sources as well as changing ones. The tram review demonstrated that listing animation opportunities without preparing their required separations can leave an otherwise clean film almost still.

## Break down relationships

Use the layer-plan template to list each object. Define its artistic role, bounding region, draw order, depth response, anchor, parent/socket, and motion method. Draw order decides which pixels cover which; depth decides response to camera motion. They need not be identical.

Identify groups before animation: a building and its ground contact; window light and its mask; chimney and smoke origin; trunk and swinging branch hinge. Record a coordinate convention once and convert inputs explicitly. Do not mix source-image pixels, normalized canvas coordinates, and atlas-cell pixels without metadata.

List every area movement may expose. A clean sky behind clouds, landscape behind a house, and painted ground behind a foreground object may require reconstruction. Include overscan at the borders and the largest planned displacement. Merely making a cutout transparent does not remove the same object from the backing painting.

## Choose the motion method

| Feature | Useful starting method | Stable relationship |
| --- | --- | --- |
| Moon, hill, building structure | Painted plate and subtle camera transform | Perspective and silhouette |
| Cloud | Optional painted cels plus slow drift | Scale, light, soft edge character |
| Smoke/flame | Changing cels | Emission point or base pivot |
| Window/curtain | Masked internal cels over fixed architecture | Window frame and glass boundaries |
| Branch | Rotation around hinge, optional leaf cels | Attachment point |
| Falling leaves | Seeded circular paths, rotation, optional flip cels | Reproducible schedule and depth size |

Establish [whole-object production layers](../LAYER-AND-LIGHT-PLANNING.md#whole-object-ownership-and-proof) for the intended scene before selecting internal motion controls. A subject can remain still while belonging to its own complete rig. Avoid speculative internal articulation or unseen views, but do not reduce a character's extraction to the one part moving in the first loop. Prioritize motion only after its production boundaries are clear.

## Judge framing and movement before choosing cuts

Use `plans/layout-notes.md` to explain the consequential decisions; the existing layer-plan fields can hold the resulting objects, backing, rigs and bounds. Meaningful objects and surfaces need independent production ownership; repeated details may be grouped. This is artistic planning, not a new executable scene schema or a requirement for a file per leaf.

- **Framing:** judge the subject's screen size, silhouette, perspective, negative space and overlap at the intended display size. Keep enough room for the proposed action. Preserving a composition means preserving its visual relationships, not blindly retaining coordinates when the user requests a new format or staging.
- **Action and parts:** name what the subject could do in this cycle or requested exploration. Choose a rigid cutout, compound rig, changing cels, or a retained plate accordingly. A rocking vase needs a pivot and backing; a turning head needs new views. More atlas cells do not create missing geometry.
- **Motion envelope:** consider rest, the largest planned displacement/rotation, and the return or exit. Identify the pixels and surfaces revealed at those positions, including undersides and objects behind the mover. Record a proposed limit until an actual proof establishes a safe range; do not imply one painting supports arbitrary rotation.
- **Overlap and contact:** decide which parts move together, which move relative to one another, and which remain in front. Keep draw order separate from camera depth. Plan contact shadows, reflections and stationary surroundings explicitly; a shadow on the floor must not rise with a levitating object.
- **Readable change:** name the feature a viewer should notice at normal speed. A silhouette change, travel past an edge, or changing overlap often reads more clearly than tiny brightness modulation. Protect the primary action and assess supporting movement in context, not from a motion-difference image alone.

For a compound or crossing action, make a small layer/blocking proof at rest and at its extremes before spending on the whole asset pack. A contact sheet alone cannot establish framing or occlusion. Retain the observed/inferred distinction when reconstructing hidden surfaces.

### Example: a figure inside a moving casket

A useful back-to-front split is repaired backing → rear casket wall/interior → figure → viewer-near rim/front wall → any foreground glass. Put the casket parts in one transform hierarchy, with a nested figure rig if it also moves independently. A foreground rim can cover the figure's lower body while the figure rises; that spatial overlap does not require camera motion. A lid or trim needs its own part only if the planned action calls for it.

Decide whether the casket alone moves inside a stationary display case or the whole display moves. For an internal lift, preserve the external glass/frame, establish clearance, repair what appears beneath the casket and vary its floor shadow separately. Small jiggles can use rigid transforms; a large turn or exposed underside needs additional painted views. Inspect the silhouette, lower-body overlap, revealed backing and shadow at the proposed lift/tilt extremes. Do not treat a crop of the casket with the figure already painted into it as independent figure/casket assets.

The same decision applies to a cat statue, pottery or a distant figure: choose a role and action first, then identify its complete silhouette, contact point, backing and any front-facing occluder. Extraction creates independent control; it does not mean every object should perform at once.

## Review the plan

Save a layer proof or labeled layout when the relationships are hard to communicate. Check that the still composition works at phone size and the reference's identity remains intact. Review proposed camera limits and hidden-pixel work before generation. Record dependencies so assets can be prepared independently where possible.

Evidence should let another operator answer: what exists, what must be made, what moves, what stays attached, and which invisible areas must be painted. Close the two planning gates only to that scope; no generated asset or render is implied.

For multi-format production, record the authored stage separately from every requested [saved view](../VIEWS.md). Design the focal area and reveal budget for both crops together; neither orientation is automatically the master. Judge subjects, overlaps and available pixels at each output size. A contained alternate crop can omit important scenery; identify expanded-art or restaging work explicitly before accepting it.
