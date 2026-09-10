# Appearance workbench and supersampled delivery

`render look-proof` produces a portable, editable look-development artifact using the same `compileScene` and `drawScene` modules as CLI rendering. It writes a fresh directory and leaves project inputs unchanged. Serve that directory through a local static HTTP server and open `index.html`; ES modules and snapshot requests require HTTP, so opening `file://` directly is unsupported.

```sh
./ambiance --project PROJECT render look-proof LOOK.json --width 360 --supersample 2 --out NEW_LOOK_DIRECTORY
./ambiance --project PROJECT preview --look NEW_LOOK_DIRECTORY
# Or use a local static server:
python3 -m http.server 8798 --directory NEW_LOOK_DIRECTORY
```

The strict version-1 recipe supports `title`, `time`, `selected_layer`, `scope`, `finishing`, and `variants`. `time` selects a saved sample within `[0, loop_seconds)`. Omitting `finishing` starts from the saved scene; `null` removes finishing for the candidate. Each optional variant is `{ "id": "cooler", "label": "Cooler moonlight", "finishing": {...} }`. IDs must be unique; `baseline` and `current` are reserved. At most 12 additional variants are allowed. Every finishing configuration must validate against the shared scene contract before the output directory is created.

```json
{
  "version": 1,
  "title": "Creature through moonlight",
  "time": 1,
  "selected_layer": "creature",
  "scope": "Compare baseline appearance and cool floor illumination",
  "finishing": {
    "version": 1,
    "working_space": "linear-srgb",
    "output_space": "srgb",
    "layers": {"creature": {"balance": [0.8, 0.9, 1.15]}},
    "lights": [{"id": "moon", "receivers": ["creature"], "rect": [0.4, 0.2, 0.5, 0.7], "color": "#7caaff", "gain": 0.4, "feather": 0.3}]
  }
}
```

The artifact includes immutable source scene/catalog snapshots, hashed images used by scene or look masks, saved baseline/current/variant PNGs, and the full local renderer module graph with hashes. `workbench.json` selects a runtime catalog pointing to copied assets; its scene retains the authored canvas size for scene downloads. `render-report.json` records the input scene/catalog identities, engine and finishing module identities, sample image hashes, output/internal dimensions, and the limited review scope. Browser asset loading verifies snapshot hashes and dimensions. Local module snapshots eliminate a dependency on whichever engine version happens to be installed later.

The workbench provides synchronized baseline and candidate views; play, pause, frame seek and playback speed; beauty, ungraded, light, shadow and reflection passes; phone-width, fit, and one-image-pixel-per-CSS-pixel display; per-scene, group, layer, and asset exposure/contrast/saturation/channel-balance controls; selected light rectangle controls; and a complete JSON finishing editor for masks, curves, signals and shadow/reflection relationships. Interactive preview starts paused at 1× supersampling, independently of saved offline sample quality. For even-dimension outputs at least 360 pixels wide, it defaults to **Draft half resolution** for responsiveness, while phone CSS width remains unchanged. Choose **Full detail** before judging sprite edges. Preview resolution and supersampling are separate controls and never change saved sample dimensions or downloaded scene dimensions. The workbench reports achieved playback rate, skipped preview-frame count, and the measured time to render both preview panels; when rendering exceeds the authored frame budget, playback skips preview frames to keep timeline speed and yields between ticks for controls. Use frame seek for every selected image, or a saved motion proof when inspecting cadence. All candidate changes validate using the shared engine. Invalid recipes do not replace the last valid preview. Slider ranges are deliberately narrower than the full schema; the JSON editor retains access to the supported range.

Downloads are explicit browser downloads, never project writes. **Download CLI operation** writes a normal version-1 batch with `{ "op": "finishing", "value": CONFIG_OR_NULL }`, ready for `scene apply`. The displayed command includes the artifact's source scene hash as `--expect-sha256`; if production has changed, reconcile the new scene rather than removing the guard without review. **Download scene** retains all source scene fields and authored dimensions while replacing only its finishing configuration. Additional art or masks must first be registered in the project and a new proof generated; the workbench uses only its captured runtime asset set.

## Supersampled frames, proofs and video

```sh
./ambiance --project PROJECT render frame --time 1 --supersample 2 --out NEW_FRAME
./ambiance --project PROJECT render proof --start 0 --seconds 2 --supersample 2 --out NEW_MOTION_PROOF
./ambiance --project PROJECT render video --supersample 2 --out NEW_VIDEO
```

`--supersample 1|2|4` multiplies the complete scene's raster dimensions, renders geometry and finishing at that internal size, then downsamples the assembled frame **once** with Canvas high-quality, transparency-aware image interpolation. PNGs and native encoder input retain the requested output dimensions and exact authored ratio. The report records `internal_canvas`, `render_canvas`, `supersample`, and the downsample stage. Scale 1 preserves the existing rendering path. All internal dimensions must remain within the shared 4096-pixel-per-side limit: a 1080×1920 deliverable supports 2× at 2160×3840, while 4× is intended for smaller proofs. `render rig-proof` retains its existing fixed-resolution matrix interface.

Supersampling reduces raster aliasing introduced by placement and transforms; it cannot reconstruct missing source detail or repair a contaminated matte. Compare ordinary and supersampled motion proofs at the same displayed size, then inspect the decoded final video. The native encoder receives only final-size pixels; `render video` performs its existing complete encoded-media verification. Canvas backend/version differences may produce small raster differences; saved PNGs identify the actual export implementation. Neither a desktop phone-width view nor a technical report constitutes a physical-phone or artistic review.

Tests: `python3 -m unittest discover -s tests -p test_finishing_render.py`; include `AMBIANCE_TEST_NATIVE=1` on macOS to exercise real encoding and decoding at the final output dimensions. The native color test compares neutral-ramp and color-patch interiors against the actual finished source PNG, with mean absolute error at most 8 byte code values and individual channel error at most 35. These tolerances test gross transfer/range errors through lossy H.264; they do not certify display calibration or arbitrary ICC inputs.
