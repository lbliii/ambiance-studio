# Independent rig inspection example

This creates a new synthetic scene with a compound lift, attached body/gesture, front rim, fixed glass and a deliberately contaminated backing. The colored shapes are diagnostic placeholders. The recipe's “accepted gesture” label names a comparison pose; it is not an approval claim.

Run from the repository root and choose fresh directories:

```sh
python3 examples/rig-proof/create_fixture.py /tmp/ambiance-rig-inspection
./ambiance --project /tmp/ambiance-rig-inspection render rig-proof examples/rig-proof/compound-inspection.json --out /tmp/ambiance-rig-inspection-proof
./ambiance --project /tmp/ambiance-rig-inspection preview
```

Open the proof's `index.html` to inspect the entire frame, body details, hidden descendants, comparisons and amplified differences. Follow its playback link for all declared variants at actual speed. Inspect the red residual imprint; the tool preserves it for review and does not certify that the backing is clean.

The [rig-proof recipe](compound-inspection.json) refers to IDs already in this fixture's inventory. Adapt those IDs, explicit times and normalized crop rectangles to a different scene rather than treating it as another object inventory.

For encoded picture reuse, render the scene once, prepare two exact-duration stereo 48 kHz PCM WAVs, then run `media compose` twice against the same `picture.mp4`. See the [rendering and media command reference](../../docs/RENDERING.md).
