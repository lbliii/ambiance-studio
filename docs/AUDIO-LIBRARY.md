# Typed local audio library (LIB-01)

The `audio library` routes store versioned local sources, prepare audition excerpts, record explicitly supplied listening observations, and copy selected bytes into another project. They make no provider calls. [Source preparation](AUDIO-SOURCES.md) remains the preparation evaluator; [audio sessions](AUDIO-SESSION.md) remain the arrangement contract. Visual image/model libraries are unchanged. Collection curation, new mixes, source generation, loudness/true-peak and encoder work are outside this slice.

## Configuration and routes

Create a fresh library with a stable, explicit location outside a Git checkout or film project. Both paths must be absolute. There is no current-directory search, environment default or implicit media-root fallback. Keep the config alongside other durable personal settings; the library holds its own sealed ID and the config pins that identity. These files contain local paths, never credentials.

```sh
./ambiance audio library configure --config /ABS/settings/audio-library.json \
  --media-root /ABS/media/ambiance-audio --library-id personal-audio
./ambiance audio library search rain --config /ABS/settings/audio-library.json --kind bed
./ambiance audio library inspect rain --version prepared-v1 --config /ABS/settings/audio-library.json
```

`configure` requires fresh root/config paths and never replaces an existing library. Source hashes are identities, not backups. Relocating a library/config is an explicit operator action, never inferred from a missing directory. Small disposable roots outside a checkout are valid for technical fixtures.

| Route after `audio library` | Inputs and result |
| --- | --- |
| `configure` | Required `--config`, `--media-root`, `--library-id`; initializes a fresh local store. |
| `search [QUERY]` | Required `--config`; optional `--kind bed/event/music`, `--state candidate/prepared/auditioned/accepted/rejected/revise`, `--out FILE`. Checks versions and review chains, then filters descriptive metadata. |
| `inspect ASSET --version VERSION` | Required `--config`; optional `--out FILE`. Exact version hash, original/working formats, metadata, review state/hash, event records and verified playable audition paths. |
| `import ASSET --version VERSION` | Requires a selected project, config, `--kind`, `--sha256` and exactly one project-relative `--source` or `--preparation`. Source imports also require `--backend pcm/macos-afconvert`; raw source flags mirror source inspection. |
| `audition ASSET --version VERSION` | Required config, `--expect-version HASH`, `--audition-id ID`; optional integer `--start-frame`, `--frames`. Publishes a fresh exact PCM excerpt, with no listening state change. |
| `observe ASSET --version VERSION` | Required config, `--expect-state HASH`, `--event-id ID`, shell-relative `--observation FILE`. Records a supplied actual listening declaration against exact bytes. |
| `promote ASSET --version VERSION` | Required config, `--expect-state HASH`, `--event-id ID`, `--decision accepted/rejected/revise`, `--by`, `--note`. Acceptance additionally requires `--observation-sha256 HASH` identifying the current suitable full-source listening event. |
| `materialize ASSET --version VERSION` | Requires a selected destination project, config, `--expect-version HASH`, `--expect-state HASH`, `--materialization-id ID`. Copies an accepted preparation into `audio/library/ID/`; explicit `--allow-unaccepted` permits diagnostic use and retains the unaccepted state. |
| `check RECEIPT` | Requires selected destination project and its project-relative receipt; optional `--out FILE`. Validates only contained files and the archived version/review identity; needs no library config. |

These nested routes preserve the existing envelope (`command: "audio library"`) and include `data.operation` with the leaf operation. `--out` belongs to the CLI result-envelope writer on search/inspect/check. Other routes publish their named fresh config, version, audition, event or materialization paths, and do not accept `--out`. Import metadata and provenance filenames are project-relative; the listening observation filename is an explicit shell-relative input.

## Immutable versions and imports

```sh
./ambiance --project ORIGIN audio library import rain --version original-v1 \
  --config /ABS/settings/audio-library.json --kind bed --source audio/rain.wav \
  --sha256 ORIGINAL_SHA256 --backend pcm --provenance audio/rain-provenance.json
./ambiance --project ORIGIN audio library import rain --version prepared-v1 \
  --config /ABS/settings/audio-library.json --kind bed \
  --preparation audio/preparations/rain-48k/receipt.json --sha256 RECEIPT_SHA256 \
  --parent-version original-v1 --parent-sha256 ORIGINAL_VERSION_SHA256
```

A source import fully inspects existing media and preserves its exact bytes as a `candidate`. A preparation import first runs `audio_sources.validate_preparation`, then preserves the original, working file, recipe and sealed source receipt verbatim as `prepared`. A prepared import can be the first version of an asset; it does not need a fabricated earlier candidate record. It cannot override recorded backend, raw declaration or provenance. Import never resamples, enhances or generates a source.

Each immutable package is `versions/ASSET/VERSION/version.json`, format `ambiance-audio-library-version`, schema 1. The record includes library/asset/version identity, kind, creation time, optional parent pin, exact file references (`path`, SHA-256, bytes), source and working formats, provenance, metadata and limits. Original/prepared identities are separate. An existing asset needs an explicit prior version and its current hash; parent chains must exist, be acyclic, retain the same original bytes and match their pins. A new original needs a new asset ID. Preparation/metadata changes never inherit listening or acceptance.

Version IDs and event/audition IDs cannot be reused. Identical original/working/recipe hash tuples are detected across asset IDs and refused with the existing version path. Candidate and prepared versions have different tuples. This bounded store preserves one original and working file per version; it does not implement a global blob collector or storage deletion.

