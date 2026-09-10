# Repository and workflow review — September 10, 2026

The highest-value next addition is a permanent local home for projects and their movies. The production tools already preserve useful evidence, but finding the current result still depends on a hand-written handoff and knowledge of the directory layout. Build artifact discovery and explicit current selections on top of the existing revision system.

This records the pre-implementation analysis at version 0.7.0. The proposed core library and iteration workflow have since been implemented in 0.8.0; see the [implementation validation](CLI-V08-VALIDATION.md) and [current usage](../docs/STUDIO-LIBRARY.md). Findings below describe the audited baseline.

## What was inspected

Reviewed the CLI and supporting Python modules, shared JavaScript renderer/editor, project server, six stage skills, root instructions, workflow/contract/architecture documents, test configuration, and the actual main-checkout project records. Opened the current museum scene in the localhost workbench. Ran `./ambiance doctor`, project discovery/status, and `./ambiance test`.

- Code checkout: `7252132b092d6a0275644ab72d7745b024a8efc0` (version 0.7.0), initially clean.
- Audit checkout: `/Users/lb/.codex/worktrees/ecd5/ambiance-studio`.
- Actual project root: `/Users/lb/Developer/ambiance-studio/projects`.
- Regression result: 164 Python tests discovered, 159 executed successfully and five optional native-media tests skipped. All five JavaScript check commands and the package audit passed. Native encode/decode and full human movie review were not performed in this audit.
- Browser observation: The Midnight Collection loads with 48 layers and 39 catalog assets. The page presents rig controls and scene JSON export, with sockets drawn over the painting. It has no exported-movie player, project switcher, edition selector, or iteration history.

## The current movie, today

The Midnight Collection's `project.json` and `handoff.md` both identify `casket-v5` as current. Its project directory contains 34 MP4 files, including older finals, drafts, and encoder tests. The current full movies live under:

`/Users/lb/Developer/ambiance-studio/projects/the-midnight-collection/deliverables/revisions/casket-v5/`

| Edition | File | Current identity check |
| --- | --- | --- |
| Score, 72 seconds | `the-midnight-collection-72s-casket-score-v5.mp4` | SHA-256 matches the export manifest: `da281ec008e3f21d7fc5623fd9cd00fce36fa7f5eb6a5a8ea48d5e40a445a209` |
| Effects, 72 seconds | `the-midnight-collection-72s-casket-effects-v5.mp4` | SHA-256 matches the export manifest: `e77abb0d97cc7e2841f5365426784d3c2b5dc51345814aa2b3c398bf1477964e` |
| Silent picture, 24 seconds | `the-midnight-collection-24s-casket-silent-v5.mp4` | SHA-256 matches the export manifest: `33164e3a252c585c9a1d0e645aa05e358d46d3454a2d3c274d33e3fc9e0ba072` |

The retained decode reports describe technically verified outputs. The handoff leaves continuous human viewing/listening and physical-phone checks open. These are current review movies. Earlier positive user feedback identifies layered-v4 and does not establish approval of casket-v5.

The working museum scene and catalog currently match the exact scene/catalog snapshots used for the casket-v5 picture. Later toolkit look trials live separately under `work/`; their presence does not select a replacement movie.

## Findings and priorities

| Priority | Observed problem | Recommended change |
| --- | --- | --- |
| P0 | `project list` returns zero projects in this worktree, but finds two when explicitly pointed at the main checkout. It searches only immediate children of `ROOT/projects`. | Maintain a local registry of canonical project locations, independent of code checkouts. Support explicit registration/relocation; expose missing locations. Development worktrees should reuse the registry while keeping their code identity visible. |
| P0 | `/` redirects to `/editor/`. The server mounts the scene, catalog, and catalog images; it never exposes film deliverables. | Make the root URL a studio library. Add project pages whose primary action plays the selected encoded movie with its real soundtrack. Keep scene editing as a separate destination. |
| P0 | The museum has `current_revision` and `current_deliverables` in `project.json`, but `project status` returns `revisions: []`. Its earlier export manifests are outside the newer captured-revision layout. | Add an explicit import/registration path for existing deliverables. Preserve their original evidence and identify them as legacy exports; do not manufacture captured revisions or migrate review passes. |
| P0 | There is no enforced current movie selection, typed soundtrack role, revision list command, or watch URL. Status enumerates captured revisions alphabetically and returns edition review states without movie paths or creation times. | Add a shared artifact query/selection layer used by the CLI and browser. Every movie has identity, role, provenance, completion state, and a stable exact-version URL. |
| P1 | `plan next` handles asset inventory. Gate status can say `revise` with no reasons, because criterion observations remain in the underlying review file. Handoff Markdown pushes exact paths into separate JSON. | Add a concise project overview with current watch links, working divergence, actionable failed/unperformed criteria, available work, and precise evidence links. Generate the factual handoff section from those same results. |
| P1 | Long production commands run synchronously and produce separate artifact directories; there is no durable top-level run view. | Add persistent run records for local production: requested inputs, output reservation, stage, logs, elapsed time, success/failure, and recovery action. Let the UI show progress and the last completed movie concurrently. |
| P1 | Several active guides repeat or contradict current capability claims. Skills are concise but route agents into that larger corpus. | Consolidate current capability/command guidance, mark historical roadmaps clearly, and use generated contract/help checks to prevent drift. Update the relevant skills to end an iteration with a registered, watchable result. |
| P2 | Ordinary tests and Linux CI omit native video tests, and browser review is manually recorded. | Add a native macOS test lane and a small browser acceptance suite for discovery, playback, seeking, current selection, and stale/missing outputs. Keep human creative review separate. |

