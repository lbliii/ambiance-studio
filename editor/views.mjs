// Saved output framing. Geometry stays in the authored canvas coordinate basis.
export const VIEW_VERSION = 1;
export const RASTER_LIMIT = 4096;
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const finite = value => typeof value === 'number' && Number.isFinite(value);
const integer = value => Number.isInteger(value) && value > 0;
function fields(value, allowed, label) {
  if (!object(value) || Object.keys(value).some(key => !allowed.includes(key))) throw Error(`Unknown or invalid ${label} fields`);
}
function canvasSize(scene) {
  const {width, height} = scene.canvas ?? {};
  if (![width, height].every(integer) || Math.max(width, height) > RASTER_LIMIT) throw Error('Invalid authored canvas dimensions');
  return {width, height};
}
export function validateFraming(scene) {
  const {width: W, height: H} = canvasSize(scene);
  if (!Object.hasOwn(scene, 'framing')) return true;
  const framing = scene.framing;
  fields(framing, ['version', 'views'], 'framing');
  if (framing.version !== VIEW_VERSION || !object(framing.views) || !Object.keys(framing.views).length) throw Error('Framing requires version 1 and nonempty views');
  for (const [id, view] of Object.entries(framing.views)) {
    if (!/^[a-z][a-z0-9_-]{0,31}$/.test(id) || id === 'authored') throw Error(`Invalid or reserved view ID: ${id}`);
    fields(view, ['rect_scene_px', 'output'], `view ${id}`);
    const rect = view.rect_scene_px;
    if (!Array.isArray(rect) || rect.length !== 4 || !rect.every(finite)) throw Error(`View ${id} needs a finite [left, top, width, height] rectangle`);
    const [x, y, w, h] = rect;
    if (x < 0 || y < 0 || w <= 0 || h <= 0 || x + w > W || y + h > H) throw Error(`View ${id} rectangle must fit inside the authored canvas`);
    fields(view.output, ['width', 'height'], `view ${id} output`);
    const {width, height} = view.output;
    if (![width, height].every(integer) || Math.max(width, height) > RASTER_LIMIT) throw Error(`View ${id} output requires positive integers at most ${RASTER_LIMIT} per side`);
    if (Math.abs((w / h) / (width / height) - 1) > 1e-9) throw Error(`View ${id} output must preserve its rectangle aspect ratio`);
  }
  return true;
}
export function viewIds(scene) {
  validateFraming(scene);
  return ['authored', ...Object.keys(scene.framing?.views ?? {})];
}
export function resolveView(scene, id = 'authored') {
  validateFraming(scene);
  const source_canvas = canvasSize(scene);
  let view;
  if (id === 'authored') view = {rect_scene_px: [0, 0, source_canvas.width, source_canvas.height], output: source_canvas};
  else if (Object.hasOwn(scene.framing?.views ?? {}, id)) view = scene.framing.views[id];
  else throw Error(`Unknown view: ${id}`);
  return {resolver_version: VIEW_VERSION, id, source_canvas, rect_scene_px: [...view.rect_scene_px],
    output: {width: view.output.width, height: view.output.height}};
}
export function viewProjection(view) {
  const [x, y, width] = view.rect_scene_px, scale = view.output.width / width;
  return [scale, 0, 0, scale, -x * scale, -y * scale];
}
export function canonicalView(view) {
  return JSON.stringify({resolver_version: view.resolver_version, id: view.id,
    source_canvas: {width: view.source_canvas.width, height: view.source_canvas.height},
    rect_scene_px: view.rect_scene_px, output: {width: view.output.width, height: view.output.height}});
}
export function dualFraming() {
  return {version: VIEW_VERSION, views: {
    portrait: {rect_scene_px: [420, 0, 1080, 1920], output: {width: 1080, height: 1920}},
    landscape: {rect_scene_px: [0, 420, 1920, 1080], output: {width: 1920, height: 1080}}
  }};
}
// Existing renderers scale the entire runtime canvas. Keep authored view
// metadata valid in that private copy without changing the saved source scene.
export function resizeSceneCanvas(scene, width, height) {
  validateFraming(scene);
  const old = canvasSize(scene);
  if (![width, height].every(integer) || Math.max(width, height) > RASTER_LIMIT || width * old.height !== height * old.width) throw Error('Runtime resize must preserve the authored aspect ratio within raster limits');
  const scale = width / old.width;
  if (scene.framing) {
    for (const view of Object.values(scene.framing.views)) view.rect_scene_px = view.rect_scene_px.map(value => value * scale);
  }
  scene.canvas.width = width; scene.canvas.height = height;
  return scene;
}

const gcd = (a, b) => b ? gcd(b, a % b) : a;
export function fitView(view, longEdge) {
  if (!integer(longEdge) || longEdge > RASTER_LIMIT) throw Error('Long-edge ceiling must be a positive integer at most 4096');
  const divisor = gcd(view.output.width, view.output.height);
  const w = view.output.width / divisor, h = view.output.height / divisor;
  const multiple = Math.floor(longEdge / Math.max(w, h));
  if (!multiple) throw Error(`View ${view.id} cannot fit its integer aspect ratio within long-edge ${longEdge}`);
  return {width: w * multiple, height: h * multiple};
}

// Plan once, before allocating canvases. One sufficiently detailed stage serves
// every output, including fractional crops, without changing the camera basis.
export function planViews(scene, requests, {supersample = 1, long_edge = null} = {}) {
  validateFraming(scene);
  if (![1, 2, 4].includes(supersample)) throw Error('Supersample must be 1, 2, or 4');
  if (!Array.isArray(requests) || !requests.length || new Set(requests.map(r => r.id)).size !== requests.length) throw Error('Select one or more unique views');
  const views = requests.map(request => {
    fields(request, ['id', 'width', 'height'], 'view render request');
    if (typeof request.id !== 'string') throw Error('Each view render request needs an explicit view ID');
    const view = resolveView(scene, request.id);
    if (long_edge !== null && (request.width != null || request.height != null)) throw Error('Long-edge sizing cannot be combined with width/height overrides');
    const width = request.width ?? view.output.width;
    const output = long_edge !== null ? fitView(view, long_edge) : {
      width, height: request.height ?? width * view.output.height / view.output.width
    };
    if (![output.width, output.height].every(integer) || Math.max(output.width, output.height) > RASTER_LIMIT) throw Error(`View ${view.id} needs integer output dimensions at most 4096 preserving its aspect ratio`);
    if (output.width * view.output.height !== output.height * view.output.width) throw Error(`View ${view.id} output must preserve its aspect ratio`);
    return {view, output};
  });
  const source_canvas = canvasSize(scene), {width: W, height: H} = source_canvas;
  const divisor = gcd(W, H), unitW = W / divisor, unitH = H / divisor;
  const required = Math.max(...views.map(v => v.output.width / v.view.rect_scene_px[2])) * supersample;
  const multiple = Math.ceil(required * divisor);
  const internal_canvas = {width: unitW * multiple, height: unitH * multiple};
  if (Math.max(internal_canvas.width, internal_canvas.height) > RASTER_LIMIT) throw Error(`Views require an internal stage of ${internal_canvas.width} × ${internal_canvas.height}; maximum is 4096 per side. Lower output size or supersampling, or choose a less magnified view.`);
  const scale = internal_canvas.width / W;
  return {version: 1, source_canvas, internal_canvas, scale, supersample,
    views: views.map(v => ({...v, source_rect_px: v.view.rect_scene_px.map(n => n * scale)}))};
}
