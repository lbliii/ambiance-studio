# 01 — From one image to a production plan

**Input:** the user's image and creative intent. **Output:** preserved reference, brief, object/layer plan, clean-plate plan, and proposed motion/sound roles. **Gates:** intent and layout.

## Inspect before inventing

Read the image at its native framing and at a small portrait preview. Identify focal subject, horizon/perspective, major light sources, warm/cool relationships, depth cues, and foreground silhouettes. Record observations separately from additions. If the image contains no city, a hilltop city is a creative proposal, not an extracted fact.

Keep the source unchanged. Copy it into project inputs and record its hash. Record reference provenance/usage context when known. Ask only for missing decisions that would materially change the result; infer routine production details and label the assumptions.

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

Use only the separation needed for the scene. Avoid dozens of new assets with no meaningful independent behavior. Prioritize the focal feature and a few supporting motions.

## Review the plan

Save a layer proof or labeled layout when the relationships are hard to communicate. Check that the still composition works at phone size and the reference's identity remains intact. Review proposed camera limits and hidden-pixel work before generation. Record dependencies so assets can be prepared independently where possible.

Evidence should let another operator answer: what exists, what must be made, what moves, what stays attached, and which invisible areas must be painted. Close the two planning gates only to that scope; no generated asset or render is implied.
