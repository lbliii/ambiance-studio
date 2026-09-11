# Agent preparation and recovery

The public `asset prepare` commands extend the existing separation rasterizer, compiler, source-placement evaluator and saved-view renderer. They operate on existing local art. The legacy `asset prepare SOURCE --backing FILE --out DIR` and `--recipe FILE` interfaces remain supported.

```sh
./ambiance --project PROJECT asset prepare init legacy-recipe.json --out PROJECT/assets/prepared/draft
./ambiance --project PROJECT asset prepare inspect PROJECT/assets/prepared/draft
./ambiance --project PROJECT asset prepare edit PROJECT/assets/prepared/draft \
  --batch edits.json --expect-sha256 HASH_FROM_INSPECT --out PROJECT/assets/prepared/edited
./ambiance --project PROJECT asset prepare check PROJECT/assets/prepared/edited
./ambiance --project PROJECT asset prepare build PROJECT/assets/prepared/edited --out PROJECT/assets/prepared/compound
./ambiance --project PROJECT asset prepare proof PROJECT/assets/prepared/compound \
  --out PROJECT/reports/compound-proof --long-edge 640
```

`inspect` returns source coordinates, part/binding/companion IDs, warnings and artifact paths. `check` additionally exits nonzero for preparation warnings. Those diagnostics identify work; they do not certify the art. `init` converts a legacy recipe into an editable compound checkpoint. `edit` validates the complete bounded batch before publishing a fresh checkpoint with parent recipe and batch snapshots. A failed or interrupted edit leaves the prior recipe intact; retry into a fresh output. Every build preserves exact input snapshots, prepared images, mappings, compiler recipes, a receipt and an isolated preview project. Existing destinations are never replaced.

## Compound recipe

`format: ambiance-compound-preparation`, `version: 1`, `path_base: project` uses the existing source/backing image identities and affine, `resampling`, shared `removal` mask, `seconds`, `parts`, and optional `context`. Parts have a unique lowercase `id`, `kind: cutout|occluder`, `mask`, source-pixel `pivot`, and optional `motion: {delta:[dx,dy],rotation_degrees}`. Fixed occluders cannot own motion. `source` on a part explicitly supplies reconstructed paint on the complete reference canvas; its absence uses the original source. Moving original occluded paint cannot reveal pixels that were never painted: supply a reconstructed part source and clean backing when needed.

Masks use the existing `{polygons:[{operation:add|subtract,points:[[x,y],...]}],image?:{file,sha256,width,height}}` contract. Imported grayscale masks preserve delicate alpha outside explicitly edited polygons. A `companions` list contains `{id,image}` grayscale masks registered on that same full source canvas. A companion exports white RGB with the original grayscale alpha. It is not automatically applied as lighting; its owner is recorded for the receiving/lighting tools.

One recipe supports 1–16 parts, up to four companions per part and 64M aggregate source pixels. Source sides are limited to 4092 to reserve two pixels of compiler padding without independent fitting. Existing polygon/vertex limits still apply. Unsupported shear/reflection in source-to-scene placement fails explicitly. No segmentation, missing-paint inference, motion reduction or paid generation is performed.

A version-1 edit batch has 1–64 `operations`:

- `set-mask` and `append-polygon`: `mask: removal`, or `part: ID, mask: cutout`, plus `value`.
- `set-motion`, `set-pivot`, `set-binding`, `set-companions`, `set-source`: `part: ID, value`.
- `add-part`: `value` containing a complete part; `remove-part`: `part: ID`.
- `set-alignment`, `set-context`, `set-seconds`: `value`.

Related changes belong in one batch. The result may be a study with `context: null`, which is explicitly labeled unbound. Quiet proposed motion does not change its part boundaries or required hidden paint.

## Production binding and saved compositions

Bound recipes use `parts[].binding: {element_id,inventory_part:{item_id,part_id}}` from the canonical [production plan](PRODUCTION-PLAN.md). The plan owner's validator resolves these references; preparation does not define another inventory or semantic census.

`context` contains project-relative `{file,sha256}` identities for `scene`, `production_plan` and canonical `inventory`, all intended saved `views` as IDs, and a source-pixel-to-authored-scene-pixel `source_to_scene` affine. The view IDs must exactly cover the production plan's outputs. Explicit single-view plans remain valid. Binding inspection validates source identities and the exact saved view envelopes through the shared view resolver. The proof scene retains these envelopes and uses the recorded affine; it is an isolated preparation study, not evidence that an entire film has been staged or reviewed.

The preparation receipt pins immutable snapshots of the scene/plan/inventory controls, while retaining their original paths and hashes under `context`. Subsequent scene authoring does not corrupt a completed pack. Current-plan/view compatibility remains a separate coverage check. Images, reconstructed paint, masks and the immutable recipe remain pinned dependencies. A source edit requires a new derivative/recipe; it does not rewrite old packs.

## Compile, place and resume

```sh
./ambiance --project PROJECT asset prepare place PROJECT/assets/prepared/compound \
  --base source-plane --prefix prepared --expect-sha256 SCENE_HASH
./ambiance --project PROJECT asset prepare place PROJECT/assets/prepared/compound \
  --base source-plane --prefix prepared --resume
```

`place` compiles and admits the immutable outputs idempotently, then replaces the existing mapped source plane with clean backing and adds the cutouts/fixed occluders through one scene transaction. The existing base must have a one-cel compiler mapping for the same reference. It preserves subpixel placement, source pivots, padding, base transforms and static socket coordinates. Its journal and normal scene history support interruption recovery. A changed scene after placement fails a resume instead of applying the parts twice. Compiled companion masks retain their owner relationship for explicit lighting bindings.

The preparation's demonstration motion is not copied into the production rig. Author production timing through `scene track/apply`; the standalone proof always labels its own clock. `--dry-run` prepares reusable compiled assets and admission checkpoints, then returns the candidate scene without saving it. This option is a scene dry run, not a promise of zero new asset files.

`preparation_receipt` in compiler recipes/provenance is a typed dependency. `compound_preparation.validate_preparation_receipt(path, sha256, source_paths, recipe=None)` checks the receipt, all source/output/map/control snapshots, and optional fixed compiler settings. It returns `{dependencies:[{path,sha256,role}],outputs,receipt}` for compiler, admission, scene transactions, revisions and packages. All parts and companions use the same full-canvas fixed registration/padding. Independent motion/edge corrections that could desynchronize companions fail; rebuild explicit corrected source/masks together.

## Proofs and observations

`proof` saves full-speed synchronized views for normal, subjects-hidden and foreground-hidden variants, plus actual rest/extreme raster frames for each view. It reuses `render views-proof` and `render frame`. `--resume` verifies completed file hashes and skips them; incomplete attempts remain for diagnosis and retry into a new local attempt. Changed preparation, sizing or runtime identity requires a new run. `proof-run.json` records exact input identities, per-attempt artifacts, completion and an unreviewed artistic status.

Inspect these pictures for duplicate subjects left in backing, foreground fragments moving with a cutout, gaps in reconstructed paint, soft edges, registration and framing. Watch both full-speed views and record who observed them, display size, timestamps and the actual findings. Raster counts, successful compilation and structural checks cannot replace those observations. A positive mask result cannot detect a visually wrong but fully opaque replacement backing by itself.

The [agent replay](../examples/agent-preparation/README.md) exercises the existing cabinet and a different cleared tea-shelf source. These are engineering fixtures. The measured fresh-painting artistic pilot, complete film delivery and any human/phone review remain separate work.
