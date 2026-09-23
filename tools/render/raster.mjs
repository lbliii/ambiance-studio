import {drawScene} from '../../editor/engine.mjs';
import {createStageRenderer} from '../../editor/stage-raster.mjs';

function difference(a, b) {
  let sum = 0, max = 0;
  for (let i = 0; i < a.length; i++)
    if (i % 4 !== 3) {
      const d = Math.abs(a[i] - b[i]);
      sum += d;
      max = Math.max(max, d);
    }
  return {rgb_mean_absolute_difference : sum / (a.length / 4 * 3), rgb_max_difference : max};
}

export function prepareRaster(job) {
  const {
    scene,
    catalog,
    viewPlan,
    width,
    height,
    supersample,
    internalWidth,
    internalHeight,
    compiled,
    fps,
    loopFrames,
    disable,
    alternate,
    alternateCompiled,
    images,
    runtime
  } = job;
  const stageRenderer =
      viewPlan ? createStageRenderer(scene, catalog, images, viewPlan, runtime.createCanvas) : null;
  const alternateRenderer =
      viewPlan && disable.length
          ? createStageRenderer(alternate, catalog, images, viewPlan, runtime.createCanvas)
          : null;
  const canvas = stageRenderer?.outputs.get(viewPlan.views[0].view.id) ??
                 runtime.createCanvas(width, height),
        internalCanvas =
            stageRenderer?.stage ??
            (supersample === 1 ? canvas : runtime.createCanvas(internalWidth, internalHeight));
  const finishingDiagnostics = [];
  const render = (time, off = false) => {
    if (stageRenderer) {
      const active = off ? alternateRenderer : stageRenderer;
      active.render(time);
      if (active.stage.finishingReport)
        finishingDiagnostics.push(
            {...active.stage.finishingReport, time_seconds : typeof time==='number'?time:time.seconds, disabled_variant : off});
      if (off) {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, width, height);
        ctx.drawImage(active.outputs.values().next().value, 0, 0);
      }
      return;
    }
    drawScene(internalCanvas, off ? alternate : scene, catalog, images, time, {
      sampler : off ? alternateCompiled.sample : compiled.sample,
      createCanvas : runtime.createCanvas
    });
    if (internalCanvas.finishingReport)
      finishingDiagnostics.push(
          {...internalCanvas.finishingReport, time_seconds : typeof time==='number'?time:time.seconds, disabled_variant : off});
    if (supersample !== 1) {
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, width, height);
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = 'high';
      ctx.drawImage(internalCanvas, 0, 0, width, height);
    }
  };
  const endpoints = new Map();
  render(0);
  const first = Buffer.from(canvas.data());
  if (stageRenderer)
    for (const [id, c] of stageRenderer.outputs)
      endpoints.set(id, {first : Buffer.from(c.data())});
  render(scene.canvas.loop_seconds);
  const endpoint = Buffer.from(canvas.data());
  if (stageRenderer)
    for (const [id, c] of stageRenderer.outputs) {
      const row = endpoints.get(id);
      row.rgba_endpoint_exact = row.first.equals(c.data());
      row.endpoint_difference = difference(row.first, c.data());
      if (compiled.clock.mode==='loop'&&!row.rgba_endpoint_exact)
        throw Error('Raster endpoint differs for view ' + id);
    }
  const endpointDifference = difference(first, endpoint);
  if (compiled.clock.mode==='loop'&&!first.equals(endpoint))
    throw Error('Raster endpoint differs from frame zero');
  render(compiled.clock.frame(loopFrames-1));
  const lastToEndpoint=difference(canvas.data(),endpoint);
  const seam = difference(first, canvas.data());
  if (stageRenderer)
    for (const [id, c] of stageRenderer.outputs)
      endpoints.get(id).last_to_first = difference(endpoints.get(id).first, c.data());
  const renderFrame=(frame,off=false)=>render(compiled.clock.frame(frame),off);
  return {stageRenderer,canvas,render,renderFrame,finishingDiagnostics,endpoints,endpointDifference,seam,lastToEndpoint,endpointExact:first.equals(endpoint)};
}
