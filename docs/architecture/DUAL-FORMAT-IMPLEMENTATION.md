# Implementation plan: one scene, portrait and landscape

Decision recorded September 11, 2026, following the user's request to select the approach and plan implementation. **Status: implementation planned; no runtime feature is implemented by this document.** The earlier [analysis](DUAL-FORMAT-PLAN.md) records the code observations and alternative approaches.

Build one shared scene with two saved, static views. Author artwork, rigs, motion, finishing and sound once; inspect portrait and landscape together; produce both through one resumable iteration and present them in one delivery. Use a bounded shared-stage composite followed by uniform crop/scale for the first release. This preserves the existing finishing behavior and gives us a reference implementation for later optimization.

**Product scope and defaults**

- Standard targets: portrait at 1080 × 1920 and landscape at 1920 × 1080. Both share the picture clock and the selected soundtrack arrangement. Soundtrack roles retain their existing meaning.
- Plan both compositions before detailed artwork production. Portrait tests focal-action readability; landscape tests the broader environment. Plan backing and motion margins for both.
- Add an opt-in `project init --format dual` for blank projects. Its initial authored stage is 1920 × 1920 with centered portrait and landscape views. This is an editable starting composition, not automatic adaptation of the reference. Copy the reference unchanged and leave art/coverage checks open.
- Preserve current `project init` behavior when `--format` is omitted. Initially accept `--format dual` only with the blank template; reject it for the existing Last Lantern template instead of stretching its scene.
- Existing scenes may add contained views without moving any layers. A portrait scene can offer a landscape crop, but a full-width environmental adaptation may need a newly authored expanded-stage derivative and more painting. Automatic canvas rebasing, background generation and per-view restaging are outside this first release.
- Ship synchronized framing previews, format-aware exports, resumable production, orientation/soundtrack selection, exact feedback and handoff together as the complete feature. A framing-only milestone is an engineering proof, not completion of the feature.
- Start with one render/encode worker. Share assets, source selection and audio; keep both output jobs under one coordinator. Actual simultaneous encoding is a later measured optimization. The user can author and review both views together from the first preview milestone.

**Saved view contract**

Store an optional, versioned `framing` extension inside `scene/scene.json`. Keeping it in the scene gives view edits the existing project lock, dry run, scene history, expected-hash validation and revision snapshot behavior. Do not create another mutable view file that can drift from the scene.

The following is the selected target schema, to become executable in milestone 1:

```json
{
  "version": 1,
  "views": {
    "portrait": {
      "rect_scene_px": [420, 0, 1080, 1920],
      "output": {"width": 1080, "height": 1920}
    },
    "landscape": {
      "rect_scene_px": [0, 420, 1920, 1080],
      "output": {"width": 1920, "height": 1080}
    }
  }
}
```

This object is the value of `scene.framing` and the complete input to `view apply`. Rectangles are `[left, top, width, height]` in the **authored canvas pixel basis**, before output scaling. The scene's existing normalized geometry and depth-driven camera retain their semantics. Cropping occurs after that camera's effect on the scene; choosing a view does not change the camera pivot or the scene clock.

Contract decisions:

1. Keep scene version 1 with this optional extension, following the existing finishing precedent. Missing framing means legacy behavior. An older CLI cannot select the new views; rendering without a view intentionally remains a full authored-canvas operation.
2. Reserve the synthetic ID `authored` for the full canvas. It is always available and cannot be redefined. Named IDs use 1–32 lowercase letters, digits, underscores or hyphens, starting with a letter. Reject unknown fields, unsupported extension versions, duplicate JSON object keys and invalid IDs.
3. Require finite rectangle coordinates, positive dimensions and containment within the authored stage. Fractional coordinates are allowed: a landscape crop of a 1080-wide scene can be 607.5 scene pixels high. Use one uniform output scale; validate the aspect ratio with a documented relative tolerance of 1e-9. Never independently stretch the two axes or round each coordinate to an integer.
4. Require positive integer output dimensions. Retain existing 4096-per-side raster limits; native video still requires even output dimensions. Validate internal stage size as well as output size before allocating or creating an output directory.
5. Named views describe composition and preferred final size. A single-view `--width/--height` override changes resolution while preserving that view's ratio. Without `--view`, current full-canvas sizing remains unchanged. Do not add an implicit default that changes old render commands.
6. A framing edit cannot change artwork, geometry, timing, paint order or finishing. Add a `framing` scene-batch operation that replaces the full extension; `value: null` removes it. Route `view apply` through that operation and the existing transaction service.

