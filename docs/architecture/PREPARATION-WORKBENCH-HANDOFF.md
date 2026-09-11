# Preparation workbench: first implementation handoff

The first slice of the [plan](ASSET-PREPARATION-WORKBENCH.md) is implemented. `asset prepare` creates an immutable separation workspace from source/backing images or an exported recipe. `preview --prepare` combines mask and alignment editing with a shared-engine movement proof. The [user guide](../PREPARATION-WORKBENCH.md) documents the contract and commands.

The workspace supports independent removal, retained-object and fixed-foreground masks; polygon addition/subtraction and undo; optional existing soft grayscale masks; full affine backing registration; isolated light/dark/checker inspection; changed-rest-pixel diagnostics; rest/maximum/play/seek and hidden-part views; and server-backed recipe downloads. Python rasterizes both saved and interactive masks. The generated scene uses the existing evaluator and renderer, and the saved parts have compiler recipes and source-coordinate mappings.

## Validation

The final `AMBIANCE_TEST_NATIVE=1 ./ambiance test` passed **195 Python tests with no skips**, the existing engine, rig, track, source-placement and finishing JavaScript checks, and the package audit. Eleven new preparation tests cover independent masks, subtraction, existing soft alpha, affine alignment, invalid inputs, input tampering, mid-build changes, occupied destinations, immutable rebuilds, compiler registration, actual native Canvas pixels, preview origins/routes and exported recipes. The full local report is `work/preparation-workbench-native-regressions.json`.

Actual browser inspection used the independent [blue cabinet fixture](../../examples/preparation-workbench/README.md). A subtraction polygon visibly cut a triangular hole in a leaf, undo restored it, invalid registration retained the valid picture, a three-pixel backing offset changed the expected picture region, and hiding the object exposed clean backing under the fixed rail. Playback, pause and frame seeking worked. Normal-speed playback reported approximately 30 fps when active; it also reported skipped frames during background/tool activity.

The browser changed vertical travel from −20 to −32 source pixels, downloaded the recipe, and the CLI rebuilt it into a fresh workspace. The downloaded bytes match the recorded recipe. The generated scene produced a four-second 384 × 512 H.264 proof that fully decoded to **120 frames** with correct timestamps. Actual decoded rest and maximum frames were inspected; the botanical ornament rises and rotates while the foreground rail and cabinet stay fixed. This proves the local preparation/export/render path on the fixture, not a new artistic film approval.

Local evidence:

- `work/preparation-workbench-fixture/reports/preparation-workbench-review.json`: performed observations and exact artifact/code/movie identities.
- `work/preparation-workbench-fixture/assets/prepared/review-v1/`: final workbench, exported recipe, source snapshots, compiler recipes and render-only preview project.
- `work/preparation-workbench-fixture/render/browser-export-v1/`: encoded proof, render receipt, full decode report and decoded contacts. Its scene/catalog bytes match the final workbench's preview project.

## Remaining milestone and limits

The next milestone is a measured object-preparation pilot on a different painting. The current fixture uses synthetic art and preauthored polygons, so it does not establish independent operation, preparation-time savings or avoided generations. Select suitable existing source/backing art, carry it through public preparation/compile/place/render commands and record actual manual work and review rounds.

The first editor handles one rigid part and one fixed foreground layer. Compound rigs remain in the scene tools. Polygon masks are hard-edged; imported grayscale masks preserve soft alpha outside edited regions. The fixture intentionally leaves small background corners around its rounded pedestal visible in isolation as a preparation exercise.

Live preview requires the recorded preparation implementation/Pillow version. Saved masks match interactive mask bytes exactly; browser/native Canvas sampling can differ at edges. Compiler source mappings pin source and prepared image, while full separation provenance remains in the complete preparation artifact; the revision dependency schema was not extended in this slice. No existing film, accepted source, sound session, review selection or provider account was changed.
