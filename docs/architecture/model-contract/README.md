# Model and character contract packet

Packet **mc/1**, September 13, 2026. Reconciled against main `00c64436543d0252fc0850f3ef58e686badda1b6`. This is the bounded engineering prerequisite for reusable-model Phase 1 and the shared technical part of first-short P00. The original packet adds no production model runtime, command, accepted art or backlog completion. Its later [C1/C2 implementation](construction-v1.md) now supplies immutable local construction and static technical proof/entry routes; I1/I2 and broad production acceptance remain open.

The integration owner is coordinator task `01a0983d-40cf-71a3-bd9c-cb8308ad6efa`. Stream M owns this packet and its fixtures. Consumers adopt a committed packet version explicitly; changing a settled meaning requires a versioned diff, updated specimens and coordinator agreement. Labels and clarifications can change without changing identity. The existing [model plan](../REUSABLE-MODEL-SCENES-PLAN.md) and [first-short packages](../FIRST-SHORT-WORK-PACKAGES.json) retain their statuses.

Read [the contract](contract-v1.md), [the clock and cue boundary](clock-v1.md), then [implementation slices and acceptance](implementation-v1.md). Machine-readable specimens live in [tests/fixtures/model-contract](../../../tests/fixtures/model-contract/README.md); they are design specimens, **not loadable model/sequence production formats**. The focused check is `node tests/test-model-contract.mjs`.

## Decision table

| Decision | mc/1 agreement | Current capability / outstanding implementation |
| --- | --- | --- |
| Scope authority | Canonical production plan/inventory owns required scene members and actions. Definition records own technical assembly only. | Existing plan/coverage services remain authoritative; no new census. |
| Stable identity | Model family ID; character ID is the same ID when kind is character; model-local part/drawing/control/socket/variant IDs; scene-local instance IDs. Names are labels. Nested identity is an ordered tuple of slot IDs. | C1 validates definitions; instance validation remains I1. Existing raster IDs and scene IDs retain their meaning. |
| Version/dependencies | Exact immutable version and file SHA-256 at every nested edge, with complete local closure. No `latest`, version range or implicit upgrade. | Reuse file identities, record seals and revision collection; add typed model edges. |
| Adoption | Explicit old pin → new pin transaction with retained/reset/conflicting overrides, contacts and evidence. Reject unresolved conflicts or stale managed layers. | Existing scene history/expected-hash transaction is the save boundary. |
| Coordinates | Fixed model-local pixel frame; full compiler cells including padding; recorded source/cell/local affines. Placement is separate. | Existing compiler/source-placement matrices apply; native sequence placement remains unsupported. |
| Construction | Nested definitions with one painted root per assembly in the first slice. | Current layer attachments can lower the lantern and complete character specimens. No new nonpaint root is assumed. |
| Overrides | Explicit typed controls, drawing-compatible variants and opt-in part channels. Structural edits create a definition revision. | No arbitrary runtime-layer JSON override or competing control expression language. |
| Clock | Model controls consume P03's evaluated finite/loop clock and local cycles. Models contain no originating film fps/duration. | Today `compileScene().sample(seconds)` always wraps; P03 adds finite behavior and common conversion. |
| Ownership/mount/order/depth | Four distinct relationships. Selection changes none. Attached children inherit depth under the existing engine. | Ownership/instance metadata is new; mounts and painter order reuse current fields. |
| Source/receiver light | Emitter belongs to fixture; receiver paint/mask belongs to receiving surface and has an explicit source link. | Existing bindings/finishing apply; automatic light transport is not promised. |
| Derived masks/evidence | Bind exact definition closure, variant, overrides, pose, resolved parts, time/view, renderer and output bytes. | New typed adapter extends existing render/revision/evidence owners; fixture checks do not accept artwork. |
| Character specialization | Registered body, view, part, drawing and named action interfaces extend the same model definition. | P02 builds registration/reconstruction tools; it does not own a second graph. |
| Independent narrative work | P03 can use flat current scenes plus the clock specimen; P04 can develop against pinned drawings/take fixtures. | Full model-library delivery is not a new prerequisite; integrated acceptance dependencies remain unchanged. |

## Outstanding decisions and inputs

The production seed, canonical first-short project, complete scene census, required actions, intended hidden surfaces, light receivers and both composition plans are **unresolved** here. No character art, selected voice, storyboard, actual performance method or human audition is selected. Phase 1/P00 cannot be marked complete from this packet.

General nonpaint transform nodes, cross-instance paint interleaving, arbitrary clipping, automatic package transport/discovery, mixed-rate sequence conform and incompatible view swaps remain deferred. Their absence does not block the bounded painted-root, contiguous-block, local-package construction slice. The exact implemented command names and package layout are in the C1/C2 contract. Other proposed formats in this packet must not be advertised as implemented CLI routes.

The [clean-component research](../../research/clean-components-2026-09-12/report.md) supplies observed contamination/attachment failures and candidate designs. mc/1 selects only the bounded decisions above after reconciling current code. Research command names, graph sketches and broader clipping/root proposals are not adopted wholesale.

The [first-assignment handoff](HANDOFF.md) records executed checks, exact artifacts, scope limits and the next implementation dependency.
