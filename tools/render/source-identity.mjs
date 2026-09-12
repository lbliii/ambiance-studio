import {createHash} from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
export const sha = data => createHash('sha256').update(data).digest('hex');

// Every extracted owner participates in runtime evidence. Keep entry-file hashes intact.
export async function rendererSources() {
  const names = [
    'tools/render-scene.mjs', ...(await fs.readdir(path.join(root, 'tools/render')))
                                  .filter(name => name.endsWith('.mjs'))
                                  .sort()
                                  .map(name => 'tools/render/' + name)
  ];
  return Object.fromEntries(await Promise.all(
      names.map(async name => [name, sha(await fs.readFile(path.join(root, name)))])));
}
