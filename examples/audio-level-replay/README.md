# AUDIO-02 public replay

From the repository root, use a fresh retained output directory:

```sh
python3 examples/audio-level-replay/replay.py --out .ambiance/audio02/trial --native
```

The fixture library lives in a retained independent system temporary directory, whose exact path and file hashes are reported. The script invokes public CLI argv, saves every response/failure and hashes the source tree plus all output artifacts. It generates deterministic reference signals from EBU Tech 3341's published definitions (1–5 and 15–19), checks their numerical tolerances, and retains silence, short, gated, mono, anti-phase, wrong-rate, truncated and changed-hash cases. It preserves a source through AUDIO-01, measures the exact prepared output and LIB-01 unaccepted materialization, captures an explicit synthetic master recipe, and produces real revision-bound native 256/320 kbps AAC editions plus a 384 kbps trial. The host may reject the latter before creating any render output. `media compose` also exercises picture reuse and configured audio encoding. A deliberately altered float artifact must block the edition export review in the existing project status before its original bytes are restored.

`--native` requires local macOS Core Audio/AVFoundation and Node Canvas access. Omitting it exercises measurements and source/revision identity without claiming native encoding. Failures remain in `replay.json`; native runs never skip a required successful supported-rate encode. No EBU recordings are redistributed. No source normalization, production mix, library acceptance, listening or artistic approval is performed.

The [method contract](../../docs/AUDIO-LEVELS.md) states backend, interval, gate, true-peak and compatibility limits. Test sources can be loud; this replay measures them and does not play them.
