# Immutable local model replay

This C1/C2 engineering example compiles the existing mc/1 geometric artwork into a complete raster-root lantern, nested candle/flame and two compatible frame drawings. A separate synthetic translucent pane exercises glass coverage. It supplies static rest, left/right extremes, unlit and hidden states for each frame variant. It does not claim production paint, motion, receiver behavior, independent scene instances or artistic acceptance.

The [implemented contract](../../docs/architecture/model-contract/construction-v1.md) specifies package identity, controls, registration and proof boundaries. No paid generation or canonical film edits are needed.

```sh
python3 examples/model-construction/replay.py --out work/model-replay
```

The wrapper records and invokes the actual public CLI for build, inspect, lower, scene check, proof, freshness check and technical admission. It then moves the original source/package/proof away and reopens the portable entry. The second lowering must reproduce the same ordinary scene, catalog and tuple mapping. Each command and exact result, source/artifact hash and retained evidence path is saved in `evidence.json`. Use a fresh output directory for each replay.

Individual public commands (fresh destinations required):

```sh
python3 examples/model-construction/create_fixture.py --out work/model-source
./ambiance model build work/model-source/models/lantern.json --source-root work/model-source --out work/model-package
./ambiance model inspect work/model-package --out work/model-inspect.json
./ambiance model lower work/model-package --state work/model-source/rest.json --out work/model-local
./ambiance --project work/model-local scene check
./ambiance model proof work/model-package --recipe work/model-source/proof.json --out work/model-proof
./ambiance model check work/model-proof --package work/model-package --recipe work/model-source/proof.json
./ambiance model admit work/model-package --proof work/model-proof --recipe work/model-source/proof.json --out work/model-entry
./ambiance model inspect work/model-entry
```

Inspect `model-entry/proof/index.html`. Each sample includes original-source versus compiler-assembly images, composite transparency, authored solid/glass/flame passes, threshold masks and existing rig-proof output. `model-proof.json` binds exact states, effective controls, selected/hidden leaves, compiler/source registration, renderer/runtime identity, crop/resolution/threshold policy and all output bytes. Changing the state or implementation makes the previous proof stale.

Compiler replay from the retained entry is independent of the old source directory:

```sh
./ambiance asset build work/model-entry/package/source/packs/flame/recipe.json --out work/flame-rebuilt
```

Atlas bytes and full-cell registration should match; compiler metadata paths deliberately reflect the new build location. Every portable editable recipe retains the original input image bytes. The local library entry's status remains `technical-candidate`; there is no automatic artistic promotion.

Focused checks:

```sh
python3 -m unittest discover -s tests -p test_models.py -v
python3 -m unittest discover -s tests -p test_cli_contract.py -v
python3 tests/test_assets.py
node tests/test-rig.mjs
node tests/test-bindings.mjs
node tests/test-source-placement.mjs
```
