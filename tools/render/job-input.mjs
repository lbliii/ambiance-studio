import fs from 'node:fs/promises';
import path from 'node:path';

import {compileScene} from '../../editor/engine.mjs';
import {secondsToFrames} from '../../editor/clock.mjs';
import {finishingAssetIds} from '../../editor/finishing.mjs';
import {planViews, resizeSceneCanvas} from '../../editor/views.mjs';
import {prepareLookProof} from '../look-proof.mjs';
import {prepareRigProof} from '../rig-proof.mjs';

import {root, sha} from './source-identity.mjs';

function finite(value, name) {
  if (!Number.isFinite(value))
    throw Error(`${name} must be finite`);
  return value;
}

export async function prepareJob(request, runtime) {
  const project = await fs.realpath(request.project), out = path.resolve(request.out);
  const inside = async relative => {
    const resolved = await fs.realpath(path.resolve(project, relative));
    if (resolved !== project && !resolved.startsWith(project + path.sep))
      throw Error(`Project input must stay inside project: ${relative}`);
    return resolved;
  };
  let scenePath, catalogPath;
  if (request.scene_path || request.catalog_path) {
    if (!request.scene_path || !request.catalog_path)
      throw Error('Both explicit scene and catalog are required');
    scenePath = await inside(request.scene_path);
    catalogPath = await inside(request.catalog_path);
  } else {
    const config =
        JSON.parse(await fs.readFile(path.join(project, 'ambiance-project.json'), 'utf8'));
    if (config.version !== 1)
      throw Error('Unsupported project configuration version');
    scenePath = await inside(config.scene);
    catalogPath = await inside(config.catalog);
  }
  const [sceneBytes, catalogBytes, engineBytes] = await Promise.all([
    fs.readFile(scenePath), fs.readFile(catalogPath),
    fs.readFile(path.join(root, 'editor/engine.mjs'))
  ]);
  const scene = JSON.parse(sceneBytes), catalog = JSON.parse(catalogBytes),
        sourceCanvas = structuredClone(scene.canvas);
  if (request.expected_scene_sha256 && sha(sceneBytes) !== request.expected_scene_sha256 ||
      request.expected_catalog_sha256 && sha(catalogBytes) !== request.expected_catalog_sha256)
    throw Error('Scene or catalog changed after view preflight; rerun the render');
  const viewPlan = request.views ? planViews(scene, request.views, request.view_options) : null;
  const width = viewPlan?.views[0].output.width ?? request.width ?? sourceCanvas.width,
        height = viewPlan?.views[0].output.height ?? request.height ??
                 width * sourceCanvas.height / sourceCanvas.width;
  if (!Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 1 ||
      (!viewPlan && width * sourceCanvas.height !== height * sourceCanvas.width))
    throw Error(
        'Render dimensions must be positive integers preserving the authored aspect ratio.');
  const supersample = viewPlan?.supersample ?? request.supersample ?? 1;
  if (![1, 2, 4].includes(supersample) || width * supersample > 4096 || height * supersample > 4096)
    throw Error('Supersampling requires scale 1, 2, or 4 and internal dimensions <=4096');
  const internalWidth = viewPlan?.internal_canvas.width ?? width * supersample,
        internalHeight = viewPlan?.internal_canvas.height ?? height * supersample;
  if (!viewPlan)
    resizeSceneCanvas(scene, internalWidth, internalHeight);
  const compiled = compileScene(scene, catalog), fps = scene.canvas.fps,
        loopFrames = compiled.clock.duration_frames;
  if (!scene.layers.length)
    throw Error('Cannot render an empty scene');
  let start = finite(request.start ?? 0, 'start'), startFrame = request.start_frame ?? null;
  if(startFrame!==null){
    if(!Number.isSafeInteger(startFrame)||startFrame<0)throw Error('Source start frame must be a safe nonnegative integer');
    if(request.start!==undefined&&request.start!==startFrame/fps)throw Error('Source start frame and seconds mirror disagree');
    start=startFrame/fps;
  }
  if (start < 0)
    throw Error('start must be nonnegative');
  const mode = request.mode;
  if (!['frame', 'proof', 'rig-proof', 'look-proof', 'video', 'views-proof', 'benchmark'].includes(
          mode))
    throw Error('Unknown render mode');
  if (mode === 'views-proof' && !viewPlan)
    throw Error('Paired proof requires explicit views');
  if (viewPlan && [ 'rig-proof', 'look-proof' ].includes(mode))
    throw Error('Named views cannot be combined with rig/look matrices');
  if (viewPlan && mode !== 'views-proof' && viewPlan.views.length !== 1)
    throw Error('Select one view for a single-output render');
  if (mode === 'rig-proof' && supersample !== 1)
    throw Error(
        'Rig-proof matrix uses fixed resolution; supersampling is supported for frame, proof, look-proof and video');
  const finiteRange=compiled.clock.mode==='finite'&&['video','proof','views-proof'].includes(mode);
  if(finiteRange&&startFrame===null)startFrame=secondsToFrames(start,compiled.clock.fps).value;
  const remaining=finiteRange?loopFrames-startFrame:loopFrames;
  const defaultFrames=['proof','views-proof'].includes(mode)?Math.min(3*fps,remaining):remaining;
  const defaultSeconds=finiteRange?defaultFrames/fps:
      ['proof','views-proof'].includes(mode)?Math.min(3,scene.canvas.loop_seconds):scene.canvas.loop_seconds;
  const seconds=finite(request.seconds??(request.frame_count===undefined?defaultSeconds:request.frame_count/fps),'seconds');
  const frames = mode === 'frame' ? 1 : request.frame_count ?? (request.seconds===undefined&&(finiteRange||scene.clock)?defaultFrames:seconds*fps);
  if(request.frame_count!==undefined&&seconds!==frames/fps)throw Error('Source frame count and seconds mirror disagree');
  if (!Number.isInteger(frames) || frames < 1 || frames > loopFrames)
    throw Error('Duration must contain an integer frame count within one scene loop');
  if(finiteRange){
    if(startFrame+frames>loopFrames)throw Error('Finite render range must stay within [0,N); endpoint inspection is frame-only');
    if(mode==='video'&&(request.repeats??1)!==1)throw Error('Finite video cannot repeat the shot');
  }
  if (mode === 'video' && (width % 2 || height % 2))
    throw Error('Native H.264 dimensions must be even');
  const disable = request.disable ?? [];
  if (!Array.isArray(disable) || disable.some(id => !scene.layers.some(l => l.id === id)))
    throw Error('Every disabled layer must exist in this scene');
  if (mode === 'views-proof' && disable.length)
    throw Error('Paired proofs cannot add disabled-layer variants');
  const alternate = structuredClone(scene);
  for (const layer of alternate.layers)
    if (disable.includes(layer.id)) {
      layer.visible = false;
      if (layer.tracks?.visible)
        layer.tracks.visible = {
          interpolation : 'hold',
          keys : [ [ 0, false ], [ layer.tracks.visible.keys.at(-1)[0], false ] ]
        };
    }
  const alternateCompiled = compileScene(alternate, catalog);
  const rigPlan = mode === 'rig-proof' ? prepareRigProof(request.rig_recipe, scene, catalog) : null;
  const lookPlan =
      mode === 'look-proof' ? prepareLookProof(request.look_recipe, scene, catalog) : null;
  const images = new Map(), assetBytes = new Map(), assetHashes = [],
        used = new Set([
          ...scene.layers.map(l => l.asset), ...finishingAssetIds(scene),
          ...(lookPlan ? lookPlan.variants.flatMap(v => finishingAssetIds(v.scene)) : [])
        ]);
  for (const asset of catalog.assets.filter(a => used.has(a.id))) {
    const assetPath = await inside(asset.file), bytes = await fs.readFile(assetPath),
          hash = sha(bytes);
    if (hash !== asset.sha256)
      throw Error(`Asset hash does not match catalog: ${asset.id}`);
    let decoded;
    try {
      decoded = await runtime.loadImage(bytes);
    } catch (error) {
      throw Error(`Cannot decode asset ${asset.id} (${asset.file}): ${error.message}`);
    }
    if (decoded.width !== asset.width || decoded.height !== asset.height)
      throw Error(`Asset dimensions do not match catalog: ${asset.id}`);
    images.set(asset.id, decoded);
    assetBytes.set(asset.id, bytes);
    assetHashes.push({id : asset.id, file : asset.file, sha256 : hash});
  }
  return {
    request,
    runtime,
    project,
    out,
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
    internalWidth,
    internalHeight,
    compiled,
    fps,
    loopFrames,
    start,
    startFrame,
    mode,
    frames,
    disable,
    alternate,
    alternateCompiled,
    rigPlan,
    lookPlan,
    images,
    assetBytes,
    assetHashes
  };
}
