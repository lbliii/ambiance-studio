# Dual-format implementation evidence

Recorded September 11, 2026 on macOS, Node 24.9.0 and the installed Node Canvas/native media backends. The [implementation plan](DUAL-FORMAT-IMPLEMENTATION.md) milestones 1–5 are implemented. Local pilot directories below are ignored production artifacts, not bundled example movies. Each retains its brief, source ledger, scene, view declaration, recipe, captured revision, receipts and handoff.

## Verified behavior

- Saved view edits use the existing transaction/history path; invalid crops, changed input hashes and unsupported raster sizes fail before publication. Omitting a view preserves authored rendering.
- The moving fixture includes an asymmetric room, a round focal body, an attached changing hand, camera/depth movement, a stationary front rim, and light/shadow/reflection effects. Independent crop comparisons test geometry at normal and supersampled sizes, fractional crops and a hole affecting only one view.
- The editor and saved paired proof use one source time. Browser checks observed both panes at matching frames during seeking/playback, including the hand's changing cel. Overlays stay outside rendered outputs.
- Native portrait and landscape movies fully decode with their own dimensions, timing, view definition/hash and revision identity. Composition preserves compressed picture samples and reuses the same PCM bytes. Reverification uses the edition's expectations after the working canvas changes.
- A version-2 recipe produces the view × soundtrack set. An injected interruption after an edition receipt was written reused that receipt and the preceding picture on resume; only the two remaining operations ran. Live coordinator locks are rejected and confirmed-dead owners can be recovered. Bad second views, invalid PCM duration and unsupported output dimensions fail before encoding.
- Duplicate or mismatched view/role entries, ambiguous feedback and missing explicit media pairs are rejected. Legacy sealed records and role URLs remain readable without rewriting their bytes. Every delivery entry has independent review state; one unready entry prevents combined release readiness.
- Browser inspection loaded the engineering portrait at 1080 × 1920 and landscape at 1920 × 1080, with the correct per-entry poster. Switching landscape score at 0.75 seconds to portrait score retained 0.75 seconds and paused the replacement. The saved engineering note identifies the portrait score edition, view hash and exact movie bytes. Format and soundtrack controls indicate the selected pair; absent effects remain disabled.
- The CLI `project latest` path was exercised against the actual version-2 demo, returning its default movie and exact pair link plus each entry's exact/current URLs. A regression test covers this path independently of the library UI.

The local full suite runs with `AMBIANCE_TEST_NATIVE=1 ./ambiance test`: 222 Python tests, engine/rig/view/raster/track/placement/finishing checks, and package audit. Native tests execute actual encode, compose and decode. Browser observations and full-resolution still inspection are separate evidence; they are not human creative, listening or device approvals.

## Production pilots

| Local project / delivery | Outputs | Evidence and scope |
| --- | --- | --- |
| `projects/dual-production-pilot` / `dual-demo` | Portrait 1080 × 1920 and landscape 1920 × 1080; 8 fps; silent 16 frames / 2 seconds and scored 32 frames / 4 seconds | One captured scene, four verified entries. The score is explicitly a quiet 220 Hz engineering test tone, not a composed soundtrack. Reproduce with `python3 examples/views/produce_motion_fixture.py NEW_PROJECT --long-edge 1920`. |
| `projects/dual-last-lantern-pilot` / `crop-review` | Portrait 180 × 320 and landscape 320 × 180; both 30 fps, 480 frames / 16 seconds | Exact copied artwork/dependencies and camera motion from the registered project; full-resolution stills at eight seconds also saved for both views. |
| `projects/dual-the-midnight-collection-pilot` / `crop-review` | Portrait 180 × 320 and landscape 320 × 180; both 30 fps, 720 frames / 24 seconds | Exact copied artwork/dependencies and 48-layer staging from the registered project; full-resolution stills at eight seconds also saved for both views. Actual landscape MP4 inspected in the browser at eight seconds. |

Both painted pilots use the same contained landscape rectangle `[0, 656.25, 1080, 607.5]` within the original 1080 × 1920 stage. Their two-second paired raster proofs have exact 0/T endpoints and no reported whole-cycle geometry/alpha coverage defects. Their movies retain the complete original picture clocks. The 320-pixel movie ceiling is a review resolution; it is not a full-resolution release claim.

At 1920 × 1080, Last Lantern's wide frame keeps the doorway, lit windows, pumpkins and path as a coherent cottage close-up. The crop excludes upper/lower environmental context, so a wider establishing shot would need expanded artwork or a newly authored stage. The Midnight Collection's wide frame keeps the mummy's face, crossed hands, glass edge and reflected floor, while the portrait includes the larger room, statues and foreground display. These are useful alternate framings with different emphasis. Full-scene parity and final creative acceptance are not established by a technically valid crop.

The Last Lantern pilot exposed three existing PNGs (`sky`, `moon`, `branch`) that Pillow decoded but the Canvas backend rejected as “Invalid SVG image.” Only the derivative pilot received `sips -s format png SOURCE --out DERIVATIVE` copies. Decoded RGBA bytes were equal before/after; original bytes remain available. `plans/png-compatibility.json` records source/output hashes and the conversion. Renderer failures now name the asset and file. No paid generation or automatic art expansion occurred.

