---
name: ambiance-produce
description: "Plan and carry an ambiance film from a reference image through layered animation, sound, review, and handoff using the Ambiance Studio project. Use for complete films or resuming their production."
---

# Produce an ambiance film

Operate from the studio root containing `studio.py`, `templates/pipeline.json`, and this skill pack. Keep the whole studio together when moving it. Read [operations](../../../docs/OPERATIONS.md) for commands and [quality gates](../../../docs/QUALITY-GATES.md) for evidence rules.

1. Locate the user's project and read its brief, handoff, and current `ambiance --project PATH project status` report. For a new project, preserve the supplied image with `ambiance project init`. If the reference is attached without a usable local path, inspect it through the available image capability and preserve a returned local copy when supported; do not claim it was archived before it exists.
2. Inspect the reference. Record what is visible separately from proposed additions. Read the [style guide](../../../docs/STYLE-GUIDE.md); adapt its defaults to the user's image and explicit direction.
3. Record tool availability, output dimensions, picture/master durations, available assets, and generation budget/authorization. Continue planning and local preparation if paid tools are unavailable. Use supported current capabilities rather than assuming a plugin login exposes an API.
4. Route the actual stage: image breakdown → `ambiance-deconstruct`; production art → `ambiance-assets`; scene/cels → `ambiance-animate`; soundtrack → `ambiance-sound`; final inspection and reusable archive → `ambiance-release`. Read only the relevant skill. These are workflow roles, not an instruction to spawn agents.
5. Maintain the source ledger, current scene, sound session, review evidence, and a short handoff with the next concrete action. Close a gate only from evidence for its current inputs. Continue independent reversible work when another review is pending.

Bring the user a small number of meaningful creative decisions: the style/composition proof, the draft with sound, and the release review are useful defaults. Do not ask them to approve routine coordinates, file formats, or every generated cel. Respect a requested level of autonomy. Quality records must still distinguish agent review, actual user feedback, unperformed checks, and explicit exceptions.

The original film's success criteria are examples, not mandatory settings for every film. Reuse compatible assets and rigs before generating replacements. Preserve partial useful work if a provider fails; uncertain generation outcomes need reconciliation before retrying. Record cost and time when available, without inventing either.

Finish the requested production scope with inspectable artifacts and a self-contained handoff. A final video is not implied by a successful planning, asset, or placement pass. Consult [capabilities and scaling](../../../docs/SCALING.md) before promising fully automated production.
