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
    source_start_frame : job.startFrame,
    source_end_frame_exclusive : job.startFrame===null?null:job.startFrame+frames,
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
    rgba_endpoint_exact : raster.endpointExact,
    picture_clock : job.compiled.clock.frame(job.compiled.clock.duration_frames),
    endpoint_policy : job.compiled.clock.mode==='finite'?'Authored endpoint N is inspection-only; exported samples are [0,N)':'Loop endpoint closes frame zero; exported samples are [0,N)',
    last_exported_to_endpoint : raster.lastToEndpoint,
    clock_engine_sha256 : sha(await fs.readFile(path.join(root,'editor/clock.mjs'))),
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

// Supplemental proof files share the receipt's immutable, artifact-relative
// identity contract. Callers provide bytes from the measured raster itself.
export async function saveProofArtifact(out, file, bytes) {
  const target = path.resolve(out, file);
  if (path.isAbsolute(file) || path.relative(out, target).startsWith('..') ||
      target === path.resolve(out) || file.split('/').includes('..'))
    throw Error('Proof artifact path escapes its directory');
  await fs.mkdir(path.dirname(target), {recursive : true});
  await fs.writeFile(target, bytes, {flag : 'wx'});
  return {file, sha256 : sha(bytes), path_base : 'artifact-relative'};
}

export function alphaDiagnosticIdentity(report) {
  return Object.fromEntries([
    'scene_sha256', 'catalog_sha256', 'source_assets', 'engine_version', 'engine_sha256',
    'bindings_engine_sha256', 'finishing_engine_sha256', 'views_module_sha256',
    'stage_adapter_sha256', 'audit_module_sha256', 'renderer_sha256', 'renderer_sources',
    'canvas_module', 'canvas_version', 'node_version', 'platform'
  ].map(key => [key, report[key]]));
}
