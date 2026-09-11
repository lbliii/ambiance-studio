# The local film library

Use the studio library to find movies across code checkouts and worktrees. Project records own the selected versions; browser tabs and conversations do not determine what is current.

```sh
./ambiance studio register /absolute/path/to/film
./ambiance studio open
./ambiance project list
./ambiance --project film project latest
./ambiance --project film project overview
```

Bookmark `http://127.0.0.1:8783/`. `studio open` starts a detached local server or reuses the registered server, reporting its code checkout and version. `--no-browser` suppresses browser opening. `studio status` inspects it; `studio stop` stops only the identified instance. After reboot, run `studio open` again; no login service is installed. An occupied port produces an error instead of silently changing the bookmark. Use `studio serve --port N` for foreground operation or `studio open --port N` to deliberately choose another port. To use newly edited server code, stop and reopen the server.

The registry defaults to `~/.ambiance-studio/registry.json`. Global `--registry FILE` or `AMBIANCE_REGISTRY` selects a separate studio. Registration saves an address without copying sources. `studio register NEW_PATH --id EXISTING_ID --relocate` explicitly updates a moved location. Missing locations remain visible. `project list` combines registered projects with immediate project children in this checkout and the Git main checkout; `--directory DIR` limits discovery to that directory. Registered project IDs work with `--project ID` from any directory. Explicit project paths still work.

## What is current

| View | Meaning |
| --- | --- |
| Working scene | Editable inputs, possibly containing unrendered changes or temporarily invalid data |
| Current review | An explicitly selected delivery set with score, effects-only and/or silent movie roles |
| Approved release | A separate selection whose every edition has current, edition-bound release evidence |

The player uses the actual MP4 and encoded soundtrack. Version-2 deliveries have independent format and soundtrack controls; switching retains an in-range playback time and pauses the replacement movie. It offers prior versions, synchronized comparison in seconds, downloads, decode reports, exact links, and timestamped notes. Missing soundtrack roles stay unavailable. Open the working scene for rig editing; those edits still require deliberate scene JSON export. A broken working scene does not hide an independently intact saved movie.

`/projects/film` follows the selected review. `/projects/film/deliveries/take-2?role=score` names that exact delivery and soundtrack. Selection changes show a notice without interrupting playback. Use exact links for feedback and handoffs. File modification times and names containing `final` are not selection authority.

## Register existing movies

Author a [delivery selection](../templates/delivery-selection.example.json) with project-relative references. The selection filename passed to the command is shell-relative:

```sh
./ambiance --project film delivery import selection.json --dry-run
./ambiance --project film delivery import selection.json
./ambiance --project film delivery present take-2 --by Codex --note "Slower smoke"
./ambiance --project film delivery list
./ambiance --project film delivery inspect take-2
./ambiance --project film delivery handoff take-2 --out /path/to/fresh/handoff
```

Each entry uses `score`, `effects`, or `silent` once. Supply `revision` and `edition` for a captured edition. For a legacy export supply `file` and `verification`; the latter must identify successful full decode of the exact unchanged movie bytes, dimensions, frame rate/count, duration and audio tracks. If older evidence lacks identity, use `media verify` on the existing movie and select its new report. No re-render is needed. Registration labels legacy provenance and never migrates approval.

Optional `poster`, `provenance`, `scene_snapshot`, and `catalog_snapshot` preserve covers/source evidence and enable working-input comparisons. Use retained render snapshots rather than mutable working files. Posters are PNG, JPEG or WebP. All references stay inside the project, including after resolving symlinks. Imported reports remain recorded evidence; registration does not perform a new decode or authenticate an observer.

Records live at `deliveries/ID.json`, including the declaration and hashes. Identical unchanged imports are idempotent; changed inputs need a new ID. `present` appends an atomic selection under `presentations/review/` using the project lock. `--expect-selection HASH` (or `none`) rejects stale selection changes. `project latest` returns the token, exact movie path and watch links. Use `--channel release` for separate release selection/query; its evidence is re-evaluated.

Missing or changed selected files remain explicit errors, with no automatic fallback. Intact soundtrack editions may still play when another movie or supporting evidence is unavailable. The server hashes files and reuses results only while identity, size, modification time and change time remain unchanged. Original movies, review receipts and the working handoff are preserved.

## Produce another iteration

The [iteration recipe](../templates/iteration.example.json) composes supported local operations:

