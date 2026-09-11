# Integrated production workflow and evidence

The foundation, saved views, canonical intent/evidence, compound preparation, painted bindings, activity/cues and paired delivery use the existing project, evaluator and revision model. The [capability index](../CAPABILITIES.json) names registered public routes and their limits; the [roadmap](PRODUCTION-IMPROVEMENTS.yaml) retains implementation and unfinished trial criteria separately.

## Runnable integration path

```sh
python3 -m pip install -r requirements-checks.txt
npm ci --ignore-scripts
./ambiance test --require-native --artifacts /tmp/studio-checks-new
python3 examples/workflow-replay/run.py --out /tmp/studio-scope-replay-new
python3 examples/workflow-replay/combined.py --out /tmp/studio-combined-new --native
python3 examples/workflow-replay/combined.py --out /tmp/studio-combined-new --native --resume
python3 tools/ci_bundle.py --run /tmp/studio-checks-new --replay /tmp/studio-scope-replay-new \
  --combined /tmp/studio-combined-new --out /tmp/studio-upload-new
```

The native path requires macOS media services. Portable CI omits `--require-native` and `--native`, retaining explicit unavailable/unperformed native states. CI runs Python 3.12/3.14 on Linux and Python 3.12 on macOS with Node 24. Exact checks and replay reports bind the source files; GitHub head and tested checkout SHA remain separately recorded. The PR and CI artifacts identify the actual passing head rather than a report filename selecting a version.

Each feature keeps its own fixture and assertions. Local fixture setup supplies synthetic paint or read-only copies of repository-cleared artwork; production operations use public CLI routes. The combined runner adds resumable attempts, unchanged-source/output verification and compact results. It does not implement another coverage, timing, rendering or binding evaluator.

| Path | What its evidence establishes |
| --- | --- |
| Production intent | Coverage, overview and preflight agree; generic reports and reduced final scope fail; both final movies receive exact captured evidence |
| Tea and cabinet | Source-bound compound preparation, independent masks/parts, shared backing, mapped placement and normal/hidden/extreme paired proofs |
| Painted bindings | Shared-clock source/follower response, receiver-local masks, hidden-source behavior and reusable look/rig package evidence |
| Activity and cues | Actual state/raster sampling, circular loop intervals, explicit warning misses, matched strength/cadence comparisons and picture/cue identity checks |
| Paired recovery | Actual SIGINT after one encode preserves the completed view, avoids selecting the incomplete pair and resumes only missing work |

The [CI evidence contract](../CI-EVIDENCE.md) defines the bounded upload subset and diagnostic failure probes. Browser parity packets and saved proofs remain inspectable. Automated CI runs the runtime/raster/native tests; actual browser/UI playback observations are separately recorded local evidence, not an implied browser-engine CI execution.

## Shared authoring guidance

The production plan owns story, semantic census and expectations. Inventory owns fulfillment; scene owns runtime; review records own actual observations. Existing census notes remain migration inputs. New pipelines watch the canonical plan for intent/layout changes; existing project pipelines and sealed editions are not rewritten. The [unplanned template](../../templates/production-plan.json) is intentionally valid to save and incomplete to produce. The existing `plan check --require-complete` remains an inventory-only fallback for unmigrated projects; canonical scope uses stage coverage.

## Explicit remaining work

Artifact replays do not complete the three [autonomous scenarios](../../tests/agent-evaluations/scenarios.json), the tram/fresh-scene film pilots, human listening or phone checks. Held-out activity fixtures retain known misses, including low-contrast and excessive motion; empty warnings cannot establish observed readability. Metrics and cache measurements remain descriptive, with no artistic grade or performance pass threshold. Normal-speed film observations, sound auditions and explicit retiming decisions remain production work. FOLLOW-01/02 stay evidence-triggered follow-ups. No provider submission, paid generation, account change, private-film rewrite or publication is performed by this integration.
