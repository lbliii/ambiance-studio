# WF-02/03 implementation handoff

This task implements advisory catalog/stage inspection and prerequisite-aware action projection on the WF-01 assessment foundation. It does not change coverage policy, pipeline authority, review persistence, canonical film scope or default next-work output. The coordinator owns central capability/backlog status and integration.

Implementation and replay instructions are in [the focused example](../../examples/workflow-guidance/README.md). The source-bound machine handoff is saved alongside this report as `WF-02-03-HANDOFF.json` after validation.

## Public interfaces

- `workflow inspect`, `workflow stage GATE`, `workflow explain ACTION_ID [--expect-assessment SHA256]`.
- `project next --guided`, sharing the same subject/action assessment and preserving unflagged compatibility.
- Explicit working/review/release selectors, revision with optional edition, and view refinement. Multi-entry selections retain every included entry's revision, edition, view, role and movie identity; pagination never merges their reviews.
- `ambiance-workflow`, `ambiance-guided-next`, and `ambiance-workflow-action` schema version 1 inside the unchanged CLI envelope. Action IDs are logical identities; assessment tokens separately bind current inputs, selection, catalog and evaluator sources.
- Native pipeline criteria/verdicts, native inventory dependencies and pure WF-01 coverage. Unsupported coverage stages and custom/altered criteria stay explicit. Catalog prose neither writes project files nor changes review digests.
- REPORT-owned `--out` only on the three new workflow routes. Existing leaf options/output ownership are unchanged except the leased opt-in next-work flags.

## Validation and observations

The public replay preserves the real initial preparation check failure (empty foreground), its explicit native `prepare edit` correction and the subsequent successful build. Earlier sandbox attempts failed AVFoundation encoding. The successful replay runs with access to the local macOS media service; no skipped or simulated native success is substituted. Each final command/output/source hash is retained in the replay manifest named in the machine handoff.

Observed synthetic images from the successful preliminary replay: the reconstructed rest image contains a small yellow rectangle on a dark blue field; its isolated backing image is a continuous dark blue field with that rectangle removed. The compiler contact sheet contains one small green/gold oval with the registration cross centered over it. These are actual static image observations of the synthetic fixture, not character preparation, full-film motion, listening, human review, artistic approval or workflow-adoption evidence.

Focused tests cover no writes under a held lock, missing optional runtime, malformed components, captured intent without editions, custom/altered pipelines, unchanged native reviews after editorial guidance changes, stale tokens, deduplicated prerequisites, stage filtering, wrong-view/stale raster evidence, entry/delivery feedback isolation, native captured view inspection, output ownership and unflagged compatibility. The final focused and full-native counts belong in the machine handoff; no GitHub CI success is claimed because runners are billing-blocked.

## Limits and acceptance boundary

Queries describe native gates and coverage separately. They do not certify aesthetics or infer human observations. Compiler source/argument resolution does not pre-execute a build. Missing authored recipes and choices stay unresolved. Existing `scene timing` lacks captured-revision selection; captured `view inspect` uses its real `--revision` route. Delivery-wide feedback keeps delivery scope, and historical feedback never becomes working-revision instructions.

The implementation stops before WF-04 packets, WF-05 outcome guidance, WF-06 operator trials and WF-07 adoption. No model construction commands are advertised by this catalog. Native proof creation remains separate from registration and actual observation. Pending human release checks stay open while independently available work remains visible.
