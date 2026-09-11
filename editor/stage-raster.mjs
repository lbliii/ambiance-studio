// Shared by browser and Node: finish the whole stage, then extract each view.
import {compileScene, drawScene} from './engine.mjs';
import {resizeSceneCanvas} from './views.mjs';

export function extractView(stage, target, resolved) {
  const {width, height} = resolved.output;
  if (target.width !== width) target.width = width;
  if (target.height !== height) target.height = height;
  const ctx = target.getContext('2d');
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
  ctx.clearRect(0, 0, width, height);
  ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high';
  const scale = width / resolved.source_rect_px[2];
  ctx.drawImage(stage, ...resolved.source_rect_px, 0, 0, width, resolved.source_rect_px[3] * scale);
  return target;
}

// Coverage deliberately omits the background fill, which would hide art holes.
// Finishing alters receiving colors, not the underlying painted layer alpha.
function drawCoverage(canvas, states, images) {
  const ctx = canvas.getContext('2d');
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  for (const state of states) {
    if (!state.visible) continue;
    ctx.setTransform(...state.matrix); ctx.globalAlpha = state.opacity; ctx.globalCompositeOperation = state.blend;
    ctx.drawImage(images.get(state.asset), ...state.source, ...state.rect);
  }
}

export function createStageRenderer(source, catalog, images, plan, createCanvas) {
  const scene = structuredClone(source);
  resizeSceneCanvas(scene, plan.internal_canvas.width, plan.internal_canvas.height);
  const compiled = compileScene(scene, catalog);
  const stage = createCanvas(plan.internal_canvas.width, plan.internal_canvas.height);
  const outputs = new Map(plan.views.map(v => [v.view.id, createCanvas(v.output.width, v.output.height)]));
  function render(time, {coverage = false} = {}) {
    const states = coverage ? compiled.sample(time) : drawScene(stage, scene, catalog, images, time, {sampler: compiled.sample, createCanvas});
    if (coverage) drawCoverage(stage, states.filter(s => !(scene.finishing?.illuminations || []).some(e => e.layer === s.id)), images);
    for (const view of plan.views) extractView(stage, outputs.get(view.view.id), view);
    return {stage, outputs, states};
  }
  return {scene, stage, outputs, render};
}