`project.json` currently records a single `output`. Retain it as the legacy primary-output summary for compatibility; a dual initializer sets its dimensions to portrait and records `intended_views: ["portrait", "landscape"]`. Treat scene framing as the executable source of dimensions. Project inspection must distinguish authored stage, intended views and primary-output summary, and report discrepancies instead of silently synchronizing files during a read.

**Shared implementation and CLI surface**

Implement view validation, resolution, projection, canonical view identity and raster planning in a new `editor/views.mjs`, reused by Node and the browser. `editor/engine.mjs` validates the optional extension through that module. The Python adapter calls the existing JavaScript bridge for view semantics; it does not implement a second geometry resolver. Add a focused `ambiance_studio/views.py` adapter and extend `scene_commands.py`/`tools/scene-command.mjs` for transaction operations.

All commands in this table are implementation targets, not currently available commands:

| Interface | Result and operational contract |
| --- | --- |
| `view inspect [ID] [--revision REV]` | Available views, resolved rectangle/output, stage dimensions, uniform scale and applicable limits. Omitted ID returns a compact list. |
| `view apply FILE [--dry-run --expect-sha256 HASH]` | Atomically replace the working scene's complete framing extension; preserve a restorable scene snapshot. |
| `view check [--view ID ...] [--revision REV --out FILE]` | Validate selected views and their all-frame geometric coverage; default to all named views, or `authored` when none exist. Return view-indexed results and actionable failures. |
| `render frame/proof/video --view ID ...` | Select one resolved view. Existing action-specific options keep their meaning relative to that view. |
| `render views-proof --view portrait --view landscape --seconds 3 --long-edge 640 --out DIR [--revision REV]` | Save synchronized PNG sequences, a comparison page and a report for one to several explicitly selected views. One timeline and exact common sample times. |
| `review draft GATE --revision REV --view ID [--edition EDITION] --out FILE` | Create an unperformed review draft for that exact view; if an edition is supplied, require its view to match. Recording uses the existing review command and subject validation. |
| `iteration run FILE --by NAME` | Accept a version-2 recipe selecting views and soundtrack editions; run/resume all requested combinations. |
| `feedback add DELIVERY --view ID --role ROLE --time N --by NAME --note TEXT` | Bind an observation to one exact orientation/soundtrack movie. Omission of view is valid only when the role resolves unambiguously. |

For `views-proof`, `--long-edge` is a preview ceiling. Resolve each output to the largest integer multiple of its reduced aspect ratio within that ceiling. Do not apply one width to differently oriented frames. Use existing start/duration rules, normal-speed playback and frame seeking; a partial loop still has an arbitrary restart and is labeled accordingly. Keep initial paired proofs separate from disabled-layer/rig/look comparison matrices so variant combinations do not multiply silently. Single-view proofs can continue using their existing comparisons.

**Rasterization, finishing and coverage**

Keep `drawScene()` and `drawFinished()` operating on a full, uniformly scaled stage. Introduce a reusable stage-raster/view-extraction adapter used by `tools/render-scene.mjs` and the editor. A selected output is an unencoded crop/scale of that composite, with exactly one final resampling operation. Do not crop a compressed video or add a second picture encode.

For requested view rectangle width `rw` and output width `ow`, internal scale must be at least `ow / rw × supersample`. Choose a common uniform stage scale for paired proofs sufficient for the highest requirement, while preserving integer stage dimensions and the authored stage aspect ratio. Scale view rectangles by that same factor. If the stage exceeds 4096 on either side, reject before rendering with the required dimensions and suggestions to lower output size/supersampling or choose a less magnified view. Do not silently lower quality. Keep the exact legacy raster path for an implicit `authored` view so unchanged inputs preserve current output.

