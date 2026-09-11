# Cel motion research and agent operation review

September 11, 2026. Focused web research and design review supporting the [implementation plan](CEL-MOTION-WORKBENCH.md). This combines primary documentation, research papers and repository inspection. No tracking algorithm, prototype or production animation was run in this review. Proposed benefits and performance remain hypotheses to test.

## Findings from existing tools and research

| Primary source | What it establishes | Design implication for this studio |
| --- | --- | --- |
| [OpenCV optical-flow tutorial](https://docs.opencv.org/4.13.0/d4/dee/tutorial_optical_flow.html) | Its classical formulation assumes similar intensities over time and locally similar motion. It explains pyramids for larger displacement and warns that a disappeared feature may acquire a plausible false match; the discussion recommends backward checks. | Use bounded tracking, selected reference patches and missing-point states. Appearance changes need separate diagnostics. A returned coordinate does not prove a correct anatomical match. |
| [Blender tracking settings](https://docs.blender.org/manual/en/latest/movie_clip/tracking/clip/toolbar/track.html) | Reference-keyframe matching resists sliding but can jump or fail as the feature deforms. Previous-frame matching accommodates change but can accumulate drift. Controls include motion models, search areas, masks, correlation thresholds and limited tracking spans. | Retain reference and neighbor estimates, expose disagreement, and add references where needed. Save the tracking choices. No one reference policy fits every pose. |
| [Blender 2D stabilization](https://docs.blender.org/manual/en/latest/movie_clip/tracking/clip/sidebar/stabilization/panel.html) | Separates the anchor frame, compensation tracks and intended camera movement. Autoscale can conceal exposed borders. Subpixel resampling trades image sharpness against residual movement from integer steps. | Preserve intended motion explicitly. Keep asset size fixed, report inadequate padding, and inspect sampled edges. Footage-oriented autoscale is a poor default for interchangeable painted assets. |
| [Harmony Shift and Trace](https://docs.toonboom.com/help/harmony-20/advanced/reference/toolbar/top/shift-and-trace-toolbar.html) | Offers temporary reference-drawing transformations and crosshairs, with a way to restore original viewing positions. | Add labeled inspection-only alignment to reveal shape differences. Keep raw registration visible; temporary viewing transforms must never silently become saved corrections. |
| [Deep Animation Video Interpolation in the Wild, CVPR 2021](https://openaccess.thecvf.com/content/CVPR2021/html/Siyao_Deep_Animation_Video_Interpolation_in_the_Wild_CVPR_2021_paper.html) | Identifies texture-poor color regions and large, nonlinear motion as challenges for animation interpolation; proposes animation-specific matching and refinement. | Do not assume successful natural-video methods transfer to generated painted cels. Test changing contours and missing features. This motivates a domain test; it does not establish the best current backend for our art. |
| [CoTracker repository](https://github.com/facebookresearch/co-tracker) | Provides point tracks and predicted visibility, manually selected queries and online/offline modes. Examples use PyTorch/CUDA. The repository describes most of the project as CC-BY-NC, with component exceptions. | A later comparison candidate, not a selected dependency. Confirm a usable local backend and applicable code/weight terms before adoption. Predicted visibility remains an estimate; no performance on this studio's cels has been measured. |
| [Video Textures, SIGGRAPH 2000](https://grail.cs.washington.edu/wp-content/uploads/2015/08/schoedl-2000-vt.pdf) | Shows that visually similar frames can have incompatible motion, using a pendulum moving in opposite directions. It compares temporal neighborhoods to preserve dynamics. | Inspect several frames around a join. Apply that lesson to deterministic authored loops; stochastic playback, blending and automatic cel reordering are separate choices. |
| [SWE-agent paper](https://arxiv.org/abs/2405.15793) and [interface documentation](https://swe-agent.com/0.7/background/aci/) | Study agent-facing interfaces for software engineering. Documented choices include concise search results, bounded file views, edit-time validation and explicit command feedback. | Design compact observations and validated batch actions. This is evidence about coding agents, not a benchmark of animation quality or this agent; transfer to our workflow is a design hypothesis. |

These sources support constrained correction and inspectable evidence. They do not justify automatic anatomical repair, a universal smoothness score, or a promise that more frames improve an animation.

## What I need as the operating agent

My useful work is choosing a coherent action, expressing constraints, inspecting evidence and iterating. Estimating exact coordinates from resized pictures, reconstructing mappings and remembering which nearly identical output was reviewed creates avoidable work and errors. A video playing in a browser does not establish that I observed every transition between tool calls.

| Likely obstacle | Tool behavior I would want | Verification |
| --- | --- | --- |
| Re-entering hashes, layouts, scene scale and clock | Initialize from a layer or pack; generate identities and mappings internally; show missing artistic inputs. | Start from an existing layer without manually copying hashes or calculating atlas geometry. |
| Marking every point in every cel | Select a few named reference patches, propagate candidates, and review difficult points. Reuse annotations only where source identity and geometry agree. | Compare annotation counts, wrong selected matches and correction rounds with the fully manual baseline. |
| Ambiguous crop coordinates | Each image has a stable view ID, cel ID and view-to-source mapping. Edits can reference that view. | Crop/resize/atlas-offset fixtures round-trip correctly; stale views cannot edit changed studies. |
| Intermittent visual observation | Exact transition strips, annotated local crops, landmark trails and short normal-speed clips with actual holds and a seam neighborhood. | A known one-frame defect appears regardless of browser sampling time. Record only the viewing actually performed. |
| Too much output or misleading highlight selection | Bounded summary and artifact manifest; worst issues, uncertainty, join and representative ordinary transitions; paged full index. | Omitted headline findings remain in full reports; control samples expose missed defects. |
| Repeating work after interruption | Save selected points, unresolved findings, rejected candidates and reasons. Resume shows changes and remaining work. | Resume with no chat history; avoid re-annotating unchanged cels or retrying unchanged rejected corrections. |
| Slow build cycles | Separate diagnosis from full scene/export checks. Cache captured inputs and unchanged analyses; identify dirty cels and expose progress for longer work. | Measure cold/warm latency; avoid recomputing unaffected inputs; cancelled work cannot appear finished. |
| Improving a score while damaging art | Show raw/corrected pixels, fit residuals, independent check points and intended deformation together. | A fit that damages another declared stable feature is detected independently. |
| A rigid solve repeatedly fails | Suggest revisiting correspondence, changing a rule, splitting a part, repairing a cel, inspecting alpha or correcting scene timing. | Contradictory constraints give an actionable next step instead of inviting identical retries. |

The current proof implementation in [assets.py](../../ambiance_studio/assets.py) confirms several gaps: one named landmark per proof operation, separately selected uniform cadence, an onion composite sampled from up to eight cels, and an anchor edit that changes exported coordinates without recalculating prepared playback. The [shared engine](../../editor/engine.mjs) supplies scene timing and transforms. These are code observations, not new visual judgments of the museum movie.

Large combined tool responses in this research session were truncated. That directly illustrates why the normal operator response should be a compact manifest with drill-down, even while retaining complete evidence. It is not a measured comparison of interface alternatives.

## Changes to the first-release design

### Useful inspection before complete annotation

Initialization resolves the study and source references; the analysis command produces an observation packet even before annotations are complete: source order, distinct/reused cels, actual exposure timing when scene-bound, existing anchors and raw transition views. Semantic constraints are still needed to label motion as wrong. An unconstrained point or region can be observed without stabilization.

The proposed `asset motion init --layer ID --out FILE` reads the selected project scene and dependencies. Keep the pack-based form. The agent normally authors named points, motion rules, masks and correction bounds; tools generate inspectable bookkeeping.

Add one validated batch-edit operation over the study, accepting expected study/view identities and saving a new version. Direct full JSON authoring stays supported. The browser uses the same semantics. Avoid a command for every GUI gesture.

### Simple propagation in the first usable release

Establish the manual solver first, then add a bounded classical adapter before the operational pilot. Use selected reference patches and translation search or sparse pyramidal tracking within explicit regions. Compare reference, forward and backward estimates; stop where evidence disagrees. Points remain proposed until selected in a saved study. Selection is an agent operation within the task, not a new human approval step for every point.

Reuse an available local implementation. If OpenCV is unavailable, report that capability honestly while manual operation continues; do not silently substitute a remote service or learned model. Record backend/settings and inspect a sample of apparently good tracks, since uncertainty ranking can miss confident errors. Learned tracking remains later.

### A saved observation packet

A version-bound packet contains a compact JSON manifest and rendered evidence. Each finding has stable IDs, source cels, presentation times where known, crop bounds, measurements/units, tested intention, visibility/uncertainty and a next-action hint. Include direct PNG/clip paths suitable for tool inspection; localhost URLs supplement them.

Provide three distinct views: raw registration, declared correction and optional inspection-only alignment. The last reveals shape differences but cannot supply corrected-motion measurements or overwrite a candidate. Include normal transitions as controls and retain an index of all analyzed transitions. Support fetching one finding or region without the entire study.

Packet generation and consumption work without browser playback. The browser remains useful for synchronized viewing and human judgment. Observations identify exact frames/clips and inspection method; starting a player does not record a completed watch.

### Loop evidence before new curve types

Bring seam neighborhoods, hold labels and sampled movement direction into the first release. They expose bad joins through the current renderer. Hermite interpolation and analytical world-contact/velocity checks remain later. Deforming drawings still require visual temporal evidence when transform velocities are known.

### Evaluation independent of fitted points

Distinguish fit landmarks from diagnostic-only landmarks with optional fixed constraints. Check points stay out of the solve while measuring whether correction helped or harmed them. Fitting one anchor perfectly does not establish that the object is stable. Unannotated anatomy remains unverified; pixels and inspection complement the points.

Keep fixed geometry and one resampling from original compiler inputs. Check whether reduced drift creates objectionable edge softness at intended display scale. Add more flexible models only after a sequence demonstrates the limitation of constrained correction.

## Failure classification and recovery

| Observation | First next action |
| --- | --- |
| Several fixed features agree on a displacement | Propose bounded whole-cel translation; inspect residuals and edges. |
| A point jumps to a similar mark while neighboring evidence disagrees | Correct correspondence or add a reference. |
| Paws remain plausible but the head changes size/anatomy | Inspect the raw cel; consider art repair or separate head animation. |
| Position is stable while alpha or edge color flickers | Use the existing alpha/edge proof and preparation tools. |
| Cels look sound but scene movement slides or stalls | Inspect holds, inherited transforms and scene path before changing art. |
| Endpoints resemble each other but movement reverses | Inspect the join neighborhood; author a closing segment or an allowed schedule change. |
| Cloud contours evolve without stable features | Keep shape change descriptive; inspect travel/coherence, then consider the cloud experiment. |

These are diagnostic routes, not claims that a cause is proven. State the supporting observation and remaining alternatives.

## Evaluation before broadening scope

Use three existing-art cases plus known-defect fixtures: a creature/seated figure, a wick-anchored flame and diffuse cloud/smoke. Include sparse poses, intentional deformation, occlusion, repeated patterns, faint alpha, lighting changes and uneven holds. Separate examples used to tune thresholds from examples used to evaluate them.

Measure correction quality against known injected displacement or independently authored evaluation landmarks; annotation count, wrong selected matches, unresolved points, preservation of intended motion and displayed edge quality. Separately measure operator turns, output volume, manual coordinate conversions, cold/warm latency, failed operations, repeated work after resumption and review rounds. These are proposed measurements, not results.

Compare the current manual workflow, the new manual workbench and the same workbench with propagation. Require the public CLI path and separate browser inspection. If propagation saves little work or yields confidently wrong points, keep it optional and improve observations. A superior tracking benchmark alone does not establish a better film-making tool.

This review selects no new production dependency or algorithm winner. Prioritize useful evidence, automatic bookkeeping, bounded repair and quick recovery from mistakes. Learned tracking, articulated deformation and cloud synthesis can use the same saved study/comparison interface when an actual sequence needs them.
