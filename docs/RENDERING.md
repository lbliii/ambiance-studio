# Rendering and encoded-media inspection

Version 0.7 adds [look-development artifacts and supersampling](LOOK-WORKBENCH.md). `render frame/proof/video --supersample 2` renders larger internal geometry before one reduction to the same output size. `render look-proof` uses the shared [finishing contract](FINISHING.md), records actual module and mask hashes, and provides editable, saved variants. `preview --look DIR` serves only the verified artifact files.

The CLI renders the selected project's saved scene through the same `compileScene()` and `drawScene()` implementation used by the browser. Project configuration determines the scene and catalog paths. Used atlas files must remain within the project and match their recorded hashes and dimensions. Renders preserve source files and write a **new output directory**, source snapshots, source/tool hashes and a report.

## Python service boundaries

[rendering.py](../ambiance_studio/rendering.py) retains command registration and
compatible entry points. [render_plan.py](../ambiance_studio/render_plan.py)
resolves dimensions, saved views, timing, proof recipes and captured PCM into a
`RenderPlan` before rendering or native compilation. The shared scene evaluator
continues to validate view geometry. [render_execution.py](../ambiance_studio/render_execution.py)
consumes the plan, executes raster/native work, composes snapshots and writes
reports. [media_operations.py](../ambiance_studio/media_operations.py) remains the
`MediaExecutor` boundary for edition preparation, execution and receipt recording.

[native_media.py](../ambiance_studio/native_media.py) exposes `capabilities`,
`native_binary(project)` and tracked `json_command` transport.
[media_verification.py](../ambiance_studio/media_verification.py) exposes
`verify_media(binary, source, out, width, height, fps, frames, audio_tracks,
loop_frames, contact_times=None, contact_frames=None)` and `requested_contacts`.
Verification retains actual decoding, input checks before/after decoding,
native provenance and exact contact hashes. Failed technical checks return a
saved unsuccessful report; invalid input or runtime transport raises the existing
structured command error. [media_inputs.py](../ambiance_studio/media_inputs.py)
owns the existing media path, identity and PCM rules without changing revision
reference or audio-session semantics. Preparation proof resume identities include
the extracted Python implementation files.

## Frames and motion proofs

```sh
./ambiance --project projects/the-midnight-collection render frame --time 6 --out projects/the-midnight-collection/render/frame-review-01
./ambiance --project projects/the-midnight-collection render proof --start 4 --seconds 3 --disable mummy-hands --out projects/the-midnight-collection/render/gesture-proof-01
```

`render frame` writes `frame.png` at the authored dimensions by default. `render proof` writes a self-contained local `index.html` plus PNG sequences, using width 360 by default and preserving the exact authored aspect ratio. Provide `--width` and optionally `--height`; both dimensions must be integers with exactly the authored ratio. No cropping or aspect-ratio conversion is implied. A width that cannot preserve that ratio is rejected.

The proof plays at the scene's actual frame rate by default. It includes pause, frame seeking and an optional half-speed view. Repeat `--disable LAYER` to add a synchronized comparison with the specified layers hidden. Their attached descendants inherit that visibility through the shared engine. This reveals the existing backing; it does not generate a clean plate or remove imagery baked into another layer. The project scene is unchanged.

Proof durations must contain an integer number of frames and fit within one visual loop; the default is three seconds or the scene's shorter loop duration. The selected segment repeats for inspection. If it covers only part of the authored loop, its restart is an arbitrary cut, not evidence of the full film's seam. A phone-sized desktop view is not a performed physical-phone check.

The report measures exact RGBA equality at the mathematical loop endpoints and the adjacent last-to-first RGB difference. These are technical measurements, not judgments about natural motion, registration or the encoded seam. Reproduction needs the same inputs and raster runtime; byte identity across different Canvas versions is not promised. Coverage explicitly initializes its layer smoothing, as does finished rendering, so the tested fresh and interleaved sequences use the same sampling policy.

## Saved portrait and landscape views

`render frame/proof/video --view ID` extracts one saved view after rendering the complete finished stage. `render views-proof --view portrait --view landscape --long-edge 640 --seconds 3 --out NEW_DIR` saves synchronized PNG sequences and a shared-clock player. Both use the same stage adapter as the editor. The output dimensions, source rectangle, view hash, internal raster and stage-adapter hash are recorded. Omitting `--view` preserves the full-stage sizing described above.

