import {compileScene, drawScene} from './engine.mjs';

const el = id => document.getElementById(id);
const clone = value => structuredClone(value);
const makeCanvas = (width, height) => Object.assign(document.createElement('canvas'), {width, height});
const maskHelp = {
  cutout: 'Keep only paint that should move. Exclude fixed rails, rims, and neighboring objects.',
  removal: 'Replace the old object and its remnants with backing paint. This region may be wider than the cutout.',
  occluder: 'Keep foreground paint fixed above the moving object, such as a rail or a vase lip.',
};

export function polygonPoint(x, y, rect, width, height) {
  return [Math.max(0, Math.min(width-1, (x-rect.left)/rect.width*width)),
    Math.max(0, Math.min(height-1, (y-rect.top)/rect.height*height))].map(n => Math.round(n*100)/100);
}

export function inspectionScene(scene, hideObject, hideForeground) {
  const result = clone(scene);
  for (const layer of result.layers) {
    if ((layer.id === 'cutout' && hideObject) || (layer.id === 'occluder' && hideForeground)) layer.visible = false;
  }
  return result;
}

async function decodeImages(urls) {
  const entries = await Promise.all(Object.entries(urls).map(async ([name, url]) => {
    const image = new Image(); image.src = url; await image.decode(); return [name, image];
  }));
  return new Map(entries);
}

