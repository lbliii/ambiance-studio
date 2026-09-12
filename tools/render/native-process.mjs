import {spawn} from 'node:child_process';
import {once} from 'node:events';

import {progress} from './progress.mjs';

const children = new Set();
function own(child) {
  children.add(child);
  child.once('close', () => children.delete(child));
  return child;
}

// The CLI owns signal handlers; importing the transport has no process-wide effects.
export function installCancellation() {
  for (const sig of ['SIGTERM', 'SIGINT'])
    process.on(sig, () => {
      for (const child of children)
        if (child.exitCode === null)
          child.kill('SIGTERM');
      process.exitCode = 130;
      setTimeout(() => process.exit(130), 100).unref();
    });
}

export async function native(binary, args) {
  progress({phase : 'native-' + args[0], completed_frames : null, expected_frames : null}, true);
  const child = own(spawn(binary, args.map(String), {stdio : [ 'ignore', 'pipe', 'pipe' ]}));
  let stdout = '', stderr = '';
  child.stdout.on('data', b => stdout += b);
  child.stderr.on('data', b => stderr += b);
  const code = await new Promise((resolve, reject) => {
    child.on('error', reject);
    child.on('close', resolve);
  });
  let result;
  try {
    result = JSON.parse(stdout);
  } catch {
    throw Error(`Native media command failed (${code}): ${stderr || stdout}`);
  }
  if (code !== 0)
    throw Error(`Native media command failed (${code}): ${stderr}`);
  return result;
}

export async function encodeFrames(binary, args, frames, getFrame) {
  const child = own(spawn(binary, args.map(String), {stdio : [ 'pipe', 'pipe', 'pipe' ]}));
  let stdout = '', stderr = '', stdinError;
  child.stdout.on('data', b => stdout += b);
  child.stderr.on('data', b => stderr += b);
  child.stdin.on('error', e => stdinError = e);
  const done = new Promise((resolve, reject) => {
    child.on('error', reject);
    child.on('close', code => code === 0
                                  ? resolve()
                                  : reject(Error(`Native encoder failed (${code}): ${stderr}`)));
  });
  done.catch(() => {});
  try {
    for (let frame = 0; frame < frames; frame++) {
      const bytes = getFrame(frame);
      if (stdinError)
        throw stdinError;
      if (!child.stdin.write(bytes))
        await Promise.race([
          once(child.stdin, 'drain'),
          done.then(() => { throw Error('Encoder exited before consuming all frames'); })
        ]);
    }
    child.stdin.end();
    await done;
  } catch (error) {
    child.stdin.destroy();
    try {
      await done;
    } catch (nativeError) {
      throw nativeError;
    }
    throw error;
  }
  return JSON.parse(stdout);
}
