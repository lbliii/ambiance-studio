# Independent edge-quality CLI pilot

```sh
python3 examples/edge-quality/build_example.py /tmp/ambiance-edge-quality-v1
```

Use a fresh destination. The script makes four synthetic calibration cels with deliberately known light-matte contamination and faint silhouette detail. It uses the public CLI to initialize a project, derive a declared-matte repair, compile both original and repaired sheets, and inspect them at exactly the same 48-pixel cell size against light, dark, and a native-pixel blue floor context.

Open `reports/before-edges/index.html` and `reports/after-edges/index.html`. Both have matching cadence, context rectangle, size, cel controls and magnification. The repair leaves alpha unchanged; the faint tail/whisker shape remains present while partially transparent RGB is corrected for the declared matte. This is a calibration fixture, not new museum art or proof that this correction is appropriate to any production sprite.

`assets/repaired/` preserves exact original bytes, recipe, before/after evidence, and hashes. `edge-pilot-receipts.json` records every actual command result. The source remains unchanged. No model generation, account spending, accepted library mutation, or production project review is involved.

See [the edge workflow contract](../../docs/EDGE-QUALITY.md) for limitations and diagnostic steps from source to decoded video.
