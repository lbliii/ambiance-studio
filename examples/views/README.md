# Saved-view fixture

This pilot uses locally drawn grid and circle artwork to exercise the saved-view foundation without a generation provider. It requires the normal studio dependencies, including Pillow and the Node Canvas runtime for its frame render. Choose a new destination:

```sh
python3 examples/views/create_fixture.py projects/view-foundation-pilot
./ambiance --project projects/view-foundation-pilot view inspect
./ambiance --project projects/view-foundation-pilot preview --port 8794
```

The script initializes a square stage, applies animated artwork through a scene transaction, checks portrait and landscape coverage at every frame, and saves a full-stage frame. Reports are in `reports/views.json` and `reports/project.json`; the authored frame is in `render/authored-frame/frame.png`. The script refuses an existing destination.

Open the editor at `/editor/`, inspect the circle at frames 0 and 30, and run **Check all frames**. The canvas should be square and the circle should stay round. These are checks of the shared stage; this milestone does not render the named portrait or landscape outputs. Paired raster proofs are milestone 2 in the [implementation plan](../../docs/architecture/DUAL-FORMAT-IMPLEMENTATION.md).

The September 11, 2026 agent-operated pilot passed both CLI view checks and the browser's 480-frame check with zero exposed-canvas frames. The agent visually inspected frames 0 and 30 and the saved PNG; the square grid and round subject retained their proportions. This is geometric fixture evidence, not a human film or phone review.
