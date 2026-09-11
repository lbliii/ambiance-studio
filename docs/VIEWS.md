# Saved output views

Saved views define portrait and landscape framing in one scene without changing its artwork, layer geometry, camera, rigs or clock. Project setup, view authoring, geometric checks, synchronized previews, paired proofs and single-view frame/video rendering are implemented. View-bound editions, resumable combined production runs and exact view/soundtrack delivery selection are implemented.

Create a blank dual-format project with:

```sh
./ambiance project init projects/new-film --format dual
./ambiance --project projects/new-film view inspect
```

The authored stage is 1920 × 1920. The initialized portrait window is 1080 × 1920; the landscape window is 1920 × 1080. They are centered within the stage. A blank project has no painted coverage and cannot pass a picture check. A reference is preserved unchanged; this command does not expand or stretch it. Omitting `--format` keeps the previous portrait initialization. `--format dual` requires the blank template.

The optional `scene.framing` extension contains version 1 and a nonempty `views` object. Each view has a `rect_scene_px` array `[left, top, width, height]` and preferred `output` dimensions:

```json
{
  "version": 1,
  "views": {
    "portrait": {
      "rect_scene_px": [420, 0, 1080, 1920],
      "output": {"width": 1080, "height": 1920}
    },
    "landscape": {
      "rect_scene_px": [0, 420, 1920, 1080],
      "output": {"width": 1920, "height": 1080}
    }
  }
}
```

Save this object as an input file and apply it through the existing scene transaction path:

```sh
./ambiance --project projects/new-film view apply framing.json --dry-run
./ambiance --project projects/new-film view apply framing.json --expect-sha256 HASH_FROM_DRY_RUN
./ambiance --project projects/new-film view check --view portrait --view landscape --out view-check.json
```

View IDs begin with a lowercase letter and contain up to 32 lowercase letters, digits, underscores or hyphens. `authored` is a reserved synthetic view for the full canvas. Rectangles use the authored canvas pixel basis, may have fractional coordinates, and must fit inside the stage. Output sizes are positive integers, at most 4096 per side, with the same aspect ratio as the rectangle (relative tolerance 1e-9). The projection uses a single uniform scale. Unknown fields, unsupported versions and duplicate JSON input keys fail explicitly.

`view apply` replaces the complete framing extension and preserves the previous scene by hash. It supports `--dry-run` and `--expect-sha256` just like `scene apply`; input-file changes during validation abort the write. A scene batch can use `{"op":"framing","value":FRAMING_OBJECT}`. Set `value` to `null`, or apply a file containing JSON `null`, to remove the extension. Removing a view required by `project.json` leaves an explicit project-scope discrepancy for `project check` to report.

`view inspect [ID]` reports the authored canvas, resolved rectangles, preferred outputs, uniform projections and canonical view hashes. `view check` samples every output-frame time and applies the existing attachment/coverage audit to each selected rectangle. Without explicit `--view` choices it checks all named views, or `authored` when none exist. No coverage plate is reported as unchecked. Empty scenes fail. This does not decode artwork, check alpha, judge composition or inspect an encoded movie.

Both inspection commands accept `--revision ID`, resolve the captured scene/catalog, and recheck captured integrity. Working-scene changes do not move a captured crop. Reports identify their actual scene, catalog, evaluator, view-module and audit hashes.

`scene check` retains the authored-stage scope. `project check` additionally checks intended views and the primary-output summary for projects using framing. `project overview` exposes a compact `framing` section, including discrepancies, without blocking access to existing review movies when the working scene is invalid. A dual initializer records `intended_views` in project settings; the first intended view supplies the expected legacy primary-output dimensions. Scene framing remains the executable dimension source, and reads never rewrite either file.

The workbench displays the authored canvas at its actual aspect ratio, with optional named-view guides. Its output panes share the scene's play/seek clock and exclude editing overlays. Both views are extracted after the camera and finishing pass. The all-frame browser audit reports the authored stage and each view separately. Preview can be switched off while editing expensive scenes.

## Render and compare

```sh
./ambiance --project projects/new-film render views-proof --view portrait --view landscape --seconds 3 --long-edge 640 --out projects/new-film/render/paired-proof
./ambiance preview --views-proof projects/new-film/render/paired-proof --port 8797
./ambiance --project projects/new-film render frame --view landscape --width 640 --out projects/new-film/render/landscape-frame
./ambiance --project projects/new-film render video --view portrait --out projects/new-film/render/portrait-video
```

`frame`, `proof` and `video` accept one `--view`. Frames and video default to that view's preferred dimensions. A named-view motion proof defaults to a 640-pixel long-edge ceiling. Explicit `--width/--height` overrides must preserve the selected aspect ratio with integer dimensions. No `--view` retains the previous full-stage behavior, including the 360-wide motion-proof default. Native video still requires macOS, even dimensions and the existing encode/decode checks. Pass `--revision ID --edition ID` to capture the rendered view identity and actual decoded dimensions. Composition inherits that view; `media verify --revision ID --edition ID` uses the recorded output expectations.

`views-proof` accepts repeated `--view` IDs and an integer `--long-edge` ceiling. At 640, the standard outputs are 360 × 640 and 640 × 360. At 639, they become 351 × 624 and 624 × 351, preserving exact ratios. One stage is rendered per requested frame time; all output PNGs share those sample times. The page has one playback/seek clock. Disabled-layer, rig and look matrices remain separate operations.

The shared planner chooses a uniform internal stage scale sufficient for the most detailed output and the selected `--supersample 1/2/4`. It preserves integer stage dimensions and rejects a stage larger than 4096 per side before creating output. Lower resolution or supersampling when a magnified crop would exceed that limit; the renderer never silently reduces requested quality. Each output gets one final crop/resample of the finished stage, preserving lights, shadows and reflections in their source coordinates. Existing full-stage render and look-preview paths retain their previous geometry and pixels.

The saved `render-report.json` includes source/tool hashes, resolved view hashes, actual dimensions, the raster plan, shared sample times, per-frame PNG hashes, per-view loop endpoint/seam measurements, wall time and process peak memory. Paired proofs also record all-frame geometric checks and reduced-resolution painted-alpha checks before background fill. Alpha checks use at most 240 pixels on the long side and do not exceed the requested proof size. `review_needed` flags coverage problems; successful artifact generation is not artistic approval. Detailed frame evidence stays in the report, while CLI output provides its path and a compact result.

`preview --views-proof` verifies the saved page and every listed PNG before serving an immutable snapshot on localhost. It rejects changed frames, incomplete lists and paths outside the proof directory. The [moving fixture](../examples/views/README.md) exercises these commands without paid art.

## Produce and review both formats

Use [iteration v2](../templates/iteration-views.example.json) to produce every requested view/soundtrack combination in one resumable job. Each view encodes once, then composition reuses its compressed picture and selected PCM. The initial coordinator uses one encoder worker; paired previews and saved proofs share one scene clock.

```sh
./ambiance --project PROJECT iteration run plans/dual-iteration.json --by Codex
./ambiance --project PROJECT project latest
./ambiance --project PROJECT delivery handoff dual-review-01 --out PROJECT/reports/dual-handoff
```

See [the library contract](STUDIO-LIBRARY.md) for exact URLs, per-view posters, review readiness and feedback. Named picture reviews use `review draft GATE --revision ID --view ID`; edition reviews inherit their movie's view. No review verdict is copied between views.
