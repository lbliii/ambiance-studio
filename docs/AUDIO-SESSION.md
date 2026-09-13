# Explicit audio sessions

Prepare incompatible or compressed originals through the explicit [audio source preparation](AUDIO-SOURCES.md) path before using their project-contained 48 kHz PCM working files in a session. Preparation preserves provenance and does not mark a mix or audition complete.
The `audio` commands arrange existing PCM WAV files without provider calls, synthesized substitutes or automatic loudness normalization. They use Python's standard library. Import or decode compressed sources deliberately before arranging them: the executable backend accepts integer PCM WAV, mono or stereo, 8/16/24/32-bit, at the session's exact sample rate. Output is stereo PCM24.

```sh
./ambiance --project projects/the-midnight-collection audio import-stems \
  audio/session.json --session-id museum-stem-diagnostic-v1
./ambiance --project projects/the-midnight-collection audio inspect \
  audio/sessions/museum-stem-diagnostic-v1.json
./ambiance --project projects/the-midnight-collection audio mix \
  audio/sessions/museum-stem-diagnostic-v1.json --start 8 --duration 12 \
  --mute lamp_flame --gain gallery_air=-14 --run-id reduced-room-proof-v1
./ambiance --project projects/the-midnight-collection audio compare \
  audio/sessions/museum-stem-diagnostic-v1.json \
  --variant-b audio/sessions/museum-reduced-room-v1.json --start 8 --duration 12
./ambiance --project projects/the-midnight-collection audio check audio/runs/RUN_ID
```

`--solo STEM`, `--mute STEM` and `--gain STEM=DB` can be repeated. Gain overrides are **relative dB changes**, added to declared stem and master gain; they do not target an RMS or LUFS number. `audio compare` renders unchanged A and explicitly modified B over the same time region. Its variant file contains only these supported controls:

```json
{
  "mute": ["lamp_flame"],
  "gain_db_by_stem": {"gallery_air": -14}
}
```

Every run writes a fresh `audio/runs/<run-id>/` directory containing a byte-preserved session snapshot, a report, separate aligned stems and masters for each variant. Existing run IDs fail. User session files and source WAVs are never rewritten. The report identifies source hashes, sample counts, excerpt origin, variant controls and output hashes. Filenames use `stem-<id>.wav` so a stem called `master` cannot overwrite the master. A failed source validation or clipped mix publishes no run.

`audio import-stems` is an explicit migration for the pilot's previous descriptive session format. It hashes each listed rendered stem and creates a new session under `audio/sessions/`. Each stem becomes one unity-gain source with its existing processing intact. This supports a truthful A/B diagnosis without pretending to reproduce arbitrary old synthesis, EQ, normalization or convolution scripts. The legacy session and prior imported versions remain untouched. Imported stems must share exact duration, rate and zero offset.

## Version 1 arrangement contract

A minimal executable session follows. Paths are relative to the project root and must remain inside it, including after resolving symlinks. Substitute the actual SHA-256 of the source file.

```json
{
  "format": "ambiance-audio-session",
  "schema_version": 1,
  "id": "gesture-proof-v1",
  "sample_rate": 48000,
  "frames": 1152000,
  "master_gain_db": 0,
  "sources": [
    {
      "id": "linen-v1",
      "path": "audio/sources/linen-v1.wav",
      "sha256": "ACTUAL_64_CHARACTER_SHA256",
      "origin": "Selected prepared source; source preparation recorded separately",
      "audition": "not-recorded"
    }
  ],
  "stems": [{"id": "linen", "gain_db": -8, "role": "near object"}],
  "clips": [
    {
      "id": "hand-gesture",
      "source": "linen-v1",
      "stem": "linen",
      "source_start_frame": 24000,
      "frames": 96000,
      "at_frame": 528000,
      "gain_db": 0,
      "fade_in_frames": 480,
      "fade_out_frames": 960,
      "circular_tail": true,
      "pan_points": [[0, -0.3], [95999, 0.2]],
      "picture_event": "mummy-hand-lift"
    }
  ]
}
```

All timing is integer sample frames, including source regions, placement and fades. `frames` in the session is its exact loop length. Clip `frames` includes any supplied decay or room tail. CLI excerpt seconds are rounded to the nearest sample, and the actual resulting indices are recorded. An excerpt is taken from the arranged full loop, so a tail crossing its circular boundary remains audible at the beginning of a proof; the excerpt does not restart clips or invent new fades.

The session requires `format`, `schema_version`, `id`, `sample_rate`, `frames`, sources, stems and clips. Optional session fields are `master_gain_db`, `notes`, `imported_from` and `picture_events`. The last three are records, not processing commands. Unknown fields fail, so an unsupported processing instruction cannot silently look implemented. IDs use letters, numbers, dots, underscores and hyphens, begin with a letter or number, and are at most 100 characters.

Sources require `id`, `path` and `sha256`; `origin` and `audition` are optional records. Every source referenced by a clip is selected and hash-checked, including sources on muted or solo-excluded stems. A missing, changed, truncated or wrong-rate selected file fails. Unreferenced sources are candidates and are reported without being loaded. Changing a source is an explicit session revision and new hash, never a fallback to a different file.

