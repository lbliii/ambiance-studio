# Future skill behavior trials

These are realistic forward-test cases, not completed independent-agent evaluations. The skills have been format/link checked; the record keeper has executable behavior tests. A second operator's end-to-end film remains an open pilot.

The [consolidated production roadmap](../docs/architecture/PRODUCTION-IMPROVEMENTS.md) extends this evaluation program through CI-02 and PILOT-01 in its [backlog](../docs/architecture/PRODUCTION-IMPROVEMENTS.yaml): paired staging, deliberate stillness, visible quiet-scene activity, coupled painted light and resumed production. Those trials remain planned; no behavior pass is implied by the instruction updates.

Run a trial in a separate project with only the stated inputs and permitted tools. Evaluate artifacts and decisions, not whether the response repeats exact wording. Use live generation only when its budget is explicitly authorized.

| User request and inputs | Expected observable behavior |
| --- | --- |
| “Turn this lighthouse painting into a quiet loop. Planning and existing assets only.” Supply a reference and the studio. | Producer preserves/inspects the reference, starts a project, plans layers and sound, records unavailable/paid capabilities, and makes no paid generation |
| “Separate this house so it can move slightly.” Supply a painting with trees behind the house. | Breakdown identifies clean backing, edges/camera range, ground contact, and attached window/smoke elements before claiming a usable moving cutout |
| “Use this smoke sprite sheet.” Supply inconsistent scale and a baked checkerboard. | Asset workflow inspects actual alpha and registration, identifies preparation work, and does not pass the asset gate based on the sheet's appearance alone |
| “Make the town lights more animated.” Supply bright base windows and a weak overlay. | Inspect base/emissive relationship; preserve architecture; produce and review an effective internal light change |
| “The loop must be 10 seconds; this sprite cycle is 3 seconds.” | Resolve cycle timing within the requested duration or propose an explicit alternative; do not silently claim a seamless incompatible loop |
| “The music generation timed out. Try again.” Supply a submitted request ID with unknown status. | Reconcile/retrieve the original request before a new paid generation; explain any real retrieval blocker |
| “This sounds great on my headphones.” Supply the exact final file and signal reports. | Record the actual feedback; leave phone-specific observation open rather than inventing it |
| “I changed only the smoke atlas after release.” Supply current review receipts and altered asset. | Detect affected stale visual/downstream reviews, retain independent sound-source review, and rerun only justified checks |
| “Hand this to my sister.” Supply a finished local project. | Package local sources, final files, capability/rebuild limits, and handoff; do not send it externally without explicit recipient/action authorization |
| “Lift this figure's casket behind fixed glass; preserve its accepted hand gesture.” Supply a padded/scaled reference, mapped parts, a contaminated interior and distinct removal/cutout masks. Local work only. | Places parts through source mappings, preserves the gesture's reference pose and cel clock, and renders rest/lift/body-hidden comparisons. Detects residual body paint and any rim carried by the body alpha. Keeps fixed glass stationary and reports limits on later relative-body motion. |
| “Prepare this returned flame sheet and finish the already authorized local sprite cleanup.” Supply an RGB checkerboard sheet with ivory cores, known wick landmarks and a small backing ghost; provide a previously generated enlarged repair, with no new generation authorized. | Preserves raw bytes, reports actual alpha, prepares a registered derivative without erasing pale cores, and returns the existing repair through explicit mapping/mask. Shows light/dark/context proofs and distinguishes drawn poses from derived light states. Continues local preparation without another approval or provider call. |
| “Keep this captured picture; make score and ambience editions from these PCM masters while I continue editing the working scene.” Supply a captured revision, its picture receipt and explicit audio provenance. | Reuses the captured compressed picture for both editions, verifies selected soundtrack identity and timing, records separate edition evidence, and reports working divergence without changing the capture. Reads actual cell-track timing when checking gait cadence; produces a handoff with unperformed human checks still open. |

For the sister pilot, record how many undocumented decisions, missing tools, unnecessary questions, and broken instructions interrupt progress. Fix the observed problems before adding more workflow rules.

## Current-movie continuation trial

Start from another code worktree with no local `projects/` directory and the shared registry already containing a project with two registered deliveries. Ask: “Open the latest museum movie, tell me what changed, and keep the older version available.” The agent should use project discovery and `project latest/overview`, return the selected review rather than the newest file timestamp, open its stable watch page, and retain an exact-version link. An unrendered working edit or a failed later run must not replace the selected movie. Record whether the agent needed the original chat or unnecessary user input. The executable delivery tests cover the underlying identity and discovery behavior; this scenario remains a separate agent behavior trial.

The [machine-readable scenario records](agent-evaluations/scenarios.json) declare permissions, inputs, expected artifacts and unperformed trials. The [public CLI artifact replay](../examples/workflow-replay/README.md) executes saved commands on synthetic data; its pass is never a live-agent behavior verdict.
