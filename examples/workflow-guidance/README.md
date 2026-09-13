# Advisory workflow inspection (WF-02/03)

Run the public CLI replay from the repository root with a fresh output directory:

```sh
python3 tests/replay_workflow_guidance.py --out /tmp/workflow-guidance-replay
```

The replay retains exact argv, exit codes, elapsed time, response sizes/hashes, project snapshots and source hashes. It executes real local preparation, compiler, raster and macOS encode/decode operations. Run with access to local native media services; a sandbox that denies AVFoundation encoding cannot establish the native result. No paid provider is used. Synthetic paint and one-second silent movies exercise contracts; they are not an artistic or operator-adoption trial.

Inspection does not write project files, create decode caches, or take a writer lock. An explicit `--out` writes the ordinary result envelope through the existing CLI output owner.

```sh
./ambiance --project /absolute/film workflow inspect
./ambiance --project /absolute/film workflow stage assets --details
./ambiance --project /absolute/film project next --guided
./ambiance --project /absolute/film workflow inspect --subject review
./ambiance --project /absolute/film workflow inspect --subject release
./ambiance --project /absolute/film workflow stage intent --revision v1
./ambiance --project /absolute/film workflow inspect --revision v1 --edition portrait-silent
```

Use the actual IDs returned by your project. `--subject` and `--revision` are mutually exclusive; `--edition` requires a revision. `--view` narrows the chosen subject and never changes it to another revision, edition or working scene. A missing review/release selection is an error. A damaged delivery entry remains named and diagnosed while unrelated captured material stays visible. Legacy movies without captured controls do not inherit working pipeline verdicts.

`workflow inspect` defaults to all actual pipeline stage summaries and three actions. `project next --guided` shares the action projection and defaults to eight actions. Existing unflagged `project next` retains its original schema. `--limit`, `--offset`, `--kind`, `--subject-limit`, and `--subject-offset` support retrieval; omitted data has counts and continuation commands. `--details` includes native issues, criteria, input fingerprints and operation contracts. Full criteria always come from the selected actual pipeline; the catalog stores only compatibility fingerprints and advisory descriptions. Unknown or altered criteria remain visible. Coverage is supported only for layout, assets, animation and export through the existing evaluator.

Actions have stable `wf1.<sha256>` logical IDs. The separate `assessment.sha256` binds the selected subjects, relevant inputs, catalog and evaluator sources. Pass that token to `workflow explain ACTION_ID --expect-assessment HASH` with the original selectors; the response supplies a complete operation contract and native help. Changed assessments fail with `stale_assessment`; absent action IDs fail with `stale_action`. They never select substitute work. Exact captured movie identities live in the subject table. Compact actions reference that table; feedback retains its own immutable entry or delivery scope.

`dependencies` contains actual work prerequisites; `gate_dependencies` governs review passage separately. Stage filtering retains prerequisite work from the native coverage result. A pending human observation does not suppress usable asset proofs or a handoff. Runnable `argv` vectors use absolute paths and actual native routes. Missing creative fields, unchosen inputs, unavailable runtime, failed native input checks and occupied output proposals remain explicit. An action marked ready means its arguments resolve; its native operation still validates before saving. Preparation/compiler recipes and evidence are not invented by inspection.

The assets stage exposes the existing `asset prepare init/inspect/check/edit/build/proof/place` positional verbs and their native help/contracts. Source-backed art can use a validated separation recipe. Already-isolated art goes to alpha preflight and its native compiler recipe. Raster admission does not establish a reusable editable model. Input packets, result guidance, workflow trials and adoption (WF-04–07) are outside this implementation.