Use `preview --views-proof DIR` to serve the verified paired artifact. These proofs include per-view geometry and reduced-resolution alpha checks; each output also has its own endpoint/seam measurements. Video still encodes one selected view per command, with normal native verification. Named-view edition registration records the crop and actual decoded output. A version-2 iteration produces and presents the requested view/soundtrack set. See [saved views](VIEWS.md) for sizing, limits and runnable examples.

For each view with failing painted alpha, the paired proof now saves the actual worst-frame raster, a heatmap and JSON metadata under `_alpha-diagnostics/`. The full receipt lists their artifact-relative paths and hashes, and the existing proof page displays them. The metadata identifies source frame/time, view, source/runtime hashes, resolution, threshold, defect bounds and bounded coordinate samples. The all-frame audit can select a source frame outside the saved playback segment. Its raster precedes background fill and finishing, so the original transparency remains visible.

The current threshold remains alpha below 254, at an audit long edge of at most 240 pixels. The heatmap marks interior failures in magenta and the one-pixel perimeter in amber; classification does not change the failing result. Fine holes can disappear during reduction, and alpha cannot detect opaque unrelated paint or establish artistic quality. `preview --views-proof` verifies the diagnostic files and their metadata against the saved receipt before serving them; earlier proofs without diagnostics remain readable.

The audit retains its measured pixels directly, and diagnostic metadata records the actual alternating sequence. Coverage initializes `imageSmoothingEnabled=true` and `imageSmoothingQuality='high'` before drawing layers, matching the existing finished-layer and view-extraction policy. Previously, coverage inherited low quality from a fresh Canvas context or high quality from a preceding finished call. The Node Canvas 0.1.100 fixture at 0.125 seconds / 90×160 produced 114 versus 120 uncovered pixels, with 146 alpha pixels differing. Setting only smoothing quality reproduced either result, including with finishing disabled. The corrected fresh and alternating coverage both produce the former high-quality result (120); fresh/coverage-only rasters intentionally change. Alpha thresholds, audit resolution, view sizing, and finishing remain unchanged.

The bounded [render-sequence replay](../examples/views/reproduce_canvas_sequence.mjs) saves source/runtime/input identities, PNG and RGBA hashes, and comparisons for stage, portrait and landscape pixels. It tests fresh, repeated, out-of-order and interleaved coverage/finished calls with finishing on/off and supersampling 1/2/4. On the recorded fixture/runtime, the correction removed all 54 history-dependent comparisons and preserved all 216 finished captures byte for byte against the baseline. This is fixture evidence, not a claim about every Canvas implementation or artistic quality. The regression also compares each retained alpha diagnostic with a fresh seek. Run the replay with a fresh output directory:

```sh
node examples/views/reproduce_canvas_sequence.mjs --out work/canvas-sequence-replay
node tests/test-view-raster.mjs
```

Named-view render receipts and alpha diagnostic metadata already include `stage_adapter_sha256`, so the corrected sampling implementation has a distinct evidence identity. Old saved proofs remain verifiable historical artifacts with their original source hash; opening them does not rerender or certify them against current code.

In the retained alpha proof, the maximum remains 120 defects (110 interior, 10 boundary), but its earliest worst frame moves from 1 to 0: the initial coverage frame now also uses high smoothing. The existing earliest-worst tie rule is unchanged. The saved finished playback frames remain identical; the diagnostic image changes to the newly selected source frame.

## Native video export

```sh
./ambiance --project projects/the-midnight-collection render video --out projects/the-midnight-collection/render/picture-review-01
./ambiance --project projects/the-midnight-collection render video --repeats 3 --audio projects/the-midnight-collection/audio/masters/midnight-collection-v2.wav --out projects/the-midnight-collection/render/score-review-01
```

`render video` currently requires **macOS AVFoundation and Xcode command-line tools**. It compiles every `.m` translation unit in `native/media/` into a cache under the selected project's `.ambiance/native/`. The cache key includes the filenames and hashes of all `.m` and `.h` files, compiler version and host platform. A change to an extracted command or shared header creates a fresh cache entry. It does not assume ffmpeg. `ambiance doctor` reports separate raster and native capabilities; runtime discovery does not imply media-service execution has been tested. A restricted host may require access to local macOS media services to encode or decode.

