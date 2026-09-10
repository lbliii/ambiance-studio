# Rig workbench v0.3 validation

September 10, 2026. This record covers the new compiler, attachment evaluator, and loop workbench. Older reports in this directory describe earlier versions and historical production.

- **24 Python tests passed:** 14 existing review-gate tests and 10 new asset-tool tests. Registration fixtures recover known displacements with identical output cels; shared scaling preserves relative shape size; empty/opaque input, stale caches and conflicting IDs are exercised. A recipe saved in the output pack resolves its originals and hits the same cache.
- **7 rig scenarios passed:** moved/scaled/rotated/animated parents across all 480 frames, nested attachments independent of paint order, cel-specific socket tracks, invalid graphs/tracks, camera coverage failure despite endpoint closure, deterministic immutable snapshots, and inherited visibility/opacity. The 8 legacy engine checks also pass.
- **Real-scene state audit:** 480 frames, 2 attachments, zero measured attachment error, valid referenced asset hashes, and no geometric sky coverage failure.
- **Browser raster check:** all 480 frames at 135 × 240, zero exposed canvas. Last-to-first normalized RGB difference 0.003130; adjacent-frame 95th percentile 0.002813. The seam heuristic did not request extra attention; that does not prove artistic continuity.
- **Deliberate browser failure:** hiding the sky produces exposed canvas in all 480 frames, with a maximum 4,176 uncovered preview pixels. This confirms that the canvas fill does not conceal missing coverage from the checker.
- **Browser operations exercised:** parent rotation/scale, socket placement by clicking the canvas, adding the compiled asset with its recorded pivot, snapping it to a socket, JSON load/save round trip, detachment, and stale-report indication after edits. Desktop layout inspected; at 390-pixel viewport width, document width is also 390 pixels.
- **Real asset compilation:** 12 existing smoke cels compiled, contact sheet inspected on light/dark backgrounds, and cache reuse verified. The compiler chose a shared scale of 5/6 to retain padding around faint edge pixels. Source clipping remains visible in some wisps; this pack is a tool study, not a newly accepted replacement for the original film asset.

[Command outputs](rig-test-results.json), [state report](rig-check.json), [browser observations](rig-browser-check.json), [compiled asset report](../assets/compiled/smoke-v1/report.json).

No new final video, audio master, physical-phone review, automatic tracking, independent operator pilot, or multi-film throughput benchmark is claimed. The user’s accepted original film remains the production reference.
