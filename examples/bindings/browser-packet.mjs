import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
export function browserPacket(project,root){
  const out=path.join(project,'render/browser-parity');fs.mkdirSync(out);fs.mkdirSync(path.join(out,'modules'));fs.mkdirSync(path.join(out,'assets'));
  const sceneBytes=fs.readFileSync(path.join(project,'scene/scene.json')),scene=JSON.parse(sceneBytes),catalog=JSON.parse(fs.readFileSync(path.join(project,'assets/catalog.json')));
  for(const a of catalog.assets)fs.copyFileSync(path.join(project,a.file),path.join(out,a.file));
  for(const name of ['engine.mjs','bindings.mjs','finishing.mjs','views.mjs'])fs.copyFileSync(path.join(root,'editor',name),path.join(out,'modules',name));
  fs.copyFileSync(path.join(root,'examples/bindings/browser-parity.mjs'),path.join(out,'browser-parity.mjs'));
  const samples=[0,1,2,3].map(time=>{const file=`state-${time}.png`;fs.copyFileSync(path.join(project,`render/state-${time}/frame.png`),path.join(out,file));return {time,file};});
  const packet={scene,catalog,samples,scene_sha256:createHash('sha256').update(sceneBytes).digest('hex'),cli_reports:samples.map(s=>`../state-${s.time}/render-report.json`)};
  fs.writeFileSync(path.join(out,'packet.json'),JSON.stringify(packet,null,2));
  fs.writeFileSync(path.join(out,'index.html'),'<!doctype html><html lang="en"><meta charset="utf-8"><title>Binding browser / CLI raster parity</title><style>body{background:#171a21;color:#eee;font:16px system-ui}main{display:flex;flex-wrap:wrap}canvas{width:256px;height:192px;image-rendering:pixelated}pre{white-space:pre-wrap}</style><h1>Binding browser / CLI raster parity</h1><pre id="result">Checking…</pre><main></main><script type="module" src="browser-parity.mjs"></script></html>');
  return out;
}
