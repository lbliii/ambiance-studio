# Saved output views

Saved views define portrait and landscape framing in one scene without changing its artwork, layer geometry, camera, rigs or clock. This first implementation provides project setup, view authoring and geometric checks. Rendering still exports the full authored canvas; named-view output and synchronized proofs are the next milestone.

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

The workbench displays the authored canvas at its actual aspect ratio. Existing full-canvas renders and look previews preserve their old geometry when internally downscaled or supersampled; framing metadata scales within the private runtime copy. The saved source is unchanged. Until named-view rendering lands, use these views for planning and geometric inspection, and keep full-stage proofs labeled as such.
