# Captured revisions and media editions

A revision freezes control documents and pins the exact binary dependencies selected for a film. Working changes remain separate. A successful capture is not a passed review.

## Select and capture

Create a selection file using **project-relative references**:

```json
{
  "format": "ambiance-revision-selection",
  "schema_version": 1,
  "scene": "scene/scene.json",
  "catalog": "assets/catalog.json",
  "documents": {
    "brief": "plans/brief.md",
    "layer_plan": "plans/layer-plan.json",
    "inventory": "plans/asset-inventory.json",
    "sound_plan": "plans/sound-brief.md"
  },
  "audio": {
    "runs": ["audio/runs/first-mix"],
    "masters": ["audio/runs/first-mix/mix/master.wav"]
  }
}
```

`documents` may also select `layout_notes`, `generation_ledger` and `source_ledger`. Audio may select an executable `session`, `runs`, `masters` and external `preparations`. Later-stage documents/audio may be omitted; the corresponding review remains incomplete. Scene/catalog and project settings/pipeline are required. References outside the project, missing inputs and unknown contract versions fail.

```sh
./ambiance --project PROJECT revision capture v1 --selection selection.json --dry-run
./ambiance --project PROJECT revision capture v1 --selection selection.json --expect-selection-sha256 HASH_FROM_DRY_RUN
./ambiance --project PROJECT revision inspect v1
./ambiance --project PROJECT revision check v1
./ambiance --project PROJECT revision compare v1 --working
```

The explicit selection filename is shell-relative; its references are project-relative. The dry-run digest covers the declaration and all resolved input identities. A changed source rejects the later capture. The destination `revisions/v1/` must be new. Captures use the project lock, validate before promotion, and never edit the working scene, catalog, review history or handoff.

The manifest stores SHA-256, bytes, role and section for every selected dependency. Mutable settings, pipeline, scene, used catalog and selected control documents are copied into `controls/`. Binary art, source files and PCM remain at their versioned project paths and are pinned by hash. No hard links are created. Keep those files: editing or deleting one invalidates the revision until the exact bytes are restored or a new revision is captured.

Compiled packs include their declared inputs, registration/source mappings and return/crop dependencies. The runtime catalog contains only used assets. Legacy image-only assets can be pinned for rendering; the manifest notes their missing rebuild recipes. An unchanged descriptive report cannot hide a changed image or PCM dependency.

## Render a captured picture

```sh
./ambiance --project PROJECT render video --revision v1 --out PROJECT/reports/picture-v1
./ambiance --project PROJECT render proof --revision v1 --out PROJECT/reports/proof-v1
```

Revision rendering uses the captured scene/catalog and verifies pinned dependencies before and after work. It never falls back to working files. Compare reports list working divergence separately from revision integrity. New rejected drafts and unused catalog entries do not redefine an existing capture.

## Record an edition

An edition associates actual encoded output with a captured revision, picture and selected soundtrack. Pass `--revision` and `--edition` when rendering/composing. Its output directory must be fresh and inside the project. The encoded media must pass actual verification before an edition receipt can be saved.

```sh
./ambiance --project PROJECT render video --revision v1 --edition scored \
  --audio PROJECT/audio/runs/first-mix/mix/master.wav --repeats 3 \
  --out PROJECT/deliverables/revisions/v1-scored

./ambiance --project PROJECT media compose PROJECT/reports/picture-v1/picture.mp4 \
  --picture-receipt reports/picture-v1/render-report.json \
  --revision v1 --edition alternate --audio PROJECT/audio/runs/second-mix/mix/master.wav \
  --audio-run audio/runs/second-mix --repeats 3 \
  --out PROJECT/deliverables/revisions/v1-alternate
```

`--audio` and explicit picture/output paths are shell-relative. `--audio-run`, `--audio-provenance`, `--audio-session` and `--picture-receipt` are project-relative. Picture composition must either cite a render receipt matching the captured scene/catalog and selected picture hash, or reuse picture already bound by an edition of that revision. Arbitrary older footage cannot be relabeled by selecting a new revision ID.

The PCM must belong to a selected revision run/preparation or an explicitly supplied `--audio-run` / `--audio-provenance`. A session alone describes sources and arrangement; it cannot establish that a separately supplied master came from it. `--audio-session` can retain additional session dependencies but does not replace output provenance.

The receipt lives at `revisions/ID/editions/EDITION.json`. It binds the revision manifest, selected sources/recipes, picture, output movie and verification report. It never rewrites the frozen revision. Alternate editions retain separate sound/mix/export evidence. A silent picture can be captured as an edition, but it cannot pass soundtrack criteria merely because the revision also selected an unrelated master.

## External sound preparation

For processing outside the supported mixer, supply an explicit declaration:

```json
{
  "format": "ambiance-external-preparation",
  "schema_version": 1,
  "sources": [{"path": "audio/sources/room.wav", "sha256": "SOURCE_SHA256"}],
  "recipes": [{"path": "audio/preparation/build.py", "sha256": "RECIPE_SHA256"}],
  "outputs": [{"path": "audio/revisions/score/master.wav", "sha256": "OUTPUT_SHA256"}],
  "notes": "Describe externally performed processing and its limits."
}
```

All hashes must be real 64-character SHA-256 values. Sources/outputs must be readable PCM. This reader pins the declared files; it does not execute the recipe, discover undeclared imports or certify its sound. Include every material preparation input explicitly. Broad folder scanning and prose parsing are not dependency readers.

## Reviews and handoff

```sh
./ambiance --project PROJECT review draft animation --revision v1 --out animation-review.json
./ambiance --project PROJECT review draft release --revision v1 --edition scored --out release-review.json
./ambiance --project PROJECT review record release-review.json
./ambiance --project PROJECT project status
./ambiance --project PROJECT revision handoff v1 --edition scored --out PROJECT/reports/handoff-v1
```

Drafts contain unperformed checks. Record actual observations against their exact evidence, retaining observer kind and criterion requirements. Version-2 receipts include the revision/edition subject and use the existing review validator with typed dependencies. Human release evidence must identify both a feedback record and the exact selected edition movie; directory naming is not proof of identity.

Revision/edition review histories are separate under `reviews/revisions/`. The captured pipeline supplies criteria and upstream dependencies. A working pipeline edit does not redefine old criteria. New revisions or editions have no inherited pass verdicts. Existing feedback can be cited in a new review only when it addresses the criterion and exact files being reviewed.

Status distinguishes working divergence, revision integrity and review states. A changed asset marks its asset evidence stale and blocks downstream gates; independent sound-source evidence remains valid. A changed selected PCM or movie is detected even when its report stays unchanged. Handoff writes a new Markdown/JSON bundle with exact paths, hashes and outstanding checks; it does not overwrite `handoff.md` or publish anything.

Legacy version-1 reviews retain their original folder-watch behavior and bytes. There is no automatic migration, inferred release selection or conversion of an old pass into a new approval.
