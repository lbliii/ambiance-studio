# Audio source CLI replay

Run from the repository root with a fresh disposable output directory:

```sh
python3 examples/audio-source-replay/replay.py --out /tmp/audio-source-pcm
python3 examples/audio-source-replay/replay.py --out /tmp/audio-source-compressed \
  --source /absolute/path/to/existing.mp3 --backend macos-afconvert \
  --provenance /absolute/path/to/known-provenance.json
```

The first command creates a 100 ms deterministic stereo fixture. The second copies an existing source before running the same public commands; no original is modified. Omit `--provenance` only when source history is unknown. Native execution requires working installed Core Audio services, which may need an execution context outside a filesystem sandbox. The script does not request generations, install dependencies or retry through another backend.

Every replay performs public source inspection, immutable preparation, receipt validation, revision capture/check, duplicate-ID rejection and truncated-source rejection. `replay.json` records exact argv, CLI envelopes, input/output hashes and artifact paths. It never renders or selects a movie. The new project and its artifacts may be removed after inspection.

Focused regressions:

```sh
python3 tests/test_audio_sources.py
AMBIANCE_TEST_NATIVE=1 python3 tests/test_audio_sources.py
```

The native mode adds real locally encoded AAC/ALAC mono/stereo fixtures, 44.1→48 kHz conversion, exact counts, 32-bit input, fractional target duration and waveform reconstruction checks. It fails if the backend is unavailable; it does not infer a pass from discovery. MP3 structural failure fixtures are synthetic; the read-only research replay separately exercises actual preserved MP3 originals. No listening, device or artistic review is implied.
