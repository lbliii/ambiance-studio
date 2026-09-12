import fs from 'node:fs/promises';
import path from 'node:path';

import {prepareJob} from './job-input.mjs';
import {renderOutputs} from './outputs.mjs';
import {prepareRaster} from './raster.mjs';
import {renderReceipt} from './receipt.mjs';

export async function renderJob(request, runtime, initializationStarted = performance.now()) {
  const job = await prepareJob(request, runtime);
  const {out, sceneBytes, catalogBytes, mode, internalWidth, internalHeight} = job;
  // Validate everything above before creating the immutable result directory.
  await fs.mkdir(out, {recursive : false});
  await fs.writeFile(path.join(out, 'scene.snapshot.json'), sceneBytes);
  await fs.writeFile(path.join(out, 'catalog.snapshot.json'), catalogBytes);
  const raster = prepareRaster(job);
  const report = await renderReceipt(job, raster);
  const {finishingDiagnostics} = raster;
  const started = Date.now();
  finishingDiagnostics.length = 0;
  await renderOutputs(job, raster, report, initializationStarted);
  if (finishingDiagnostics.length)
    report.finishing_diagnostics = {
      samples : finishingDiagnostics.length,
      max_clipped_pixels : finishingDiagnostics.reduce((n, x) => Math.max(n, x.clipped_pixels), 0),
      clipped_pixels_sum : finishingDiagnostics.reduce((n, x) => n + x.clipped_pixels, 0),
      internal_pixels_per_frame : internalWidth * internalHeight,
      scope : mode === 'video' ? 'Encoded output and encoder preroll samples'
                               : 'Saved render samples',
      automatic_artistic_judgment : false
    };
  report.elapsed_seconds = (Date.now() - started) / 1000;
  report.peak_rss_bytes = process.resourceUsage().maxRSS * 1024;
  await fs.writeFile(path.join(out, 'render-report.json'), JSON.stringify(report, null, 2) + '\n');
  return report;
}