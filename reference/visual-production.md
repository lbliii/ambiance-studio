# The Last Lantern — version 2

This version separates the scene into painted depth layers and adds actual image sequences. Clouds pass in front of the moon, the hilltop town changes its window lights, chimney smoke changes shape, and the cottage windows contain changing flames and curtain shadows.

## Video

- `the-last-lantern.mp4`: 16 seconds, 1080 × 1920, 30 fps, H.264, with the original woodland ambience.
- `the-last-lantern-silent.mp4`: the same revised animation without sound.
- `the-last-lantern-cover.jpg`: a clean portrait cover.

## Layers and animation

The scene contains separate sky, moon, cloud passes, far hills, town/hill, woodland, cottage, ground, woodland frame, and branch layers. Their relative motion supplies depth. The cottage and doorstep share a camera transform to keep the building grounded. Near foliage moves farther than the distant landscape.

The changing artwork is stored in real sprite sheets. The renderer selects rectangular cells from those sheets; the smoke, clouds, and cottage details change drawings as the video plays. Leaves and branch motion still use transforms and paths.

| Sheet | Layout | Cell size | Frames | Playback in scene |
| --- | --- | --- | --- | --- |
| cloud-cels.png | 4 × 2 | 512 × 192 | 8 | 2 fps; 4-second cycle |
| smoke-cels.png | 4 × 3 | 192 × 384 | 12 | 6 fps; 2-second cycle |
| flame-cels.png | 4 × 2 | 128 × 192 | 8 | Incorporated into the cottage cels |
| window-cels.png | 4 × 3 | 260 × 222 | 12 | 6 fps; 2-second cycle |
| cottage-cels.png | 4 × 3 | 704 × 704 | 12 | 6 fps; 2-second cycle |
| town-window-cels.png | 4 × 4 | 432 × 192 | 16 | 2 fps; 8-second cycle |

Frames read left to right, then top to bottom. Each sheet uses fixed cell dimensions. Scale and vertical baselines are normalized across each sequence. The frame viewer plays the standalone flame study at 8 fps; in the scene, those poses are incorporated into the 12 cottage cels.

Clouds, smoke, and flames began as generated painted frame sheets. Cottage and window cels combine the original architecture, generated flame poses, and authored curtain/shadow drawings. Town cels isolate and vary window illumination. These are composited frame sequences, rather than independently regenerating the entire building for every frame.

The moon and hills stay rigid painted plates. Frame sets are most useful for changing shapes and internal detail; the depth layers and their movement are a separate part of the animation design.

## Loop and checks

All cycle durations divide the 16-second master loop. The frame at exactly 16 seconds reproduces frame zero pixel for pixel before compression. The video exports frames 0–479, without a duplicated endpoint. Both MP4 files are decoded completely during validation. The frame viewer was checked for playback, asset selection, and manual scrubbing at desktop and phone widths.

See `source/validation.json` for measured results and `source/animation.json` for the sheet manifest. `animation-cels.zip` contains the sprite sheets and manifest.

## Rebuild

The original artwork, intermediate painted plates, registered layers, exact prompts, and macOS source are retained in `source`. `build-assets.m` builds the mattes and registered cel sheets. `render-v2.m` composites and encodes the video through Core Graphics and AVFoundation. The soundtrack is reused from the first version.

From the original workspace directory:

```sh
clang -O2 -fobjc-arc -framework Cocoa -framework ImageIO \
  outputs/v2/source/build-assets.m -o work/v2/build-assets
./work/v2/build-assets
clang -O2 -fobjc-arc -Wno-deprecated-declarations -Wno-incompatible-pointer-types \
  -framework Cocoa -framework AVFoundation -framework CoreVideo \
  -framework CoreMedia -framework ImageIO outputs/v2/source/render-v2.m -o work/v2/render
./work/v2/render --preview
./work/v2/render --render
./work/v2/render --mux
./work/v2/render --verify
```

Use a fresh workspace copy for re-encoding; existing video files are protected from overwrite. The macOS media encoder requires access to native media services.