This stage-first approach retains light zones, receiving surfaces, shadow softness, reflections and their source-coordinate relationships. A simple outer Canvas transform would fail because the finishing implementation resets transforms and uses canvas-sized buffers. Stage-first cropping also means effects cannot recover content already clipped at the stage boundary; plan sufficient stage/backing margins and test that case explicitly.

Per-view checks must distinguish:

- Declared plate geometry against each view rectangle over every output sample, including camera extrema and attached motion.
- Actual composite alpha coverage before the canvas background fill hides holes, clipped to each requested view. Reuse the existing pixel-audit logic with view coordinates.
- View-raster endpoint and last-to-first measurements, plus visual review at each output's intended display size.
- Actual decoded movie dimensions, frame count, clock, seam and presented audio duration for every exported combination.

Retain `scene check` as the authored-stage check. `project check` includes the configured intended views and explicitly labels stage versus view results. Structural absence of a declared coverage plate is reported as unchecked, not as proof that artwork covers the frame. Do not infer focal-subject approval or valid platform UI safe areas from geometry.

**Revision and edition identity**

Continue capturing one immutable scene/catalog revision. The captured scene includes the full framing extension. Resolve views from the captured scene whenever `--revision` is supplied; a later working-scene edit cannot change that render.

Add a canonical `view_sha256` over the validated resolved view definition and a resolver version. Include the scene/revision identity, view ID/hash, authored rectangle, requested output dimensions, effective raster plan, supersampling and tool identities in every render report. Pin `editor/views.mjs` and the new stage adapter as tool dependencies alongside existing engine/finishing hashes. Keep actual output resolution in the render identity even when it differs from the named view's preferred output size.

Introduce edition schema version 2 with the resolved view identity and output expectations. Composition inherits view identity from the selected picture receipt; reject a declared mismatch. `media compose` must not label a portrait picture as landscape because both came from the same revision. Verification defaults derive from the bound picture/view and edition clock, not the working canvas.

Keep readers for existing version-1 editions, assigning them the synthetic `authored` view in memory. Do not rewrite sealed files. Update `read_sealed` callers with explicit supported versions **per record kind**; do not globally accept every schema version. The scene-containing revision format can remain version 1; new edition and delivery semantics require their own versioned readers/writers.

Extend review context with an exact view ID/hash and explicit subjects for named-view picture reviews; existing edition reviews inherit their edition's view. Use separate picture-review directories for named views while retaining the legacy `picture` location for `authored`. Reuse the existing gate DAG and validator: this release does not split them into a new shared/per-view gate engine. The same actual asset/audio evidence can be cited in multiple review records, but no pass is transferred automatically. A full-stage or other-view picture review cannot silently satisfy the new view's composition review.

Conservatively require new review records after a new revision is captured; preserve old reviews with their original subjects. Per-view identities prevent confusion within a revision; they do not promise selective carry-forward of approvals between revisions. `project overview` must show readiness for every requested view/edition, rather than reporting only the default movie's gate state. Release selection requires the relevant evidence for every requested delivery entry. Open human checks still allow presenting a labeled review delivery.

**Iteration, delivery and viewing**

Use iteration schema version 2 with an explicit view list, the existing soundtrack-edition list and a default `{view, role}` pair. Produce the Cartesian product. Per-view durations, per-view soundtrack mixes and layout overrides are deferred. Example target recipe:

```json
{
  "format": "ambiance-iteration",
  "schema_version": 2,
  "id": "dual-review-01",
  "revision": "dual-r1",
  "capture_selection": "plans/revision-selection.json",
  "views": ["portrait", "landscape"],
  "default": {"view": "portrait", "role": "score"},
  "editions": [
    {"role": "silent"},
    {
      "role": "score",
      "audio": "audio/runs/score/mix/master.wav",
      "audio_run": "audio/runs/score",
      "repeats": 3
    }
  ]
}
```

Each view receives one encoded picture; soundtrack editions reuse that view's compressed samples. Reuse each selected PCM master without regenerating or normalizing it. Match sample counts to the requested repeated picture duration as today. Keep encoder warmup, verified sync-frame trimming and AAC presentation checks intact.

