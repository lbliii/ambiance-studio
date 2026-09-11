# Provider and tool operations

Providers supply sources; the studio owns the scene, selected assets, preparation, edits, evidence, and archive. Keep provider-specific controls in adapters or stage notes rather than spreading them across every scene recipe.

## Preflight

Record available image tools, audio tools, local media codecs, scripting runtimes, and file access. A skill's presence describes guidance, not a working connector. A signed-in browser does not establish API availability. Check the current supported capabilities and output formats of the chosen route.

The original production used image generation for painted sources, native macOS graphics/media tooling, Python/NumPy for audio processing, and an authenticated ElevenLabs browser workflow. FFmpeg was not installed. The new package's project/review tools and editor run locally without paid generation; the general generation/export pipeline is not yet implemented.

## Request lifecycle

Use a ledger with `planned → submitted → completed → retrieved → accepted/rejected`. An uncertain response is `unknown`, not `failed`. A confirmed failure can be recorded as `failed`. Preserve the original request ID, response IDs, settings, and attempt timestamps when returned.

Before submission, record a request fingerprint from provider, model/capability, prompt, references, settings, and intended asset. Keep planned/authorized cost and actual reported cost separate. Missing cost is unknown, not zero. Record the authorized budget/candidate scope and pause new paid requests when it would be exceeded; continue local preparation and review.

Use provider idempotency where supported. A local fingerprint alone does not make a remote call idempotent. If an outcome is uncertain, inspect the original request/job/history within authorized scope or ask for the missing access. Do not generate a replacement simply because a result card disappeared.

## Retrieval

Download the task's known returned asset. Verify a nonempty file, actual media type/duration/dimensions, decodability, and hash. A button click, toast, or download event is not proof the file exists. A WAV wrapper or high-bit-depth export does not improve a lossy source's original detail.

Store persistent local sources and returned IDs. Do not retain credentials, session cookies, or temporary signed URLs in reusable manifests or handoff archives. Account-specific project IDs can be historical provenance, but a recipient may not have access to that account; the portable local source is what makes the project usable.

## Browser fallback

Use a supported connector/API when it provides the needed operation and is available. A browser route can be practical, but should preserve the same ledger and file-verification contract. Operate only on task-related results, retain any existing authorization, and do not widen public sharing simply to retrieve media.

In the original run, the main music page failed, the home-page generator worked, a result disappeared, and history retrieval was needed. Sound-effect duration controls and downloads behaved differently from their accessibility descriptions. These are examples of why provider adapters should record capabilities and outcomes instead of depending on a brittle memorized click sequence.

## Provider changes

Recheck current docs when changing models, output formats, endpoints, or billing assumptions. Keep the renderer and asset contract independent of the supplier. Test an adapter with a small authorized request and retain a manual source-import path.

The original capability references are [ElevenLabs sound effects](https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert) and [music composition](https://elevenlabs.io/docs/api-reference/music/compose). They are starting points for verification, not permanent promises about an account's access or plan.

## Executable local recording and reconciliation

`asset request` maintains managed records inside the existing `plans/generation-ledger.json`; legacy records remain unchanged. These commands make no network/provider calls and grant no generation authority.

```sh
./ambiance --project PROJECT asset request record request.json
./ambiance --project PROJECT asset request reconcile take-1 --receipt timeout.json
./ambiance --project PROJECT asset request inspect take-1
./ambiance --project PROJECT asset request reconcile take-1 --receipt retrieved.json
./ambiance --project PROJECT asset request reconcile take-1 --receipt selected.json
```

Start with `templates/generation-request.json`. Source references are explicit project-relative `{file,sha256}` records. Preserve unknown provider/model/price/job IDs as null. Managed states are `pending`, `submitted`, `uncertain`, `retrieved`, `selected`; the earlier descriptive lifecycle remains historical guidance for legacy records. Submission is an externally performed action recorded by an event, never a CLI adapter capability.

A receipt has `version:1`, a stable `event_id`, `state`, and optional returned `provider_request_id`, `actual_model_returned`, `reported_cost`, `note`. A `retrieved` event adds `outputs:[{file,sha256,provider_output_id:null}]` for actual local decodable images. A `selected` event names `selected_output_sha256` from retrieved outputs. A tool-returned image can move directly from pending to retrieved without inventing a provider job ID. Managed image snapshots are byte-preserved at `assets/raw/generation/REQUEST/SHA.bin`; the extension does not change their decoded media format. Audio/video use their existing import/verification paths.

Recording the same request/event is idempotent. Reusing an ID with different contents fails. Identical request fingerprints cannot silently be recorded under another ID; an uncertain job cannot transition back to submitted. Inspect/reconcile its existing result first. A fingerprint does not imply remote provider idempotency. Confirmed intentional regeneration requires a separately reviewed request with changed explicit settings or source/prompt; no automatic retry request is synthesized.

Returned content is deduplicated by hash while preserving receipt aliases. Original returned files may disappear after retrieval; selection uses the verified local snapshot. Changed input sources or tampered snapshots block new retrieval/selection. Interrupted snapshot writes publish atomically, and interrupted ledger updates can safely replay the same event. Known reported cost stays separate from estimated cost/authority; missing costs are unknown, never zero. `inspect` returns the exact ledger path, current state, unknown fields and next recovery action.
