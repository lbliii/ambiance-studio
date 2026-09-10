#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {auditScene} from '../editor/audit.mjs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const args=process.argv.slice(2),sceneFile=path.resolve(args[0]||path.join(root,'scenes/last-lantern-rigged.json'));
const option=name=>{const i=args.indexOf(name);return i>=0?args[i+1]:null;};
const catalogFile=path.resolve(option('--catalog')||path.join(root,'assets/catalog.json'));
const hash=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
let report;
try{
  const scene=JSON.parse(fs.readFileSync(sceneFile)),catalog=JSON.parse(fs.readFileSync(catalogFile));
  report=auditScene(scene,catalog);
  const assetRoot=path.dirname(path.dirname(catalogFile));
  report.inputs={scene_sha256:hash(sceneFile),catalog_sha256:hash(catalogFile),
    engine_sha256:hash(path.join(root,'editor/engine.mjs')),audit_sha256:hash(path.join(root,'editor/audit.mjs'))};
  report.asset_hashes={};
  for(const id of new Set(scene.layers.map(l=>l.asset))){
    const asset=catalog.assets.find(a=>a.id===id),file=path.resolve(assetRoot,asset.file);
    if(path.relative(assetRoot,file).startsWith('..'))throw Error(`Asset outside root: ${id}`);
    const actual=hash(file);report.asset_hashes[id]=actual;
    if(actual!==asset.sha256)throw Error(`Asset hash mismatch: ${id}`);
  }
}catch(e){report={ok:false,error:e.message};}
const result=JSON.stringify(report,null,2)+'\n';
if(option('--out'))fs.writeFileSync(option('--out'),result);
process.stdout.write(result);process.exitCode=report.ok?0:1;