The output uses H.264 High, BT.709 color tags, fixed frame timestamps, and no frame reordering. Default bitrate scales from 12 Mb/s at 1080×1920; `--bitrate` overrides it. Native dimensions must be even. `--seconds` can make a short encoder check; the default renders one whole authored visual loop. `--repeats` copies the compressed picture without a second image encode. It does not make a partial-loop segment seamless.

Every encode includes one complete visual loop of warmup frames. The retained picture starts only after the backend verifies an independent sync frame, then copies the compressed samples with timestamps shifted to zero. The intermediate warmup encode and trim receipt are retained. This preserves the fix for a demonstrated first-frame texture/quality dip in the original museum export. A sync-frame failure is explicit; the CLI never silently produces a dependent-frame trim.

After encoding, `encode-checkpoint.json` saves source identities and the intermediate hash before trimming. It is diagnostic evidence, not a successful render or verification receipt. If packaging fails, the completed intermediate can be inspected without repainting the scene.

Optional audio must be an existing stereo 48 kHz PCM WAV with exactly the final repeated picture duration. Its bytes are captured before picture rendering and retained as `selected-audio.wav`; that snapshot is encoded to AAC once inside the final mux. Pre-encoded AAC and missing or mismatched selected sources fail; no audio synthesis or source substitution occurs. This avoids a demonstrated AAC passthrough edit-list error of 2,112 samples. Audio arrangement remains a separate operation.

Successful `render video` automatically performs a complete native verification of its output. It writes `picture.mp4`, or `video.mp4` when composition is needed, together with `render-report.json` and `verification/`. The report names the exact output and whether the verification passed. An interrupted/failed fresh directory is diagnostic evidence and is never overwritten by a retry.

## Verify existing encoded media

```sh
./ambiance --project projects/the-midnight-collection media verify projects/the-midnight-collection/deliverables/final/the-midnight-collection-72s-score.mp4 --frames 2160 --loop-frames 720 --audio-tracks 1 --out projects/the-midnight-collection/reports/media-recheck-01
```

Without an edition selector, expected dimensions, frame rate and loop frames default to the selected scene. Expected total frames also default to one scene loop; specify `--frames` for a repeated edition. `--audio-tracks` defaults to zero without an edition selector. With `--revision ID --edition ID`, verification first matches the exact movie hash, then defaults dimensions, timing and audio tracks to that edition. Legacy editions derive expectations from their pinned decode report. Explicit expectation flags override defaults for diagnostic checks. Expectations can be set with `--width`, `--height`, `--fps`, `--frames` and `--loop-frames`.

Verification decodes all picture and audio samples and returns nonzero for incomplete decode, wrong dimensions/frame count/rate, unordered or mistimed picture timestamps, wrong track count, wrong audio rate/channels, or incorrect audio presentation duration. Decoded PCM must cover the presented interval contiguously; decoder allocation/copy/output failures fail explicitly. Media identity is hashed before and after decoding; a changed input invalidates the report. It reports raw audio sample counts separately from the samples presented within the intended timeline, including track starts, durations and edit segments.

Contacts include the start/end, cycle quarters and frames around each requested loop join. Decoded PCM is retained when audio exists. The report measures adjacent-frame differences at joins and compares the movie's first frame to later loop starts, making encoder startup inconsistencies inspectable. These differences are reported without an invented aesthetic threshold; moving pixels can legitimately differ. Human visual, listening and device reviews remain unperformed until actually recorded.

## Dependencies and regression checks

Raster rendering loads `@napi-rs/canvas` from normal Node resolution, then the user's bundled Codex runtime location if available. `AMBIANCE_CANVAS_MODULE` explicitly chooses an installed module; an invalid override fails rather than falling back. No dependency installation or provider call occurs. `AMBIANCE_MEDIA_BINARY` can explicitly choose a compatible native executable; its hash is included in media verification.

```sh
python3 -m unittest discover -s tests -p test_rendering.py
AMBIANCE_TEST_NATIVE=1 python3 -m unittest discover -s tests -p test_rendering.py
```

The native tests require actual macOS media-service access. They render an independent tiny scene, retain sync-frame warmup, compose a known PCM source, verify exact decoded presentation counts and repeated-picture equality, and prove wrong counts and compressed-audio inputs fail. The ordinary suite explicitly skips native execution where it is not requested. Canvas-dependent tests skip when that optional dependency is absent.