async function boot() {
  const response = await fetch('workbench.json');
  if (!response.ok) throw Error('Saved workbench is unavailable');
  const saved = await response.json();
  let recipe = clone(saved.recipe), result = saved, images;
  let points = [], history = [], busy = false, frame = 0, clock = 0, playing = false;
  let lastTick = performance.now(), lastPaint = 0, observedFps = 0, skipped = 0, compiled;
  const names = ['source', 'registered-backing', 'backing', 'cutout', 'occluder', 'rest',
    'difference', 'removal-mask', 'cutout-mask', 'occluder-mask'];
  images = await decodeImages(Object.fromEntries(names.map(name => [name, `images/${name}.png`])));
  const W = recipe.source.width, H = recipe.source.height;
  for (const name of ['source', 'candidate']) { el(name).width = W; el(name).height = H; }
  el('dimensions').textContent = `${W} × ${H}`;
  const message = (text, error = false) => { el('message').textContent = text; el('message').className = error ? 'error' : ''; };
  const stop = () => { playing = false; el('play').textContent = 'Play'; };
  function setBusy(value) {
    busy = value;
    for (const id of ['editing', 'download', 'apply-recipe', 'reset']) el(id).disabled = value;
    el('saved-state').textContent = value ? 'Calculating preview…' : history.length ? 'Unsaved browser draft' : 'Captured recipe';
    document.documentElement.dataset.preparationBusy = String(value);
  }
  function recompile() {
    const scene = inspectionScene(result.scene, el('hide-object').checked, el('hide-foreground').checked);
    compiled = compileScene(scene, result.catalog);
  }
  function sourceView() {
    const canvas = el('source'), ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, W, H); ctx.drawImage(images.get('source'), 0, 0);
    const mask = images.get(el('mask').value+'-mask');
    const tint = makeCanvas(W, H), tc = tint.getContext('2d');
    tc.drawImage(mask, 0, 0);
    const data = tc.getImageData(0, 0, W, H);
    for (let i = 0; i < data.data.length; i += 4) {
      const alpha = data.data[i]*.38;
      data.data[i] = 241; data.data[i+1] = 115; data.data[i+2] = 153; data.data[i+3] = alpha;
    }
    tc.putImageData(data, 0, 0); ctx.drawImage(tint, 0, 0);
    if (points.length) {
      ctx.strokeStyle = '#eef09d'; ctx.fillStyle = '#eef09d'; ctx.lineWidth = Math.max(1, W/240);
      ctx.beginPath(); points.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.stroke();
      for (const [x, y] of points) { ctx.beginPath(); ctx.arc(x, y, Math.max(2, W/170), 0, Math.PI*2); ctx.fill(); }
    }
    el('mask-help').textContent = maskHelp[el('mask').value];
    const spec = recipe.masks[el('mask').value];
    el('points-info').textContent = `${points.length} pending vertices · ${spec.polygons.length} applied polygons${spec.image ? ' · imported base mask' : ''}`;
    el('close-polygon').disabled = points.length < 3;
    el('undo-point').disabled = !points.length;
    el('cancel-polygon').disabled = !points.length;
    el('undo').disabled = !history.length;
  }
  function drawCandidate() {
    const canvas = el('candidate'), context = canvas.getContext('2d'), mode = el('inspection').value;
    if (mode === 'context') {
      drawScene(canvas, compiled.scene, result.catalog, images, frame/30, {sampler: compiled.sample, createCanvas: makeCanvas});
    } else { context.clearRect(0, 0, W, H); context.drawImage(images.get(mode), 0, 0); }
    el('candidate-label').textContent = el('inspection').selectedOptions[0].textContent;
    el('seek').value = frame;
    el('time').textContent = `${(frame/30).toFixed(2)} s`;
    el('playback-info').textContent = `Shared scene renderer · frame ${frame} of ${Math.round(recipe.motion.seconds*30)} · 30 fps authored${observedFps ? ` · ${observedFps.toFixed(0)} fps observed` : ''} · ${skipped} preview frames skipped. Seek for individual-frame inspection.`;
  }
  function inputGrid(id, fields) {
    const parent = el(id); parent.replaceChildren();
    for (const [key, label, value] of fields) {
      const row = document.createElement('label'); row.textContent = label;
      const input = document.createElement('input'); input.type = 'number'; input.step = 'any';
      input.value = value; input.id = key; input.setAttribute('aria-label', label); row.append(input); parent.append(row);
    }
  }
  function controls() {
    inputGrid('alignment', recipe.backing_to_source.map((v, i) => [`affine-${i}`, ['Scale X (a)', 'Shear Y (b)', 'Shear X (c)', 'Scale Y (d)', 'Offset X (px)', 'Offset Y (px)'][i], v]));
    inputGrid('motion', [['pivot-x', 'Pivot X (px)', recipe.motion.pivot[0]], ['pivot-y', 'Pivot Y (px)', recipe.motion.pivot[1]],
      ['move-x', 'Travel X (px)', recipe.motion.delta[0]], ['move-y', 'Travel Y (px)', recipe.motion.delta[1]],
      ['rotate', 'Rotation (°)', recipe.motion.rotation_degrees], ['seconds', 'Loop (seconds)', recipe.motion.seconds]]);
  }
  function refresh() {
    el('title').textContent = recipe.title;
    el('recipe').value = JSON.stringify(recipe, null, 2);
    el('export-recipe').value = JSON.stringify(recipe);
    el('seek').max = Math.round(recipe.motion.seconds*30)-1;
    clock = Math.min(clock, recipe.motion.seconds-1/30); frame = Math.floor(clock*30);
    const facts = result.facts;
    el('changed-count').textContent = facts.changed_rest_pixels.toLocaleString();
    el('uncovered-count').textContent = facts.cutout_outside_removal_pixels.toLocaleString();
    el('missing-count').textContent = facts.removal_without_opaque_backing_pixels.toLocaleString();
    el('warnings').replaceChildren();
    for (const warning of result.warnings) { const li = document.createElement('li'); li.textContent = warning; el('warnings').append(li); }
    el('draft-label').textContent = history.length ? 'Current draft' : 'Saved recipe';
    recompile(); controls(); sourceView(); drawCandidate();
  }
  async function commit(candidate, mode = 'edit') {
    if (busy) return;
    stop(); setBusy(true); message('Calculating masks and alignment…');
    try {
      const response = await fetch('/api/preview', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(candidate)});
      const reply = await response.json();
      if (!response.ok || !reply.ok) throw Error(reply.error || 'Preview request failed');
      const nextImages = await decodeImages(reply.data.images);
      compileScene(reply.data.scene, reply.data.catalog);
      if (mode === 'undo') history.pop(); else if (mode === 'reset') history = []; else history.push(clone(recipe));
      recipe = reply.data.recipe; result = reply.data; images = nextImages; points = [];
      refresh(); message('Preview updated. Export the recipe to rebuild this version.');
    } catch (error) { message(`Rejected: ${error.message}. The last valid preview is retained.`, true); }
    finally { setBusy(false); }
  }
  function numeric(id) {
    const input = el(id);
    if (!input.value.trim() || !Number.isFinite(input.valueAsNumber)) throw Error('Supply a finite number for '+input.getAttribute('aria-label'));
    return input.valueAsNumber;
  }
  function change(mutator) {
    if (busy) return;
    try { const candidate = clone(recipe); mutator(candidate); return commit(candidate); }
    catch (error) { message(error.message, true); }
  }
  el('source').onpointerdown = event => {
    if (busy) return;
    if (points.length >= 512) { message('Close this polygon before adding more vertices.', true); return; }
    points.push(polygonPoint(event.clientX, event.clientY, el('source').getBoundingClientRect(), W, H)); sourceView();
  };
  el('mask').onchange = () => { points = []; sourceView(); };
  el('undo-point').onclick = () => { points.pop(); sourceView(); };
  el('cancel-polygon').onclick = () => { points = []; sourceView(); };
  el('close-polygon').onclick = () => change(candidate => candidate.masks[el('mask').value].polygons.push({operation: el('operation').value, points: clone(points)}));
  el('clear-mask').onclick = () => change(candidate => { candidate.masks[el('mask').value].polygons = []; });
  el('undo').onclick = () => { if (history.length) commit(clone(history.at(-1)), 'undo'); };
  el('apply-alignment').onclick = () => change(candidate => { candidate.backing_to_source = Array.from({length: 6}, (_, i) => numeric(`affine-${i}`)); });
  el('apply-motion').onclick = () => change(candidate => {
    candidate.motion = {pivot: [numeric('pivot-x'), numeric('pivot-y')], delta: [numeric('move-x'), numeric('move-y')],
      rotation_degrees: numeric('rotate'), seconds: numeric('seconds')};
  });
  el('apply-recipe').onclick = () => {
    try { commit(JSON.parse(el('recipe').value)); } catch (error) { message(`Invalid JSON: ${error.message}`, true); }
  };
  el('reset').onclick = () => commit(clone(saved.recipe), 'reset');
  el('export-form').onsubmit = event => {
    if (busy) { event.preventDefault(); return; }
    message('Recipe download requested. The applied recipe is also available under Recipe and rebuild.');
  };
  el('command').textContent = './ambiance --project PROJECT asset prepare --recipe preparation-recipe.json --out PROJECT/assets/prepared/part-v2';
  function seek(time) { stop(); clock = time; frame = Math.floor(time*30); drawCandidate(); }
  el('seek').oninput = () => seek(Number(el('seek').value)/30);
  el('rest').onclick = () => seek(0);
  el('extreme').onclick = () => seek(Math.floor(recipe.motion.seconds*15)/30);
  el('play').onclick = () => { playing = !playing; el('play').textContent = playing ? 'Pause' : 'Play'; lastTick = performance.now(); lastPaint = 0; observedFps = 0; skipped = 0; };
  el('inspection').onchange = () => { if (el('inspection').value !== 'context') stop(); drawCandidate(); };
  for (const id of ['hide-object', 'hide-foreground']) el(id).onchange = () => { recompile(); drawCandidate(); };
  for (const id of ['display', 'background']) el(id).onchange = () => { el('views').className = `views ${el('display').value} ${el('background').value}`; };
  function tick(now) {
    if (playing && !busy) {
      const next = clock+(now-lastTick)/1000, advance = Math.floor(next*30)-Math.floor(clock*30);
      clock = next%recipe.motion.seconds;
      const nextFrame = Math.floor(clock*30);
      if (frame !== nextFrame) {
        skipped += Math.max(0, advance-1); frame = nextFrame;
        if (lastPaint) observedFps = 1000/(now-lastPaint);
        lastPaint = now; drawCandidate();
      }
    }
    lastTick = now; requestAnimationFrame(tick);
  }
  for (const id of ['play', 'rest', 'extreme']) el(id).disabled = false;
  setBusy(false); refresh(); message('Captured inputs verified. Select a mask and outline a region on the source.');
  document.documentElement.dataset.preparationReady = 'true'; requestAnimationFrame(tick);
}

if (typeof document !== 'undefined') boot().catch(error => {
  el('message').textContent = `Cannot open workbench: ${error.message}`;
  el('message').className = 'error'; document.documentElement.dataset.preparationError = error.message;
});
