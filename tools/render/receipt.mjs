import fs from 'node:fs/promises';
import path from 'node:path';

import {ENGINE_VERSION} from '../../editor/engine.mjs';
import {canonicalView} from '../../editor/views.mjs';

import {rendererSources, root, sha} from './source-identity.mjs';

export async function renderReceipt(job, raster) {
  const {
    scenePath,
    catalogPath,
    sceneBytes,
    catalogBytes,
    engineBytes,
    scene,
    catalog,
    sourceCanvas,
    viewPlan,
    width,
    height,
    supersample,
    fps,
    start,
    mode,
    frames,
    rigPlan,
    assetHashes,
    runtime
  } = job;
  const {endpoints, endpointDifference, seam} = raster;
  const report = {
    ok : true,
    mode,
    scene : scenePath,
    scene_sha256 : sha(sceneBytes),
    catalog : catalogPath,
    catalog_sha256 : sha(catalogBytes),
    engine_version : ENGINE_VERSION,
    engine_sha256 : sha(engineBytes),
    source_canvas : sourceCanvas,
    render_canvas : {...scene.canvas, width, height},
    internal_canvas : structuredClone(scene.canvas),
    supersample,
    downsample : supersample === 1 ? null : {
      passes : 1,
      filter : 'Canvas high-quality image smoothing',
      alpha : 'Canvas premultiplied interpolation',
      stage : 'after complete scene render; before PNG or native encoder'
    },
    bindings_engine_sha256 : sha(await fs.readFile(path.join(root, 'editor/bindings.mjs'))),
    finishing_engine_sha256 : sha(await fs.readFile(path.join(root, 'editor/finishing.mjs'))),
    views_module_sha256 : sha(await fs.readFile(path.join(root, 'editor/views.mjs'))),
    start_seconds : start,
    frames,
    seconds : frames / fps,
    source_assets : assetHashes,
    canvas_module : runtime.module,
    canvas_version : runtime.version,
    node_version : process.version,
    platform : process.platform,
    renderer_sha256 : sha(await fs.readFile(path.join(root, 'tools/render-scene.mjs'))),
    rig_proof_renderer_sha256 :
        rigPlan ? sha(await fs.readFile(path.join(root, 'tools/rig-proof.mjs'))) : null,
    rgba_endpoint_exact : true,
    endpoint_difference : endpointDifference,
    last_to_first : seam,
    visual_review_performed : false
  };
  if (viewPlan) {
    report.raster_plan = viewPlan;
    report.internal_canvas = {...sourceCanvas, ...viewPlan.internal_canvas};
    report.stage_adapter_sha256 =
        sha(await fs.readFile(path.join(root, 'editor/stage-raster.mjs')));
    report.extraction = {
      passes : 1,
      filter : 'Canvas high-quality image smoothing',
      stage : 'after complete finished stage; before PNG or native encoder'
    };
    report.downsample = null;
    report.views = Object.fromEntries(viewPlan.views.map(v => {
      const {first, ...measurements} = endpoints.get(v.view.id);
      return [ v.view.id, {...v, view_sha256 : sha(canonicalView(v.view)), ...measurements} ];
    }));
    if (mode === 'views-proof') {
      report.render_canvas = null;
      report.views_proof_renderer_sha256 =
          sha(await fs.readFile(path.join(root, 'tools/views-proof.mjs')));
    } else
      report.view = report.views[viewPlan.views[0].view.id];
  }
  report.renderer_sources = await rendererSources();
  return report;
}
