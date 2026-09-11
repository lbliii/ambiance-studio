# Coordinated painted-light fixture

The fixture uses locally drawn test cards and a prepared dim floor. It exercises a flame mounted to a pumpkin, independent floor paint, source intensity/lean/cel bindings, moving receiver, fixed foreground blocker and portrait/landscape views. It does not represent a production painting.

```sh
node examples/bindings/create_fixture.mjs projects/binding-proof
./ambiance --project projects/binding-proof binding inspect --time 1
./ambiance preview --views-proof projects/binding-proof/render/paired --port 8798
./ambiance preview --look projects/binding-proof/render/look --port 8799
```

Choose a fresh destination. The creator uses the public CLI to initialize, author, inspect, capture, render and export a reusable package. The paired proof plays the same four-second loop in both compositions at its actual 12 fps. The look proof lets you inspect the painted illumination pass. Serve `render/browser-parity/` on localhost to compare browser pixels with CLI PNGs from the same scene; it requires exact receiver/mask/occluder pixels and confines any rasterizer difference to the rotated source edges. Reports preserve source inputs and runtime hashes. Low/rest occurs at 0 seconds, high/right at 1, off/rest at 2, low/left at 3; the loop joins at 4. A separate source-hidden proof shows the prepared base.

Automated tests cover these state/pixel behaviors and compiler/package preservation. Actual visual observations and native encoded evidence are recorded separately; no human artistic approval is implied.
