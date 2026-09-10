# CLI-first studio architecture

## Decisions implemented in 0.4

The CLI is an adapter over the existing tools. It emits structured results, selects a project explicitly, and calls the shared JavaScript evaluator for scene validation and sampling. It does not recreate motion math in Python. The browser reads the same saved scene/catalog through a read-only project server.

A project owns references, prepared assets, scene, sound records, checks and review history. A repository owns code, reusable example assets, templates and workflows. The historical session archive is retained alongside the repository but excluded from Git and from preview HTTP routes.

Scene changes validate before writing, preserve the previous content by hash and use one project lock. Project initialization builds in a temporary directory, then promotes a complete workspace. `project check` checks that project's catalog rather than the bundled one. Blank projects do not claim a passing picture check. Template projects start with no accepted quality gates.

The initial source launcher needs no installer. Distributable packages will require moving runtime resources into a deliberate package/resource layout; an incomplete wheel is not offered as an installation path.

## Next engineering slices

1. Add a CLI frame renderer that consumes the same sampled scene and produces deterministic image files. Port missing full-film effects, establish preview/final parity, then encode exact frame counts and inspect the actual video join.
2. Extend asset registration with named per-cel landmark files and a visual onion-skin authoring panel. Keep its output compatible with the existing recipe and socket-track fields.
3. Add reusable rig modules and explicit scene operations for module instantiation, dependency locks and migrations. Preserve existing releases when library versions change.
4. Add an audio-session CLI for stems, gains, timed events, circular tails, mix/loop checks and picture muxing. Preserve the sound story as an inspectable arrangement.
5. Add durable provider jobs with request identity, retrieval, uncertain-outcome reconciliation and budget scope. Run an independent second-scene/operator pilot before batch queues.

Each slice needs a usable CLI command, a saved contract/example, meaningful positive/negative checks and a documented capability boundary. Do not add command names that only print a future plan as if they perform production work.
