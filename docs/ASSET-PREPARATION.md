# Raster preflight, crop and registered return

For interactive separation of one moving part and its fixed foreground, use the [preparation workbench](PREPARATION-WORKBENCH.md). It keeps removal and cutout masks distinct, uses this module's affine resampler, and exports source-mapped derivatives with compiler recipes.

These helpers produce local derivatives and measured facts. They never call an image provider, infer a clean matte from an alpha channel, or replace accepted source art. Every output directory must be new.

```sh
./ambiance --project /path/to/project asset preflight /path/to/project/art/source.png --out /path/to/project/proofs/source-preflight
./ambiance --project /path/to/project asset crop /path/to/project/art/source.png --recipe /path/to/project/plans/crop.json --out /path/to/project/art/crop-v1
./ambiance --project /path/to/project asset return /path/to/project/art/returned-edit.png --mapping /path/to/project/plans/return-v1.json --out /path/to/project/art/registered-return-v1
```

Command input/output paths use the shell's current directory. New manifest file references use the **selected project root**, explicitly marked `path_base: "project"`; crop/return inputs and outputs must stay within that project. Results include `resolved_path` and `path_base` so the two conventions are visible. Compiler recipe input paths retain their existing recipe-relative convention.

## Preflight

`asset preflight` decodes the actual bytes and records format, width/height, original channel mode, alpha-channel presence, transparency metadata, decoded alpha range and transparent/partial/opaque pixel counts. It writes `light.png`, `dark.png`, `alpha.png` and `report.json` with source/output hashes. An RGB checkerboard has opaque pixels. An opaque RGBA image has an alpha channel but no transparency. Neither an alpha channel nor varying alpha certifies clean edges or acceptable artwork.

Previews preserve aspect ratio and have a maximum side of 1024 pixels. Facts and bounds are measured at full resolution. For an animated input, the report explicitly describes frame zero; crop/return requires a still image.

## Crop contract

A version-1 crop recipe requires native integer bounds and explicit export dimensions:

```json
{
  "version": 1,
  "crop_xyxy": [100, 240, 260, 360],
  "export_size": [640, 480],
  "resampling": "bicubic"
}
```

Bounds follow pixel-edge coordinates `[left, top, right, bottom]`, with right/bottom excluded. They must lie within the source. Export dimensions are positive integers up to 8192 per side. `nearest` and `bicubic` are supported; the default is bicubic. Resampling uses premultiplied color to avoid transparent-RGB halos.

Outputs include the enlarged `crop.png`, a byte-preserved recipe, `crop-manifest.json`, `source-mapping.json`, light/dark/alpha previews and a `return-template.json`. The manifest binds original and crop hashes/dimensions, the crop rectangle, export dimensions and the exact export-to-reference affine. The original file is untouched.

The template intentionally has no registration affine. An operator must inspect the returned art and author a mapping; equal dimensions do not establish unchanged landmark positions. This is an explicit data requirement, not another user approval step.

## Return contract

Copy the return template into a new authored mapping and supply its registration:

```json
{
  "format": "ambiance-asset-return",
  "version": 1,
  "path_base": "project",
  "crop_manifest": {
    "file": "art/crop-v1/crop-manifest.json",
    "sha256": "ACTUAL_MANIFEST_SHA256"
  },
  "expected_edit_size": [640, 480],
  "registration": {
    "edit_to_export": [1, 0, 0, 1, -8, 0],
    "note": "Inspected return shifted the stable edge eight export pixels right; shift it back."
  },
  "blend_mask": {"kind": "full"},
  "resampling": "bicubic"
}
```

Affine arrays use `[a,b,c,d,e,f]`: `x' = a*x + c*y + e`, `y' = b*x + d*y + f`. `edit_to_export` maps returned-image pixels into the original exported crop's coordinates. An identity affine is permitted when explicitly authored after inspection. If the return dimensions changed, update both `expected_edit_size` and the registration intentionally; the command does not silently resize an unexpected return. Singular or nonfinite transforms fail.