Sources: [Python CLI adapter](../ambiance_studio/rendering.py), [shared-engine raster adapter](../tools/render-scene.mjs), [native backend](../native/media/media.m), [regressions](../tests/test_rendering.py).

The JavaScript entry point handles stdin/stdout and cancellation setup. The
[render job](../tools/render/job.mjs) coordinates validated inputs, shared-engine
rasterization, output modes and receipt finalization. Proof presentation and
[native process transport](../tools/render/native-process.mjs) have separate
owners; the transport retains child ownership, backpressure and encoder failure
propagation. Relative Canvas overrides retain their original entry-directory
resolution. Saved proof HTML and PNG naming remain unchanged.

Native command dispatch delegates to [encode](../native/media/encode.m),
[compose and trim](../native/media/compose.m), [decode verification](../native/media/verify.m),
[audio presentation verification](../native/media/verify_audio.m), and
[inspection](../native/media/inspect.m). Shared helpers are limited to native
failure, fresh-output checks, asset opening, JSON emission and writer readiness
and completion. Compressed picture payloads and PCM presentation calculations
retain their existing contracts.

New render reports add `renderer_sources`, mapping the entry point and extracted
JavaScript owners to their hashes. Preparation-proof resume checks those files
as well. Native verification and composition recipes add `native_sources`, with
per-file hashes and a combined `sha256` from the
[native source inventory](../ambiance_studio/native_sources.py). Existing
entry-file hash fields keep their original meaning, and existing artifacts are
not rewritten. An explicitly selected native binary is identified separately
by its executable hash; source inventory does not certify how an override was
built.

`tests/test-render-transport.mjs` exercises real child-process failures,
backpressure and cancellation. `tests/test_native_sources.py` covers source and
header cache invalidation and native raw-stream rejection, AAC encoding and
inspection. These are part of `./ambiance test --require-native` alongside the
existing native compose, recovery and proof-integrity cases.

## Captured revision rendering

`render frame`, `render proof`, `render rig-proof`, and `render video` accept `--revision ID`. The revision reader verifies captured documents and pinned dependencies, supplies explicit captured scene/catalog paths, and checks integrity again after rendering. There is no fallback to the working scene. The report records the revision ID and manifest hash along with the actual rendered scene/catalog hashes.

`render video --revision ID --edition ID` can register the resulting edition through the revision adapter. Edition registration is separate from rendering and happens only after successful technical verification. Where selected audio differs from the captured sound selection, the revision adapter requires explicit sound dependencies through `--audio-run`, `--audio-session`, or `--audio-provenance`; these paths are project-relative. Merely naming a session does not establish that an independently supplied PCM master was produced by it. See the revision contract and CLI documentation for the accepted provenance types.

## Rig inspection matrix

```sh
./ambiance --project PROJECT render rig-proof INSPECTION.json --out NEW_PROOF_DIRECTORY
```

The version-1 recipe contains explicit `samples`, normalized `regions`, and `comparisons`. Each sample names an `id`, a `time` within `[0, loop_seconds)`, an optional label and optional `overrides` keyed by existing layer ID. Supported override fields are `x`, `y`, `scale`, `rotation`, `opacity`, `visible` and `cell`. The shared engine validates every candidate before the output directory is created. Forced values replace matching tracks; position/rotation overrides also suppress their corresponding sinusoidal offset for that proof variant. Unsupported or invalid overrides fail.

A `visible: false` override stays false even when an authored visibility track exists. The report lists explicitly hidden layers, effectively hidden layers, zero-opacity layers and descendants hidden by a parent. This matters when hiding the body also hides its attached gesture. The backing is not repainted or certified clean.

Each region has an `id` and `rect: [x, y, width, height]` in normalized full-frame coordinates. It must fit entirely within the image. Comparisons name `left` and `right` sample IDs. Optional `difference: true` produces an absolute RGB difference image; `difference_gain` sets its display amplification, default 4, while reported metrics use unamplified pixels. All samples include full scene context and detail crops; comparisons include side-by-side context and details.

Optional `playback_seconds` produces an actual-speed player containing all variants, each beginning at its declared sample time. Such targeted segments may restart at arbitrary points in the film. The report explicitly distinguishes these selected samples and endpoint measurements from a complete-loop visual review. Labels such as “accepted gesture” are authored descriptions, not automatic approval.

