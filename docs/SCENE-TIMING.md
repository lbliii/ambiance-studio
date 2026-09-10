# Timing reports from the renderer's clock

`./ambiance --project PROJECT scene timing [--layer ID --out FILE]` returns a version-1 timing payload inside the existing CLI JSON envelope. `project check` uses the same report through `kit.py`. Reporting does not change the scene or rendered sampling. Node is required so Python does not implement another cel/track/visibility evaluator.

The report separates authored source-cel intervals from their presentation at the export clock. A rat can have eight source cels, a dormant 24-second fallback cycle and an explicit 10/15-Hz gait schedule. Dividing eight by 24 describes only its unused fallback.

| Field | Meaning |
| --- | --- |
| `timing_driver` | `cell_track` when an explicit cell track wins; otherwise `cycle` for a multi-cel atlas or `static` for one cel |
| `fallback_cycle` | Declared seconds, phase, nominal `frame_count / seconds`, and whether this fallback drives the layer; null for a plain image |
| `authored.holds` | Maximal consecutive intervals selecting the same source cel; repeated identical key values merge |
| `authored.rate_segments` | Consecutive holds with equal duration; `cel_selection_hz` is populated only for runs of at least two holds, otherwise null |
| `sampled.segments` | Output-frame intervals with the same cel, inherited visibility, zero-opacity state and render eligibility |
| `sampled.unpresented_authored_holds` | Authored intervals for which no output-clock sample selects that cel during the interval |
| `sampled.effective_visibility_windows` | Frame intervals where the layer and its ancestors permit visibility |
| `sampled.zero_opacity_intervals` | Frame intervals with exactly zero effective multiplicative opacity |
| `sampled.render_eligible_windows` | Frame intervals that are both visible and nonzero-opacity |
| `join` | Declared loop policy, first/last render eligibility, and counts of leading/trailing nonrendered frames |

Top-level `picture_seconds`, `output_fps` and `output_frames` identify the sampling clock. Frame intervals are half-open: `start_frame` is included, `end_frame_exclusive` is excluded. Corresponding sampled seconds use those frame boundaries. Authored intervals retain exact saved key times. Rate equality uses a `1e-9`-second tolerance for arithmetic noise; a variable schedule remains multiple intervals rather than one average rate.

`authored.cel_changes` counts changes inside `[0,T)`; `authored.seam_cel_change` separately compares the last authored hold with the first. Sampled transition counts compare adjacent output frames; seam change is again separate. `render_eligible_cel_transitions` counts a transition only when both adjacent samples are render eligible. A cel interval can be sampled while hidden; `unpresented_authored_holds` describes sampling, not human perception. Use the visibility windows alongside it.

The evaluator samples exactly frames `0..N-1` at `frame / fps`. The endpoint key at T declares closure and is never appended as a duplicate frame. Fractional/subframe holds can disappear at the output clock. The report handles automatic phase offsets, hold tracks and parent inheritance through the shared engine. It does not determine whether artwork looks distinct, is offscreen, is behind a painted occluder, or is perceptible on a phone. Hidden-reset contract validation remains the engine's responsibility; a nonrendered seam report is not a replacement for an explicit required visibility track.

Automatic cycling retains the existing evaluator's `1e-7` cel-unit tolerance before `floor`, which stabilizes floating-point cycle boundaries. Timing reporting does not introduce a new quantizer or change that tolerance. Explicit cell tracks retain their saved hold-key semantics.

For compatibility, `project check` retains `cycles[].seconds` as declared fallback information. Automatic cycles retain their numeric `cel_fps`; **a cell-track override now reports `cel_fps: null`**. New `timing_driver`, `fallback_cycle` and `timing_summary` fields identify why. Consumers that require the running gait rate should read the authored rate segments or sampled transitions. One-cell atlases retain their legacy nominal numeric result even though their timing driver is static.

Reports are bounded to two million layer samples and 100,000 automatic authored cel intervals per layer. Exceeding either limit is an explicit failure, never a truncated success. A layer filter limits output rows but still evaluates the full dependency graph.

Create the [independent placement fixture](../examples/source-placement/create_fixture.py) for a runnable project and regular gesture clock. The [rat-route batch](../examples/scene-transactions/rat-route-batch.json) supplies explicit cell/visibility tracks. `node tests/test-source-placement.mjs` covers automatic and static clocks, 10/15-rate segments, repeated values, variable holds, inherited visibility, fractional key times, missed holds and a hidden join.
