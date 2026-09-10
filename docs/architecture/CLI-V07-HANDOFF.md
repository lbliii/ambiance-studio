# CLI 0.7 — finishing and edge quality

Implemented the [finishing plan](CLI-FINISHING-PLAN.md) as executable shared rendering, CLI authoring, preparation, packages and visual inspection tools. The museum's accepted art, scenes, sound, reviews and editions were not edited. Trials use independent project directories.

## What now works

| Area | Executable result |
| --- | --- |
| Appearance | Ordered asset, direct-group, instance and scene grades; exposure, contrast, saturation, RGB balance, curves and catalog masks |
| Local light | Feathered scene or layer-anchored zones, explicit receivers, colored gain and shared cel/closed-key signals |
| Shadows/reflections | Receiver-clipped projections, source-relative orientation, ground sockets, paint-order occlusion and authored lift responses; reflections use caster appearance |
| Color | Opt-in linear-sRGB grade/compositing arithmetic and explicit sRGB output; alpha-safe source isolation and linear premultiplied reflection blur |
| Reuse | Validated look apply/export/import, optional rig templates with sockets/cel timing/tracks and attachment ancestors, explicit bindings, exact mask/rig versions and revision dependency closure |
| Edge quality | All-cel light/dark/context proofs at explicit display size; opt-in matte cleanup, choke, feather and isolated padding; original bytes and full preparation provenance retained |
| Export | True internal supersampling followed by one output-size reduction for frames, motion proofs and native video; original aspect ratio retained |
| Workbench | Saved variants, synchronized views, grade/light controls, JSON recipe editing, effect passes, seek/play, explicit draft/full resolution and guarded transaction downloads |
| Inspection | Receipt-verified `preview --look`, clipped-pixel diagnostics, stale-input rejection and real pixel/native-media tests |

Commands and schemas: [CLI](../CLI.md), [finishing](../FINISHING.md), [edge quality](../EDGE-QUALITY.md), [workbench](../LOOK-WORKBENCH.md).

## Validation and examples

The complete native-enabled regression suite passes **164 Python tests with no skips**, existing engine/rig/track/placement checks, **15 new actual-pixel finishing checks**, and package/link audit. Native tests encode/decode supersampled outputs and compare neutral/color patch interiors against finished PNGs. Their explicit lossy tolerance detects gross transfer/range mistakes, not calibrated-display accuracy. The final report is stored locally under `work/cli-v07-regressions-final.json`.

The public-CLI engineering fixture at `work/cli-v07-finishing-fixture/` demonstrates a moving creature crossing moonlight, a flame's cel signal driving nearby illumination, and a lifting casket changing its receiving shadow. Its exported package and explicit binding template are reusable. Source generator: [finishing example](../../examples/finishing/README.md). The extended pilot at `work/cli-v07-rig-package-fixture/` exports both look-only and rig-inclusive packages, performs an explicit bound dry run and saved import, and confirms the identity-bound scene values remain unchanged. Twelve package/CLI tests cover adoption, source order, mounting/cel metadata and rejection paths.

The independent edge pilot at `work/cli-v07-edge-pilot-final/` exercised six public CLI calls. Its known-matte correction reduced the inspected fringe while preserving alpha bytes and the exact original source. Compiler 1.2.0, scene authoring and revision capture follow its declared edge preparation report through raw source, recipe, snapshots and repaired atlas. Fifteen edge regressions include identity behavior, neighboring-cell isolation, concurrent output claims and upstream mutation.

The museum trial at `work/cli-v07-museum-final/` copies and verifies 34 source inputs. It compares the original picture, an identity linear pipeline, baseline rat correction and local moonlight. It saves a 93-frame moving-rat proof and a 1080 × 1920 portrait rendered internally at 2160 × 3840. `look-workbench-final/` is built from an explicitly captured baseline revision with the final shared modules. This is a candidate look for inspection, not a replacement movie or an artistic approval. Reproduce it with [museum_trial.py](../../examples/finishing/museum_trial.py).

Actual browser inspection passed on the independent fixture and the museum frame-110 comparison. It covered grade/light controls, invalid-recipe rejection, draft/full resolution, isolated contributions, half-speed playback and pause. The observed museum rat is cooler than the saved baseline with the same portrait composition. The exact inspected module/image identities are recorded in `work/cli-v07-browser-review.json`. The edge viewer's `file://` navigation was rejected by browser URL policy, which prohibited workaround navigation; it was not retried. Its raster contacts and scripted behavior tests passed, but interactive edge-viewer playback is not claimed as verified.

## Practical boundaries

- Legacy scenes without `finishing` retain their prior rendering. Enabling it deliberately changes compositing arithmetic; compare the identity variant before accepting a new look.
- Artwork must be sRGB; there is no automatic ICC conversion, HDR workflow or recovered unlit material. Masks are luminance × alpha data. Canvas performs spatial sampling; grading and compositing use the declared linear arithmetic.
- Projections are authored 2D approximations. They flatten the relative caster transform onto a chosen receiver and use explicit lift response, rather than solving a 3D floor or physical illumination.
- Direct group grades do not implicitly follow transform attachments. Apply explicit instance grades when an attached child needs the same appearance.
- Rig inclusion is explicit on export and import. It reinstalls saved normalized placement, mounting, timing and relative paint order among bound targets. The destination must already contain the declared images/layers/groups, with a matching canvas and clock; this does not perform artwork migration or infer placement in a different camera setup.
- The CPU workbench starts paused in an explicitly labeled draft resolution. It reports render time, achieved playback rate and skipped preview frames. Full-detail frame inspection and saved motion proofs provide separate quality/cadence checks.
- Supersampling cannot recreate missing source detail. Choke and feather can erase delicate features; defaults preserve source alpha, and repairs remain opt-in recipes.
- Technical receipts, browser inspection and this handoff do not imply human creative acceptance, continuous full-film viewing/listening or a physical-phone test.
