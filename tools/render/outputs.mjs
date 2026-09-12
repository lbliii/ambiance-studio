import fs from 'node:fs/promises';
import path from 'node:path';

import {auditViewPixels, auditViews} from '../../editor/audit.mjs';
import {renderLookProof} from '../look-proof.mjs';
import {renderRigProof} from '../rig-proof.mjs';
import {viewsProofPage} from '../views-proof.mjs';

import {encodeFrames, native} from './native-process.mjs';
import {progress} from './progress.mjs';
import {htmlProof} from './proof-page.mjs';
import {root, sha} from './source-identity.mjs';

function gcd(a, b) { return b ? gcd(b, a % b) : a; }

export async function renderOutputs(job, raster, report, initializationStarted) {
  const {
    out,
    sceneBytes,
    catalogBytes,
    scene,
    catalog,
    viewPlan,
    width,
    height,
    supersample,
    fps,
    loopFrames,
    start,
    mode,
    frames,
    disable,
    rigPlan,
    lookPlan,
    images,
    assetBytes,
    request,
    runtime
  } = job;
  const {stageRenderer, canvas, render} = raster;
  if (mode === 'look-proof') {
    Object.assign(report, await renderLookProof(lookPlan, {
                    out,
                    root,
                    runtime,
                    catalog,
                    images,
                    assetBytes,
                    width,
                    height,
                    supersample,
                    sourceScene : JSON.parse(sceneBytes),
                    sceneHash : sha(sceneBytes),
                    catalogHash : sha(catalogBytes)
                  }));
    report.frames = null;
    report.seconds = null;
    report.start_seconds = null;
    report.scene_loop_frames = loopFrames;
    report.look_recipe = {
      resolved_path : request.look_recipe_path,
      path_base : 'absolute',
      sha256 : request.look_recipe_sha256
    };
    report.full_loop_review_performed = false;
    report.check_scope =
        'Saved look samples and editable shared-engine preview; no automatic artistic or full-loop approval';
  } else if (mode === 'rig-proof') {
    Object.assign(report, await renderRigProof(
                              rigPlan, {out, runtime, catalog, images, width, height, htmlProof}));
    // A pose matrix is not one continuous clip. Keep saved-frame scope separate
    // from the authored loop whose endpoints were measured above.
    report.frames = null;
    report.seconds = null;
    report.start_seconds = null;
    report.scene_loop_frames = loopFrames;
    report.saved_sample_frames = rigPlan.variants.length;
    report.saved_playback_frames_per_variant = rigPlan.playback_frames;
    report.saved_playback_frames_total = rigPlan.playback_frames * rigPlan.variants.length;
    report.rig_recipe = {
      resolved_path : request.rig_recipe_path,
      path_base : 'absolute',
      sha256 : request.rig_recipe_sha256
    };
    report.inventory = request.inventory_identity ?? null;
    report.part_ids = request.rig_recipe.part_ids ?? [];
    report.full_loop_review_performed = false;
    report.check_scope =
        'Selected variant poses, optional targeted playback, plus endpoint measurement; no full-loop visual inspection';
  } else if (mode === 'benchmark') {
    const times = request.sample_times;
    if (!Array.isArray(times) || times.length < 3 || times.length > 20 ||
        times.some(t => !Number.isFinite(t) || t < 0 || t >= scene.canvas.loop_seconds))
      throw Error('Invalid benchmark sample times');
    report.benchmark = {
      initialization_seconds : (performance.now() - initializationStarted) / 1000,
      samples : []
    };
    for (const [index, time] of times.entries()) {
      const before = performance.now();
      render(time);
      const elapsed = (performance.now() - before) / 1000;
      const name = `sample-${String(index).padStart(2, '0')}.png`;
      await fs.writeFile(path.join(out, name), canvas.toBuffer('image/png'));
      report.benchmark.samples.push({time, render_seconds : elapsed, file : name});
      progress({phase : 'benchmark', completed_frames : index + 1, expected_frames : times.length},
               true);
    }
    report.output = path.join(out, 'sample-00.png');
    report.output_sha256 = sha(await fs.readFile(report.output));
  } else if (mode === 'frame') {
    render(start);
    const bytes = canvas.toBuffer('image/png');
    await fs.writeFile(path.join(out, 'frame.png'), bytes);
    report.output = path.join(out, 'frame.png');
    report.output_sha256 = sha(bytes);
  } else if (mode === 'views-proof') {
    const ids = viewPlan.views.map(v => v.view.id);
    report.geometry = auditViews(scene, catalog, ids);
    report.pixels = await auditViewPixels(scene, catalog, images, ids, runtime.createCanvas,
                                          () => {}, viewPlan);
    report.audit_module_sha256 = sha(await fs.readFile(path.join(root, 'editor/audit.mjs')));
    report.review_needed = !report.geometry.ok || !report.pixels.ok;
    const outputs =
        viewPlan.views.map(v => ({id : v.view.id, output : v.output, files : [], hashes : []}));
    for (const output of outputs)
      await fs.mkdir(path.join(out, output.id));
    for (let frame = 0; frame < frames; frame++) {
      render(start + frame / fps);
      for (const output of outputs) {
        const relative = output.id + '/' + String(frame).padStart(5, '0') + '.png',
              bytes = stageRenderer.outputs.get(output.id).toBuffer('image/png');
        await fs.writeFile(path.join(out, relative), bytes);
        output.files.push(relative);
        output.hashes.push(sha(bytes));
      }
    }
    await fs.writeFile(path.join(out, 'index.html'),
                       viewsProofPage(outputs, fps, start, frames, scene.canvas.loop_seconds));
    report.output_sha256 = sha(await fs.readFile(path.join(out, 'index.html')));
    report.output = path.join(out, 'index.html');
    report.outputs = outputs;
    report.sample_times = Array.from({length : frames}, (_, frame) => start + frame / fps);
    report.playback = 'One timeline; every output samples each identical source time';
    report.stage_frames_rendered = frames;
  } else if (mode === 'proof') {
    const files = [];
    for (const off of disable.length ? [ false, true ] : [ false ]) {
      const dir = off ? 'disabled' : 'current';
      await fs.mkdir(path.join(out, dir));
      const list = [];
      for (let frame = 0; frame < frames; frame++) {
        render(start + frame / fps, off);
        const relative = `${dir}/${String(frame).padStart(5, '0')}.png`;
        await fs.writeFile(path.join(out, relative), canvas.toBuffer('image/png'));
        list.push(relative);
      }
      files.push(list);
    }
    await fs.writeFile(path.join(out, 'index.html'), htmlProof(files, fps, width, height, disable));
    report.output = path.join(out, 'index.html');
    report.disabled_layers = disable;
    report.variants = files.length;
    report.playback = 'Actual frame rate by default; disabled layers are hidden, not repainted';
  } else {
    const nativePath = request.native;
    if (!nativePath)
      throw Error('Native media binary is required for video');
    const prerollFrames = loopFrames, encodedFrames = frames + prerollFrames;
    const bitrate =
        request.bitrate ?? Math.max(300000, Math.round(12000000 * width * height / (1080 * 1920)));
    if (!Number.isInteger(bitrate) || bitrate < 1000)
      throw Error('bitrate must be a positive integer >= 1000');
    const intermediate = path.join(out, 'preroll-and-picture.mp4'),
          video = path.join(out, 'picture.mp4');
    progress({
      phase : 'render-encode',
      completed_frames : 0,
      expected_frames : encodedFrames,
      preroll_frames : prerollFrames,
      encoded_frames : 0
    },
             true);
    report.native_encoder =
        await encodeFrames(nativePath,
                           [
                             'encode', intermediate, width, height, fps, encodedFrames, bitrate,
                             'rgba', gcd(loopFrames, fps * 2)
                           ],
                           encodedFrames, frame => {
                             render(start + (frame - prerollFrames) / fps);
                             progress({
                               phase : 'render-encode',
                               completed_frames : frame + 1,
                               expected_frames : encodedFrames,
                               preroll_frames : prerollFrames,
                               encoded_frames : Math.max(0, frame + 1 - prerollFrames)
                             },
                                      frame + 1 === encodedFrames);
                             return canvas.data();
                           });
    report.encoder_preroll_frames = prerollFrames;
    await fs.writeFile(path.join(out, 'encode-checkpoint.json'), JSON.stringify({
      ...report,
      ok : false,
      stage : 'encoded-before-trim',
      intermediate,
      intermediate_sha256 : sha(await fs.readFile(intermediate))
    },
                                                                                null, 2) +
                                                                     '\n');
    report.preroll_trim =
        await native(nativePath, [ 'trim', intermediate, video, prerollFrames, frames, fps ]);
    report.output = video;
    report.output_sha256 = sha(await fs.readFile(video));
  }
}
