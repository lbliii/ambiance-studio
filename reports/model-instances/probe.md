# I1/I2 capability probe

Base: `75d24b85a8977f234d87daa1c18993d394036c1c`.

Executed the existing public `model build` and `model lower` on the actual
`examples/model-construction/create_fixture.py` lantern at `/tmp/m3-probe-*`.
Construction and lowering succeeded, with five owned painted leaves and four
registered mounts. The specimen is geometric engineering art. No new painting
or artistic acceptance is implied.

The closest operation emits a fresh standalone one-second compatibility scene;
it has no destination scene, independent instance namespace, previous pin,
managed-layer fingerprint, version adoption or transaction merge. The existing
scene transaction commits only a scene, whereas placement also needs catalog
entries. The implementation adds an instance adapter and a scene/catalog bundle
commit; it consumes the existing lowerer, affine functions, reparent-at-time and
scene validator. It does not add another evaluator or renderer.

Public probe argv:

```sh
python3 examples/model-construction/create_fixture.py --out /tmp/m3-probe-source
./ambiance model build /tmp/m3-probe-source/models/lantern.json --source-root /tmp/m3-probe-source --out /tmp/m3-probe-package
./ambiance model lower /tmp/m3-probe-package --state /tmp/m3-probe-source/rest.json --out /tmp/m3-probe-lowered
```
