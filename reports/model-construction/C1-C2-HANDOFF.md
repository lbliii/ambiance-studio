# M2 local model construction handoff

C1/C2 now provide a project-free immutable local package and static proof/library-entry path. Construction uses exact compiler/definition/source byte pins; nested mounts, controls, forwarding, variants and drawing identities lower into ordinary scene/catalog data through the existing engine and source-placement functions. Older output directories and competing publishers are preserved. No scene-instance/adoption API or second evaluator was added.

Owned implementation commits:

- `93ffc66` — six CLI routes, package/definition services, shared-engine lowering/proof bridge, public replay, focused tests and implemented contract.
- `260fe7c` — geometric fixture with pane openings and unclipped extreme poses, exact visual observations.

Adopted D2 dependencies, in order:

- original `e74b72cd318bb9a734a5f5cbd338f07da3545940`, local `695c477`.
- original `06a3b53699b7041e0463cf4cc6a490df4c64b3ce`, local `107388b`.

The final full-native candidate is `260fe7c5a35a6ad4cdc6dd29e456d607189e7dd1`. The final engine SHA-256 is `84881ab6f3a2eb71e2bd026a55478d60e589c316bcbaf183e6690fde7c7ac4e7`. Do not duplicate D2 patches when integrating M2's owned commits onto a tree that already contains D2.

Owned paths are `ambiance_studio/model_commands.py`, `model_definition.py`, `model_package.py`, `tools/model/`, `tests/test_models.py`, `examples/model-construction/`, `docs/architecture/model-contract/construction-v1.md`, `reports/model-construction/`, and narrow CLI/option/output fixture hooks. The coordinator retains central capability/backlog registration. New routes explicitly declare artifact versus report `--out` ownership and select no project.

Public replay: `python3 examples/model-construction/replay.py --out work/m2/replay-v2`. This invoked actual `model build`, `inspect`, `lower`, `proof`, `check`, `admit`, existing `scene check`, then reopened the entry after moving the original source/package/proof away. All actual argv, outputs and hashes are retained in `work/m2/replay-v2/evidence.json`. The recipe selects ten static states (rest, left, right, unlit, hidden across square/arched frame variants), solid/glass/flame roles, threshold 16 and explicit local framing.

Exact retained products:

- Replay evidence SHA-256: `ef3462fb47e78696f56792856deb7548aa3bab8c149a05126ab8dfaa05dd0db1`.
- `entry/package/model-package.json`: `4bde936936c2fff7aa92e914b42277dff78ad199749b0bd8eb1ea7b4146dd036`.
- `entry/proof/model-proof.json`: `1e6ce097aae3f6b4bc9fe31c13172cb020ca8dc4f90943919aadc39282e715a5`.
- `entry/model-entry.json`: `d8d267bd0b17bfdc76f64f3efc80222fae7deafad7e7a837108e813a1ec688fc`.

Every proof sample binds actual included/excluded/selected/hidden leaves, resolved state/clock/variant/control values, definition and compiler closure, runtime/renderer identities, mappings, policy and file hashes. The package/source/entry payloads contain relative paths; they do not depend on the mutable source worktree. Full proof data are retained in ignored `work/m2/`; the committed observation report identifies the exact observed output hashes.

Actual image inspection found and corrected an initial fixture with opaque pane backing and clipped extreme poses. The final source/assembly pair has matching placement, the solid mask preserves pane openings, the glass pass retains translucency, the flame pass contains only the flame, both tilted variants stay within the viewport, unlit removes the flame and hidden is empty. Numeric resampling differences remain visible in the report. These are agent observations of geometric art, not production painting or human approval; no listening occurred.

Focused validation: 27 model tests, 8 CLI-contract tests, 10 compiler tests and existing rig, binding and source-placement Node checks passed with no skips. Model tests exercise broken pins, bad registration/mounts, duplicate identities, competing/forwarded writers, unknown controls/cycles, variant compatibility, source escapes, changed closure, interrupted/racing publication, repeated nested tuples, compiler rebuild, deterministic ordinary lowering, source-bound masks, stale state and portable entry reopen.

Remaining acceptance gaps: production painted art and broader model families; animated/cycle control/finite timing (explicitly rejected); project-relative advanced preparation-receipt materialization; independent scene instances and version adoption; scene receiver-light/occluder/removal proofs; portrait/landscape motion films and full Phase 1/P00. Technical entry status is `technical-candidate`; no artistic gate, coverage provider or human observation is invented. The native suite establishes regression behavior, not those gaps. GitHub jobs remain blocked by account billing/spending limits; no CI pass or account changes are claimed.

Required-native validation passed on the exact frozen candidate: **475 recorded cases / 460 Python tests, zero skips**. Public argv: `./ambiance test --require-native --out work/m2/native-suite-unsandboxed.json --artifacts work/m2/native-suite-unsandboxed`. The run used approved local loopback/Core Audio/AVFoundation access. Report SHA-256: `8d7383b42fb70a3aee4a11d1ba5eb6b10e6548c4f1780844438f069ec148c6cd`; tracked tree: `edf8afe41163db50b4552320aac6e3d3048c985ff11b2c0d18e1b4a13e595048`.

The original sandbox attempt is retained in `work/m2/native-suite/run.json`, SHA-256 `d3fa1dd458bf523022548db17adfdd3448dcd7e6cdcbdf6ad9abf2ffd9455601`. Its localhost EPERM, unavailable AAC and AVFoundation encoder failures were resolved by the unchanged rerun with the required local access. No tests were weakened or skipped. The native slot was explicitly released to W2.

The final handoff commit changes only this document and the native-result field in the [exact observation record](observations-v1.json); runtime, tests and proof bytes remain those of the tested candidate. Read the [implemented contract](../../docs/architecture/model-contract/construction-v1.md) and [public replay instructions](../../examples/model-construction/README.md). No push or merge was performed by this task.
