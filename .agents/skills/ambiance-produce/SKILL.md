---
name: ambiance-produce
description: "Plan and carry an ambiance film from a reference image through layered animation, sound, review, and handoff using the Ambiance Studio project. Use for complete films or resuming their production."
---

# Produce an ambiance film

Use `./ambiance` from the studio root, with `--project PATH` before the command. Read [operations](../../../docs/OPERATIONS.md) for project handling and [quality gates](../../../docs/QUALITY-GATES.md) for evidence rules.

1. Locate the user's project and read its brief, handoff, and current `ambiance --project PATH project status` report. For a new project, preserve the supplied image with `ambiance project init`. If the reference is attached without a usable local path, inspect it through the available image capability and preserve a returned local copy when supported; do not claim it was archived before it exists.
2. Inspect the reference. Record what is visible separately from proposed additions. Read the [style guide](../../../docs/STYLE-GUIDE.md); adapt its defaults to the user's image and explicit direction.
3. Use `doctor` to inspect local capabilities. Record dimensions, picture/master durations, assets and generation authority. Continue local work if paid tools are unavailable; a plugin login does not establish API access.
4. Route the actual stage: image breakdown → `ambiance-deconstruct`; production art → `ambiance-assets`; scene/cels → `ambiance-animate`; soundtrack → `ambiance-sound`; final inspection and reusable archive → `ambiance-release`. Read only the relevant skill. These are workflow roles, not an instruction to spawn agents.
5. Maintain project records and reconcile the [production inventory](../../../docs/PRODUCTION-INVENTORY.md) with `plan inspect/check/next`. Retain intentional static/deferred scope. Continue independent reversible work when another review is pending.

Bring the user a small number of meaningful creative decisions: the style/composition proof, the draft with sound, and the release review are useful defaults. Do not ask them to approve routine coordinates, file formats, or every generated cel. Respect a requested level of autonomy. Quality records must still distinguish agent review, actual user feedback, unperformed checks, and explicit exceptions.

For a workflow exploration, name the few capabilities the current cycle will demonstrate and show their concrete proofs. Distinguish independent object/occlusion layers from local image patches, and changing drawings from light modulation. A finished file does not by itself establish that the requested layering or cel workflow was exercised.

Reuse compatible assets and rigs before generating replacements. Reconcile uncertain generation outcomes before retrying; preserve useful work and record cost/time only when known.

For a selected production version, use [revision capture and checks](../../../docs/REVISIONS.md), then bind renders, reviews and editions to that revision. Legacy folder-watch receipts remain unchanged; capture does not migrate their verdicts. Finish the requested scope with inspectable artifacts and a handoff. A planning or asset pass does not imply a final video.
