# Integrated production foundation

The baseline reconciles dual-format PR #5 (`9a58e36`, after merging main `dae0e18`) with the preserved 25-file production foundation and encoder checkpoint commit `c53a5e4`. The immutable source handoff's 25 file hashes and patch hash (`66c25c55ae508d2f98ed0dd9dd691dfa038f33d8ed0493665327cf7ed317b6a2`) were verified before integration. No project media, private project records or accepted assets are included or modified.

## Accounted source changes

- Four production skills, AGENTS, style/quality guidance, two stage workflows, seed-to-stage, layer/light and motion direction docs carry whole-scene scope, action room, backing and actual normal-speed review. Explicit single-format or nearly-still user direction still controls the scope.
- Legacy `plan check --require-complete` now rejects an empty or unfinished inventory. Required entries need tracked parts and cannot silently become `static-deferred`. It checks declared inventory fulfillment only; typed expectations and exact creative evidence remain DATA-01/02 work.
- Editor group controls appear only for an actual group, explain group mode and direct attached-layer users to their parent. Authored aspect sizing, view guides and both synchronized panes remain intact.
- The new pipeline criteria apply to newly initialized projects. Existing project pipelines, captured revisions, reviewed editions and selections are not migrated or rewritten.
- `encode-checkpoint.json` records the completed intermediate's identity before trim. It remains `ok: false`, stage `encoded-before-trim`, and cannot substitute for a successful render/verification receipt.
- The Markdown rationale, YAML backlog and parallel ownership handoff distinguish implemented tools from remaining artistic pilots and agent trials. Historical starting-point status is labeled as such.

Conflict resolution combined the existing dual-format animation guidance with scope requirements; retained all view-specific gate descriptions; combined group CSS with canvas aspect sizing; and kept the implemented views/cel-motion capability descriptions. The source snapshots were not copied over newer dual-format files wholesale.

## Validation and observations

On September 11, 2026, macOS with Python 3.14.0 / Node 24.9.0:

- `AMBIANCE_TEST_NATIVE=1 ./ambiance test`: 243 Python tests passed with native media enabled and no skips; shared engine, rig, views, view raster, tracks, source placement, finishing and package audit passed. The package audit includes local links and skill structure. Local exact report: `/private/tmp/ambiance-foundation-native-tests.json`.
- The PR #5 integration separately passed 240 Python cases and all subsequent checks. Six fresh Linux/macOS CI checks passed at exact head `9a58e36`; see [PR #5](https://github.com/lbliii/ambiance-studio/pull/5).
- The CLI-created synthetic moving fixture was inspected in the browser. Seeking frame 8 selected 1.000 s in both panes/timelines. Play/pause shared the clock. With no group, the unavailable control was hidden; an attached hand instructed selecting its body parent. After a CLI transaction added a `Focal rig` group, selecting its body exposed the control, and toggling it selected group coordinates with an explicit whole-group hint. The fixture's saved files and transaction remain local under `/private/tmp/ambiance-pr5-browser`.
- Existing native view/delivery tests exercise captured revision integrity, exact current links, interrupted receipt recovery and retained movie identity. No private film was re-rendered or presented.

These checks establish contract, state, raster/native and inspected UI behavior. They are not an autonomous unfamiliar-seed trial or a finished film. CI-02 artistic observations, full DOCS-01 scenario behavior, PILOT-01 and FOLLOW-01/02 remain open. CI artifact/replay work follows in its own change.
