# Ambiance CLI

The supported entry point is `./ambiance` in the repository, or its absolute path from another directory. `python3 -m ambiance_studio` also works from the repository. There is no wheel or global shell installation in this version.

## Project selection and output

The [studio library](STUDIO-LIBRARY.md) provides shared discovery, exact/current movie links, recorded iteration runs and feedback. Start with `./ambiance studio open`. Registered IDs work with `--project ID` across worktrees; use `studio register PATH` for other project locations. Global `--registry FILE` or `AMBIANCE_REGISTRY` selects an isolated registry.

Use `ambiance --project PATH COMMAND`, placing the global project option before the command. Without it, the CLI searches the current directory and its parents for `ambiance-project.json`. This small file points to `scene/scene.json` and `assets/catalog.json` within the project. Source paths never depend on the original chat location.

Each finite command writes one JSON result to stdout: `ok`, `schema_version: 1`, `command`, and `data`. Errors contain `error.code` and `error.message`. Exit codes: 0 success, 1 failed checks, 2 invalid input or a locked project, 3 missing runtime/runtime failure, 130 interruption. Help/version are plain text. Preview prints one startup JSON object and serves until Ctrl-C; HTTP request logs go to stderr.

`--out` on check/test commands writes the same result envelope to a file. CLI checks do not close quality gates; they are evidence for a separate review.

`--out` on asset proofs, rendering and media verification instead names a **fresh artifact directory**. Those commands save their own reports alongside actual outputs. Audio outputs are immutable directories under the selected project's `audio/runs/`. Explicit recipe/batch/render paths are relative to the shell working directory; audio session and source paths are project-relative as described in the audio contract.

Revision selections and asset/placement manifests use project-relative references. Their explicit command input/output filenames retain shell-relative semantics. `revision handoff --out` also creates a fresh artifact directory. Revision-aware commands identify working divergence separately from captured input integrity and review verdicts; see [revisions and editions](REVISIONS.md).

## Implemented commands

