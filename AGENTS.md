# Working in this studio

This is a personal studio for painted, layered ambiance films. Start an end-to-end film with `.agents/skills/ambiance-produce/SKILL.md`. For a focused revision, read only the relevant stage skill and workflow reference.

- User direction sets the scope, artistic choices, and authority. The playbook does not authorize paid generations, account changes, sending files, or publishing. Preserve authorization already given; do not request it again without a material change.
- Keep project state in its project directory: brief, layer plan, source ledger, scene, sound session, evidence, reviews, and handoff. Read current files instead of relying on a previous conversation.
- Quality gates describe readiness, not permission. Continue independent reversible work while a review is open. Existing user feedback can satisfy a criterion when it actually addresses that criterion and the reviewed files are identified. Never invent a human audition or phone check.
- Protect originals and accepted library versions. Work on derivatives; record their source hashes and preparation recipes. Do not spend a new generation to recover a result that might already exist.
- Design asset boundaries from the intended actions and overlaps, including explicitly requested exploration. Use the framing and movement judgment in `docs/workflows/01-reference-and-layers.md`; a quiet first pass does not by itself justify baking every object into one plate.
- Distinguish executable capability from a documented workflow. The browser editor supports rigs and preview checks; it is not a complete final renderer. `studio.py` tracks evidence; it does not independently certify aesthetics or decode media.
- Use one owner for a project's review records at a time. Take changes in scene, art, audio, or export back through affected gates. The status command detects recorded file/dependency changes.
- Add a general rule only after a demonstrated problem. Test shared code with `python3 tests/test_studio.py`; run the editor's existing checks when its renderer or scene data changes. Packaging changes also need the package audit.

Commands are documented in `docs/OPERATIONS.md`. The stage criteria live in `templates/pipeline.json`; `docs/QUALITY-GATES.md` explains evidence and failure handling.

For registration or rig changes, read `docs/RIG-WORKBENCH.md`. Run `python3 tests/test_assets.py` for the compiler and `node tests/test-rig.mjs` for attachments/audits. Browser checks use the actual edited scene; a geometric state check does not establish raster or encoded-media quality. Catalog registration is not artistic approval.

## CLI development

Design for agent operation first. The agent pilots production through structured tools, CLI commands and saved project state; the human observes, directs and judges quality. Localhost provides observable progress, visual inspection, comparisons and optional human or agent computer-driven editing over the same capabilities. A production operation must be usable without browser interaction. Prefer compact actionable results, direct artifact paths, batchable changes and resumable work; retain detailed evidence separately. Validate new workflows through an agent-operated CLI path before prioritizing additional UI controls.

Use `./ambiance` as the main production entry point; read `docs/CLI.md`. New projects have `ambiance-project.json`. Prefer existing library/evaluator functions over reimplementing rules in a command. Commands emit JSON, validate before saving, preserve restorable scene snapshots and expose nonzero failures. Run `./ambiance test` after shared-code changes, and inspect the browser when preview behavior changes. Read `docs/architecture/CLI-FIRST.md` for the next slices. The local `archive/` is historical evidence, not active instructions or source code to execute blindly.

Use `project list/overview/latest` and `docs/STUDIO-LIBRARY.md` to find the actual project and selected movie across worktrees. Finish a movie review iteration with an explicit delivery presentation and exact/current watch links. File names, timestamps and scratch renders do not select the current review; pending human checks do not prevent presenting a labeled review movie.

When working versions and reviewed editions diverge, use explicit revision capture and edition evidence (`docs/REVISIONS.md`); a report filename or legacy watched folder does not bind the media it describes. Source placement and reparent commands preserve recorded geometry, while `scene timing` reports the clock that actually runs. Keep artistic decisions and actual visual/listening observations explicit.
