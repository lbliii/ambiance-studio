# Quality gates and evidence

The canonical gate definitions are in `templates/pipeline.json`. A project receives its own copy so a later studio update cannot silently change its review criteria. The table below is a guide; the project's pipeline file is the executable record.

| Gate | Required outcome and evidence | If it fails |
| --- | --- | --- |
| `intent` | Inspected reference, emotional brief, style/focal decisions, delivery/tool/budget scope | Clarify the actual uncertainty; continue useful planning |
| `layout` | Whole-scene census, story/action choices, requested output composition proofs, draw/depth order, light relationships, attachments and hidden-paint plan | Repair missing scope, composition or spatial relationships before producing affected assets |
| `assets` | Real production files, catalog/recipes, integrity report, cel registration and edge review, provenance | Fix the asset or preparation recipe; preserve unaffected accepted assets |
| `animation` | Completed declared scope, noticeable story/environment motion in each requested composition, deterministic timing and join/coverage checks | Repair the missing action, cadence, artwork, composition or technical defect at its source |
| `sound-design` | Emotional sound brief, separate selected sources, actual audition notes, source records | Replace or edit the weak source without discarding the whole mix |
| `mix` | Circular arrangement, exact masters/stems, measured levels/seam/mono, repeated listening with picture | Adjust phrasing, tails, event timing, processing, or level |
| `export` | Fully decoded final media, correct frame/audio presentation timeline, encoded join, correct editions | Fix the export/mux or source issue and verify the new actual file |
| `release` | Human look/listen and phone review of the exact final file; delivery/use scope considered | Keep the release review open; fix or explicitly document the remaining limitation |
| `library` | Rebuild record, versioned reusable modules, clear handoff | Complete the archive so another operator can continue without the chat |

Sound design depends on intent and can progress alongside layout, assets, and animation. Mixing depends on the picture draft and the selected sound sources. Export, release, and library follow from there.

## Evidence rather than a checkbox

A passing criterion records:

1. The criterion ID and `pass` result.
2. The actual observer kind/name: agent, tool, or human.
3. Specific observations, including what was inspected or measured and any relevant method.
4. Project-relative paths to nonempty evidence files.

`studio.py record` adds file hashes, the gate criteria hash, project settings hash, watched file inventory, and dependency receipt hashes. It preserves the previous receipt in `reviews/history/` when replacing a review. `status` reports `pending`, `blocked`, `revise`, `stale`, or `passed`.

A change to an evidence file, a watched input/output, project settings, gate criteria, or an upstream receipt causes re-evaluation. Unaffected independent work can retain its review: changing a smoke atlas should not by itself invalidate the sound-source audition.

The recorder checks evidence presence and consistency. **It does not inspect image aesthetics, listen to audio, authenticate a reviewer's identity, or prove that a supplied report is truthful.** The observer is responsible for performing the stated check and saving the real evidence. This is a local production record, not an audit service or digital-signature system.

New project templates include whole-scene census, requested output composition and scope-coverage criteria following the tram feedback. Existing projects retain their copied criteria and historical reviews; no automatic migration or reapproval occurs. `plan check --require-complete` checks declared production completeness and supplies one piece of scope evidence. It cannot detect an omitted requirement or establish that an action is artistically readable. Apply the [seed-to-stage workflow](SEED-TO-STAGE.md) to the current user direction and record new-revision observations separately from prior edition reviews.

Technical reports should identify the inspected file hashes, commands/tool versions, actual results, and limits. A contact sheet proves which images were available to inspect, but not that someone watched the animation. A peak measurement cannot establish pleasant sound. A zero/end state test cannot establish that the last encoded frame joins smoothly.

## Human review without constant interruptions

Use creative checkpoints at useful moments; do not ask for approval of every low-level edit. An agent may perform and record visual or technical reviews it can actually carry out. For `release`, the human look/listen and phone criteria require an identified human observation, a feedback record, and the exact final file as evidence.

Feedback already given counts when it establishes the specific criterion for the identified artifact. Do not ask the same thing again. “I love it” can support a creative response; it cannot be rewritten as “tested on an iPhone speaker” without that evidence.

Quality readiness is distinct from authorization. A pending review does not bar independent reversible work or delivery of a clearly labeled review draft. A passing review does not grant permission to publish or send files. If the user chooses to deliver with an unperformed check, retain it as open and describe the scope accurately; never manufacture a pass to match the decision.

## Failure and change handling

Use `revise` with specific failed/unperformed checks and a next repair. Fix the earliest responsible source. Then repeat affected reviews, rather than replaying the entire pipeline mechanically. Preserve candidate versions and concise reasons for rejection.

Record defects by asset/layer/cue and timestamp: `chimney-smoke`, 15.9→0 seconds, visible jump; or `hearth`, 6.8 seconds, sharp transient. Severity should describe impact: blocks the intended experience, noticeable but acceptable by explicit choice, or polish opportunity.

Project review receipts have a single writer at a time. File replacement is atomic, but the prototype has no multi-user locking or authenticated approvals. Do not let two independent runs overwrite the same project's current review records.

## What a complete gate is not

- A file named `final.mp4` is not proof of a completed decode.
- A provider's “loop” checkbox is not proof of musical continuity.
- A checkerboard baked into an image is not transparency.
- A skill-format validator is not proof that an agent follows the workflow well.
- The bundled example's tests do not validate a new scene unless run against its actual data.
- Historical user approval is not a fresh technical certification of a repackaged file.