For a bounded repair, replace the mask declaration with:

```json
{"kind":"image", "file":"art/native-crop-mask.png", "sha256":"ACTUAL_MASK_SHA256"}
```

The mask must be an `L` grayscale image at **native crop** dimensions, where 0 excludes and 255 includes the repair. The effective patch alpha is returned alpha multiplied by the mask. `full` is an explicit all-white mask. There is no inferred segmentation or automatic checkerboard removal.

The registered `patch.png` has native crop dimensions; `composite.png` places it over a copy of the original source at its recorded origin using source-over alpha compositing. Pixels outside the crop remain unchanged. Transparent returned pixels reveal the original; they do not erase it. The command also saves the effective mask, recipe snapshot, `source-mapping.json`, previews and a report. It validates the original, exported crop, crop manifest, mask and return identities before promotion. Occupied outputs and changed inputs fail.

Nearest-neighbor integer-grid round trips can be pixel-exact. Bicubic registration intentionally resamples, so its result is a derivative rather than a promise of identical source bytes. Registration can move content outside the bounded crop; inspect the alpha/context proofs for clipping or uncovered areas.

## Source mapping and compiler registration

Both crop and return emit `ambiance-asset-source-mapping` version 1:

```json
{
  "format": "ambiance-asset-source-mapping",
  "version": 1,
  "path_base": "project",
  "reference": {"file":"art/source.png", "sha256":"...", "width":941, "height":1672},
  "image": {"file":"art/registered-return-v1/patch.png", "sha256":"...", "width":160, "height":120},
  "image_to_reference": [1,0,0,1,100,240],
  "native_crop_xyxy": [100,240,260,360],
  "export_size": [640,480],
  "registration": {},
  "resampling": "bicubic"
}
```

Crop mappings scale export pixels back into reference pixels; returned native patches normally use unit scale plus crop origin. A returned mapping also records the edited-image identity, authored `edit_to_export`, composed `edit_to_reference`, crop-manifest identity, authored recipe identity and optional external mask identity. These are explicit dependency records for revision capture, not filenames to infer from arbitrary text.

To compile that exact mapped image, add this optional field to the existing compiler recipe:

```json
"source_mapping": {"file":"../registered-return-v1/source-mapping.json", "sha256":"ACTUAL_MAPPING_SHA256"}
```

This reference is **recipe-relative**. Mapped compilation currently accepts a single input image and requires an `ambiance-project.json` ancestor of the recipe to resolve the mapping's project-relative identities. It validates the reference and exact compiler input image hashes/dimensions. A mapped multi-cell source sheet can carry registration metadata, but native scene placement may require a one-cell cutout. Generated character size still needs explicit authored intent.

Every newly compiled asset now includes `registration_mapping` version 1 in both `asset.json` and `report.json`:

- `input_sources`: ordered original image files, hashes and decoded dimensions; `input_path_base` is `recipe`.
- `cell_size`, `shared_scale`, `padding`: actual compiler geometry, using its single shared sequence scale.
- `cels`: `source_index`, whole-input `source_rect`, raw cel `source_pivot`, `raw_cel_to_cell` and `source_to_cell`.
- For mapped inputs, `reference` with `reference_path_base: "project"`, `source_mapping` identity and per-cel `reference_to_cell`.

`raw_cel_to_cell` maps coordinates inside an extracted grid cell or frame image into its padded output cell. `source_to_cell` maps the **whole original input image** into that cell, accounting for a grid cell's origin. `reference_to_cell = source_to_cell × inverse(image_to_reference)`. Placement can therefore compose real crop scale, registration, sequence scale and padding rather than reconstructing them from alpha bounds. The compiler's raw preparation remains the authority; these matrices do not move scene objects by themselves.

Existing accepted packs are unchanged. A new compiler version changes the build key; use a new output directory for rebuilding old inputs. Named landmark registration and explicit pivots remain supported. See the [rig workbench](RIG-WORKBENCH.md) and [runnable independent example](../examples/asset-preparation/README.md).
