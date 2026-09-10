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
