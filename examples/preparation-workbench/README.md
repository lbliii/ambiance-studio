# Blue cabinet preparation exercise

This creates an independent 384 × 512 synthetic source/backing pair and a preparation recipe. A brass botanical ornament rises behind a fixed front rail. These shapes demonstrate registration, mask editing and overlap inspection; they are not a newly produced painted film.

```sh
python3 examples/preparation-workbench/create_fixture.py work/preparation-example
./ambiance preview --prepare work/preparation-example/assets/prepared/cabinet-v1 --port 8785
```

Choose **Maximum**, then **Hide object**: the backing should reveal the empty cabinet while the foreground rail stays present. In the cutout mask, draw a subtraction polygon over one leaf and close it. The isolated cutout should show the hole, and undo should restore it. Move the backing three pixels horizontally to inspect alignment differences. Try a singular affine (zero X scale without shear): it must retain the last valid preview and explain the rejection.

Change vertical travel from −20 to −32 source pixels, export the recipe and rebuild it in a new output directory. Compare the recipe and generated scene. `render frame/proof/video` can render the saved `preview-project` with the normal shared engine.

The fixture has preauthored polygon masks. The block-shaped pedestal mask retains small background corners around the rounded source pedestal, which are visible in the isolated view; correcting those boundaries is a useful manual exercise. The fixture does not establish automatic segmentation or a fresh-painting/operator benchmark.

The [workbench guide](../../docs/PREPARATION-WORKBENCH.md) specifies the saved contract and remaining limits. `tests/test_preparation.py` covers source preservation, mask independence, affine registration, soft-mask inputs, immutable rebuilds, rejected input changes, compiler source mapping, actual raster rendering and local preview/export routes.