Stems require `id`, with optional `gain_db`, `role` and `notes`. All stems are exported, including silence for an excluded stem. Stems include the variant settings and master gain; their unity sum reconstructs the master within PCM24 rounding. The mix is evaluated in floating point, has no limiter and rejects out-of-range PCM24 samples instead of clipping or normalizing.

Clips require `id`, `source`, `stem`, `at_frame` and positive `frames`. The optional fields are:

| Field | Behavior |
| --- | --- |
| `source_start_frame` | Start in the source, default 0. The complete region must exist. |
| `gain_db` | Relative clip gain, default 0 dB. |
| `repeat`, `every_frames` | Number of starts and distance between them. Defaults are one start and the clip length. Every start must lie within the session. Overlaps sum explicitly. |
| `fade_in_frames`, `fade_out_frames` | Linear clip-relative amplitude fades. The outermost sample is zero; a one-sample fade zeros that endpoint. These never fade the whole master automatically. |
| `circular_tail` | Defaults false. When true, existing samples past the session end wrap modulo its sample count. Multiple revolutions sum. When false, an overhanging clip is rejected. |
| `pan` | Static -1 left to +1 right. Explicit pan folds the source to `(L+R)/2` and uses equal-power placement. Omit pan to preserve stereo channels exactly. |
| `pan_points` | `[clip_frame, pan]` pairs, linearly interpolated across the complete clip. The first point is frame 0 and the last is frame `frames-1`. Cannot combine with `pan`. |
| `picture_event`, `notes` | Editorial relationship and notes. They do not move picture or assert visual timing validation. |

Pan applies to the supplied clip as a whole. For an object whose direct sound travels while earlier reflections remain in the room, supply separate direct and room-return sources/clips with their own routing. This backend does not synthesize distance EQ, room response or Doppler. A written depth role does not turn into processing.

## Numerical checks and limits

`audio inspect SESSION` validates identity and shows selected-source measurements plus the authored timeline. A mix report shows master/stem measurements, one-second rolling RMS windows at a half-second hop, and every cue's event windows. Wrapped event windows are split at the loop boundary. Comparing room and gesture measurements in the same window helps expose a buried event; it is not a perceptual masking score.

`audio check FILE.wav` measures the decoded PCM. `audio check RUN_DIRECTORY` also verifies hashes, exact master/stem timing and unity stem reconstruction. It reports peak samples, full-scale sample count, last-to-first adjacent-sample delta, left/right RMS, and mono fold-down `(L+R)/2` levels. A fully cancelling mono fold is reported as silence with null dBFS. All logarithmic silence values are `null`, not JSON Infinity.

Peaks are **sample peaks**, not oversampled true peaks. RMS is unweighted dBFS, **not LUFS**. A seam delta is a numerical observation, not proof of a seamless musical phrase. The commands do not claim listening, spatial realism, phone readability, an effective score, AAC alignment or final media review. Record actual listening observations against the output filename/hash separately.

Regression fixtures in `tests/test_audio.py` check exact placement and circular tails, region selection, repeats, fades, stereo preservation, pan travel, relative A/B gains, excerpt timing, source mutation/missing-source failures, output immutability, reconstruction, tampering and unsupported processing fields. They require no provider or network.
# Explicit picture-action cue binding

Use [scene activity](SCENE-ACTIVITY.md) to measure the complete selected picture loop at stride one before binding sound. This is separate from the existing descriptive `picture_events` notes.

```sh
./ambiance --project PROJECT audio cue-bind audio/session.json --activity reports/activity/activity-report.json --links cue-links.json --pcm audio/selected.wav --out audio/session-cues.json
./ambiance --project PROJECT audio cue-check audio/session-cues.json --activity reports/revised-activity/activity-report.json --pcm audio/selected.wav --out reports/cue-check.json
```

The links input is an array such as `[{"clip_id":"rustle","action_id":"paper-turn","picture_frames":[30,150],"offset_samples":2400}]`. Each repeated clip start needs an explicit picture frame. `offset_samples` is a signed integer on the session PCM clock. The binding command requires every actual clip start to equal `picture_frame × sample_rate / picture_fps + offset_samples` exactly, without implicit rounding. Picture/session lengths and an optional selected PCM length must match. The source session is preserved; the output is a fresh derivative.

The optional session `picture_sync` version 1 stores the exact activity receipt hash, scene/catalog/plan/clock identities, measured action state hashes and authored cadence, links, selected source byte/decoded PCM hashes, and optional selected PCM identity. It never changes gains, samples, generation or audition state. `audio cue-check` returns nonzero on changed/deleted/retimed/repeated actions, picture fps/loop changes, moved audio clips, source changes or different selected PCM. A changed gesture can require sound review even if its first onset is unchanged. Identical-duration views with identical action state can reuse the same selected soundtrack; crop-dependent sound design remains an explicit separate session.

The diagnostics identify affected clip IDs and preserve before/after evidence. They do not choose replacement anchors, stretch waveforms, generate new effects or assert a listening pass. After deliberately revising timing, write a new binding and listen to the chosen picture/sound pair. Native tests verify identical selected PCM snapshots and exact sample counts/alignment across both view movies; lossy AAC decoding is not claimed to preserve PCM bytes.
