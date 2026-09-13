# mc/1 — shared time and audio/cue specimen

P03 owns the one finite/loop clock implementation, conversion/rounding helpers and evaluator integration. Models, characters, bindings, mouth cues and sequence consumers must call it. This packet selects semantics and input/output specimens; **it does not implement a second clock**. Public helper names and scene-extension spelling are for P03/coordinator to register. Existing `compileScene(scene,catalog).sample(seconds)` keeps its state-array result and legacy behavior when no finite extension is supplied.

## Clock boundary

The evaluated context must identify its contract version, mode (`loop` or `finite`), clock/shot ID and pinned definition/revision, rational fps, integer duration in frames, requested/effective time, whether the request is before/inside/at-or-after the end, and local cycle values. Integer frame requests preserve that index; subframe inspections retain their exact requested time and are not disguised as output frames. Passing already evaluated time to a model must not wrap it again.

Timebase fps is a positive rational `numerator/denominator`; integer fps is denominator 1. Use exact integer/rational arithmetic for frame/sample conversions, reducing fractions and rejecting unsafe/nonfinite inputs. Existing scene `canvas.fps` remains a number; its adapter must preserve existing supported values and results. First native finite acceptance uses 24/1 and existing integer profiles. Arbitrary rational output rates are not supported by today's evaluator and are not promised by this packet; rational arithmetic prevents conversion ambiguity. A rational field in a specimen is not a new currently accepted scene field.

Finite duration N exports exactly frames `[0,N)`, at `f/fps`. Finite inspection clamps negative time to zero and requests at/after `N/fps` to the authored endpoint pose. The endpoint at N may differ from the last exported sample N−1; it is a track boundary/inspection hold and **is never appended as a movie frame**. This distinguishes terminal authored pose from last-sample display hold. A player holding the final decoded frame holds N−1. Finite tracks begin at zero and end at N/fps, with no loop-closure requirement. At the endpoint, held cel/visibility tracks select their endpoint keys, per-cel sockets follow that selected cel, and attachments inherit that same final pose/visibility/opacity. Local cycles are evaluated at the clamped endpoint time and then held for later inspection; they do not keep advancing after the shot ends. P03 must report both endpoint and last-exported behavior.

Legacy loop time retains the existing modulo policy for negative and out-of-order seeks, loop track closure/hidden-reset rules, and frames `[0,N)`. No implicit migration or changed rounding of current cel schedules. An explicit local cycle has a positive rational period in seconds and phase in turns. Its evaluated progress is modulo one, independent of finite shot length. It can repeat 2.5 times inside a shot and ends wherever the shot ends. A loop host still needs compatible local-cycle closure or a supported explicit hidden/reset policy; “local cycle” must not silently waive a loop seam requirement.

Model defaults use local units/seconds, not a source-film fps/duration. Instance controls can request a phase/period; P03 converts/evaluates once. Stable control targets consume the resulting progress/selected cel under the shared engine. State selection, per-cel sockets, tracks, source bindings and camera must agree on the same evaluated context. Refactoring only `compileScene.sample` is insufficient: `sampleLayerMotion`, appearance/reparent timing, finishing signal evaluation, timing reports and render/receipt clocks are affected owners.

## Sequence and cue boundary

The smallest P05 sequence uses one output fps shared by its selected shots. Each selection pins a shot revision, output view, source frame range `[in,out)` and edit `at_frame`. For a straight cut at equal rate:

```text
edit_frame = at_frame + source_frame - in_frame
selection_length = out_frame - in_frame
```

Selections must stay in shot bounds; edit ranges cannot overlap accidentally or leave undeclared gaps. Time stretching, transitions and mixed-rate conform are outside this first slice and must reject or remain explicitly unresolved, not round silently. A duration edit changes downstream offsets and sequence identity; prior cue/coverage/movie evidence is stale until reconformed.

Audio-take identity names the selected byte hash, PCM hash, sample rate, channels, sample format, sample count and provenance. Sources live in audio-aware records. A drawing map pins the character definition/view plus stable drawing IDs. A cue record pins the take and drawing map, distinguishes imported alignment from authored corrections, and retains original sample intervals. Transcript/word timestamps are optional provenance, not phonemes; laughter is an authored event. A replacement take invalidates its cue import/corrections until explicit rebind/review.

Source, shot and edit coordinates remain distinct. Given a selected take's trim `source_in_samples`, placement `at_shot_frame`, and signed `offset_samples`:

```text
shot_sample(s) = exact_sample(at_shot_frame) + offset_samples + s - source_in_samples
edit_sample(s) = shot_sample(s) + exact_sample(at_frame - in_frame)
```

Audio output remains sample-exact. Existing `audio_cues.alignment` requires picture anchors to fall on exact PCM samples; preserve that rejection behavior. New helper calls may request a named rounding policy (`floor`, `ceil`, `nearest-half-away-from-zero`), but never choose it implicitly for a required exact anchor. Round only at the declared conversion boundary and record the residual rational error. P03 owns the implementation, including signed ties; P04/P05 consume it.

To display a mouth interval `[s0,s1)` on output-frame **sample instants**, use `[ceil(s0*fps/rate), ceil(s1*fps/rate))` after applying source/shot offsets and clipping to the selected shot range. This is interval membership, not nearest-frame rounding and not audio retiming. Report collapsed intervals as unpresented; never silently widen them. Gaps use a declared neutral drawing, and ambiguous overlapping mouth intervals fail until authored priority/correction resolves them. Retain audio-sample intervals even when no output frame presents them.

The [unequal-shot specimen](../../../tests/fixtures/model-contract/clock-cues.json) uses 24 fps and 48 kHz (2,000 samples/frame). Shot A has 60 frames; B has 96. Selecting A `[12,60)` at edit 0 and B `[6,78)` at edit 48 yields 120 frames (five seconds), with lengths 48 and 72. B's take starts at shot frame 18 with +500 samples offset and trims 2,400 source samples. Cue `[4,400,6,400)` maps to shot `[38,500,40,500)` samples and edit `[122,500,124,500)`, presenting shot frame 20 / edit frame 62. Tiny cue `[4,450,4,500)` presents no frame. The supplied PCM is generated silence for identity/conversion checks, not speech or an audition.

The specimen carries expected conversion and boundary tables. The test checks integer identities/equations and existing legacy APIs; **finite engine sampling, new conversion helpers, cue import and sequence encoding remain P03/P04/P05 implementation acceptance**. Do not treat arithmetic fixture success as those tools already existing.
