# Region preparation replay

Run a complete public-command path with locally drawn, cleared fixture images:

```sh
python3 examples/art-regions/replay.py /tmp/art-region-study
```

Use `--no-render` for a shorter CLI, compilation, placement and revision check. The default includes portrait and landscape still renders. The script saves every operation in `reports/replay.json`; it performs no provider calls.

Optional `--source IMAGE --mask MASK_JSON --paint IMAGE --paint-rect L T R B` uses copies of existing local art. The mask has the documented `{ "polygons": [...] }` format. Without `--paint`, an explicit source uses its own reference for a registered retention study. Local private painting inputs and their output artifacts are not bundled in this repository.

The replay initializes a dual-view study, compiles a mapped source plane, centers the study views on the traced subject, authors/builds a region, records and selects local paint through the generation ledger, registers and compiles the result, places it through `scene place`, captures a revision and renders both views. Returned state is explicitly unreviewed until visual observations are recorded. This is a static component study, not a complete film.

See [the contract](../../docs/ART-REGIONS.md) and [handoff](../../docs/architecture/REGION-ART-HANDOFF.md).
