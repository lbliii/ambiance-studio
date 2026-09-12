# Feedback, review, configuration and cleanup replay

Run the supplied engineering fixture through the public CLI on a macOS host with native media services:

```sh
python3 examples/midnight-production/replay.py --out /tmp/midnight-workflow
```

The fresh project retains every command, response size, elapsed time, exact movie, packet and feedback event under `replay/` and `recipes/`. It exercises packet creation/resume, untimed feedback, disposition/reopen and current-selection preservation. The four-second reference tone and brush-mark art establish mechanics only. Open the returned HTML for paired playback and source audition; observations stay separate.

The [sheltered](sheltered.json), [open-window](open-window.json) and [established-haunting](established-haunting.json) plans demonstrate different authored causes, cues and emphasis using the existing production-plan fields. Apply each to its own fresh project with `plan spec apply FILE`. Their cues are explicitly authored requirements; these files do not claim the scene has been built or viewed. Do not apply an invented open-window or curse premise to repair a sheltered-room movie.

For a layered recipe, copy this example's `config/` directory into the fixture, then run:

```sh
./ambiance --project /tmp/midnight-workflow iteration resolve /tmp/midnight-workflow/config/draft.yaml
./ambiance --project /tmp/midnight-workflow iteration init /tmp/midnight-workflow/config/draft.yaml --out /tmp/midnight-workflow/recipes/layered-draft
```

The ordered studio/project layers and request values resolve the draft size to 160 pixels. The compiler saves an ordinary recipe and a configuration-resolution record. No template executes during rendering. `{$value: render.long_edge}` inserts a typed literal. Arrays replace in full, later object values win, and null removes a field. Unknown variables, invalid recipes and paths outside the project fail before initialization.

Finish an iteration with a storage check and a cleanup plan:

```sh
./ambiance --project /tmp/midnight-workflow project storage
./ambiance --project /tmp/midnight-workflow project cleanup plan --keep-days 30 --out /tmp/midnight-cleanup.json
./ambiance --project /tmp/midnight-workflow project cleanup apply /tmp/midnight-cleanup.json
```

The plan names exact eligible bundles and protected reasons. Apply rechecks references and file identities, then moves eligible bundles to project-local trash. The returned restore command restores the same bytes. A fresh fixture normally has no eligible bundles under the 30-day default. `--include reports/BUNDLE --keep-days 0` selects an explicit generated study for immediate analysis; it does not bypass dependency protection. Source art, selected movies, captures and reviews are outside the cleanup roots. There is no permanent purge command.

See [operations and contracts](../../docs/MIDNIGHT-OPERATIONS.md) and the [implementation handoff](../../docs/architecture/MIDNIGHT-IMPLEMENTATION-HANDOFF.md) for measured outcomes and limits.
