# Ambiance Studio

A local studio for painted, layered ambiance films. The CLI is the main interface for agents and repeatable production; the browser workbench provides visual placement and review.

Version 0.4.0 brings the existing tools together, adds project-specific preview and validated scene editing, and preserves the full Last Lantern production history.

## Start here

Run these commands from this repository. No CLI installation or account is required. Use Python 3.10+ and Node 18+; the asset compiler additionally needs Pillow from `requirements-assets.txt`. This machine was tested with Python 3.14 and Node 24. `./ambiance doctor` reports actual availability.

```sh
./ambiance doctor
./ambiance project list
./ambiance --project projects/last-lantern project check
./ambiance --project projects/last-lantern preview
```

The migrated local repository includes `projects/last-lantern`. A fresh Git clone excludes working projects; create one with:

```sh
./ambiance project init projects/last-lantern --template last-lantern --title "The Last Lantern"
```

Open the URL printed by `preview` (normally `http://127.0.0.1:8783/editor/`). The server exposes only the editor and the selected project's declared assets. It is read-only. Browser edits need scene JSON export; CLI edits save validated files and retain a restorable history.

## Work through the CLI

```sh
./ambiance --project projects/last-lantern scene inspect
./ambiance --project projects/last-lantern scene set cottage --scale 1.05
./ambiance --project projects/last-lantern scene sample --time 3.5
./ambiance --project projects/last-lantern scene check --out projects/last-lantern/reports/animation/cli-check.json
./ambiance --project projects/last-lantern project status
./ambiance test
```

Commands emit JSON with stable exit codes. Inside a project, the CLI discovers its configuration, so `--project` can be omitted. The executable can also be invoked by absolute path from another directory. See the [CLI guide](docs/CLI.md) for asset preparation, sockets, review records, history and errors.

## Repository map

| Path | Purpose |
| --- | --- |
| `ambiance`, `ambiance_studio/` | CLI, project operations, read-only preview server |
| `editor/`, `tools/scene-command.mjs` | Shared absolute-time evaluator, visual workbench and JSON scene bridge |
| `tools/asset_tool.py` | Registration, atlas preparation, proofs and cache checks |
| `studio.py`, `kit.py` | Existing review/integrity tools; retained for compatibility |
| `assets/`, `scenes/`, `templates/` | Reusable example inputs and production contracts |
| `.agents/skills/`, `docs/` | Six production skills, guides, quality gates and engineering plans |
| `tests/`, `.github/workflows/` | Local regression suite and CI definition |
| `projects/` | Local film workspaces; excluded from Git |
| `archive/session-2026-09-10/` | Full prior production session, including films, sound, sources, drafts and earlier kits; excluded from Git |

Small reusable PNG assets are tracked in this repository. Large media, working projects and archives live alongside it locally and need their own backup. A Git clone alone does not include the finished-film archive. The migration inventory records each copied source file and hash. The original chat workspace is retained to keep its links usable.

## Guides

- [CLI guide](docs/CLI.md): implemented commands and practical recipes.
- [Rig workbench](docs/RIG-WORKBENCH.md): registration choices, sockets and visual inspection.
- [Start a film with an agent](START-HERE.md): production workflow and creative checkpoints.
- [Architecture](docs/architecture/CLI-FIRST.md): boundaries and next engineering steps.
- [Contributing](CONTRIBUTING.md): conventions and validation.
- [Quality gates](docs/QUALITY-GATES.md): evidence, freshness and creative review.
- [Tool strategy](docs/TOOL-STRATEGY.md): research and priorities behind this direction.

Final video rendering, integrated audio arrangement, automatic feature tracking and provider orchestration remain to build. The CLI does not call a paid provider or publish a film. Historical native production scripts remain available in the archive.
