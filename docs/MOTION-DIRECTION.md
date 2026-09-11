# Motion size, readability, and cadence

This is an authored direction and review vocabulary, not an implemented automatic classifier or new scene schema. It responds to the user's review of **A Quieter Tomorrow / first-film-v2**: clean, stable animation was too small and infrequent to notice in the whole composition.

## Readability levels

Judge the active action at normal speed, in the full composition, at the intended display size. Keep the target level separate from an observed result; an unchecked target is not a pass.

| Level | Name | Intended viewing experience |
| --- | --- | --- |
| 0 | Still | Deliberately fixed reference or structure. |
| 1 | Trace | Discovered by looking closely at a particular detail. |
| 2 | Readable | Clearly noticeable during ordinary viewing without an arrow, zoom, or instruction to stare at it. |
| 3 | Featured | An unmistakable gesture or silhouette change that briefly attracts attention. |
| 4 | Dominant | Broad movement or a major event that becomes the main subject. |

These are perceptual judgments, not universal pixel thresholds. Small movement over a broad high-contrast region can read strongly; substantial motion in a tiny dark object may remain hard to see. Registration accuracy does not establish readability. Default ambiance direction should include readable environmental life; reserve trace motion for secondary details unless the user asks for a nearly still image.

## Record independent dimensions

- **Role and method:** environment, character gesture, accent, or fixed reference; translation, rotation, changing cels, light, or parallax. A role does not imply an intensity.
- **Size:** displacement relative to the object and to the frame, silhouette change, and rotation where relevant. Report intended display-pixel travel when measured. Use actual painted bounds, not an atlas's transparent padding. Describe both travel and speed; slow movement can cover a large distance.
- **Readability:** target level, observed level, viewing size/speed, and the actual observation. Use `unreviewed` until viewed. Whole-frame difference statistics cannot assign the observed level by themselves.
- **Cadence:** continuous, recurring, or occasional; actual action windows, onset, duration, repeat interval and longest rest. Evaluate readability while active, and waiting time separately.
- **Coverage:** where visible movement occurs, how much of the image it affects, and whether the entire scene has long apparently still intervals. Cel changes can be duplicates, hidden, or imperceptible; count neither transitions nor moving layers as a substitute for looking.
- **Safety envelope:** fixed contacts, maximum reveal, required hidden paint, occluders, and how the cycle closes. Registration should remove accidental drift while retaining the intended action.

Example direction: “Clouds: environment; broad slow travel; readable level 2; continuous; most of the window; layered independently behind the frame.” “Mouse: character; clear head/upper-body silhouette change with planted feet; level 2; recurring, two-second bouts every 6–9 seconds.” These are targets to test, not measurements of completed footage.

## Agent workflow

1. Assign motion targets before asset boundaries. Separate any surfaces needed for different depth, speed, deformation, or overlap. A foreground cutout over one static background is not an implemented depth stack.
2. Establish a readable full-scene motion draft before final art polish and full-resolution encoding. Compare quieter, target, and stronger versions at the same intended size and speed. Label variants by what actually changed; changing amplitude, speed and frequency are different experiments.
3. Use the existing `scene timing` and `render proof` tools for actual timing and playback. Record size measurements and observations alongside the project plan. Do not add unsupported classification fields to executable scene data.
4. Inspect the scene without pointing at the animated object. If the viewer must search for the primary or supporting action, record that miss and revise amplitude, silhouette, staging, contrast, cadence, or layer separation at the responsible source.
5. Review excessive activity as well as insufficient activity. Fixed structure and resting characters can coexist with continuous environmental motion. Do not increase every channel or repeat a conspicuous unique gesture mechanically.

## Executable activity evidence

Use [scene activity](SCENE-ACTIVITY.md) for action-linked per-view state, painted bounds, real disabled-element raster contributions, temporal maps and matched strength/cadence proofs. The warning calibration retains misses and false warnings. Actual readability/composition observations remain named, exact-artifact reviews; these measurements do not implement a salience classifier or aggregate artistic score.

## Window motion

A window frame is a fixed occluder; the exterior is separately controlled artwork behind it. For a traveling vehicle, near exterior features should pass faster than the distant skyline, with sky/moon nearly stationary. Relative travel produces the parallax. For a stationary vehicle and fixed camera, clouds and water can move while the buildings stay still; merely adding layers does not create parallax.

Plan the exterior revealed through every window and around foreground ivy. A longer/repeatable background or a deliberate longer picture period may be needed for one-way travel. Do not make the city reverse direction just to close a short loop, or reset a unique landmark in full view.
