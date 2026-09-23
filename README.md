# Ambiance Studio

A local studio for painted, layered ambiance films, designed for agent operation first. The agent pilots production through structured CLI/tools and saved project state. Localhost lets the human observe, compare and judge results, with optional visual editing for the human or agent.

The broader direction is [agent-operated traditional animation](docs/architecture/AGENT-ANIMATION-VISION.md): agents use familiar drawing, posing, exposure-sheet, pencil-test and revision practices to make editable films under human direction. Text, image, audio and vision capabilities support that work. Narrative authoring and agent dailies are planned extensions; current capability remains defined by the shipped commands.

For planned development, start with the [studio plan alignment](docs/architecture/STUDIO-PLAN-ALIGNMENT.md): workflow guidance, reusable models, narrative films and quality/sound-library work, with explicit owners and shared acceptance. These plans are separate from the shipped commands below.

Version 0.8.0 adds a [local film library](docs/STUDIO-LIBRARY.md): projects shared across worktrees, explicit current review movies, edition history and comparison, timestamped feedback, and resumable local iteration runs. It preserves the existing rendering, sound, finishing, revision and evidence workflows.

[Dual-format production](docs/VIEWS.md) adds portrait 9:16 and landscape 16:9 views of one scene, synchronized previews, view-bound editions, and one resumable export/delivery job. Start a blank stage with `project init --format dual`, or add contained views to existing artwork. Try the [complete local-art demo](examples/views/README.md) and see the [validation evidence](docs/architecture/DUAL-FORMAT-VALIDATION.md).

The [asset preparation workbench](docs/PREPARATION-WORKBENCH.md) combines source/backing inspection, separate removal/cutout/foreground masks, alignment and a shared-engine movement preview. Author its JSON recipe directly and run `asset prepare` to build fresh, reproducible parts. The browser can inspect the result or export optional visual edits through the same recipe. Try the [independent example](examples/preparation-workbench/README.md).

Before requesting replacement paint, use [art regions](docs/ART-REGIONS.md) to trace its opening, square or reframe the reference without stretching, calculate output demand, and build a packet with masks and return mappings. `asset region` and `preview --region` share saved recipes; the returned production asset retains its higher resolution.

## Start here

Run these commands from this repository. No CLI installation or account is required. Use Python 3.10+ and Node 18+. Install Pillow for asset preparation and Node Canvas for raster rendering and the full test suite:

```sh
python3 -m pip install -r requirements-checks.txt
npm ci --ignore-scripts
```

This machine was tested with Python 3.14 and Node 24. `./ambiance doctor` reports actual availability.

```sh
./ambiance doctor
./ambiance studio open
./ambiance project list
./ambiance project init --title "The Last Lantern" --template last-lantern
./ambiance --project the-last-lantern project check
./ambiance --project the-last-lantern preview --port 8784
```

New projects are stored outside the tool checkout under `~/Ambiance Projects` by default. Set `AMBIANCE_PROJECTS_DIR` to choose another project root. When `project init` has no destination, `--title` is required and its normalized lowercase slug names the new project; an existing path or project ID is an error. Existing explicit destinations continue to work.

This migrated checkout also has a legacy local `projects/last-lantern` example. Working projects and the production archive are ignored by Git; a fresh Git clone does not include them. The title-only command above creates a separate copy of the example in the default external project root.

Bookmark `http://127.0.0.1:8783/` for the film library. Use `./ambiance --project PROJECT project latest` for the exact selected movie and `project overview` to resume work. Register external project folders once with `./ambiance studio register PATH`.

The separate `preview` command opens the scene editor (use `--port 8784` if the library is running). The scene preview exposes only the editor and the selected project's declared assets. It is read-only. Browser edits need scene JSON export; CLI edits save validated files and retain a restorable history.

## Work through the CLI

```sh
./ambiance --project the-last-lantern scene inspect
./ambiance --project the-last-lantern scene set cottage --scale 1.05
./ambiance --project the-last-lantern scene sample --time 3.5
./ambiance --project the-last-lantern project status
./ambiance test
```

Commands emit JSON with stable exit codes. Inside a project, the CLI discovers its configuration, so `--project` can be omitted. The executable can also be invoked by absolute path from another directory. See the [CLI guide](docs/CLI.md) for asset preparation, sockets, review records, history and errors.

## Repository map

| Path | Purpose |
| --- | --- |
| `ambiance`, `ambiance_studio/` | CLI, project operations, film library, delivery selections and local runs |
| `studio/` | Movie library, player, version comparison and feedback interface |
| `editor/`, `tools/scene-command.mjs` | Shared absolute-time evaluator, visual workbench and JSON scene bridge |
| `tools/asset_tool.py` | Registration, atlas preparation, proofs and cache checks |
| `studio.py`, `kit.py` | Existing review/integrity tools; retained for compatibility |
| `assets/`, `scenes/`, `templates/` | Reusable example inputs and production contracts |
| `.agents/skills/`, `docs/` | Six production skills, guides, quality gates and engineering plans |
| `tests/`, `.github/workflows/` | Local regression suite and CI definition |
| `projects/` | Legacy local film workspaces; excluded from Git. New projects default outside the checkout. |
| `archive/session-2026-09-10/` | Full prior production session, including films, sound, sources, drafts and earlier kits; excluded from Git |

Small reusable PNG assets are tracked in this repository. Large media, working projects and archives are outside normal Git tracking and need their own backup. Newly created projects default outside the tool checkout. A Git clone alone does not include the finished-film archive. The migration inventory records each copied source file and hash. The original chat workspace is retained to keep its links usable.

## Guides

- [Local film library](docs/STUDIO-LIBRARY.md): current movie links, discovery, iteration runs and feedback.

- [CLI guide](docs/CLI.md): implemented commands and practical recipes.
- [Rig workbench](docs/RIG-WORKBENCH.md): registration choices, sockets and visual inspection.
- [Start a film with an agent](START-HERE.md): production workflow and creative checkpoints.
- [Architecture](docs/architecture/CLI-FIRST.md): boundaries and next engineering steps.
- [First animated short roadmap](docs/architecture/FIRST-SHORT-ROADMAP.md): the aspiration for vintage-inspired 2D storytelling, proposed tool development, early acting experiments and parallel work packages.
- [Reusable model scene plan](docs/architecture/REUSABLE-MODEL-SCENES-PLAN.md): whole-scene ownership, editable nested models, derived masks, library reuse and phased acceptance; development details deferred until related work settles.
- [TV quality and sound library plan](docs/architecture/TV-QUALITY-AND-SOUND-LIBRARY.md): proposed 4K asset checks, compact masters, audio quality, reusable sounds, and deferred surround/long exports.
- [Contributing](CONTRIBUTING.md): conventions and validation.
- [Quality gates](docs/QUALITY-GATES.md): evidence, freshness and creative review.
- [Tool strategy](docs/TOOL-STRATEGY.md): research and priorities behind this direction.

Frames and HTML motion proofs use Node Canvas; H.264 export and encoded-media verification currently use macOS AVFoundation. Audio arrangement uses explicit PCM WAV sources and Python's standard library. See [rendering](docs/RENDERING.md), [audio](docs/AUDIO-SESSION.md) and [production inventory](docs/PRODUCTION-INVENTORY.md). Automatic image decomposition/feature tracking and provider orchestration remain to build. The CLI does not call a paid provider or publish a film.