Rig-proof reports set continuous-clip `frames`, `seconds`, and `start_seconds` to null. They record `scene_loop_frames`, `saved_sample_frames`, `saved_playback_frames_per_variant`, and `saved_playback_frames_total` separately; these counts exclude detail crops, comparison images, and endpoint measurements.

Optional `inventory` is an existing project-relative inventory path; `part_ids` must name entries in that inventory's `items` array. This binds the proof to the existing worklist without creating another inventory. Explicit recipe/output CLI arguments remain shell-relative. The proof saves the recipe, exact source identities, PNG hashes and comparison regions. See the [runnable independent compound fixture](../examples/rig-proof/README.md) and its [inspection recipe](../examples/rig-proof/compound-inspection.json).

## Reuse encoded picture for soundtrack editions

```sh
./ambiance --project PROJECT media compose PICTURE.mp4 --audio SCORE.wav --repeats 3 --out NEW_SCORE_EDITION
./ambiance --project PROJECT media compose PICTURE.mp4 --audio AMBIENCE.wav --repeats 3 --out NEW_AMBIENCE_EDITION
```

`media compose` reads compressed picture directly; it does not invoke Canvas or the raster renderer. Its current boundary is one CFR H.264 video track with positive integer frame rate, zero start time, an independent first frame, exact timing and a final raster orientation encoded without a track transform. Unsupported codecs, transformed tracks and VFR fail explicitly. The selected stereo 48 kHz PCM WAV must match the final repeated duration. Existing audio tracks in the input movie are ignored and **replaced by the explicitly selected PCM**; input and output track counts are recorded.

Picture and PCM inputs are copied into the fresh edition directory as independent snapshots. The receipt binds their original paths, bytes and hashes, the native source/binary and host, the composition recipe and final output identity. Original inputs and snapshots are checked for changes during processing. Verification decodes the whole result and compares the elementary compressed video sample hash sequence against the original sequence repeated N times. A new MP4 container hash is expected; unchanged compressed picture payloads establish picture reuse.

An edition can be bound with `--revision ID --edition ID`. To prevent attributing an arbitrary movie to that revision, the revision adapter requires the picture to be already bound to the revision or explicitly supplied through `--picture-receipt FILE`, an existing project-relative render report that identifies the captured scene/catalog and picture hash. The manifest is never rewritten by composition. Named-view composition inherits the exact picture view and output dimensions. Optional `--view ID` asserts that identity and rejects a mismatch; it requires edition registration. Without edition registration, ordinary composition remains available.

The output directory contains `picture-input.mp4`, `selected-audio.wav`, `composition-recipe.json`, `video.mp4`, `compose-report.json` and `verification/`. Source changes, failed decode or a differing compressed sample sequence produce a failed result and no accepted edition.

## Request action-specific decoded contacts

```sh
./ambiance --project PROJECT media verify VIDEO.mp4 --frames 2160 --audio-tracks 1 --contact-time 3.67 --contact-time 18.13 --contact-frame 719 --out NEW_CONTACT_REVIEW
```

Repeat `--contact-time` and `--contact-frame` as needed. For supported CFR media, a timestamp selects the displayed frame containing it: `floor(time × fps)`. Values within `1e-7` frame of an integer boundary snap to that boundary to absorb floating-point representation error. The time itself must be finite and within `[0, duration)`; indices must be integers in `0..N−1`. Out-of-range requests fail before a report directory is created. At 30 fps, 3.67 seconds selects frame 110 and 18.13 seconds selects frame 543.

Requested contacts are retained alongside standard start/end, cycle-quarter and seam contacts. Each requested result records its original request, actual frame index, presentation timestamp, resolved PNG path and hash. VFR contact selection is unsupported; expected timing/decode checks must pass before this report is usable.

The additional native integration suite is:

```sh
AMBIANCE_TEST_NATIVE=1 python3 -m unittest discover -s tests -p test_media_compose.py
```

It exercises public CLI composition, two soundtrack editions, exact elementary-payload reuse, explicit input-audio replacement, requested contact hashes, mismatched duration, changed-source rejection and revision-context rendering on independent fixtures. Native execution still requires actual macOS media-service access.
