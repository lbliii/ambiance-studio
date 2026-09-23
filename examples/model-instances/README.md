# Independent model instances and explicit adoption

Run the public argv replay with a fresh retained directory:

```sh
python3 examples/model-instances/replay.py --out .ambiance/model-instances/public-replay
```

The replay builds and lowers the complete C1/C2 geometric lantern, places two
independent instances, moves/mounts/varies/hides one, observes its bounded receiver
signal, captures a revision, adopts a compatible new version, restores the prior
scene, and reopens a project after its original source/package/project paths
become unavailable. Every actual argv, result, source identity and output hash is
retained in `evidence.json`. `index.html` presents the actual raster comparisons.
This is engineering evidence, not a painted film or artistic acceptance.

## Recipe and output contract

`model instance apply RECIPE [--dry-run] [--out REPORT]` is project-scoped.
`model instance inspect [--id ID] [--out REPORT]` returns pins, managed fingerprints,
part/runtime mappings, sockets, state, placement and relationships.
`model instance evidence --receipt RASTER --instance ID [--instance ID] --out FILE`
writes a fresh sealed model wrapper around an existing actual `render frame` or
`render views-proof` receipt. Frame evidence requires an explicit `--view`.
The wrapper is a typed raster provider; it does not turn static pixels into a
motion observation or model-local masks into scene coverage.

```json
{
  "format": "ambiance-model-instance-operations",
  "schema_version": 1,
  "expected_scene_sha256": "EXACT_CURRENT_SCENE_BYTE_HASH",
  "operations": [{
    "op": "place",
    "instance_id": "lantern-a",
    "package": "package",
    "package_sha256": "EXACT_MODEL_PACKAGE_JSON_BYTE_HASH",
    "placement": {
      "position": [60, 100], "scale": 1.5, "rotation": 0, "depth": 0
    }
  }]
}
```

Package paths are recipe-relative (absolute paths are accepted). CLI input and
output paths retain shell-relative semantics. `position` names the model pivot
in host pixels; scale is positive uniform, rotation is clockwise radians, and
depth is the unmounted root's parallax. State is the existing C1/C2 static-state
contract; only declared controls/variants are writable. A mount is
`{"layer":"ground","socket":"light","at_seconds":0}` and preserves the placed
world pose using existing `reparentAtTime`. `null` detaches by rebuilding from
the explicit saved world placement. This does not promise preservation of the
future world trajectory. Optional `order` has exactly one `before` or `after`
runtime layer target; it cannot split another instance's contiguous paint block.

`update` requires `expected_pin` and `expected_managed_sha256` from inspection.
It accepts complete replacements of `state`, `placement`, `mount` and `receivers`,
plus explicit paint order. Omitted fields retain the prior authored values.
A batch has 1–64 operations, with each instance ID appearing once. Duplicate
placements and stale retries fail; they never silently create another instance.

`adopt` additionally requires a new exact `package` and `package_sha256`, retaining
the same model family with a different version label. It accepts `reset_controls`
and `reset_variants` as arrays of existing explicit override identities. Dry-run
reports retained/reset/conflicting overrides and contacts plus before/after
effective state. An incompatible interface returns `applicable:false` without
publishing; actual adoption fails. This conservative subset accepts compatible
metadata/default revisions. Changed parts, sockets, registered drawing maps,
control interfaces/ranges, nested dependency pins and registration conflict.
Automatic remapping and transitive live upgrades remain unsupported.

## Source/receiver and transaction boundary

An optional receiver contact names an existing finishing illumination, an owned
source part, per-cel values and explicit valid host-pixel bounds:

```json
{
  "id": "floor",
  "source_part_path": ["candle", "flame"],
  "illumination": "a-floor",
  "values": [0.4, 0.7, 1, 0.6],
  "valid_bounds": [20, 60, 110, 120]
}
```

The adapter appends namespaced existing cel signals and opacity bindings with
`off:0`. The receiving surface owns its illumination paint and geometry. Hiding
the source disables its contribution; unrelated illumination stays unchanged.
Bounds are checked at the mount sample and each output frame (up to 100,000),
not continuously between frames. There is no automatic spatial light transport.
Unmanaged contact/writer edits conflict; source/receiver reauthoring is explicit.

All operations lower into one private candidate using the shared scene evaluator.
Static cel holds span the host duration in seconds; construction-proof fps and
duration are not imported. Runtime tuple identities remain stable across variants
and compatible adoption. Catalog art IDs include the package pin and reuse exact
immutable bytes across instances. The catalog retains previous-version assets so
ordinary scene history restore can reopen the old scene. Restoring a scene with
no instances also permits placing the same exact package again: retained art
identifies its already-contained package, which is verified before reuse. A
changed retained manifest or conflicting catalog mapping fails without replacing
the accepted package.

The transaction publishes an active generation beneath
`.ambiance/model-generations/<recipe-byte-hash>/`, then atomically replaces the
existing project configuration's scene/catalog pointers as the sole selection
commit. Other configuration fields are preserved. The selected scene remains
ordinary mutable scene state; captured previous scene/config files and contained
packages are retained immutable inputs. Dry-run and invalid candidates publish
nothing. Failure before pointer selection may retain an unselected complete
generation; an occupied generation is rejected rather than overwritten. Direct
file writers bypass the CLI lock; this is not a filesystem compare-and-swap.

Revision and evidence adapters re-lower the exact package/state, compare the full
managed subject (including signals/bindings), and derive runtime-to-compiler IDs
and exact recipe/pack/image pins. A recomputed fingerprint cannot authorize a
swapped valid pack or changed managed writer. All original asset comparisons
remain active for unrelated catalog entries. New scene-context evidence is
required after state/adoption changes; old captured revisions keep their pins.
Configured captures retain the selected project configuration as an animation
origin and captured control. Working comparison also checks selected scene/catalog
paths for historical captures without that origin. Switching active generations
therefore reports working divergence while the old revision remains intact and
renderable. Legacy literal-path gate watches remain a separate integration owner.

The broader model Phase 4–7 acceptance, character views, nonpaint roots, clipping,
animation controls, automatic light transport and whole-scene artistic trials
remain open.
