# BASE-01 source inventory and AUDIO-01 evidence

Survey baseline: `00c64436543d0252fc0850f3ef58e686badda1b6`. This is evidence for source and backend readiness, not a pilot selection, backlog-status update, sound-library approval or film review.

The early [inventory](inventory.json) contains actual source paths, SHA-256 and byte sizes, prepared art dimensions/registration mappings, immediate source identities, view summaries, current selection records/edition identities, audio format probes, complete PCM payload reads and recorded provenance/listening state. Its SHA-256 is `e2e5f00257e23b8926bd3b82f4f2cf7659247aa47cf4d608fdb02536fd6db1ec`. The bounded read-only [survey script](inventory.py) reproduces this scope; a later survey may differ because the source projects are mutable.

| Available project | Catalog assets | Audio files under audio/ | Authored picture / current selection |
| --- | ---: | ---: | --- |
| Amberwatch | 72 | 17 | 1448×1086, 16 s picture; `amberwatch-review-02`, revision `amberwatch-r2`, four 48 s portrait/landscape × score/effects editions |
| Last Lantern | 15 | 0 | 1080×1920, 16 s picture; no current delivery selection in this project |
| The Midnight Collection | 39 | 91 | 1080×1920, 24 s picture; legacy `casket-v5`, 72 s score/effects and 24 s silent outputs |

Amberwatch's portrait crop resolves to 1080×1920 with 1.768 output pixels per scene pixel; its landscape resolves to 1920×1080 with 1.326. Its painted stage is 1448×1086 and its principal cel sheets range from 1536×1024 to 1774×887. These scales are framing facts, not per-layer detail bounds. The future TV audit must evaluate source ancestry, every relevant cel, crop/padding and camera/parent motion before claiming adequate native detail. All 15 Last Lantern entries and all 39 Midnight entries lack the current catalog registration mapping; usable historical art may still exist, but atlas dimensions alone do not prove its original detail. Missing source mapping remains explicit.

All source media were read only. The script used `deliveries.current/load` and `views.project_summary` instead of `project overview/latest`, whose baseline coverage paths can persist reports. It did not copy or modify project controls, select a movie or rewrite review records. `a-quieter-tomorrow-fresh` and `midnight-reading-room` remain unavailable and were not recreated. No pilot was selected, so no writable overview copy was needed.

Historical repository references identify four originals also preserved under Amberwatch: music MP4, woodland WAV, hearth WAV and leaves WAV. The bell source has a recorded hash but no matching file in the bounded available-project inventory. The original reference document's `source/elevenlabs/` paths are also absent under the saved repository root. This is an unresolved location, not a reason to regenerate. Extra historical variants and subscription entitlement remain unknown.

## Compressed source findings

The three Midnight provider originals are present despite their `.audio` extension. The ledger identifies the actual ElevenLabs connected-flow models and output IDs. Real-byte inspection confirms 44.1 kHz/128 kbps MP3 for room air and cloth/bronze, and 48 kHz/192 kbps MP3 for Music v2. Their source auditions are explicitly unperformed in the saved records. Nearby local candidates are documented deterministic synthesis; they do not become provider originals or auditioned natural recordings through reuse.

The [decode and replay evidence](decode-evidence.json) supplements the early inventory's compressed packet probes. It binds a complete native decode/preparation and public CLI revision capture to each copied original hash:

| Preserved original | Decoded source frames / rate | Working frames / rate |
| --- | --- | --- |
| Midnight room air | 1,323,000 / 44,100 | 1,440,000 / 48,000 |
| Midnight cloth/bronze | 352,800 / 44,100 | 384,000 / 48,000 |
| Midnight sparse music | 3,456,000 / 48,000 | 3,456,000 / 48,000 |
| Historical Music v1 MP4/AAC | 2,646,976 / 44,100 | 2,881,062 / 48,000 |

The historical MP4's decoded duration exceeds its requested 60 seconds. Its preparation retains the actual source interval with recorded rational rounding; no duration correction was inferred from the request. MP3-to-PCM24 preparation preserves the original compressed quality limit. Some newly prepared bytes differ from older derivatives because the explicit converter settings/preparation path differ. This is not evidence of an audible improvement.

The machine had no FFmpeg/FFprobe. Existing macOS movie verification was examined but does not expose standalone source resampling. Installed `afinfo` and `afconvert` 2.0 were the smallest tested route; no native extension or installation was needed. The first sandboxed conversion failed with Core Audio `fmt?`; the same bounded conversion and later public replays passed outside the sandbox with authorization. Doctor reports availability separately from execution.

## Acceptance boundaries and next dependency

The [new source contract](../../AUDIO-SOURCES.md) and [public replay](../../../examples/audio-source-replay/README.md) cover local inspection/preparation. Focused tests cover mono/stereo, PCM8/16/24/32, raw declarations, AAC/ALAC, MP3 structure/real MP3 decode, wrong rates, truncated payloads, unsupported speaker maps, changed originals and receipts, exact counts, reconstruction, provenance and revision capture. Exact run/log/artifact hashes are in the decode evidence.

Provider route/format facts above come from preserved local records and actual retrieved bytes. Current API capabilities and subscription entitlements were not checked online; no provider format upgrade is promised. No costed new-generation comparison is needed to answer this local decoder/preparation question. Same-take format quality comparisons, human auditions and 15–20 clip curation remain separate work.

AUDIO-02 can consume these identified prepared sources for level/true-peak and encoder work. LIB-01 must implement typed version records and explicit destination-contained materialization so reuse stops depending on the first mutable project. TV-01/02 can use the inventory now but still require effective source-detail and full-resolution visual evidence. No loudness, true-peak, audio library, new mix, artwork revision, full-film or artistic acceptance is claimed here.