Implementation anchors: [project selection and dispatch](../ambiance_studio/cli.py), [localhost routes](../ambiance_studio/preview.py), [revision/status/handoff implementation](../ambiance_studio/revisions.py), [inventory reconciliation](../ambiance_studio/planning.py), [gate-state implementation](../studio.py), [editor](../editor/index.html), and [CI](../.github/workflows/ci.yml).

## The localhost experience to build first

One bookmarked address, for example `http://127.0.0.1:8783/`, opens the studio library. A proposed `./ambiance studio open` command starts or reuses its server and opens that address. It should report the serving code checkout/version and registered project roots, recognize its own existing process, and report an occupied port clearly. The current server remains tied to a foreground process; process discovery/reuse and explicit stop/status behavior need implementation.

A project card shows its cover, title, current movie label, duration, soundtrack, and an honest review status. Clicking it opens this proposed arrangement:

```text
The Midnight Collection
Current review: Casket v5 · 72 seconds · 1080 × 1920

[                   Actual movie player                  ]
[ Score ]  [ Effects only ]  [ Silent picture ]

Technically checked · Human review pending
Changed: lifting casket, local flame illumination

[ Previous versions ] [ Compare ] [ Working scene ] [ Files ]
```

The project page should group the three editions as one iteration. If an edition has not been produced for that iteration, show it as unavailable; do not silently substitute audio or picture from another version. Put checks, assets, sound stems, and proofs one level deeper. Present diagnostic overlays in the editor rather than the watch page.

The same server can host receipt-listed asset, rig, motion, and look proofs through artifact-specific adapters. Retain explicit file mounts. Movie streaming needs byte ranges/HEAD support, correct content types, and bounded reads; the existing image-serving `read_bytes()` approach should not be reused for large movies.

The library must load even if a working scene is broken or empty. An independently intact completed movie remains playable. Surface source/rebuild or review problems separately. Today `preview` runs a whole project check before starting, so the new library cannot simply inherit that prerequisite.

## Define “current” explicitly

Three concepts need separate labels:

| Label | Meaning | How it changes |
| --- | --- | --- |
| Working scene | Editable project inputs; may have unrendered changes | Validated authoring transactions |
| Current review movie | The completed candidate selected for the user to watch | A recorded presentation selection after production/verification |
| Approved release | An explicitly selected edition with applicable release evidence | A separate recorded release selection and current review evidence |

Also show the newest completed exports in history. A throwaway render or newer look experiment must not displace the current review movie merely because its timestamp is later. File modification times and names such as `final-v5` are discovery hints, not selection authority.

Store presentation selections in a small project-owned record referencing immutable artifact IDs and receipt/movie hashes. Record who selected the result, when, why, and which previous selection it replaces. Keep an append-only selection history and update the current pointer atomically under the project lock. Support a soundtrack role/default for the selected iteration. Human approval is not required to present a clearly labeled review candidate.

Every production result should return both an exact-version link and a project-current link. Feedback attaches to the exact version and timestamp. The current link may advance; the exact link never changes meaning. If a selected file is missing or changed, show that condition with an explicit route to earlier intact versions instead of silently falling back. When a new candidate appears during playback, offer it without interrupting the movie already playing.

## Make the workflow easier for agents

Preserve the existing strengths: structured CLI output, dry runs and expected hashes, atomic scene changes, restorable history, shared preview/export evaluation, explicit PCM provenance, immutable output directories, and separation of technical evidence from human observations. The six short stage skills are a sensible routing layer.

