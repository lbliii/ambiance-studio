# Working on Ambiance Studio

Keep changes scoped to a demonstrated production problem. Start with `./ambiance doctor`, read the relevant guide, and inspect the current project state. Preserve raw media and accepted asset versions. Never require paid provider access for local tests.

The root launcher is intentionally runnable without package installation. Python handles orchestration, files and review records. JavaScript owns scene validation and absolute-time evaluation. Image preparation stays in the Pillow compiler. Keep new UI and CLI behavior on these shared boundaries.

Use UTF-8, LF, final newlines, four spaces in Python and two in JSON/JavaScript. Follow surrounding code where historical files differ. Run `./ambiance test`; add behavior tests for meaningful new state transitions or failure modes. If the editor changes, also inspect it through the browser. Record what actually ran rather than implying that JSON validation is an artistic review.

Code, examples and small reusable assets are tracked. Working projects, full media, caches and the original session archive are ignored by Git. Preserve their local backup/inventory separately. The repository has no remote configured by the initializer. No open-source license or redistribution rights are assigned to the artwork by this setup.

The CI definition runs the same local checks on Python 3.12 and 3.14 with Node 24. It has not run on GitHub until this repository is hosted and the workflow executes. Action versions follow the official [checkout](https://github.com/actions/checkout), [setup-python](https://github.com/actions/setup-python), and [setup-node](https://github.com/actions/setup-node) documentation checked September 10, 2026.
