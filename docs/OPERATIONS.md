# Operator commands and project state

Run commands from the repository root using `./ambiance`. The CLI requires Python 3.10+; scene operations/checks use Node. Pillow is optional for asset preparation. See [CLI guide](CLI.md) for the complete interface. Legacy `studio.py` and `kit.py` remain compatibility entry points.

## Find the current movie and resume

Use `./ambiance studio open` for the local film library. Register canonical project folders with `studio register PATH`; their IDs work across code worktrees. `project latest` resolves the selected review movie; `project overview` includes working divergence, open criteria and recent runs. Complete review iterations with a registered delivery and an explicit presentation selection. See [studio library](STUDIO-LIBRARY.md).

## Create a project

```sh
./ambiance project init --reference /path/to/reference.png --title "Autumn Library"
./ambiance --project autumn-library project status
```

With no destination, the project is created under `~/Ambiance Projects` or the directory selected by `AMBIANCE_PROJECTS_DIR`. The title is normalized into a lowercase ASCII slug (`Autumn Library` becomes `autumn-library`), used as the folder and project ID. A directory or registered/discoverable ID collision is reported; choose another title or provide an explicit destination. Supplying `DIR` keeps the original behavior and creates the project exactly there.

The initializer creates `ambiance-project.json`, an empty scene/catalog by default, copies the reference, records its hash, and creates the working folders, brief, layer plan, source ledger, and project-specific gate definitions. It refuses to overwrite an existing directory. Without `--reference`, it creates an intake project with the reference still missing. It does not generate media, spend credits, mark gates passed, or mutate the studio registry. `project list` discovers immediate children of the configured external root, so their IDs can be used with `--project` from any working directory.

The default delivery settings are 1080 × 1920, 30 fps, 16-second picture and 48-second master. Edit these to fit the film before closing intent. The budget starts unspecified; record actual scope/authority before paid generation.

## Record a review

```sh
PROJECT="$HOME/Ambiance Projects/autumn-library"
./ambiance --project autumn-library review draft intent --out "$PROJECT/review-drafts/intent.json"
```

Complete the draft using the actual checks. Each criterion begins as `not-run`, and the overall verdict begins as `revise`. Add the observer, observations, and evidence paths. Paths are relative to the project, such as `inputs/reference.png` or `plans/brief.md`.

```sh
PROJECT="$HOME/Ambiance Projects/autumn-library"
./ambiance --project autumn-library review record "$PROJECT/review-drafts/intent.json"
./ambiance --project autumn-library project status
```

Use `pass` only when every criterion passed and dependencies are current. A `revise` record may retain failed or unperformed checks and does not pretend the stage is ready. Do not edit generated current receipts directly; submit a new review. Previous receipts are preserved by content hash.

For a human release observation, save the user's actual note and identify its source/date in `feedback/`. Include both that note and the exact selected movie file in the relevant criterion's evidence. The tool records the assertion; it does not authenticate the observer or independently perform the review.

## Working folders

| Folder/file | Purpose |
| --- | --- |
| `project.json` | Identity, output settings, reference hash, budget scope |
| `pipeline.json` | This project's gate criteria and dependencies |
| `inputs/` | Preserved user references |
| `plans/` | Brief, layer/occlusion plan, sound idea, generation ledger |
| `assets/raw/` and `assets/production/` | Unmodified sources and prepared derivatives |
| `scene/` | Scene recipe, rigs, motion data, renderer configuration |
| `audio/` | Selected sources, source log, session, masters, aligned stems |
| `reports/` | Actual asset, animation, sound, mix, and export checks |
| `deliverables/picture/` and `deliverables/final/` | Review picture and final editions |
| `feedback/` | Identified creative/listening observations |
| `review-drafts/`, `reviews/` | Editable proposed reviews and recorded receipts |
| `library/` | Reusable modules, compatibility notes, archive records |
| `deliveries/`, `presentations/` | Immutable movie sets and explicit current/release selection history |
| `runs/`, `feedback/movies/` | Resumable local production progress and exact-movie notes |
| `handoff.md` | Authored creative context; use `project overview` and `delivery handoff` for generated current facts |

## Inspect the bundled example

```sh
./ambiance doctor
./ambiance --project projects/last-lantern project check
./ambiance --project projects/last-lantern preview --port 8784
```

The new preview reads the selected project's scene/catalog from `ambiance-project.json`. A fresh clone can create the example with `./ambiance project init projects/last-lantern --template last-lantern`. The legacy `kit.py serve` command still opens the bundled example. Projects created only by the legacy `studio.py` need explicit CLI configuration before the new preview can open them.

## Validate this studio package

```sh
./ambiance test
```

This runs review-state, asset, CLI and rig regressions plus the package audit. It checks behavior and file integrity; it does not certify a film. New shared functionality should add meaningful behavior checks to the appropriate tool.

## Resuming after interruption

Read `handoff.md`, `project.json`, gate status, and the relevant stage's files. For an uncertain generation, consult the ledger and reconcile the original request before submitting another. Do not restart the whole film because a session changed. If the workspace moved, relative paths should remain valid; credentials and temporary provider URLs should not be part of the project.

## Current limits

The gate tool is a local, single-writer record keeper. It checks saved evidence and dependency freshness, not semantic truth. The editor is a rig and cel-animation workbench with preview checks; the CLI now provides [rendering and media verification](RENDERING.md) and [explicit PCM audio arrangement](AUDIO-SESSION.md). A separate Pillow compiler performs registration and packing, with CLI proof/landmark authoring. Follow the capability matrix in [SCALING.md](SCALING.md) when planning work.

## Registration and rig checks (v0.3)

Follow the [rig workbench guide](RIG-WORKBENCH.md) for compiler commands, named sockets, complete-frame diagnostics and report limits. Run `python3 tests/test_assets.py` and `node tests/test-rig.mjs` when changing those tools, in addition to the existing review and engine checks. The asset compiler requires the optional Pillow dependency in `requirements-assets.txt`.