The original registered scene/catalog hashes and presentation selections were rechecked after production and remained unchanged. Local `reports/dual-feature-evidence.json` pins movie, verification, poster and proof hashes plus source-preservation checks. `reports/dual-feature-handoff/` contains exact/current links and open checks. The engineering pilot also retains `reports/all-pilot-evidence.json` and `reports/raster-benchmarks.json`.

## Measurements and limits

Each bounded raster benchmark used four source times at preferred sizes, with a 1920 × 1920 internal stage. Separate processes keep peak RSS attributable to one case. Reproduce with `node examples/views/benchmark_raster.mjs on pair`, substituting `off` or `single` as needed.

| Finishing | Outputs | Four-frame paint/extraction time | Peak process RSS |
| --- | --- | ---: | ---: |
| Off | Portrait | 0.301 s | 148 MiB |
| Off | Portrait + landscape | 0.274 s | 170 MiB |
| On | Portrait | 5.779 s | 530 MiB |
| On | Portrait + landscape | 5.424 s | 538 MiB |

These are short local measurements, not statistically significant speed comparisons. They exclude PNG writing, proof audits and encoding. Finishing dominates this fixture; extracting the second crop adds little compared with rendering another finished stage. Keep a single encoder worker and prioritize low-resolution paired review. Do not infer full-resolution real-time playback from these results.

The full-resolution engineering iteration took 94.75 seconds for four verified movies. Its two picture render processes reported 41.13/40.98 seconds and about 521 MiB peak RSS each; the two soundtrack compositions each took under 0.8 seconds. Other checks were active on the host during this run, so wall time is an observed run cost rather than an isolated throughput baseline.

The painted pilots' paired proofs took 14.25 seconds (Last Lantern, 231 MiB peak RSS) and 12.14 seconds (Midnight Collection, 219 MiB); both used a 324 × 576 internal stage and 60 saved frames per view, with additional whole-loop audit work. Their complete two-movie iterations took 30.83 and 28.73 seconds respectively. Full-resolution wide stills used a 1926 × 3424 internal stage: 1.255 seconds / 288 MiB for Last Lantern and 0.955 seconds / 258 MiB for Midnight Collection. The stage's integer aspect-ratio sizing explains the small oversize before final extraction.

Internal dimensions remain capped at 4096 per side. A magnified crop or higher supersampling can exceed that limit even if the final movie is small; preflight rejects it. Concurrent encoders, direct-view rendering, automatic expanded artwork, per-view restaging/mixes/durations and transferred creative approvals remain outside this feature.

## Local presentation

The pilot registry is `projects/dual-production-pilot/.ambiance/registry.json`. Start its library with `./ambiance --registry projects/dual-production-pilot/.ambiance/registry.json studio open --port 8798`. Exact examples:

- [Engineering portrait](http://127.0.0.1:8798/projects/dual-production-pilot/deliveries/dual-demo?view=portrait&role=silent) and [landscape](http://127.0.0.1:8798/projects/dual-production-pilot/deliveries/dual-demo?view=landscape&role=silent); [current demo](http://127.0.0.1:8798/projects/dual-production-pilot).
- [Last Lantern portrait](http://127.0.0.1:8798/projects/dual-last-lantern-pilot/deliveries/crop-review?view=portrait&role=silent) and [landscape](http://127.0.0.1:8798/projects/dual-last-lantern-pilot/deliveries/crop-review?view=landscape&role=silent); [current crop study](http://127.0.0.1:8798/projects/dual-last-lantern-pilot).
- [Midnight Collection portrait](http://127.0.0.1:8798/projects/dual-the-midnight-collection-pilot/deliveries/crop-review?view=portrait&role=silent) and [landscape](http://127.0.0.1:8798/projects/dual-the-midnight-collection-pilot/deliveries/crop-review?view=landscape&role=silent); [current crop study](http://127.0.0.1:8798/projects/dual-the-midnight-collection-pilot).

These are labeled review deliveries. Human look/listen and phone checks remain open. New-project templates now address every requested view; existing copied project pipelines and accepted source-project selections were not migrated.

## Integration with cel motion and canvas sizing

PR #5 was reconciled with main `dae0e18` on September 11, 2026. CLI registration retains both motion-study and synchronized-view previews; doctor reports both capabilities. Editor canvas dimensions continue to determine its displayed aspect ratio. The integrated `AMBIANCE_TEST_NATIVE=1 ./ambiance test` passed all 240 Python tests and all subsequent Node/package checks, with no skipped native tests (Python 3.14.0, Node 24.9.0, macOS media services enabled). A restricted first run failed explicitly on unavailable encoder/localhost access; it was not counted as passing validation.

The repository synthetic moving fixture was inspected in the merged browser editor. Both output panes displayed their distinct crops, seeking to frame 8 produced shared time 1.000 s, and both timelines followed playback/pause together. No browser error logs appeared. These integration observations concern UI synchronization and rendered fixture behavior, not artistic film approval. The source-only merge does not modify pilot projects or captured deliveries.
