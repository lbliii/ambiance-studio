# Finite clock technical replay

This fixture uses generated solid-color test PNGs. It contains a moving root,
three cels, a cel-dependent socket/marker and a separate one-second local cycle
inside a 2.5-second finite shot. It is independent of canonical film projects.

Run from the repository root, replacing `/tmp/finite-clock-demo` with a fresh path:

```sh
python3 examples/finite-clock/create_fixture.py /tmp/finite-clock-demo
./ambiance --project /tmp/finite-clock-demo scene clock --file /tmp/finite-clock-demo/clock.json
./ambiance --project /tmp/finite-clock-demo scene apply /tmp/finite-clock-demo/acting.json
./ambiance --project /tmp/finite-clock-demo scene sample --frame -1 --context
./ambiance --project /tmp/finite-clock-demo scene sample --frame 59 --context
./ambiance --project /tmp/finite-clock-demo scene sample --frame 60 --context
./ambiance --project /tmp/finite-clock-demo scene sample --frame 61 --context
./ambiance --project /tmp/finite-clock-demo scene timing
./ambiance --project /tmp/finite-clock-demo scene check
./ambiance --project /tmp/finite-clock-demo render frame --time 2.5 --out /tmp/finite-clock-demo/endpoint
./ambiance --project /tmp/finite-clock-demo render video --out /tmp/finite-clock-demo/movie
./ambiance --project /tmp/finite-clock-demo media verify /tmp/finite-clock-demo/movie/picture.mp4 --frames 60 --fps 24 --contact-frame 59 --out /tmp/finite-clock-demo/decode
./ambiance --project /tmp/finite-clock-demo preview --port 8793
```

The decoded movie has 60 frames at 24 fps, duration 2.5 seconds. Frame 59 is yellow
and its white marker sits at the middle socket. The authored endpoint at frame 60
is blue and shifts the marker to the third socket. Requests beyond the endpoint
hold the blue pose. The small independent local-cycle card ends partway through
its third cycle. Inspect actual pixels and normal-speed playback separately from
state assertions. Preview Play holds frame 59; manual seek can inspect frame 60.

Meaningful failures to try in fresh output directories: `render video --repeats 2`,
`render proof --start 2 --seconds 1`, a missing `local_cycle`, a finite clock whose
frame count disagrees with the canvas, or a loop host that cannot close its local
cycle. Invalid authoring must preserve the previous scene/history.

Focused tests: `node tests/test-clock.mjs`, `python3 tests/test_clock_cli.py` (native
case requires `AMBIANCE_TEST_NATIVE=1` and macOS media-service access). The full
required-native suite discovers both files. [Clock contract](../../docs/FINITE-CLOCK.md)
documents explicit revision labels, rational serialization and residual signs.
