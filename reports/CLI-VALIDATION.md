# CLI validation — 0.4.0

The unified command suite passes 37 Python tests (the original 24 plus 13 CLI/project/preview tests), the 8 legacy engine checks, 7 rig scenarios, and the package audit. Local tests use no provider accounts or credits.

The CLI tests cover isolated project catalogs, pending initial gates, invalid changes leaving original bytes intact, seek/sample output, history and restoration, missing sockets/cycles, altered asset hashes, empty-scene checks, existing destinations, concurrent-writer locks, project path containment, imported pivots, review drafts and read-only preview route boundaries. The browser loaded the relocated project title, 16 layers and 15 assets with no error. It checked 480 frames, 2 attachments with zero measured drift, and no uncovered pixels at 135 × 240. See `cli-browser-check.json`.

The suite was run locally on Python 3.14 and Node 24. GitHub CI is configured, not yet executed remotely. The CLI does not encode video or mix audio; prior pixel/film/audio observations remain scoped to their original reports.
