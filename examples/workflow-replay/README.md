# Public CLI workflow replay

Run `python3 examples/workflow-replay/run.py --out NEW_DIRECTORY` from any directory. It creates only locally drawn synthetic art and calls the public CLI for saved views, raster proof, incomplete-scope failure, per-view backing failure and scene restoration. Re-run with the same output and `--resume` to reuse completed steps and verify receipts. Changed code or a partial fixture initialization requires a new directory; an interrupted backing test restores its saved scene before retrying. No private project, provider call or existing delivery is touched.

`replay.json` records commands, expected/nonzero exits, receipt hashes, active step and what remains unperformed. Both original and injected backing proofs are retained. The latter deliberately exposes a landscape-only coverage defect; its existence does not imply approval. Additional feature-owned scenarios run through the combined entry point below.

This is a deterministic artifact replay. The [scenario definitions](../../tests/agent-evaluations/scenarios.json) describe three unperformed autonomous trials and their observation requirements. A test pass must never be reported as completing those trials or a film.

CI uploads use `tools/ci_bundle.py`'s fixed synthetic-proof allowlist, file/byte limits and manifest. Never upload an arbitrary project folder as a substitute.

## Combined feature replay

Run `python3 examples/workflow-replay/combined.py --out NEW_DIRECTORY --native` for the native lane, or omit `--native` for the portable raster lane. The latter explicitly records paired native recovery as not run. Each feature retains its existing fixture and evaluator: production intent/coverage, compound tea and cabinet preparation, painted source/receiver bindings, activity diagnostics and paired interruption recovery. Repeatable `--feature ID` selects a subset; unselected work is listed, never counted as completed.

`combined.json` pins the source tree, selected fixtures, their own result paths and every generated file hash. `--resume` verifies completed output without regenerating it. Failed or externally interrupted fixtures retain their prior attempts and retry into fresh directories; this wrapper does not replace production's internal checkpoints. A timeout stops the fixture's process group. Source changes or tampered completed files require a fresh replay, and failures remain nonzero. No agent trial or artistic review is inferred from these fixture assertions.

CI's combined artifact subset includes the attributable summary, fixture command output, named proof reports and selected synthetic raster/native media. The full local replay retains the complete sources and proofs. An uploaded subset is diagnostic evidence; it is not a self-contained project or a substitute for rerunning the feature's full proof validator.

## Actual paired-delivery interruption

On macOS with native media services, run `python3 examples/workflow-replay/paired_delivery.py --out NEW_DIRECTORY`. The public CLI first proves native capability, then starts a captured two-view iteration. A fixture-local backend wrapper delegates actual encoding and pauses its second encode. The replay signals only that subprocess group with SIGINT, verifies exit 130 plus a saved interrupted run, confirms the first view/receipt remained intact and the incomplete pair was not selected, then resumes the same recipe. Exactly one remaining view is encoded. `recovery.json` and `interrupted-run.json` retain the observations and identities.

The first real run exposed that CLI interruption returned 130 without its promised JSON envelope. The CLI now emits `error.code: interrupted` with the same exit status. This is a contract fix, not a replacement iteration engine. The reusable iteration/edition recovery still belongs to the existing production model. A later externally interrupted replay can be inspected using its saved project/recipe; the diagnostic wrapper itself requires a fresh destination.