| Command | Effect |
| --- | --- |
| `doctor` | Report runtime paths and executable capability availability |
| `project init DIR [--reference FILE] [--title NAME] [--template blank or last-lantern] [--format dual]` | Create an isolated workspace atomically; optional dual framing requires the blank template |
| `project list [--directory DIR]` | List registered/main-checkout projects, or limit discovery to child projects in DIR |
| `studio register PATH [--id ID --relocate]` | Register or explicitly relocate a canonical local project address |
| `studio open [--port N --no-browser]` / `studio serve [--port N]` | Start/reuse the background film library, or serve it in the foreground |
| `studio status` / `studio stop` | Identify or stop the current registry's server |
| `project latest [--channel review/release]` | Resolve the current selection to its exact movie and watch links |
| `project overview [--out FILE]` | Current movies, working divergence, open criteria, available work and recent runs |
| `delivery import FILE [--dry-run]` | Register an immutable movie set from captured editions or identity-bound legacy reports |
| `delivery list` / `delivery inspect ID` | Inspect movie roles, identity and availability |
| `delivery present ID --by NAME [--note TEXT --channel review/release --expect-selection HASH]` | Select a review or evidence-qualified release; preserve selection history |
| `delivery handoff ID --out DIR` | Write a fresh handoff containing watch links, hashes and open checks |
| `iteration run FILE --by NAME` / `iteration list` / `iteration inspect ID` | Run/resume capture/render/compose/verify/register/present recipes and inspect durable progress |
| `feedback add ID --role score/effects/silent --time N --by NAME --note TEXT` / `feedback list ID` | Save/read exact-movie observations and timestamps |
| `project status` | Read actual evidence/dependency freshness |
| `project check [--out FILE]` | Check this project's asset integrity, scene graph, timing, attachments and geometric coverage |
| `asset list` | Inspect this project's catalog |
| `asset build RECIPE --out DIR` | Run the existing Pillow compiler with its immutable cache policy |
| `asset motion init/inspect/check/edit/analyze/solve/track/proof` | Source-bound cel studies, validated observations, bounded translation, patch proposals and synchronized proofs; see [cel motion](CEL-MOTION.md) |
| `preview --motion DIR [--port N]` | Serve a verified motion proof with in-memory draft recalculation |
| `asset inspect PACK` | Inspect metadata/report and verify built output hashes |
| `asset proof PACK_OR_ID --out DIR [--catalog FILE --landmark NAME --fps N --width N]` | Produce contact sheet, onion skin, playback and an HTML source-anchor editor |
| `asset preflight SOURCE --out DIR` | Decode image/channel/alpha facts and produce light/dark/alpha previews |
| `asset request record/reconcile/inspect` | Durable local generation-result recording and selection; never submits requests; see [provider recovery](PROVIDERS.md) |
| `asset prepare init/inspect/check/edit/build/proof/place` | Structured compound preparation, bounded immutable edits, source-mapped placement and resumable saved-view proofs; see [agent preparation](AGENT-PREPARATION.md) |
| `asset prepare [SOURCE --backing FILE] [--recipe FILE] --out DIR` | Create or rebuild an interactive separation workspace with distinct masks, alignment, compiler recipes and a shared-engine movement scene |
| `asset crop SOURCE --recipe FILE --out DIR` | Export a source crop with preserved coordinate/identity mapping |
| `asset return EDIT --mapping FILE --out DIR` | Return explicitly registered edited art as a native patch and composite derivative |
| `asset edges PACK_OR_ID --display-width N --out DIR` | Inspect every cel at intended display size on light/dark backgrounds, with optional explicit context placement |
| `asset edge-repair SOURCE --recipe FILE --out DIR` | Prepare an immutable, registered alpha/matte-color repair with source and recipe snapshots |
| `asset admit PACK` | Add a compiled pack within the project to its catalog; protect existing IDs |
| `library find [QUERY] [--directory DIR]` | Find assets and real proof paths across bundled and initialized project catalogs |
| `library inspect ID [--catalog FILE]` | Inspect exact source metadata, integrity and decoded cel counts |
| `plan inspect/check/next [--inventory PATH --out FILE]` | Reconcile intended parts, actual evidence, dependencies and remaining work; next returns five ready items by default (`--limit N`) |
| `plan spec inspect/check [--details --out FILE]` | Validate canonical production intent and source identities; report legacy required-flag contradictions |
| `plan spec apply FILE [--dry-run --expect-sha256 HASH]` | Apply explicit scope revisions with a reviewable diff and preserved plan history |
| `plan spec migrate FILE --original PATH [--original PATH] --out DIR` | Preserve original notes/inventory and emit an authored migration candidate/diff without saving it |
| `plan complexity [--out FILE]` | Separate workload dimensions and declared coverage counts, without an aesthetic score |
| `plan check --require-complete [--inventory PATH --out FILE]` | Also fail empty or unfinished declared production scope; report remaining items without certifying artistic quality |
| `scene inspect [--full]` | Return the summary, or complete authored scene including camera/groups |
| `view inspect [ID] [--revision ID]` | Inspect saved framing, preferred dimensions, projection and exact view identity |
| `view apply FILE [--dry-run --expect-sha256 HASH]` | Replace framing through a validated, restorable scene transaction |
| `view check [--view ID ... --revision ID --out FILE]` | Check geometric coverage/attachments for selected view rectangles at every output frame |
| `scene apply FILE [--dry-run --expect-sha256 HASH]` | Validate an atomic batch; preview or save one restorable transaction |
| `scene track LAYER FILE [--dry-run --expect-sha256 HASH]` | Author deterministic movement/cel tracks through the same transaction path |
| `scene timing [--layer ID --out FILE]` | Report actual timing, holds, authored rates, output-frame sampling and inherited visibility |
| `scene place FILE [--dry-run --expect-sha256 HASH]` | Resolve source-coordinate placement and save a validated batch |
| `scene reparent LAYER --to PARENT --socket NAME --keep-world --at N [--dry-run --expect-sha256 HASH]` | Preserve world geometry/appearance at one reference time; report changed inheritance |
| `scene sample --time SECONDS` | Return sampled matrices, source rectangles, cels and sockets |
| `scene add ASSET --id ID [--name NAME] [--x N --y N --width N --depth N]` | Add an instance using the asset's default pivot |
| `scene set LAYER [--x N --y N --scale N --rotation-deg N --opacity N --depth N --cycle-seconds N --phase-frames N]` | Validate and atomically save an authored change |
| `scene socket LAYER NAME --u N --v N` | Define an object-local normalized static socket |
| `scene attach CHILD --to PARENT --socket NAME [--offset-x N --offset-y N]` | Attach a child, inheriting its parent's depth/group; preserve its authored motion |
| `scene check [--out FILE]` | Technical asset and authored-stage check; project check also inspects intended views when configured |
| `scene history` | List preserved snapshots |
| `scene restore SHA256` | Validate and restore a snapshot; preserve the current scene first |
| `revision capture ID --selection FILE [--dry-run --expect-selection-sha256 HASH]` | Capture control snapshots and pin typed dependencies; never transfer pass verdicts |
| `revision inspect ID` / `revision check ID [--out FILE]` | Inspect a captured manifest or verify actual pinned dependencies |
| `revision compare ID --working [--out FILE]` | Show working divergence separately from captured integrity |
| `revision handoff ID [--edition ID] --out DIR` | Save a new handoff with exact artifacts and outstanding checks |
| `review draft GATE [--revision ID --edition ID --view ID] --out FILE` | Create an unperformed legacy or revision-bound review draft |
| `review record FILE` | Record actual criteria/evidence with the existing gate tool |
| `look inspect/check [--time N --out FILE]` | Validate grades, light signals, receiving surfaces and actual typed dependencies |
| `look apply FILE [--dry-run --expect-sha256 HASH]` | Save a complete finishing recipe through the scene transaction path |
| `look export --out DIR [--include-rig]` | Package a look and optionally its mounting, cel/track, group and layer definitions |
| `look import PACKAGE --bindings FILE [--include-rig --dry-run --expect-sha256 HASH]` | Rebind a package to explicit targets; rig adoption requires matching canvas/clock and exact rig assets |
| `preview [--port N] [--look DIR or --prepare DIR or --views-proof DIR]` | Serve the selected project or verified artifact; preparation supports in-memory draft editing and recipe downloads without project writes |
| `render frame --time N --out DIR [--revision ID --view ID]` | Render an actual PNG from the shared scene evaluator and drawing code |
| `render proof --out DIR [--revision ID --view ID --start N --seconds N --disable LAYER --width N]` | Render a normal-speed HTML comparison with frame seeking and optional disabled layers |
| `render views-proof --view ID --view ID --out DIR [--revision ID --start N --seconds N --long-edge N --supersample 1/2/4]` | Save synchronized crops of each finished stage frame with per-view coverage, seam and frame-hash evidence |
| `render rig-proof FILE --out DIR [--revision ID --width N]` | Render named poses/hidden-part variants, detail crops, differences and optional playback |
| `render look-proof FILE --out DIR [--revision ID --width N --supersample 1/2/4]` | Save interactive baseline/variant comparison, grading/light controls, passes and downloadable transactions |
| `render video --out DIR [--revision ID --view ID --edition ID --seconds N --repeats N --audio WAV --width N --height N --bitrate N]` | Encode H.264, optionally mux PCM, and verify output; edition binding retains exact named-view identity |
| `media compose PICTURE --audio PCM --repeats N --out DIR [--revision ID --edition ID --view ID --picture-receipt FILE]` | Reuse compressed picture samples with selected PCM; verify the resulting edition |
| `media verify FILE [--revision ID --edition ID --view ID] --out DIR [--frames N --loop-frames N --audio-tracks 0/1 --contact-time N --contact-frame N]` | Completely decode video/audio, check timing and save join/requested-contact evidence |
| `audio inspect SESSION` | Validate explicit selected PCM sources and inspect arrangement/levels |
| `audio import-stems SESSION --session-id ID` | Preserve a legacy session and create a new executable session from its rendered stems |
| `audio mix SESSION [--run-id ID --start N --duration N --solo STEM --mute STEM --gain STEM=DB]` | Render a versioned circular arrangement, aligned stems and numerical reports |
| `audio compare SESSION --variant-b FILE [--run-id ID --start N --duration N]` | Create matching A/B excerpts without automatic normalization |
| `audio check WAV_OR_RUN` | Inspect PCM or verify a saved run's hashes, timing and stem reconstruction |
| `test [--out FILE --artifacts DIR --require-native]` | Run Python/Node regressions and package audit; save bounded JSON/JUnit/log evidence with exact inputs |

