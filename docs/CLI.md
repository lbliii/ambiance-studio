# Ambiance CLI

The supported entry point is `./ambiance` in the repository, or its absolute path from another directory. `python3 -m ambiance_studio` also works from the repository. There is no wheel or global shell installation in this version.

## Project selection and output

Use `ambiance --project PATH COMMAND`, placing the global project option before the command. Without it, the CLI searches the current directory and its parents for `ambiance-project.json`. This small file points to `scene/scene.json` and `assets/catalog.json` within the project. Source paths never depend on the original chat location.

Each finite command writes one JSON result to stdout: `ok`, `schema_version: 1`, `command`, and `data`. Errors contain `error.code` and `error.message`. Exit codes: 0 success, 1 failed checks, 2 invalid input or a locked project, 3 missing runtime/runtime failure, 130 interruption. Help/version are plain text. Preview prints one startup JSON object and serves until Ctrl-C; HTTP request logs go to stderr.

`--out` on check/test commands writes the same result envelope to a file. CLI checks do not close quality gates; they are evidence for a separate review.

## Implemented commands

| Command | Effect |
| --- | --- |
| `doctor` | Report runtime paths and executable capability availability |
| `project init DIR [--reference FILE] [--title NAME] [--template blank or last-lantern]` | Create an isolated workspace atomically; preserve a reference and initialize pending gates |
| `project list [--directory DIR]` | List initialized child projects |
| `project status` | Read actual evidence/dependency freshness |
| `project check [--out FILE]` | Check this project's asset integrity, scene graph, timing, attachments and geometric coverage |
| `asset list` | Inspect this project's catalog |
| `asset build RECIPE --out DIR` | Run the existing Pillow compiler with its immutable cache policy |
| `asset inspect PACK` | Inspect metadata/report and verify built output hashes |
| `asset admit PACK` | Add a compiled pack within the project to its catalog; protect existing IDs |
| `scene inspect` | Return the scene's canvas and authored layers |
| `scene sample --time SECONDS` | Return sampled matrices, source rectangles, cels and sockets |
| `scene add ASSET --id ID [--name NAME] [--x N --y N --width N --depth N]` | Add an instance using the asset's default pivot |
| `scene set LAYER [--x N --y N --scale N --rotation-deg N --opacity N --depth N --cycle-seconds N --phase-frames N]` | Validate and atomically save an authored change |
| `scene socket LAYER NAME --u N --v N` | Define an object-local normalized static socket |
| `scene attach CHILD --to PARENT --socket NAME [--offset-x N --offset-y N]` | Attach a child, inheriting its parent's depth/group; preserve its authored motion |
| `scene check [--out FILE]` | Same technical check as project check |
| `scene history` | List preserved snapshots |
| `scene restore SHA256` | Validate and restore a snapshot; preserve the current scene first |
| `review draft GATE --out FILE` | Create an unperformed review draft without replacing an existing file |
| `review record FILE` | Record actual criteria/evidence with the existing gate tool |
| `preview [--port N]` | Serve the selected project on localhost, read-only |
| `test [--out FILE]` | Run Python regressions, legacy/rig Node checks and package audit |

A blank project is the default for new artwork. It has no layers; its technical check deliberately reports incomplete until prepared assets and a scene are added. The explicit Last Lantern template copies the existing assets into the project, so editing one project cannot modify another's catalog or artwork.

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

The read-only preview never saves over a CLI change. Export browser JSON deliberately, then reload the page to pick up saved project files. Asset/catalog edits and scene edits make affected review evidence stale through the project's watch paths. Existing projects created only with `studio.py` need the explicit project configuration before the new CLI can open them; no silent migration is attempted.

The CLI has no full-fidelity frame/video export, audio mix engine or provider queue yet. Browser pixel audits, human visual/listening review and encoded-video checks remain separate evidence.