```sh
./ambiance --project film iteration run iteration.json --by Codex
./ambiance --project film iteration list
./ambiance --project film iteration inspect take-3
```

It selects a captured revision; optional `capture_selection` captures one first from a project-relative selection. An existing revision must have the same declaration and valid inputs. The workflow renders one silent picture, composes requested sound editions with selected PCM, verifies outputs, registers the delivery, then presents it for review. Audio references are project-relative. `audio_run` or `audio_provenance` can establish PCM provenance when not selected in the revision. No synthesis, paid requests, arbitrary shell commands, normalization, or publishing occurs.

`runs/ID/` retains recipe, commands, stage progress, completed output identities, attempts and errors. Repeating a completed recipe returns its recorded result. Retrying an unchanged failed recipe reuses intact completed steps and reconciles an edition receipt saved before interruption. Failed attempts stay separate. Changed recipes or completed outputs need a new ID. After a hard kill, the coordinator recovers a lock only when the operating system reports its recorded owner PID no longer exists. A live or unverifiable owner remains locked. Progress is by stage, not by frame.

The starting selection token prevents a slow earlier run from replacing a later selected version. Its completed delivery remains available; inspect and explicitly present it if appropriate. Completion does not establish human approval.

## Resume and record feedback

`project overview` returns selected movies/links, working-input comparisons, available asset work, open review criteria and observations, and recent runs. `project status` retains gate/revision behavior and adds current delivery state. Open gates do not prevent delivery of a clearly labeled review movie.

```sh
./ambiance --project film feedback add take-3 --role score --time 6.2 \
  --by "Viewer name" --note "The left flame changes too quickly here."
./ambiance --project film feedback list take-3
```

Browser notes retain movie hash, chosen soundtrack, observer and current playback position under `feedback/movies/`. They do not automatically pass a gate; cite applicable notes through the existing review workflow. `delivery handoff` creates a fresh Markdown/JSON bundle with watch links, hashes and open checks, preserving authored creative notes in `handoff.md`.

The server binds to loopback and mounts only registered movies, their reports/covers, and selected scene assets. Seeking uses byte-range/HEAD support and bounded reads. Non-local Host headers and cross-origin feedback writes are rejected; shutdown requires its private local token. It never serves the repository tree or starts paid jobs over HTTP.

## Two formats in one job

Use the [version-2 iteration example](../templates/iteration-views.example.json): `views` selects saved IDs, `editions` selects shared soundtrack roles, and `default` is an explicit `{view, role}` pair. The job produces their Cartesian product. The optional `long_edge` limits review resolution while preserving integer aspect ratios; omit it for each view's preferred output. Native dimensions must be even. Version 2 accepts `long_edge`, not a single `width`; version 1 keeps its existing authored-picture semantics.

The complete view raster plan, PCM provenance/duration, edition IDs and next attempt destinations are checked before the first encode. One coordinator renders each view once and composes its soundtrack variants without re-encoding the picture. Selected PCM bytes are shared unchanged across orientations. All requested outputs must verify before the one delivery is presented; a failure preserves completed steps and the previous current selection. Per-view duration, mix overrides and concurrent encoders are not implemented.

Version-2 delivery selections use `entries: [{view, role, revision, edition, poster?}]` and an explicit `default`. Each pair must be unique and bound to a captured edition with the same view. Each entry pins its own movie, decode report, edition receipt and poster. The poster defaults to the edition's first decoded contact and must match its movie dimensions. Legacy imports and sealed records keep schema 1.

The stable entry ID is `VIEW.ROLE`, for example `portrait.score`. Exact watch links use `/projects/film/deliveries/take-2?view=portrait&role=score`; current links use `/projects/film?view=portrait&role=score`. Omitted view/role selectors resolve through the saved default pair; a role-only v2 link uses the default view. An explicit missing pair is an error, never a fallback. Media and report paths use the exact entry ID (`/media/film/take-2/portrait.score`, `/files/film/take-2/portrait.score`). An entry's poster is `/media/film/take-2/poster?entry=portrait.score`. Old role paths continue to resolve unchanged for v1 deliveries.

`project overview`, the player and `delivery handoff` expose review state for each exact entry. Combined release readiness requires every entry. Browser comments bind the resolved pair, revision, edition and movie hash. CLI feedback requires `--view ID` when a soundtrack appears in multiple views:

```sh
./ambiance --project film feedback add take-2 --view landscape --role score --time 6.2 \
  --by "Viewer name" --note "The left edge needs more room."
```
