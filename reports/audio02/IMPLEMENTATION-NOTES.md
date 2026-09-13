# AUDIO-02 bounded implementation notes

Base: `75d24b85a8977f234d87daa1c18993d394036c1c`.

Closest operations probed: `./ambiance audio --help`, `./ambiance media --help`, and `audio measure missing.wav` (invalid-choice result). Existing `audio.check_audio` measures integer sample peaks/RMS only. Existing `verifyAudio` already selects presentation samples by timestamp; its PCM16 decode cannot retain AAC over-full-scale samples for trustworthy true-peak measurement. Existing native `compose` hardcodes 256000 bps and reads PCM16. These are the demonstrated narrow gaps; source preparation and existing renderer/edition ownership remain in use.

Method: 48 kHz mono/stereo only, independent channel K-weighted energy and two-stage integrated gating from ITU-R BS.1770-5 Annex 1; Annex 2's published 4x polyphase FIR. Streaming double precision on the already-required Node runtime. This is not a full EBU Mode meter or a compliance certification. No loudness target or normalization.

References: [ITU-R BS.1770-5](https://www.itu.int/rec/R-REC-BS.1770-5-202311-I), [EBU Tech 3341](https://tech.ebu.ch/docs/tech/tech3341.pdf), [EBU test set](https://tech.ebu.ch/publications/ebu_loudness_test_set). Both published `/files/live/sites/tech/files/shared/testmaterial/ebu-loudness-test-setv05.zip` and historical `/docs/testmaterial/ebu-loudness-test-setv05.zip` returned HTTP 403 during the local download attempt (restricted first attempt also failed DNS). The committed fixture generator implements the published deterministic signal definitions; it does not redistribute EBU recordings. Real-programme reference recordings are consequently unavailable in this trial.

Observed native gap: the first `AVAssetWriter.canApplyOutputSettings` preflight admitted 384000 bps, but real AAC encoding failed with AVFoundation -11861 / underlying -12651. `AVAudioConverter.applicableEncodeBitRates` for stereo48k reports a maximum of320000 on this host (whereas its global available list contains384000). Preflight now uses the format-specific list;256000 and320000 were encoded/decoded successfully without fallback. Restricted preflight failure and the failed384k encode are retained under `.ambiance/audio02/`.

Replay repairs: the initial fixture had an empty scene (renderer correctly rejected it); the next attempted to test edition staleness via `revision check`, which owns captured inputs only; a third had incomplete synthetic project metadata. The current replay uses a nonempty synthetic picture, valid project metadata, and the existing edition review/status dependency owner. These failures do not establish a production capability gap.

LIB-01 correctly rejected a media root inside the fixture project/Git checkout. The replay now uses an independent retained system-temporary library root and records its exact files; the materialized working source remains project-contained. No library rule was bypassed or changed.
