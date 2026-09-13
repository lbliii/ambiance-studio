# Finite clock and explicit local cycles (P03)

The opt-in version-1 `scene.clock` extends the existing scene evaluator. Absent
this extension, legacy modulo time, cel schedules, closed tracks and hidden-reset
rules remain in force. This implements the bounded engineering portion of
[mc/1 clock](architecture/model-contract/clock-v1.md). Full P00 production
acceptance, cues, sequence assembly and film evidence remain open.

```json
{
  "version": 1,
  "mode": "finite",
  "id": "shot-a",
  "revision": "shot-a-timing-v1",
  "duration_frames": 60,
  "local_cycles": {
    "flame": {
      "period_seconds": {"numerator": 1, "denominator": 1},
      "phase_turns": {"numerator": 1, "denominator": 4}
    }
  }
}
```

`canvas.fps` retains its existing positive integer schema. `canvas.loop_seconds`
remains the duration mirror, including on finite scenes. Authored integer
`duration_frames` is authoritative; the mirror must equal `duration_frames / fps`.
No count is reconstructed by multiplying that floating-point mirror. Arbitrary rational output fps is not enabled. `id` and
`revision` are required authored identifiers, not self-referential scene hashes.
Assign a stable timing revision label, change it when adopting another timing
definition, and capture the scene using the existing revision/receipt machinery.
Those external records pin the exact scene bytes and actual dependencies. The
clock label alone neither authenticates a revision nor proves an observation.

Finite output contains exactly frames `[0,N)`. Sampling negative time holds zero;
sampling at or after `N/fps` holds the authored endpoint at N, which can differ
from N−1. Held cel and visibility keys at N take effect, including per-cel sockets,
attachments and bound/light responses. Frame rendering may inspect this endpoint;
movie/proof source ranges must stay in `[0,N)` and start on an exact output frame.
Finite movie repetition is rejected. Encoder preroll holds the first pose and is
trimmed away; it does not append endpoint N. The browser Play control holds N−1
and restarts from zero on the next play. Its timeline also permits inspection of N.
Saved raster proof segments still repeat, explicitly for inspection.

`render proof`, `render video` and `render views-proof` accept `--start-frame N`,
mutually exclusive with `--start SECONDS`. The integer start and count survive
planning, raster sampling and receipt serialization. Display seconds never get
converted back into frame identity. With no duration, finite video selects all
remaining frames; proofs select up to three seconds of remaining frames. Thus a
60-frame shot started at frame 1 produces 59 samples, source `[1,60)`. Decimal
`--start` still requires exact frame alignment for finite output: use
`--start-frame 1` to express 1/24 second exactly. Nonzero finite source ranges with
audio are rejected before rendering; audio conformance is outside this package.

An optional `local_cycle` on a layer, camera or keyed finishing signal selects a
named cycle. Missing, empty and unknown references fail validation. Progress is
`(clamped_host_seconds / period_seconds + phase_turns) mod 1`. A layer's tracks
span zero through the local period, motion cycles use that period, and untracked
cels divide the local progress into equal intervals. The existing atlas
`cycle_seconds` stays required as a positive fallback but is inactive under an
explicit local cycle or cel track; `phase_frames` still offsets untracked cels.
Cel-sourced finishing signals follow the source state and cannot name another
cycle. Finite local cycles need not divide shot length. Loop-host local cycles
must divide its duration exactly. Local tracks must close or meet the existing
explicit hidden-reset rule; naming a local cycle never waives the seam rule.

Finite tracks without a local cycle span the scene duration and need not close.
The legacy `track_loop` field does not impose loop closure on finite host tracks.
No implicit track retiming occurs when the duration changes; author affected
tracks and clocks together in one `scene apply` transaction when needed.

## Public authoring and sampling

`scene clock --loop-seconds N` retains its existing operation. The additional
`scene clock --file clock-values.json` passes the same validated atomic operation
as `{"op":"clock","values":...}`. Its values allow `fps`, `clock` and
`loop_seconds`. Supplying `clock` derives the duration mirror from its frame count
and the selected fps. An explicit `loop_seconds` must agree with a supplied clock;
when changing an existing duration alone it updates that clock's frame count.
Dry runs, expected hashes and saved history use the existing transaction service.

```sh
./ambiance --project PROJECT scene clock --file clock-values.json --dry-run
./ambiance --project PROJECT scene sample --frame 59 --context
./ambiance --project PROJECT scene sample --frame 60 --context
./ambiance --project PROJECT scene sample --time 0.001 --context
./ambiance --project PROJECT scene timing
```

`--time` and `--frame` are mutually exclusive. Without `--context`, both return
the existing state array. With it they return `{clock,states}`. A subframe request
has `requested_frame: null`; it is never relabeled as an output frame. Timing
reports retain legacy fields and add endpoint/last-exported state summaries,
named cycle selection and evaluated contexts. Frame N is never added to sampled
presentation intervals.

## Shared API and exact arithmetic

`compileScene(scene,catalog).sample(seconds)` retains its array result shape.
`compiled.clock.seconds(seconds)` and `.frame(integer)` produce a frozen context;
`compiled.sample(context)` consumes it without another wrap. `.sampleFrame(f)` is
the direct frame convenience. Contexts can cross equivalent compiled snapshots;
different clock definitions reject. `consumerTime(context, cycleId?)` supplies
the evaluated seconds, duration and progress. Passing a serialized object as an
evaluated context is not supported: preserve the live context or explicitly
evaluate a new requested time. Camera, layers, attachments, bindings, finishing,
source placement/reparent and raster adapters consume this single clock.

`editor/clock.mjs` exports `rational`, `roundRational`, `frameToSeconds`,
`framesToSamples`, `samplesToFrames` and `secondsToFrames`. Python command/audio
adapters use equivalent snake-case arithmetic from `ambiance_studio.timebase`;
this module does not evaluate scenes. Fractions are reduced using integer
arithmetic. Numeric inputs and frame/sample indices must be finite and safe;
larger exact rational components serialize as decimal integer strings, avoiding
rounded JSON numbers. Numeric seconds retain their decimal value. Use the frame
API when the request is an integer frame rather than a rounded seconds value.

Conversions default to `exact` and reject fractional destination samples/frames.
Opt-in policies are `floor`, `ceil`, `nearest-half-away-from-zero`. Results contain
`value`, `exact`, `rounding`, and `residual` (rounded minus exact, in destination
units). Signed ties round away from zero. Existing audio cue anchors retain their
exact-sample rejection. Cue import/edit offsets and sequence conform remain
future consumers; no cue or sequence runtime is introduced here.

Render reports add `picture_clock`, `clock_engine_sha256`, `endpoint_policy`,
`last_exported_to_endpoint`, and the clock module in `renderer_sources`.
`source_start_frame` and `source_end_frame_exclusive` bind exact frame selections;
they are null when a legacy/subframe request has no integer source selection.
`rgba_endpoint_exact` reports measured endpoint-to-zero equality; false is valid
for finite output. It remains required for loops. These are single-scene picture
receipts, not P06 aggregate film evidence or artistic approval.

See the reproducible [technical replay](../examples/finite-clock/README.md).
