# Move to the developer workspace

The active repository is `/Users/lb/Developer/ambiance-studio`. Its CLI entry point is `./ambiance`. The complete prior production session is under `archive/session-2026-09-10/`; 467 files totaling 1,396,431,890 bytes were copied and SHA-256 verified against the originals. The staging directory and disposable OS/Python caches were excluded.

The original chat workspace remains intact so its existing media links keep working. Active development should continue in this repository. The archive includes earlier kits and ZIP packages as well as the finished video, audio and production sources; these large files are intentionally outside Git. The root source code, example art, guides, six skills, tests and CI definition are tracked.

`projects/last-lantern/` is an independently editable film workspace created through the new CLI. It starts with pending quality gates, preserving the distinction between imported example art and a newly reviewed film. The preview now loads that project's actual scene/catalog.

The migration created a local Git repository on `main`. No remote was added and no files were published. See the recorded [file inventory](../reports/migration-manifest.json).
