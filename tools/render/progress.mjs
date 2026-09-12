import {writeSync} from 'node:fs';
let lastProgress = 0;
export function progress(event, force = false) {
  const fd = Number(process.env.AMBIANCE_PROGRESS_FD);
  if (!process.env.AMBIANCE_PROGRESS_FD || !Number.isInteger(fd))
    return;
  if (!force && Date.now() - lastProgress < 500)
    return;
  lastProgress = Date.now();
  try {
    writeSync(fd, JSON.stringify(event) + '\n');
  } catch {
  }
}
