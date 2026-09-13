# mc/1 specimens

These small synthetic records accompany [the versioned model/character packet](../../../docs/architecture/model-contract/README.md). They are engineering examples, not a production schema, library entry, model resolver, finite runtime or artistic approval.

- `models/lantern-v1.json` pins `candle-v1.json`; the latter owns wax/flame. Stable frame variants and exposed source/phase controls are explicit.
- `models/character-v1.json` owns a complete body, head and mouth, with a character-view reference, explicit padded geometric registration assertions and stable drawing IDs.
- `instances.json` pins two independent lantern instances and a separately owned ground-light relationship. Its derived subject is an **input specimen**, not a receipt for nonexistent masks or observations.
- `runtime.json` is a separately hand-authored current-engine scene/catalog. It exercises attachment, draw order, source/receiver and legacy-clock semantics; no model-to-runtime lowering is implied.
- `clock-cues.json` contains expected unequal-shot, finite endpoint, local-cycle and cue-offset tables. They specify future consumer behavior and do not execute finite scenes.
- `shots/*.json` pins the two finite-shot semantic inputs. Shot A includes distinct last-output/endpoint cel, visibility and child-socket positions. These are not fabricated captured revisions or loadable finite scenes.
- `art/*.png` and `silence.wav` are tiny locally generated fixture bytes, not borrowed film media. RGBA images contain simple solid rectangles or frame strokes; registration metadata is an authored assertion, not a fabricated compiler report. PCM is 9,600 zero-valued mono signed-16 samples at 48 kHz, written using Python `wave` (no speech or audition). Art uses Pillow RGBA canvases with explicit dimensions in the records; source rectangles/padded mappings are fixed in the character specimen.

Run from the repository root:

```sh
node tests/test-model-contract.mjs
```

The test validates selected contract invariants and deliberately invalid mutations, checks all referenced fixture file hashes, uses the current scene evaluator/affines for state and geometry, and verifies cue arithmetic against saved expected values. It does not implement a general definition graph traversal, time helper, model compiler, media renderer or evidence verifier. Cycle/writer/mount rejection goes through the existing evaluator. Full closure validation, arbitrary schemas, runtime lowering, finite sampling and raster/encoded acceptance belong to implementation packages.

Edit a specimen deliberately, then update every exact referring file pin; a changed file must fail a stale-pin test. Do not regenerate masks or invent reviews to make a contract check pass. Source images and audio are intentionally tiny so the packet is portable without any private project or worktree dependency.
