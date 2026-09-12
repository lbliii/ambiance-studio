#!/usr/bin/env node
// CLI transport only; every render uses the browser's shared scene engine.
import {canvasRuntime} from './render/canvas-runtime.mjs';
import {renderJob} from './render/job.mjs';
import {installCancellation} from './render/native-process.mjs';

installCancellation();

async function main() {
  const initializationStarted = performance.now();
  const runtime = canvasRuntime();
  if (process.argv.includes('--probe')) {
    return {ok: true, module: runtime.module, version: runtime.version, node: process.version};
  }
  let input = '';
  for await (const chunk of process.stdin) input += chunk;
  return renderJob(JSON.parse(input), runtime, initializationStarted);
}

try {
  console.log(JSON.stringify(await main()));
} catch (error) {
  console.log(JSON.stringify({ok: false, error: error.message}));
  process.exitCode = 1;
}
