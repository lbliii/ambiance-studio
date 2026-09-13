# Local audio source inspection and preparation

Use `audio source-inspect` before selecting an original, then explicitly prepare it at 48 kHz. These commands do not generate media, select a film soundtrack, normalize loudness or record listening approval. The existing [audio arrangement contract](AUDIO-SESSION.md) still requires matching-rate PCM sources.

```sh
./ambiance --project PROJECT audio source-inspect audio/originals/take.audio --backend macos-afconvert
./ambiance --project PROJECT audio source-prepare audio/originals/take.audio \
  --backend macos-afconvert --source-sha256 HASH_FROM_INSPECTION \
  --preparation-id take-48k-v1 --provenance audio/take-provenance.json
./ambiance --project PROJECT audio source-check audio/preparations/take-48k-v1/receipt.json
```

Source, provenance and receipt paths are project-relative and must remain inside the project after symlink resolution. Preparation IDs create fresh `audio/preparations/ID/` directories. Existing IDs fail. Inspection uses disposable temporary decoding files and publishes nothing in the project. A validation/conversion failure publishes no preparation; runtime failures retain the existing nonzero CLI error envelope.

`doctor` reports discoverable source backends separately from successful execution. `pcm` is a standard-library reader and exact 8/16/24-bit integer expansion at 48 kHz. It refuses rate conversion and 32-bit quantization. `macos-afconvert` uses installed `/usr/bin/afinfo` and `/usr/bin/afconvert`; it fully decodes at the original rate to integer PCM32, then resamples once with Core Audio's `bats` converter at quality 127 and quantizes to PCM24. No tools are installed and no alternative backend is selected automatically. Core Audio may be discoverable yet fail in a sandbox; the September 13 local probe returned `ExtAudioFileSetProperty ('cfmt') failed ('fmt?')` there and succeeded with authorized execution outside the sandbox.

Supported sources are integer PCM WAV (8/16/24/32-bit), explicitly declared little-endian raw PCM, MPEG Layer III MP3, and single-audio-track AAC/ALAC MP4. Only mono and stereo, integer rates from 8 to 192 kHz, positive durations up to one hour, and files up to 2 GB are admitted. This bounded path is for compact source material. Other containers, floating-point WAV, surround or unknown explicit speaker maps fail. Missing maps retain mono/stereo channel order and are labeled as an interpretation; a channel count does not establish surround semantics. MP4 may contain picture as well as its one selected audio track; this operation decodes audio only and preserves the complete original file.

Raw PCM must declare all three fields; an extension is not a sample-format declaration:

```sh
./ambiance --project PROJECT audio source-inspect audio/cue.pcm --backend pcm \
  --raw-format s16le --raw-rate 48000 --raw-channels 1
```

The accepted raw representations are `u8`, `s16le`, `s24le`, and `s32le`. Known containers cannot be overridden as raw PCM. Partial sample frames, inconsistent RIFF/chunk lengths, malformed MPEG frames, inconsistent MP3 frame-count tags and truncated ISO media boxes fail before decoding. Complete decoder output counts are checked against declared PCM or compressed packet-table valid frames where available. These checks do not detect every corruption in codecs without checksums; a complete MP3 lacking an original length declaration cannot reveal that whole frames were removed before import.

Inspection reports actual container/codec, sample rate, channel-layout basis, meaningful source bit depth, bitrate, exact decoded sample frames and PCM hash. Compressed bit depth remains null where it has no useful meaning. MP3 packet samples include padding; decoded valid samples and packet-table priming/remainder fields remain separate. A fractional output duration is recorded as an exact rational target plus the backend's actual floor/ceiling sample boundary. No samples are silently padded or trimmed to force a requested count.

## Immutable receipt and provenance

Each successful directory contains `original.source` (byte-preserved original), `working.wav` (48 kHz PCM24 with the same channel count), `recipe.json`, and a sealed `receipt.json` of format `ambiance-audio-preparation`, schema 1, kind `prepared-source`. The original filename is recorded in the origin reference; the neutral preserved filename never determines its format.

The receipt pins the selected origin, preserved copy, recipe and working file by path, bytes and SHA-256. It records source/working format, raw declaration, decoded PCM identity, exact source/output counts, resampling choice, actual tool versions and binary hashes, OS version and preparation implementation hashes. Reusing or checking it never silently adopts changed source bytes. Reproduction on a different backend/version can legitimately produce different bytes and requires a new preparation identity.

Optional provenance separates generation and retrieval from subsequent processing:

```json
{
  "origin_kind": "generated",
  "provider": "ElevenLabs",
  "generation": {
    "request_id": "recorded-request-id",
    "output_id": "recorded-output-id",
    "candidate_id": "recorded-candidate-id",
    "model": "actual-returned-model-id",
    "route": "recorded-connected-flow"
  },
  "retrieval": {
    "requested_format": "unknown",
    "returned_format": "MP3",
    "retrieved_at": "recorded timestamp"
  },
  "terms_reference": null,
  "entitlement": "unknown",
  "audition": "not performed",
  "prior_processing": "No preparation recorded before this original retrieval"
}
```

Provenance is a declaration, not verification of entitlement, source history or an audition. Actual bytes take precedence over claimed format. Missing facts stay unknown. Credentials and signed download URLs are rejected. PCM24 output does not make a compressed original lossless or recover earlier discarded detail. Comparisons of formats must use the same take; comparisons of models/different takes cannot isolate codec quality. Gain matching and actual listening remain separate work.

## Revision and future library boundary

Add the receipt to the existing selection's `audio.preparations`. Revision capture validates it and pins the receipt, origin, preserved original, working source and recipe under `sound-design`. It does **not** add a master or mark sound complete. Existing external-preparation declarations retain their previous behavior. A prepared mono cue becomes a complete soundtrack only through separately authored arrangement/mix and edition evidence.

The read-only adapter is `audio_sources.validate_preparation(project, path)`. It returns `kind: prepared-source`, exact receipt/working references, formats and a `dependencies` array whose elements contain `path`, `sha256`, `bytes`, `section` and `role`. Roles are `audio_preparation`, `audio_source_origin`, `audio_source_original`, `audio_prepared_source`, and `audio_preparation_recipe`.

This receipt deliberately pins the first project's selected origin as well as its preserved copy. LIB-01 must implement explicit portable materialization: copy pinned source bytes into the destination, write a newly identified receipt with destination-relative dependencies and preserve prior provenance/version references. It must not silently repoint this immutable receipt or require the former mutable project to remain available after materialization. No audio library or relocation command is implemented here.

Run the [public replay](../examples/audio-source-replay/README.md) for disposable evidence. The [BASE-01 survey](research/audio-sources-2026-09-13/README.md) records actual source availability and open quality questions. Neither software test establishes artistic approval.