Preflight the complete recipe, views, internal dimensions, audio and intended output paths before the first encode. Run keys include view, stage and role; persist their exact identity and generated edition IDs within existing filename limits. Store independent attempt/output directories. Retry an unchanged run by verifying and reusing completed steps and reconciling any edition receipt written before a crash. Keep one state writer; never let two workers overwrite `run.json` or select different current deliveries.

The default run presents only when the complete requested set is verified. A failed portrait step leaves a successful landscape artifact available and preserves the previous current delivery. An explicitly requested partial review can use delivery import/present with a clear scope note. Preserve the existing expected-selection check so a resumed run cannot replace a newer user selection unnoticed. Cross-revision render caches and concurrent encoders are follow-up optimizations, not prerequisites for resumption.

Delivery schema version 2 stores entries identified independently of soundtrack role. Require unique `(view, role)` pairs; each entry pins the revision, edition receipt, movie, verification and its own poster. Persist a default pair. Keep presentation records append-only and preserve legacy role-keyed deliveries through a reader adapter. Version-1 iteration recipes keep their one-picture semantics and remain resumable.

The library UI gains two independent choices: **Portrait / Landscape** and **Score / Effects only / Silent**. Show available combinations, dimensions and readiness; do not silently switch to another movie when a requested combination is missing. Preserve playback time when switching compatible editions and pause when needed to avoid an unintended jump. The framing comparison uses one shared source clock; two independently playing HTML video elements are not a synchronized proof.

Exact watch URLs include the delivery and selected pair, for example `?view=portrait&role=score`. Stable project-current links can request that same pair from the selected delivery. Media routes resolve an entry ID rather than assuming the last path component is a soundtrack role. Preserve old exact links and `?role=score` behavior for version-1 deliveries. Resolve legacy shorthand on version-2 records only through a documented default-view rule; reject invalid explicit pairs. Feedback always stores the resolved pair and exact movie hash. Handoffs list both orientation links and the open checks for each.

**Implementation milestones**

Implement in dependency order. Each milestone has a CLI path and saved evidence; add UI controls over the same operation only after the CLI path works.

| Milestone | Code and feature work | Acceptance artifact |
| --- | --- | --- |
| 1 — Saved views | Add `editor/views.mjs`, `ambiance_studio/views.py`, bridge validation/framing operation, CLI parsers/dispatch, dual blank initialization and project-summary consistency. Preserve transaction/history behavior. | CLI fixture defines both views, inspects them, rejects invalid geometry/stale edits and restores its prior scene. Its sampled rigs/timing remain unchanged by framing edits. |
| 2 — Paired picture proof | Add the stage/view raster adapter; extend `rendering.py`, `render-scene.mjs`, `editor/audit.mjs`, and `editor/editor.mjs`/HTML/CSS. Implement single-view renders and `views-proof`; add stage guides and synchronized output panes. | A moving layered fixture with cels, sockets, a fixed occluder and finishing produces paired normal-speed proofs. Compare each crop to an independently specified reference crop and inspect browser output. |
| 3 — Verified view editions | Extend `revisions.py`, render/compose/verify receipts and CLI review context. Update `studio.py` subject handling only where needed; add named-view review scopes and strict per-kind schema adapters. | Both orientations encode and fully decode with exact view/revision identity, correct sound duration and inherited composition provenance. A mismatched picture/view receipt is rejected; old edition/review fixtures still read correctly. |
| 4 — One run, one delivery | Extend `production.py`, `deliveries.py`, `studio_server.py` and `studio/studio.mjs`/HTML/CSS for iteration v2, entry selection, per-view posters, readiness, feedback and exact/current routes. | One CLI recipe produces the requested pair, survives an injected failure/crash, reuses completed outputs and presents one delivery. Browser switches view/role, preserves exact feedback identity and keeps old links working. |
| 5 — Production workflow and handoff | Document supported commands/contracts; update production/deconstruction/animation/release guidance and new-project templates for requested views. Run isolated and real-art pilots, record resource limits and remaining adaptation work. | Agent-operated production from a saved brief/recipe through paired proof, captured revision, verified movies and exact/current links, plus browser and full-resolution visual observations. |

