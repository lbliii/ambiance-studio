# Code quality audit — September 12, 2026

The largest maintenance risks are mixed responsibilities, dependencies pointing
back into command adapters, and repeated contract/transport code. File length
alone understates the problem: several JavaScript and native files pack many
operations into each line.

The audit started from clean commit `23f9ca7d8ecb89708520a7b9042b09640eeb623c`.
It surveyed active Python, editor/studio JavaScript, command tools and native
media sources, using file/function sizes, Python import inspection and manual
tracing of production, media, evidence and preview paths. Historical archives
and production artwork were excluded. This is a structural audit and focused
refactor, not an exhaustive correctness or security review.

## Changes implemented

- **Separate production responsibilities.** [production.py](../../ambiance_studio/production.py)
  shrank from 518 to 208 lines. It retains command adapters, overview and
  handoff presentation. [iteration_plan.py](../../ambiance_studio/iteration_plan.py)
  owns recipe validation, readiness integration and view/audio preflight;
  [iterations.py](../../ambiance_studio/iterations.py) coordinates runs;
  [iteration_steps.py](../../ambiance_studio/iteration_steps.py) owns checkpoints,
  output identity checks and receipt recovery. Existing `production` entry
  points remain available as compatibility imports.
- **Remove the orchestration-to-CLI dependency.** Previously, each iteration
  assembled strings, instantiated the entire CLI parser and recursively called
  `cli.run`. [media_operations.py](../../ambiance_studio/media_operations.py)
  now supplies immutable picture/composition requests and a `MediaExecutor`
  protocol. Both CLI and iteration execution use the same edition
  prepare/render/record lifecycle. Saved command arguments remain available
  for inspection and manual recovery; execution does not parse them.
- **Share the production loop.** Legacy and paired-view recipes now share
  picture reuse, composition and registration. Version-specific job names,
  edition IDs, default selection order, snapshots and legacy posters are
  preserved. Recipe initialization/configuration import validation directly
  rather than importing the production command adapter.
- **Consolidate file hashing.** [file_identity.py](../../ambiance_studio/file_identity.py)
  supplies streaming SHA-256 for studio records, audio, activity, checks and
  rendering. Existing helper names remain import-compatible. Media verification
  and final-output hashing no longer buffer an entire movie merely to hash it.
  Hashes of already-captured bytes and format-specific canonical JSON encodings
  remain separate operations.
- **Remove diverging PCM validation.** `render video` and `media compose` now
  use the same PCM validator. The former checked header format/duration but did
  not check that all declared sample bytes existed. Truncated PCM now fails
  before starting the native encoder or creating the render directory.

## Remaining work, in recommended order

| Priority | Evidence and impact | Next bounded refactor | Verification needed |
| --- | --- | --- | --- |
| Completed | [revisions.py](../../ambiance_studio/revisions.py) previously held 644 lines owning schema helpers, path/reference utilities, dependency collection, captures, editions, review contexts and command routing. Many unrelated modules import `fields`, `identifier`, `seal`, `relative` and other helpers from this domain module. | Extracted record_contracts, project_references, revision_dependencies, revision_capture, editions and revision_reviews; revisions retains CLI routing and compatibility exports. See [ownership](../REVISIONS.md#python-ownership-and-compatibility). | Existing revision/edition/tamper tests plus compatibility fixtures for persisted seals, schema versions and path containment. |
| High | [rendering.py](../../ambiance_studio/rendering.py) still combines argparse registration, native discovery/build, JSON subprocess transport, view sizing, raster requests, verification, muxing and reports. [production_coverage.py](../../ambiance_studio/production_coverage.py) and other modules call private rendering functions. | Extract a public native media adapter and verification service, then separate render request planning from execution. The new `MediaExecutor` is the orchestration boundary; renderer internals still need this work. | Actual frame/proof, H.264 encode/decode, compressed-sample preservation, source-tamper and failure tests. Inspect browser proofs if their generated content changes. |
| High | [production_coverage.py](../../ambiance_studio/production_coverage.py), 542 lines, owns context loading, several typed evidence validators, decoding/cache work, registration/history writes and stage readiness decisions. Adding an evidence kind touches the evaluator. | Extract typed evidence adapters behind a small explicit verifier interface; keep stage/readiness policy in one evaluator. Separate evidence acquisition/cache writes from decisions without weakening actual decode requirements. | Existing coverage matrix, stale-evidence cases, readiness parity across CLI/overview/iteration, and native movie evidence tests. |
| Medium | [preparation_server.py](../../ambiance_studio/preparation_server.py), [region_server.py](../../ambiance_studio/region_server.py) and [motion_server.py](../../ambiance_studio/motion_server.py) repeat origin checks, response headers, bounded body reads, evaluation locks and loopback server startup. Their error/status behavior and CSP policies differ. | Extract small HTTP response/body/origin helpers with explicit per-workbench policy. Retain each handler's route allowlist and draft/source-identity validation. Avoid a generic route/plugin framework. | Existing HTTP tests plus malformed length, unexpected origin, concurrent draft, content type and download behavior; inspect each affected workbench. |
| Medium | [tools/render-scene.mjs](../../tools/render-scene.mjs) is only 227 lines but about 24 KB. Its main routine mixes filesystem snapshots, mode branching, raster loops, child-process coordination, receipts and generated proof HTML. [native/media/media.m](../../native/media/media.m) is 315 lines but about 36 KB. | Split by actual runtime responsibilities: proof presentation, render job execution, native process transport; then native encode/compose/verify commands. Expand dense control flow while touching each extracted owner. | Shared-engine parity, proof output integrity, cancellation and real native regression checks. A formatting-only diff should be separate from semantic changes. |
| Medium | [cli.py](../../ambiance_studio/cli.py) has a long command dispatcher and a growing negative condition in `main` deciding whether `--out` is a JSON file or an artifact directory. | Give command registrations explicit output semantics and narrow execution adapters, following the existing scene/plan/region command modules. Keep the CLI responsible for parsing, project resolution and envelopes. | Public command replay, help/capability audit, error exit codes and representative JSON-file/artifact-directory output cases. |

## Extraction constraints

The existing shared scene evaluator, scene transaction path and project lock are
useful boundaries and should remain authoritative. Reuse those services rather
than copying motion math or write semantics into new adapters.

Do not merge similarly named utilities blindly. `studio.inside` and
`audio.inside` accept different path spellings; JSON hash encodings have different
NaN/Unicode policies; immutable artifact writes differ from replaceable control
files. Those differences need explicit contracts and compatibility cases before
consolidation. A catch-all `utils.py`, a protocol for every helper or a global
line-count limit would hide rather than resolve these responsibilities.

The implemented refactor adds one execution protocol where an actual boundary
was missing. Existing schema validators and the shared renderer remain the
runtime authority; Python annotations do not replace their validation.

## Validation

Portable regression checks cover typed-job/CLI option parity, failed edition
preparation, renderer failure, truncated PCM rejection, streaming file identity,
checkpoint reuse and tampered outputs. The native paired-delivery regression
exercises real encoding, interruption after an edition receipt, resume without
CLI parsing, soundtrack reuse and stable selection identity.

Run the full required suite with `./ambiance test --require-native`. It includes
Python discovery, Node engine/rig/view/binding/finishing checks, the package audit
and the failure-report contract. Native tests require access to macOS media
services; sandboxed execution can report AVFoundation error -11834 even when
the encoder is installed. Retained suite artifacts distinguish actual native
success from mere capability detection.