Optional `--metadata FILE` contains descriptive `role`, `family`, `material`, `intensity`, `tonal_character`, `distance`, `room_treatment`, `channel_behavior`, `pairing_notes` and `limitations`. These are supplied descriptions, not DSP. `suggested_gain_db` is only a starting suggestion. Optional `measurements` is an array of `{method, source_sha256, notes}`, pinned to a file in this version; no LUFS/true-peak measurement is performed. Timing uses the working clock when prepared, otherwise the source clock:

```json
{"role":"quiet background","distance":"recorded distant perspective",
 "loop":{"start_frame":0,"end_frame":1440000,"closure_recipe":"Describe the actual existing join preparation"},
 "limitations":"No new listening observation recorded"}
```

Use either `loop` or `tail: {tail_frames, silence_frames, notes}`; indices/counts must fit the selected source. There is no executable `seamless: true` field. Actual source codec/container, meaningful bit depth, rate, channel layout and frame count remain the AUDIO-01 observations. PCM24 does not establish lossless ancestry. Unknown entitlement, provider history, prior loss and undocumented room treatment remain unknown; declaration is not verification.

## Audition, observations and decisions

An audition excerpt copies an exact integer sample region of the selected working WAV, preserving bits/rate/channels and sample bytes. It defaults to up to 30 seconds and is bounded to 60 seconds. The sealed `ambiance-audio-library-audition` v1 receipt pins version, source, region and output. Inspection checks its actual payload against the selected source region. Rendering it leaves the source `prepared`.

Only `observe` can record `auditioned`, and only a current suitable observation of the complete working source permits acceptance. For longer sources, listen to the full working WAV directly; a short excerpt cannot be misrepresented as full-source evidence. An observation input has this shape; replace every field with actual facts before recording:

```json
{
  "version_sha256":"EXACT_VERSION_SHA256",
  "source_sha256":"EXACT_WORKING_WAV_SHA256",
  "listened":true,
  "observer":"Actual observer",
  "observed_utc":"2026-09-13T00:00:00+00:00",
  "device":"Actual playback device",
  "playback_path":"Actual player and selected file",
  "start_frame":0,
  "frames":1440000,
  "heard":"Actual listening observations and limitations",
  "suitability":"suitable"
}
```

Optional `audition: {id, sha256}` binds a saved excerpt; its region must equal the observation. Suitability may be `suitable`, `unsuitable`, `revise` or `unknown`. Missing/empty observation facts, `listened: false`, future/unzoned timestamps, stale versions, changed excerpts or regions beyond the source fail. The tool validates identity and a declaration's completeness; it cannot independently verify that the declared human listening happened. A software test's simulated observer is not production audition evidence.

Observations and decisions are append-only sealed `ambiance-audio-library-event` v1 files. Sequence number, unique ID, previous event hash and exact version pin define one review chain. `state_sha256` identifies its head (initially the version file hash). A library writer lock serializes CLI import, audition, review and materialization. Stale promotion or a stale materialization selection fails. `rejected` and `revise` decisions need explicit notes, and do not claim an audition. Recording a later observation deliberately returns the version to `auditioned` until another explicit decision. Old event bytes remain intact. Direct manual file edits are detected by seals/dependency checks and are not a supported write path.

## Portable materialization and revision use

Materialization writes a new sealed `ambiance-audio-materialization` v1 receipt, kind `library-source`, under the destination project's `audio/library/ID/receipt.json`. Its `source/` contains exact original/working/recipe bytes, the unmodified prior preparation receipt and version file, and any review events/referenced audition files needed to validate the chosen review state. It contains no published hard links or symlinks. Default use requires `accepted`; diagnostic opt-in preserves its actual state.

The new receipt pins its library version, contained source-version snapshot, contained files and review state. Its dependency array is derived from explicit typed file roles. Prior preparation origin paths and a version's prior parent pin are archival provenance; they are never live external dependencies or generic recursively collected references. The archived version is an immutable snapshot, not a promise that an external library is still available.

AUDIO-01's sealed receipt remains unchanged. To reuse its evaluator, validation reconstructs that receipt's namespace only inside a disposable temporary projection, connecting its origin and preserved-original references to the exact local original. Read-only hard links with byte-copy fallback avoid redundant validation I/O. Nothing in that temporary namespace is published. `audio_sources.validate_preparation` then checks the existing recipe/format/layout/sample-count semantics; there is no second preparation evaluator and no change to preparation v1. Archival paths must still be safe relative paths within that temporary namespace.

The command returns a strict session `source` object with destination-relative path/hash and actual library state. Put that source into an authored session, and include the receipt in an existing revision selection's `audio.preparations`:

```json
{"audio":{"session":"audio/session.json",
           "preparations":["audio/library/rain-use-v1/receipt.json"]}}
```

The typed revision adapter pins only the destination receipt and contained dependencies under `sound-design`; it adds no master and awards no film gate. Missing or changed selected bytes fail capture/check. A project handoff must copy the selected project bytes, including this materialization and revision controls. `revision handoff` produces review/path summaries; it is not a source copier. Restoration means restoring the exact pinned bytes at the recorded project-relative paths, or authoring a new version/materialization; there is no silent version adoption.

Run the [public replay](../examples/audio-library-replay/README.md) for actual CLI argv and portable source/revision evidence. The replay removes the original library/project addresses, validates source use in a second project, then copies that project and verifies again. Its generated local tone stays unaccepted; no listening or collection completion is claimed.