Add an overview query that supplies the selected movie and links, relevant scene/revision identities, working divergence, newest completed runs, open criteria with observations, and a bounded list of next actions. Reuse `project_status`, `compare`, and `planning.inspect`; keep one interpretation of evidence across CLI and UI. Avoid rehashing the same large dependency several times in one request. Separate quick discovery from an explicit integrity refresh, always showing when and what was checked.

A common iteration operation can compose the existing capture, proof/render, media verification, and presentation selection functions. Use a saved recipe for intended editions and selected inputs. On success it registers all outputs and advances the selected review set; on failure it preserves the old selection and exposes the failed run. A slow older run must not replace a newer selected iteration when it finishes late. This wrapper should reduce repeated manifest authoring without hiding which sources or checks were used.

Generate handoff facts from this state and retain authored creative notes separately. The current revision handoff writes gate states to Markdown while requiring JSON to find the movie; make the actual watch links prominent in both formats. The museum's careful manual handoff demonstrates the content to automate.

Give feedback an artifact ID, movie hash, timestamp/range, optional layer/cue, observation, and resolution. Reuse the current review machinery to bind it to exact evidence. A note such as “the left flame flickers too quickly at 6 seconds” should survive task changes and link directly back to the movie.

Durable provider submission/retrieval remains useful later. Start run tracking with local rendering and mixing, where completion and failure can be tested without spending generation credits. Reserve broader automation until the common iteration path works reliably.

## Instructions and guidance to simplify

The best existing guidance is concrete: act within user scope, preserve sources, reuse returned generations, distinguish cels from light states, inspect actual rasters/audio, and reopen only affected evidence. Keep these principles.

There is demonstrated drift to repair:

- [pyproject.toml](../pyproject.toml) reports 0.4.0 while the package and CLI report 0.7.0; the browser labels itself 0.4.
- [SCALING.md](../docs/SCALING.md) lists matte repair as unautomated, then proposes export, audio, and project-loading work already partly implemented. Its project browser is postponed to the fifth milestone despite the user's present discovery problem.
- [PROCESS.md](../docs/PROCESS.md) retains earlier priorities and tool assumptions; [CONTRACTS.md](../docs/CONTRACTS.md) routes review users to legacy entry points and describes audio mainly as an editorial record, whereas the focused audio contract documents executable mixing.
- [OPERATIONS.md](../docs/OPERATIONS.md) emphasizes `deliverables/final/`; the actual current movie lives under `deliverables/revisions/`. [REVISIONS.md](../docs/REVISIONS.md) correctly explains immutable binding but intentionally offers no current-selection policy.
- The package audit checks links/frontmatter/assets, not whether capability statements or command recipes remain accurate. [Skill scenarios](../tests/skill-scenarios.md) explicitly remain proposed behavior trials.

Use AGENTS.md for shared operating principles, stage skills for task routing and artistic checks, one generated command/capability reference for executable behavior, and focused contracts for file schemas. Label version-specific engineering reports as history. Move repeated project-specific examples into examples linked from the relevant workflow. Add a latest-deliverable skill trial: start a fresh task in a different worktree and require it to find the same current movie without the earlier chat.

For the toolkit itself, prefer focused changes over a rewrite: shared project/artifact/path helpers, clearer typed errors and remediation, uniform output identities, full rendering-toolchain provenance, and readable formatting when modules are touched. Reuse the existing renderer and review validator. Later, add portable project bundles that include pinned dependencies; a revision hashes binaries in place and does not back them up, while Git excludes production media.

## Suggested delivery order and acceptance checks

1. **Reliable discovery and selection.** Registry, artifact queries, explicit legacy registration, grouped current editions, immutable identities, and exact/current links. Seed the museum using its existing handoff and export records without relabeling approval.
2. **A useful studio home.** Library, movie player, edition/history navigation, server start/reuse/status, and links to the existing editor/proofs. The bookmarked page and CLI query must resolve the same movie.
3. **A dependable iteration loop.** Run records, combined production/presentation recipe, concise overview, timestamped feedback, generated handoff facts, and revised skills/guidance.

Acceptance should exercise actual user journeys: find the current movie from a new code worktree; play and seek with sound; produce a newer review set and observe it at the same project URL; retain the old exact link; prevent failed/partial/out-of-order runs from replacing it; keep score/effects/silent roles unambiguous; detect a missing or changed selected file; and find an intact movie while its working scene is invalid. Measure clicks/time to find the movie and the number of undocumented decisions needed to resume production.

This should precede more rendering effects or a large provider queue. It directly addresses an observed problem while making the existing production capabilities easier for both the user and an agent to operate.
