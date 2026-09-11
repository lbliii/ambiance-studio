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

## Moving paired proof

```sh
node examples/views/create_motion_fixture.mjs projects/paired-views-pilot
./ambiance --project projects/paired-views-pilot preview --port 8796
./ambiance preview --views-proof projects/paired-views-pilot/render/paired-proof --port 8797
```

This second fixture adds an attached two-cel hand, camera motion, a moving round body, a fixed foreground rim, lighting, shadow and reflection. The script creates local test artwork, applies the complete scene through CLI transactions, runs `project check`, and produces both views through `render views-proof`. It preserves the full-size output intentions while using a small authored stage for inexpensive interactive inspection. Choose a fresh destination.

The initial paired pilot generated sixteen 180 × 320 portrait frames and sixteen 320 × 180 landscape frames. Rendering and its reduced-resolution checks took 1.182 seconds with 193,560,576 bytes of peak process memory on the local Node Canvas runtime. This small fixture is not a performance estimate for production artwork or full-HD finishing.

The agent inspected frame 0 in the editor and frame 4 in the saved proof: the subject stayed round, its changed hand cel remained attached, the rim stayed in front, and the reflection appeared in both views. Both panes reported frame 4 at 0.5 seconds after seeking and later frame 10 during shared playback. The browser's sixteen-frame stage and view checks passed with zero exposed frames. Automated raster tests compare every fixture frame against independently specified crops and inject a transparent defect visible only in portrait. These observations are separate from a human aesthetic or physical-phone review.

## Complete native production demo

```sh
python3 examples/views/produce_motion_fixture.py projects/dual-production-demo --long-edge 320
./ambiance studio register projects/dual-production-demo
./ambiance --project projects/dual-production-demo project latest
```

This CLI path creates a fresh local-art project, paired motion proof, captured revision and one version-2 iteration containing portrait/landscape × silent/score. The score is explicitly a quiet 220 Hz engineering test tone. Use `--long-edge 1920` for full preferred output sizes. Native encoding requires macOS media services. Re-run the saved `plans/iteration.json` through `iteration run` to verify/resume outputs; the fixture creator itself always requires a fresh project directory.
