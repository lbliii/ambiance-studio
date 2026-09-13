// Focused mc/1 specimen checks, not a production model validator/resolver/clock.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {compileScene, multiply, inverseMatrix, point} from '../editor/engine.mjs';
import {referenceMapping, placeFromSource} from '../editor/source-placement.mjs';
import {sceneTiming} from '../editor/timing.mjs';

const root = fileURLToPath(new URL('./fixtures/model-contract/', import.meta.url));
const read = name => JSON.parse(fs.readFileSync(path.join(root, name), 'utf8'));
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
const clone = structuredClone;
const checks = [];
const check = (name, fn) => { fn(); checks.push(name); };
const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} != ${b}`);
const id = value => assert.match(value, /^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$/);
function distinctIds(rows, key) {
  rows.forEach(row => id(row[key]));
  assert.equal(new Set(rows.map(row => row[key])).size, rows.length, `Duplicate ${key}`);
}
function pin(base, ref) {
  assert.equal(typeof ref.file, 'string');
  assert.equal(path.isAbsolute(ref.file), false);
  const file = fs.realpathSync(path.resolve(root, base, ref.file));
  assert.ok(file.startsWith(root), 'Fixture reference escapes fixture root');
  assert.match(ref.sha256, /^[a-f0-9]{64}$/);
  const bytes = fs.readFileSync(file);
  assert.equal(hash(bytes), ref.sha256, `Stale pin: ${ref.file}`);
  if (ref.model_id !== undefined) {
    id(ref.model_id); id(ref.version);
    const model = JSON.parse(bytes);
    assert.equal(model.model_id, ref.model_id);
    assert.equal(model.version, ref.version);
    assert.equal(model.packet_version, 'mc/1');
    return model;
  }
  return bytes;
}
const lantern = read('models/lantern-v1.json');
const candle = read('models/candle-v1.json');
const character = read('models/character-v1.json');
const instances = read('instances.json');
const clock = read('clock-cues.json');
const runtime = read('runtime.json');

// This intentionally checks only exposed controls/variants in the fixed lantern
// specimen. Production validation/closure resolution belongs to construction.
function lanternInstance(instance, definition = lantern) {
  id(instance.instance_id);
  assert.equal(pin('.', instance.definition).model_id, definition.model_id);
  for (const [key, value] of Object.entries(instance.overrides)) {
    const control = definition.controls.find(c => c.control_id === key);
    assert.ok(control, `Undeclared control: ${key}`);
    assert.equal(typeof value, control.type, `Wrong control type: ${key}`);
    if (control.type === 'number') {
      assert.ok(Number.isFinite(value) && value >= control.min && value <= control.max, 'Control out of range');
    }
  }
  for (const [key, value] of Object.entries(instance.variants)) {
    const set = definition.variant_sets.find(v => v.variant_set_id === key);
    assert.ok(set?.variants.some(v => v.variant_id === value), 'Unknown variant');
  }
  assert.ok(Number.isFinite(instance.placement.scale) && instance.placement.scale > 0);
}

check('Exact fixture bytes, explicit nested pins, stable IDs and registered drawings', () => {
  for (const model of [lantern, candle, character]) {
    assert.equal(model.packet_version, 'mc/1'); id(model.model_id); id(model.version);
    for (const [rows, key] of [[model.parts, 'part_id'], [model.drawings, 'drawing_id'], [model.controls, 'control_id'], [model.sockets, 'socket_id']]) distinctIds(rows, key);
    assert.ok(model.parts.some(p => p.part_id === model.root_part_id && p.drawing_id));
    assert.equal(model.local_frame.clip, 'none');
    assert.equal(model.canvas, undefined);
    for (const drawing of model.drawings) {
      const bytes = pin('models', drawing.asset);
      assert.equal(bytes.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
      assert.equal(bytes.readUInt32BE(16), drawing.asset.width);
      assert.equal(bytes.readUInt32BE(20), drawing.asset.height);
      const [w, h] = drawing.asset.cell_size;
      assert.equal(drawing.asset.width % w, 0); assert.equal(drawing.asset.height % h, 0);
      assert.ok(Number.isInteger(drawing.cel_index) && drawing.cel_index >= 0 && drawing.cel_index < drawing.asset.width / w * drawing.asset.height / h);
    }
    for (const part of model.parts) if (part.drawing_id) assert.ok(model.drawings.some(d => d.drawing_id === part.drawing_id));
  }
  assert.deepEqual(pin('models', lantern.parts.find(p => p.part_id === 'candle').definition), candle);
  assert.deepEqual(lantern.paint_order, [['housing'], ['candle', 'wax'], ['candle', 'flame'], ['front']]);
  assert.equal(character.kind, 'character');
  assert.equal(clock.drawing_map.character_id, character.model_id);
  assert.deepEqual(pin('.', clock.drawing_map.definition), character);
  pin('models', character.character_views[0].reference);
  pin('models', character.registration_chain_specimen.input);
  for (const a of runtime.catalog.assets) pin('.', a);
});

check('Stale bytes/version, missing dependency, unsafe path and duplicate IDs reject', () => {
  const p = clone(instances.instances[0].definition);
  assert.throws(() => pin('.', {...p, sha256:'0'.repeat(64)}), /Stale pin/);
  assert.throws(() => pin('.', {...p, version:'latest'}));
  assert.throws(() => pin('.', {...p, file:'models/missing.json'}));
  assert.throws(() => pin('.', {...p, file:'../../test-model-contract.mjs'}), /escapes/);
  assert.throws(() => distinctIds([...lantern.parts, lantern.parts[0]], 'part_id'), /Duplicate/);
});

check('Independent instance tuple identities and compatible label changes retain overrides', () => {
  distinctIds(instances.instances, 'instance_id');
  instances.instances.forEach(i => lanternInstance(i));
  const tuples = instances.instances.flatMap(i => lantern.paint_order.map(parts => JSON.stringify([i.instance_id, parts])));
  assert.equal(new Set(tuples).size, 8);
  const renamed = {...lantern, name:'A new display label'};
  lanternInstance(instances.instances[0], renamed);
  assert.deepEqual(instances.instances[0].overrides, {'source-on':true, 'flame-phase':0});
  for (const overrides of [{'source-on':1}, {'flame-phase':2}, {'flame-phase':NaN}, {'internal.asset':'other'}]) {
    assert.throws(() => lanternInstance({...instances.instances[0], overrides}));
  }
  assert.throws(() => lanternInstance({...instances.instances[0], variants:{frame:'missing'}}));
  assert.throws(() => lanternInstance(instances.instances[1], {...lantern, controls:[lantern.controls[0]]}), /Undeclared/);
});

check('Padded character cells map through current source/engine affines without alpha fitting', () => {
  const view = character.character_views[0];
  const chain=character.registration_chain_specimen;
  assert.deepEqual(multiply(chain.raw_cel_to_cell,[1,0,0,1,-chain.source_rect[0],-chain.source_rect[1]]),chain.source_to_cell);
  assert.deepEqual(multiply(chain.source_to_cell,inverseMatrix(chain.image_to_reference)),chain.reference_to_cell);
  for(const [mapping,p] of [[chain.raw_cel_to_cell,chain.raw_point],[chain.source_to_cell,chain.input_point],[chain.reference_to_cell,chain.reference_point]]) assert.deepEqual(point(mapping,...p),chain.cell_point);
  assert.notDeepEqual(point(chain.raw_cel_to_cell,...chain.input_point),chain.cell_point,'Using raw-cel mapping on whole-input pixels must differ');
  for (const r of character.registration_assertions) {
    const drawing = character.drawings.find(d => d.drawing_id === r.drawing_id);
    const a = {...drawing.asset, id:drawing.asset.asset_id};
    const explicit = {version:1, asset_sha256:a.sha256, cell_size:r.cell_size, reference:view.reference, reference_to_cell:r.reference_to_cell};
    const actual = multiply(view.reference_to_local, inverseMatrix(referenceMapping(a, view.reference, explicit)));
    const part = character.parts.find(p => p.drawing_id === r.drawing_id);
    actual.forEach((v, i) => near(v, part.cell_to_local[i]));
    assert.throws(() => referenceMapping(a, view.reference, {...explicit, cell_size:[r.cell_size[0]-1, r.cell_size[1]]}), /identity differs/);
    assert.throws(() => referenceMapping(a, {...view.reference, sha256:'f'.repeat(64)}, explicit), /identity differs/);
    assert.throws(() => referenceMapping(a, view.reference, {...explicit, reference_to_cell:[0,0,0,0,0,0]}), /Singular/);
  }
  const head = character.parts.find(p => p.part_id === 'head');
  assert.deepEqual(point(head.cell_to_local,20,20),[60,40]);
  assert.deepEqual(point(head.cell_to_local,0,0),[20,0]);
  assert.deepEqual(point(head.cell_to_local,40,40),[100,80]);
  const body = character.parts.find(p => p.part_id === 'body');
  assert.deepEqual(point(body.cell_to_local,70,120),[130,230]);
  // The current placement operation (not just matrix inversion) rejects shear.
  const scene = clone(runtime.scene), catalog = clone(runtime.catalog);
  const base = catalog.assets.find(a => a.id === 'ground-v1'), art = catalog.assets[0];
  const map = a => ({version:1, asset_sha256:a.sha256, cell_size:[a.width,a.height], reference:view.reference, reference_to_cell:[1,0,0,1,0,0]});
  assert.throws(() => placeFromSource(scene,catalog,{op:'place_from_source',id:'bad',asset:art.id,base:'ground',mode:'native',reference:view.reference,base_mapping:map(base),mapping:{...map(art),reference_to_cell:[1,0,1,1,0,0]}}), /shear/);
});

const states = (scene, time=0) => Object.fromEntries(compileScene(scene,runtime.catalog).sample(time).map(s => [s.id,s]));
check('Current evaluator keeps mounted parts together, independent instances and front-frame order', () => {
  const before = states(runtime.scene), changed = clone(runtime.scene);
  changed.layers.find(l => l.id === 'lamp-a').x += .1;
  const after = states(changed);
  for (const member of runtime.owned_sets['lamp-a']) {
    near(after[member].matrix[4] - before[member].matrix[4], 24);
    near(after[member].matrix[5], before[member].matrix[5]);
  }
  for (const member of [...runtime.owned_sets['lamp-b'], 'ground', 'unrelated-light']) assert.deepEqual(after[member], before[member]);
  assert.deepEqual(changed.layers.map(l=>l.id),runtime.scene.layers.map(l=>l.id));
  for (const p of ['a','b']) assert.ok(changed.layers.findIndex(l=>l.id===p+'-flame') < changed.layers.findIndex(l=>l.id===p+'-front'));
  changed.layers.find(l=>l.id==='lamp-a').visible=false;
  const hidden = states(changed);
  runtime.owned_sets['lamp-a'].forEach(member=>assert.equal(hidden[member].visible,false));
  assert.equal(hidden['ground-a-light'].opacity,0);
  for (const member of [...runtime.owned_sets['lamp-b'], 'ground', 'unrelated-light']) assert.deepEqual(hidden[member],before[member]);
  assert.equal(runtime.scene.layers.find(l=>l.id==='ground-a-light').attach.layer,'ground');
});

check('Existing graph rejects child depth, absent socket, mounting cycle and conflicting writers', () => {
  for (const mutate of [
    s=>{s.layers.find(l=>l.id==='a-flame').depth=1;},
    s=>{s.layers.find(l=>l.id==='a-flame').attach.socket='missing';},
    s=>{const a=s.layers.find(l=>l.id==='lamp-a');a.attach={layer:'a-wax',socket:'wick'};delete a.depth;},
    s=>{s.layers.find(l=>l.id==='ground-a-light').tracks={opacity:{interpolation:'linear',keys:[[0,1],[2,1]]}};}
  ]) { const s=clone(runtime.scene); mutate(s); assert.throws(()=>compileScene(s,runtime.catalog)); }
});

check('Legacy clock remains deterministic for random/negative seeks and actual timing cadence', () => {
  const compiled=compileScene(runtime.scene,runtime.catalog);
  for (const t of [1.25,0,.75,-.25,2,4.5,.75]) assert.deepEqual(compiled.sample(t),compileScene(runtime.scene,runtime.catalog).sample(t));
  assert.deepEqual(compiled.sample(-.25),compiled.sample(1.75));
  assert.deepEqual(compiled.sample(2),compiled.sample(0));
  const report=sceneTiming(runtime.scene,runtime.catalog,{layer:'a-flame'});
  assert.equal(report.layers[0].timing_driver,'cycle');
  assert.equal(report.layers[0].fallback_cycle.nominal_cel_fps,4);
  const noninteger=clone(runtime.scene); noninteger.canvas.fps=24000/1001;
  assert.throws(()=>compileScene(noninteger,runtime.catalog), /canvas/);
});

check('Derived subject is explicitly bound to pose, variants, overrides, nested pins and mask policy', () => {
  const subject=instances.derived_subject;
  const verify = s => {
    assert.equal(s.status,'input-identity-specimen-no-rendered-proof');
    pin('.',s.definition); pin('models',s.nested_definitions[0]);
    assert.deepEqual(s.definition,instances.instances[0].definition);
    assert.deepEqual(s.variants,instances.instances[0].variants);
    assert.deepEqual(s.overrides,instances.instances[0].overrides);
    assert.deepEqual(s.nested_definitions,[lantern.parts[1].definition]);
    assert.deepEqual(s.included_parts,lantern.paint_order);
    assert.deepEqual(s.product.roles,['solid']);
    // This subject promises the fixed rest-mask inputs, with threshold 1.
    assert.equal(s.product.threshold,1);
    const sampled=states(runtime.scene,s.clock.frame/24);
    assert.equal(s.pose.drawing_ids[2],`flame-${sampled['a-flame'].cell}`);
    assert.equal(s.clock.local_cycles.flame.progress,s.clock.frame/24%1);
  };
  verify(subject);
  for(const mutate of [s=>s.pose.drawing_ids[2]='flame-1',s=>s.variants.frame='arched',s=>s.overrides['source-on']=false,s=>s.nested_definitions[0].sha256='0'.repeat(64),s=>s.product.threshold=128,s=>s.clock.frame=1]) {
    const next=clone(subject); mutate(next); assert.throws(()=>verify(next));
  }
  assert.deepEqual(subject.excluded_external_contributions,['ground-a-light']);
  assert.deepEqual(subject.product.roles,['solid']);
});

check('Selected silent take bytes/PCM and character drawing map are pinned independently', () => {
  const bytes=pin('.',clock.take);
  assert.equal(bytes.toString('ascii',0,4),'RIFF'); assert.equal(bytes.toString('ascii',8,12),'WAVE');
  // Fixed Python-wave PCM specimen only; this is not a general WAV decoder.
  assert.equal(bytes.toString('ascii',36,40),'data');
  assert.equal(bytes.readUInt16LE(20),1); assert.equal(bytes.readUInt16LE(22),clock.take.channels);
  assert.equal(bytes.readUInt32LE(24),clock.take.sample_rate); assert.equal(bytes.readUInt16LE(34),16);
  assert.equal(bytes.length-44,clock.take.samples*2); assert.equal(hash(bytes.subarray(44)),clock.take.pcm_sha256);
  const drawingIds=new Set(character.drawings.map(d=>d.drawing_id));
  [clock.drawing_map.neutral,clock.drawing_map.open,...clock.cues.map(c=>c.drawing_id)].forEach(d=>assert.ok(drawingIds.has(d)));
  const changed={...clock.take,sha256:'0'.repeat(64)}; assert.throws(()=>pin('.',changed),/Stale/);
  assert.equal(drawingIds.has('mouth-missing'),false);
});

check('Unequal edit and cue offsets preserve exact samples and end-exclusive presentation', () => {
  assert.equal(clock.packet_version,'mc/1');
  const fps=clock.fps.numerator/clock.fps.denominator, samplesPerFrame=clock.take.sample_rate/fps;
  assert.equal(samplesPerFrame,2000);
  let nextFrame=0;
  for(const edit of clock.edit) {
    const shot=clock.shots.find(s=>s.shot_id===edit.shot_id);
    const descriptor=JSON.parse(pin('.',shot.revision));
    assert.equal(descriptor.packet_version,'mc/1'); assert.equal(descriptor.shot_id,shot.shot_id);
    assert.equal(descriptor.revision_id,shot.revision_id); assert.equal(descriptor.duration_frames,shot.duration_frames);
    assert.deepEqual(descriptor.fps,clock.fps);
    assert.equal(edit.at_frame,nextFrame); assert.ok(0<=edit.in_frame && edit.in_frame<edit.out_frame && edit.out_frame<=shot.duration_frames);
    nextFrame+=edit.out_frame-edit.in_frame;
  }
  assert.equal(nextFrame,clock.expected_edit_frames);
  const p=clock.placement, edit=clock.edit.find(s=>s.shot_id===p.shot_id);
  for(const cue of clock.cues) {
    assert.ok(cue.source_samples[0]>=p.source_in_samples && cue.source_samples[1]<=clock.take.samples);
    cue.source_samples.forEach((s,i)=>{
      const shot=s+p.at_shot_frame*samplesPerFrame+p.offset_samples-p.source_in_samples;
      const global=shot+(edit.at_frame-edit.in_frame)*samplesPerFrame;
      assert.equal(shot,cue.shot_samples[i]); assert.equal(global,cue.edit_samples[i]);
      // Verify the saved ceiling result by interval inequalities, without adding a time helper.
      for(const [sample,frame] of [[shot,cue.shot_frames[i]],[global,cue.edit_frames[i]]]) {
        assert.ok((frame-1)*samplesPerFrame < sample && sample <= frame*samplesPerFrame);
      }
    });
  }
  assert.deepEqual(clock.cues[1].edit_frames,[62,62]);
  assert.equal(clock.cues[1].diagnostic,'unpresented');
  assert.deepEqual(clock.finite_inspection.map(s=>s.effective_frame),[0,59,60,60]);
  assert.deepEqual(clock.rounding_cases.map(s=>s['nearest-half-away-from-zero']),[-2,2,0]);
  // Finite and local-cycle tables are future acceptance vectors, not runtime tests.
  assert.deepEqual(clock.local_cycle.samples.map(s=>s.progress),[.25,0,.5,.75]);
});

console.log(JSON.stringify({ok:true,packet_version:'mc/1',checks,limits:[
  'Specimen invariants and current evaluator state only; no model runtime, finite evaluator, raster or artistic acceptance.',
  'Fixed dependency pins and expected time tables are not a production graph resolver or time conversion implementation.'
]},null,2));