A blank project is the default for new artwork. It has no layers; its technical check deliberately reports incomplete until prepared assets and a scene are added. The explicit Last Lantern template copies the existing assets into the project, so editing one project cannot modify another's catalog or artwork.

[Saved views](VIEWS.md) support portrait/landscape project setup, framing edits, checks, synchronized previews, paired raster proofs and single-view video export. Omitting `--view` preserves full authored-canvas rendering. Version-2 iteration recipes produce the Cartesian product of views and soundtrack editions, with resumable steps and one combined delivery.

Detailed contracts and examples: [inventory and asset proofs](PRODUCTION-INVENTORY.md), [crop/return preparation](ASSET-PREPARATION.md), [scene transactions](architecture/SCENE-TRANSACTIONS.md), [authored tracks](SCENE-CONTRACT.md), [rendering/media](RENDERING.md), [audio sessions](AUDIO-SESSION.md), [revisions and editions](REVISIONS.md). Edition audio may cite `--audio-run`, `--audio-provenance` or additional `--audio-session` inputs; their provenance requirements are described in the revision contract.

Track files contain `version: 1`, a `tracks` object and optional `track_loop` (`closed` by default). Track values use the scene contract's units; rotation is radians. A batch can author a whole rig, including existing motions and per-cel sockets, in one file. Dry runs validate without writing history or the scene. `--expect-sha256` rejects stale edits under the project lock. Failed batches preserve the original scene.