Milestones 1–2 are the first reviewable engineering increment. Milestones 1–5 constitute the first complete feature. Continue each milestone within its authorized implementation scope; technical readiness checks are not new permission prompts. Estimated effort is relative: model/CLI work is smaller, renderer/finishing validation and delivery compatibility are the larger portions. Do not assign calendar promises before the raster and legacy-fixture checks establish the integration cost.

**Validation and pilot plan**

Add focused tests where they protect real behavior, using existing suites rather than duplicating the implementation:

- Geometry/transactions: new `tests/test-views.mjs` and CLI coverage alongside scene tests. Test fractional crops, preserved aspect/proportions and sockets, unchanged clocks, malformed/duplicate fields, immutable dry runs, stale inputs and restore.
- Raster: extend `tests/test_rendering.py`, `tests/test_finishing_render.py` and Node finishing/rig fixtures. Preserve legacy pixels at representative times; compare named-view output to a known crop of the same finished stage. Exercise light/shadow/reflection boundaries, alpha holes, magnified crops and rejected oversized internal rasters. Measure seams per output, not only on the uncropped stage.
- Evidence: extend `tests/test_revisions.py`, `tests/test_media_compose.py` and `tests/test_studio.py`. Test working divergence, altered captured framing, mismatched picture/view identity, old sealed records, separate view review subjects and per-entry release readiness.
- Delivery/resume: extend `tests/test_deliveries.py`, `tests/test_production_cli.py` and `tests/test_iteration_native.py`. Test two score entries in distinct views, duplicate-pair rejection, defaults/missing pairs, old URLs, exact feedback, interruption after receipt creation and stale current-selection protection.
- Run `./ambiance test` after shared changes; retain compiler, Node rig, link/package checks. Run native integration with `AMBIANCE_TEST_NATIVE=1` on macOS with media services, including `tests/test_iteration_native.py`. Explicitly report skipped native capabilities. Inspect the edited scene in the browser and actual decoded movies; numerical tests cannot stand in for either.

The independent fixture should have asymmetric surroundings, a focal rig, distinct cels, camera motion and visible receiving effects, so a stretched or incorrectly centered output cannot accidentally pass. Use simple existing/local fixture art; no paid generation is needed for engineering validation. Inject a coverage defect visible in only one view and verify it is attributed correctly.

For the real-art pilot, use isolated derivatives of the registered projects, preserving their originals and current deliveries. Last Lantern exercises the moving camera; The Midnight Collection exercises nested staging and multiple subjects. First evaluate contained alternate crops. Record honestly when a convincing landscape requires expanded art or a newly authored stage. A technically valid crop is not evidence of artistic success. Complete the feature's two-format art demonstration using suitable already available layered artwork; do not imply that this plan authorizes new paid generations or adaptation of accepted releases.

Record wall time, internal raster size and peak memory where measurable for single/paired proofs and representative exports, with and without finishing. The first performance decision is whether full-stage rasterization is acceptable at the target sizes. Optimize only demonstrated bottlenecks; a later direct-view renderer must match the stage-first reference before replacing it.

**Documentation integration and completion**

As capabilities land, update `docs/CLI.md`, `docs/SCENE-CONTRACT.md`, `docs/RENDERING.md`, `docs/REVISIONS.md`, `docs/STUDIO-LIBRARY.md` and the scene-transaction contract. Add executable view/iteration examples only with the implementation that accepts them. Add format intentions to brief/layer planning and carry each requested view through backing, edge-size, motion, encoded-output and release review. Make those changes in the relevant stage skills and workflow references; no additional global AGENTS rule is needed.

Update new-project gate descriptions to address every requested view without inventing new aesthetic approval stages. Existing projects retain their copied pipeline definitions; adoption of revised criteria must be explicit and recorded. Keep any existing phone/human checks unperformed until actual feedback identifies the exact movie. Named views do not require duplicate source generation or duplicate source auditions when the same evidence applies.

Completion means a production can be planned, edited, checked, rendered, resumed and presented in both orientations entirely through the CLI, with synchronized preview and unambiguous human review in localhost. The two movies share their source scene and soundtrack, preserve intended geometry, carry exact evidence, and remain individually identifiable through feedback and handoff.
