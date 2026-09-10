# Studio library and iteration workflow — validation

Implemented September 10, 2026, on top of `7252132b092d6a0275644ab72d7745b024a8efc0`. The CLI and package version is 0.8.0. Usage and file contracts are in [STUDIO-LIBRARY.md](../docs/STUDIO-LIBRARY.md).

## Delivered behavior

- A registered project library at a stable localhost address, independent of the current code worktree. Start/reuse/status/stop identify the serving checkout and process. Each registry has its own server record and log.
- Explicit delivery registration and append-only current-review selections. Exact movie hashes and typed score/effects/silent roles bind playback, downloads, notes, and handoff links. Approved release selection separately requires applicable edition evidence.
- Actual MP4 playback and seeking, earlier-version history, synchronized comparison, timestamped feedback, and links to the existing working editor. A failed working scene or supporting report does not hide an independently intact movie.
- A saved local iteration recipe runs capture, one picture render, soundtrack composition, verification, delivery registration, and review presentation. Recorded steps support retries and interrupted-receipt recovery. Stale completion cannot silently replace a later selection.
- A project overview and generated handoff expose current links, working-input changes, runs, open criteria, and available asset work. Production/release skills and current command guidance use these interfaces. Historical roadmaps are labeled.

## Automated checks

`AMBIANCE_TEST_NATIVE=1 ./ambiance test` passed on macOS with Python 3.14.0:

| Check | Result |
| --- | --- |
| Python suite | 176 tests; all passed, no skips; 36.884 seconds |
| Shared renderer, rigs, tracks, source placement, finishing | All five JavaScript check commands passed |
| Package audit | Passed, including local links, skills, assets, version consistency, and browser-script syntax |
| Changed skill authoring validators | Both passed |
| Whitespace/diff check | Passed |

[Delivery tests](../tests/test_deliveries.py) cover current/history identity, idempotence, stale selection, role/report/path failures, same-size file changes, broken working inputs, byte ranges/HEAD, route boundaries, exact feedback and cross-origin rejection, registry discovery/relocation, isolated server addresses, and failed iteration retention.

[Native iteration testing](../tests/test_iteration_native.py) renders and encodes a small actual picture, composes an explicitly sourced PCM soundtrack, verifies/registers/presents it, reuses a completed run, and recovers an edition receipt saved before run-state persistence. Synthetic delivery fixtures test identity rules and make no codec claims.

A macOS native-media CI lane is added. Its commands passed locally; no remote CI run is claimed.

## Live acceptance

The local registry points to the original project directories. Casket v5 and Layered v4 were explicitly registered from their retained movies and matching decode reports. Casket v5 was selected using the existing project handoff; this did not infer human approval. Last Lantern remains visible with no current review movie selected.

Verified through the browser:

- Library discovery shows both projects. The stable Midnight Collection project URL resolves to Casket v5, matching `project latest` from an unrelated working directory.
- The scored movie loads as 72 seconds and plays without a browser media error. Native seeking moves playback to the requested position. Switching to silent loads its distinct 24-second movie.
- Comparison seeks both movies and plays together. After correcting initial double audio, the left movie is audible and the right is muted. An observed sample was 13.209429 versus 13.227894 seconds; this is a sampled observation, not a continuous synchronization guarantee.
- The working editor loads the actual Midnight Collection painting with 48 layers and 39 catalog assets. The watch page shows the encoded movie without editor overlays.
- The narrow browser layout has no horizontal overflow. The final page was visually inspected and left open on the current review.
- Stopping and reopening the server retains the same URL and selection. Opening again from another directory reuses the same identified process.
- A generated factual handoff contains current/exact links and movie identities. Current working scene/catalog hashes match the selected snapshots.

No creative approval, continuous human listening, or physical-phone viewing is implied. Browser acceptance was performed interactively; an unattended browser CI suite and the independent-agent skill scenario remain future checks. Provider jobs, login-start services, portable media bundles, and broader proof galleries remain outside this slice.

The implementation runs from the development worktree; production project media stays at its registered original location. Keep this code checkout available while it serves the library, or stop and reopen from another checkout containing this implementation. After reboot, run `./ambiance studio open` again.
