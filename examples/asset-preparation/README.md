# Independent crop/return and registration fixture

Run from the repository root with Python and Pillow:

```sh
python3 examples/asset-preparation/build_example.py /tmp/ambiance-crop-example-v1
```

Choose a fresh destination. The example creates its own portrait reference fixture, runs decoded preflight, enlarges a bounded crop, explicitly authorizes identity registration in a return recipe, returns the unchanged crop, and compiles the native patch with source mapping. It verifies exact nearest-neighbor round-trip pixels and preserves the original source bytes. No provider, active production project or accepted library asset is used.

Inspect `preflight/`, `crop/`, `returned/` and `pack/`. The returned `source-mapping.json` binds exact image/reference identities, while `pack/asset.json` exposes composed per-cel reference placement. The authored `return.json` illustrates the distinction between explicitly recorded registration and an unfilled return template.

The same operations are available through `asset preflight`, `asset crop`, `asset return` and `asset build`; see [the contract](../../docs/ASSET-PREPARATION.md) for command syntax and path conventions.
