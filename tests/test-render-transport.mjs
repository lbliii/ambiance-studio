import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {test} from 'node:test';
import {encodeFrames, native} from '../tools/render/native-process.mjs';
import {htmlProof} from '../tools/render/proof-page.mjs';
import {rendererSources} from '../tools/render/source-identity.mjs';

const transportURL = new URL('../tools/render/native-process.mjs', import.meta.url).href;

test('relative Canvas overrides keep the original entry-directory resolution', async () => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'ambiance-canvas-'));
  try {
    const tools = path.join(directory, 'tools');
    await fs.mkdir(path.join(tools, 'render'), {recursive:true});
    await fs.copyFile(new URL('../tools/render/canvas-runtime.mjs', import.meta.url), path.join(tools, 'render/canvas-runtime.mjs'));
    await fs.writeFile(path.join(tools, 'fake-canvas.cjs'), 'module.exports={fixture:true}');
    await fs.writeFile(path.join(tools, 'package.json'), JSON.stringify({version:'fixture'}));
    const module = pathToFileURL(path.join(tools, 'render/canvas-runtime.mjs')).href;
    const code = `process.env.AMBIANCE_CANVAS_MODULE='./fake-canvas.cjs';const {canvasRuntime}=await import(${JSON.stringify(module)});console.log(JSON.stringify(canvasRuntime()));`;
    const result = await native(process.execPath, ['--input-type=module', '-e', code]);
    assert.equal(result.fixture, true);
    assert.equal(result.version, 'fixture');
    assert.equal(result.module, await fs.realpath(path.join(tools, 'fake-canvas.cjs')));
  } finally {
    await fs.rm(directory, {recursive:true, force:true});
  }
});

test('transport reports native JSON, process failures and malformed output', async () => {
  assert.deepEqual(await native(process.execPath, ['-e', 'console.log(JSON.stringify({ok:true}))']), {ok:true});
  await assert.rejects(native(process.execPath, ['-e', 'console.error("bad request"); process.exit(2)']), /failed \(2\): bad request/);
  await assert.rejects(native(process.execPath, ['-e', 'console.log("not json")']), /not json/);
  await assert.rejects(native('/nonexistent/ambiance-native', []), /ENOENT/);
});

test('encoder preserves a backpressured stream and surfaces partial-input failures', async () => {
  const frames = 16;
  const bytes = Buffer.alloc(256 * 1024, 73);
  const expected = createHash('sha256');
  for (let i = 0; i < frames; i++) expected.update(bytes);
  const code = `const {createHash}=require('node:crypto');const hash=createHash('sha256');let bytes=0;
    process.stdin.on('data',b=>{bytes+=b.length;hash.update(b)});
    process.stdin.on('end',()=>console.log(JSON.stringify({bytes,sha256:hash.digest('hex')})));`;
  const result = await encodeFrames(process.execPath, ['-e', code], frames, () => bytes);
  assert.deepEqual(result, {bytes:frames * bytes.length, sha256:expected.digest('hex')});
  await assert.rejects(encodeFrames(process.execPath, ['-e', 'process.stderr.write("partial stream");process.exit(4)'], 100, () => bytes), /Native encoder failed \(4\): partial stream/);
  const reader = 'process.stdin.resume();process.stdin.on("end",()=>console.log("{}"))';
  await assert.rejects(encodeFrames(process.execPath, ['-e', reader], 4, frame => {
    if (frame === 1) throw Error('raster failure');
    return bytes;
  }), /raster failure/);
});

test('cancellation terminates the owned encoder during a blocked write', async () => {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), 'ambiance-transport-'));
  const ready = path.join(directory, 'ready');
  const stopped = path.join(directory, 'stopped');
  const childCode = `const fs=require('node:fs');process.on('SIGTERM',()=>{fs.writeFileSync(${JSON.stringify(stopped)},'yes');process.exit(0)});fs.writeFileSync(${JSON.stringify(ready)},String(process.pid));setInterval(()=>{},1000);`;
  const script = `import {encodeFrames,installCancellation} from ${JSON.stringify(transportURL)};
    installCancellation();try {await encodeFrames(process.execPath,['-e',${JSON.stringify(childCode)}],100,()=>Buffer.alloc(1024*1024));}catch{process.exitCode=1}`;
  const owner = spawn(process.execPath, ['--input-type=module', '-e', script], {stdio:'ignore'});
  const closed = once(owner, 'close');
  let childPid;
  try {
    for (let i = 0; i < 200; i++) {
      try {childPid = Number(await fs.readFile(ready, 'utf8')); break;} catch {}
      await delay(10);
    }
    assert.ok(childPid, 'encoder started and installed its signal handler');
    owner.kill('SIGTERM');
    await Promise.race([closed, delay(3000, null, {ref:false}).then(() => {throw Error('owner did not stop')})]);
    assert.equal(await fs.readFile(stopped, 'utf8'), 'yes');
    assert.throws(() => process.kill(childPid, 0), {code:'ESRCH'});
  } finally {
    owner.kill('SIGKILL');
    if (childPid) {try {process.kill(childPid, 'SIGKILL');} catch {}}
    await closed;
    await fs.rm(directory, {recursive:true, force:true});
  }
});

test('proof presentation escapes embedded data and runtime identity includes every owner', async () => {
  const page = htmlProof([['current/00000.png']], 6, 64, 96, ['</script><script>bad()']);
  assert.ok(page.includes('1× (actual speed)'));
  assert.ok(!page.includes('</script><script>bad()'));
  assert.ok(page.includes('\\u003c/script>'));
  const sources = await rendererSources();
  const directory = fileURLToPath(new URL('../tools/render/', import.meta.url));
  for (const name of (await fs.readdir(directory)).filter(name => name.endsWith('.mjs'))) {
    const bytes = await fs.readFile(path.join(directory, name));
    assert.equal(sources['tools/render/' + name], createHash('sha256').update(bytes).digest('hex'));
  }
  assert.ok(sources['tools/render-scene.mjs']);
});
