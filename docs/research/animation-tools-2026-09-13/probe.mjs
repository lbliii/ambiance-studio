// Bounded mechanics research, not a renderer, production recipe, or quality test.
// Run from any directory: node /path/to/probe.mjs > /tmp/animation-tools-probe.json
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {compileScene, wrapTime} from '../../../editor/engine.mjs';

const root = fileURLToPath(new URL('../../../', import.meta.url));
const work = fs.mkdtempSync(path.join(os.tmpdir(), 'animation-tools-research-'));
const project = path.join(work, 'fixture');
const sceneFile = path.join(project, 'scene/scene.json');
const hash = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const write = (file, value) => fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n');
const commands = [];
function cli(args, success = true) {
  const run = spawnSync(path.join(root, 'ambiance'), args, {cwd: root, encoding: 'utf8'});
  if (run.error) throw run.error;
  const result = JSON.parse(run.stdout);
  commands.push({argv: args.map(a => a.replaceAll(work, '$WORK')), exit_code: run.status,
    ok: result.ok, error: result.error ?? null});
  assert.equal(run.status === 0, success, run.stdout + run.stderr);
  return result;
}
cli(['project', 'init', project, '--template', 'blank']);
// Metadata-only specimen adapted from tests/test-tracks.mjs. No art is admitted.
const catalog = {version: 1, assets: [{id: 'drawings', width: 128, height: 32,
  atlas: {cell_width: 32, cell_height: 32, columns: 4, rows: 1, frame_count: 4}}]};
const scene = {version: 1, id: 'research-exposures', title: 'Exposure mechanics only',
  canvas: {width: 100, height: 200, fps: 24, loop_seconds: 2, background: '#000'},
  camera: {overscan: 1, x_amplitude: 0, y_amplitude: 0, zoom_amplitude: 0}, groups: [],
  layers: [{id: 'subject', name: 'subject', asset: 'drawings', x: .5, y: .5,
    width: .2, height: .1, anchor: [.5, .5], scale: 1, rotation: 0, opacity: 1,
    visible: true, blend: 'source-over', depth: 0, cycle_seconds: 2, phase_frames: 0}]};
write(path.join(project, 'assets/catalog.json'), catalog);
write(sceneFile, scene);
const args = ['--project', project];
function applyKeys(keys, success = true) {
  const batch = path.join(project, 'probe-batch.json');
  write(batch, {version: 1, operations: [{op: 'set', layer: 'subject',
    values: {tracks: {cell: {interpolation: 'hold', keys}}}}]});
  const before = hash(sceneFile);
  const preview = cli([...args, 'scene', 'apply', batch, '--dry-run'], success);
  assert.equal(hash(sceneFile), before, 'Dry run changed the scene');
  if (!success) return preview;
  assert.equal(preview.data.previous_sha256, before);
  cli([...args, 'scene', 'apply', batch, '--expect-sha256', before]);
  assert.equal(hash(path.join(project, '.ambiance/scene-history', before + '.json')), before);
  assert.deepEqual(read(sceneFile).layers[0].tracks.cell.keys, keys);
  return preview;
}
const initial = [[0, 0], [.5, 0], [1, 1], [1.5, 2], [2, 0]];
applyKeys(initial);
const timing = cli([...args, 'scene', 'timing', '--layer', 'subject']).data;
const holds = timing.layers[0].authored.holds;
assert.equal(holds[0].end_seconds, 1);
const beforeRig = compileScene(read(sceneFile), catalog);
const changed = [[0, 0], [.25, 3], [.5, 0], [1, 1], [1.5, 2], [2, 0]];
applyKeys(changed);
const afterRig = compileScene(read(sceneFile), catalog);
const changedFrames = Array.from({length: 48}, (_, f) => f)
  .filter(f => beforeRig.sample(f / 24)[0].cell !== afterRig.sample(f / 24)[0].cell);
assert.deepEqual(changedFrames, [6, 7, 8, 9, 10, 11]);
const rejectedClosure = applyKeys([[0, 0], [1, 1], [2, 1]], false);
const beforeClock = hash(sceneFile);
const rejectedClock = cli([...args, 'scene', 'clock', '--loop-seconds', '4', '--dry-run'], false);
assert.equal(hash(sceneFile), beforeClock);
assert.deepEqual(afterRig.sample(2), afterRig.sample(0));
const snapshot = afterRig.sample(.75);
afterRig.sample(1.75); afterRig.sample(.125);
assert.deepEqual(afterRig.sample(.75), snapshot);

// Check conventional frame addressing instead of assuming seconds conversion is exact.
const frameKeys = [[0, 0], [1, 1], [3, 2], [5, 3], [48, 0]];
applyKeys(frameKeys.map(([f, value]) => [f / 24, value]));
const mixedRig = compileScene(read(sceneFile), catalog);
const mismatches = [];
for (let f = 0; f < 48; f++) {
  const expected = frameKeys.filter(([start]) => start <= f).at(-1)[1];
  const observed = mixedRig.sample(f / 24)[0].cell;
  if (expected !== observed) mismatches.push({frame: f, expected, observed,
    input_seconds: f / 24, wrapped_seconds: wrapTime(f / 24, 2)});
}
const sources = ['editor/engine.mjs', 'editor/timing.mjs', 'tools/scene-command.mjs',
  'ambiance_studio/scene_transactions.py', 'ambiance_studio/scene_commands.py',
  'docs/CAPABILITIES.json', 'docs/architecture/FIRST-SHORT-WORK-PACKAGES.json'];
const git = spawnSync('git', ['rev-parse', 'HEAD'], {cwd: root, encoding: 'utf8'});
assert.equal(git.status, 0);
const report = {schema_version: 1, researched_at: new Date().toISOString(),
  repository_commit: git.stdout.trim(), node: process.version,
  probe_sha256: hash(fileURLToPath(import.meta.url)),
  source_hashes: Object.fromEntries(sources.map(p => [p, hash(path.join(root, p))])),
  observations: {
    separate_equal_cell_keys: {saved_keys: initial, timing_report_holds: holds,
      saved_boundary_at_half_second: true, report_merges_boundary: true},
    bounded_substitution: {saved_keys: changed, changed_output_frames: changedFrames,
      output_fps: 24, dry_run_preserves_scene: true, previous_scene_snapshot_preserved: true},
    finite_clock: {sample_at_duration_equals_start: true,
      nonclosing_track_error: rejectedClosure.error, clock_only_change_error: rejectedClock.error,
      rejected_clock_preserves_scene: true},
    arbitrary_seek: {repeat_sample_equal: true},
    mixed_exposures: {authored_frame_keys: frameKeys, fps: 24, output_frames: 48,
      all_requested_frame_selections_match: mismatches.length === 0,
      exact_frame_mismatches: mismatches}
  }, commands,
  limits: ['Metadata-only synthetic specimen; no raster, audio, or artistic observation.',
    'External applications and interchange libraries were not executed.',
    'Public CLI mutations and timing plus the shared evaluator were exercised; no new runtime capability.',
    'Exit zero means observation completed; inspect mixed_exposures for observed mismatches.']};
write(path.join(work, 'report.json'), report);
process.stderr.write(`Retained local fixture and full report: ${work}\n`);
process.stdout.write(JSON.stringify(report, null, 2) + '\n');