Run `scene apply batch.json --dry-run` to review its candidate and obtain `data.previous_sha256`. Supply that exact value as `--expect-sha256` when saving the batch. The command also checks that the scene did not change during validation. Direct file writers do not participate in the CLI lock.

## Attach without coordinate reconstruction

```sh
./ambiance --project projects/last-lantern scene socket cottage chimney --u 0.5788262295 --v 0.1270647541
./ambiance --project projects/last-lantern scene attach chimney-smoke --to cottage --socket chimney
./ambiance --project projects/last-lantern scene set cottage --rotation-deg 3 --scale 1.05
./ambiance --project projects/last-lantern scene check
```

The zero-offset child's anchor follows the socket. Authored child translation motion still moves it relative to that socket. Position/size units and track semantics are in the [scene contract](SCENE-CONTRACT.md). Children inherit parent depth; setting an independent depth on an attached child is rejected.

## Prepare a pack inside a project

The template includes portable recipes and their source art. Use a new ID/output directory when changing an accepted recipe. An unchanged recipe returns cached output.

```sh
./ambiance asset build projects/last-lantern/assets/recipes/smoke-v1.json --out projects/last-lantern/assets/compiled/smoke-v1
./ambiance asset inspect projects/last-lantern/assets/compiled/smoke-v1
./ambiance --project projects/last-lantern asset admit projects/last-lantern/assets/compiled/smoke-v1
```

These paths are relative to the shell's working directory; they are explicit even when a project is selected. Reuse the whole asset/source tree to rebuild. Standalone atlas rendering only requires the generated atlas and catalog metadata. Admission means catalog availability, not artistic approval.

## Recovery and scope

Scene writes are validated by the same evaluator used in the browser. The previous file is retained by SHA-256 under `.ambiance/scene-history/`. A per-project write lock prevents simultaneous CLI writers. If a process is killed, verify that no writer is active before removing its stale `.ambiance/write.lock`. Direct file edits and the legacy scripts do not acquire this CLI lock.

The read-only preview never saves over a CLI change. Export browser JSON deliberately, then reload the page to pick up saved project files. Asset/catalog edits and scene edits make affected legacy review evidence stale through the project's watch paths. Existing projects created only with `studio.py` need the explicit project configuration before the new CLI can open them; no silent migration is attempted.

Version 0.7 adds opt-in [finishing](FINISHING.md), [edge quality](EDGE-QUALITY.md), and a [look workbench](LOOK-WORKBENCH.md). `render frame/proof/video` also accept `--supersample 1/2/4`; internal dimensions must remain at most 4096 per side, and output size/aspect ratio stay unchanged. A 1080 × 1920 export supports scale 2. `preview --look DIR` needs no selected project; it loads only receipt-listed files and rejects altered artifacts.

The renderer uses Node Canvas for images/proofs and macOS AVFoundation for video/verification. This does not port all historical Last Lantern effects into the shared scene automatically. Audio arrangement accepts explicit PCM WAV sources and performs no source synthesis, resampling or automatic normalization. Provider queues and automatic image decomposition remain unimplemented. Browser pixel audits, human visual/listening review and encoded-video checks establish different evidence.

The [preparation workbench](PREPARATION-WORKBENCH.md) combines existing source/backing images, independent removal/cutout/occluder masks, an explicit backing affine and a standalone movement proof. `asset prepare` accepts either source/backing inputs (with optional `--backing-to-source A B C D E F`) or a saved `--recipe`, and always writes a fresh directory. `preview --prepare` needs no selected project; drafts use the captured inputs and the saved preparation implementation. Export and rebuild the recipe to save a new version.

Test diagnostics: `--artifacts` names a fresh immutable directory; without it, a temporary evidence directory is returned. Each check has a stable ID, bounded scrubbed logs and exact source/runtime identity. `--require-native` (also implied by `AMBIANCE_TEST_NATIVE=1`) fails unavailable media capability and any skipped required test. Native availability is not a successful encode; the native regression cases actually exercise encode/decode. See [CI evidence](CI-EVIDENCE.md) and the [public CLI replay](../examples/workflow-replay/README.md).
