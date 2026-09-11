# Public CLI workflow replay

Run `python3 examples/workflow-replay/run.py --out NEW_DIRECTORY` from any directory. It creates only locally drawn synthetic art and calls the public CLI for saved views, raster proof, incomplete-scope failure, per-view backing failure and scene restoration. Re-run with the same output and `--resume` to reuse completed steps and verify receipts. Changed code or a partial fixture initialization requires a new directory; an interrupted backing test restores its saved scene before retrying. No private project, provider call or existing delivery is touched.

`replay.json` records commands, expected/nonzero exits, receipt hashes, active step and what remains unperformed. Both original and injected backing proofs are retained. The latter deliberately exposes a landscape-only coverage defect; its existence does not imply approval. Additional feature-owned scenarios join this replay after their APIs merge.

This is a deterministic artifact replay. The [scenario definitions](../../tests/agent-evaluations/scenarios.json) describe three unperformed autonomous trials and their observation requirements. A test pass must never be reported as completing those trials or a film.

CI uploads use `tools/ci_bundle.py`'s fixed synthetic-proof allowlist, file/byte limits and manifest. Never upload an arbitrary project folder as a substitute.
