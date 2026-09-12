import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';

// Relative overrides historically resolve from tools/render-scene.mjs.
const require = createRequire(new URL('../render-scene.mjs', import.meta.url));

export function canvasRuntime() {
  const override = process.env.AMBIANCE_CANVAS_MODULE;
  const candidates = override ? [ override ] : [
    '@napi-rs/canvas',
    path.join(
        os.homedir(),
        '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@napi-rs/canvas')
  ];
  for (const candidate of candidates)
    try {
      const resolved = require.resolve(candidate), api = require(resolved);
      return {
        ...api,
        module : resolved,
        version : require(path.join(path.dirname(resolved), 'package.json')).version
      };
    } catch (error) {
      if (override)
        throw Error(`AMBIANCE_CANVAS_MODULE cannot be loaded: ${error.message}`);
    }
  throw Error(
      'Install @napi-rs/canvas for this Node runtime or set AMBIANCE_CANVAS_MODULE to its installed module path.');
}
