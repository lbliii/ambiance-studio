# LIB-01 public replay

Run from the checkout with a fresh absolute directory outside every Git checkout:

```sh
python3 examples/audio-library-replay/replay.py --out /private/tmp/ambiance-lib01-replay
```

This creates a tiny local stereo tone, explicit library config and two disposable projects. All production operations use `./ambiance`: configure, candidate/prepared import, search, inspect, excerpt creation, negative promotion/duplicate checks, materialization, source/session validation and revision capture/check. Every actual argv, result and exit status is saved in `replay.json` with implementation and artifact SHA-256 identities.

The original project, library and config are renamed after materialization, making their recorded locations unavailable. The second project's contained files remain valid. Its complete project is then copied to `portable-handoff`, the second address is removed, and source use/revision checks run again. The original, working samples, sample rate, channel count and sealed prior receipt retain their exact identities. `portable-handoff` is a usable package; a revision handoff summary alone would not contain the media.

The replay does not generate a new mix, invoke a provider, record an audition or accept the source. Promotion without actual observation is expected to fail. Diagnostic materialization explicitly uses `--allow-unaccepted`. The unit test suite separately labels every simulated review input as a software fixture; none is real listening evidence.

See the [audio library contract](../../docs/AUDIO-LIBRARY.md) for every route, output ownership, version/review state and typed receipt.
