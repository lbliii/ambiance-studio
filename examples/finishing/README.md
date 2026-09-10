# Finishing production trials

Create an independent creature, lamp, floor and lifting-casket fixture through the public CLI:

```sh
python3 examples/finishing/create_fixture.py --out /tmp/ambiance-finishing-demo
./ambiance --project /tmp/ambiance-finishing-demo look check
./ambiance --project /tmp/ambiance-finishing-demo preview
```

The generator creates geometric engineering artwork, registered packs, shared cel illumination, a moonlight zone, ground sockets, projections and a reusable look package. These are technical examples, not accepted artwork. See the [finishing contract](../../docs/FINISHING.md) for package bindings and optional rig reuse, and the [look workbench](../../docs/LOOK-WORKBENCH.md) for editable comparisons.

To reproduce the museum comparison in a fresh, separate project:

```sh
python3 examples/finishing/museum_trial.py work/museum-finishing-trial
./ambiance preview --look work/museum-finishing-trial/look-proof --port 8817
```

This imports exact copies of the current museum's used images, records original hashes, compares baseline correction and local light, and saves a 93-frame motion proof plus a supersampled 1080 × 1920 frame. It verifies all 34 selected source files afterward and does not edit the museum. The source project is an explicit `--source` option; the default is the local `projects/the-midnight-collection`, which is not included in a fresh clone.
