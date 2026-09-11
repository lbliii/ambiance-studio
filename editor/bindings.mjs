// Explicit one-way mappings; the scene evaluator supplies the only clock and
// evaluated source states. No expressions, accumulation, or feedback.
import {sampleSignal} from './finishing.mjs';

const object=v=>v&&typeof v==='object'&&!Array.isArray(v);
const finite=v=>typeof v==='number'&&Number.isFinite(v);
const clamp=v=>Math.max(0,Math.min(1,v));
const fields=(v,keys,label)=>{if(!object(v)||Object.keys(v).some(k=>!keys.includes(k)))throw Error(`Invalid ${label} fields`);};
const span=(v,label,equal=false)=>{if(!Array.isArray(v)||v.length!==2||!v.every(finite)||!finite(v[1]-v[0])||(equal?v[0]>v[1]:v[0]>=v[1]))throw Error(`Invalid ${label} range`);};
const channels=['x','y','rotation','scale','opacity','cell'];

export function validateBindings(scene,catalog){
  if(scene.bindings===undefined)return true;
  const config=scene.bindings;
  fields(config,['version','links'],'bindings');
  if(config.version!==1||!Array.isArray(config.links))throw Error('Bindings require version 1 and links array');
  const layers=new Map(scene.layers.map(l=>[l.id,l])),assets=new Map(catalog.assets.map(a=>[a.id,a]));
  const signals=new Map((scene.finishing?.signals||[]).map(s=>[s.id,s]));
  const dependencies=new Map(scene.layers.map(l=>[l.id,l.attach?[l.attach.layer]:[]]));
  const ids=new Set(),writers=new Set();
  const layer=id=>{if(!layers.has(id))throw Error(`Missing binding endpoint layer: ${id}`);return layers.get(id);};
  for(const link of config.links){
    fields(link,['id','source','target','map','off'],'binding');
    if(typeof link.id!=='string'||!link.id||ids.has(link.id))throw Error('Invalid or duplicate binding ID');ids.add(link.id);
    const {source:s,target:d,map:m}=link;
    fields(s,['signal','layer','channel','range'],'binding source');fields(d,['layer','channel','range'],'binding target');
    const target=layer(d.layer),asset=assets.get(target.asset);
    if(!channels.includes(d.channel))throw Error(`Unsupported binding target channel: ${link.id}`);
    span(d.range,'target',true);
    const value=v=>{if(!finite(v)||v<d.range[0]||v>d.range[1]||d.channel==='opacity'&&(v<0||v>1)||['x','y','rotation'].includes(d.channel)&&Math.abs(v)>100||d.channel==='scale'&&(v<.001||v>100)||d.channel==='cell'&&(!asset.atlas||!Number.isInteger(v)||v<0||v>=asset.atlas.frame_count))throw Error(`Binding output outside valid range: ${link.id}`);};
    d.range.forEach(value);value(link.off);
    const writer=`${d.layer}.${d.channel}`;
    if(writers.has(writer)||target.tracks?.[d.channel])throw Error(`Multiple writers / track conflict: ${writer}`);writers.add(writer);
    const amplitude={x:'x_amplitude',y:'y_amplitude',rotation:'rotation_amplitude'}[d.channel];
    if(amplitude&&target.motion?.[amplitude])throw Error(`Binding conflicts with additive motion: ${writer}`);
    let sourceLayer,count;
    if(s.signal!==undefined){
      if(s.layer!==undefined||s.channel!==undefined||!signals.has(s.signal))throw Error(`Missing or incompatible binding signal: ${link.id}`);
      span(s.range,'source');if(s.range[0]<0||s.range[1]>8)throw Error(`Signal source range must be within 0..8: ${link.id}`);
      sourceLayer=signals.get(s.signal).layer;
    }else{
      sourceLayer=s.layer;const src=layer(sourceLayer);
      if(s.channel==='cell'){
        if(s.range!==undefined)throw Error(`Discrete source uses a complete cel table, not a range: ${link.id}`);
        count=assets.get(src.asset).atlas?.frame_count||1;
      }else{
        if(!['x','y','rotation','scale'].includes(s.channel))throw Error(`Unsupported normalized pose channel: ${link.id}`);
        span(s.range,'pose source');
      }
    }
    if(sourceLayer!==undefined)dependencies.get(d.layer).push(sourceLayer);
    if(count!==undefined){
      fields(m,['values'],'discrete binding map');
      if(!Array.isArray(m.values)||m.values.length!==count)throw Error(`Binding requires one output per source cel: ${link.id}`);
      m.values.forEach(value);
    }else{
      fields(m,['keys','interpolation'],'continuous binding map');
      if(!['linear','smoothstep','hold'].includes(m.interpolation)||!Array.isArray(m.keys)||m.keys.length<2||m.keys.length>64)throw Error(`Invalid binding map: ${link.id}`);
      if(d.channel==='cell'&&m.interpolation!=='hold')throw Error(`Cel output requires hold interpolation: ${link.id}`);
      let previous=-1;
      for(const key of m.keys){if(!Array.isArray(key)||key.length!==2||!finite(key[0])||key[0]<0||key[0]>1||key[0]<=previous)throw Error(`Binding map inputs must strictly increase in 0..1: ${link.id}`);previous=key[0];value(key[1]);}
      if(m.keys[0][0]!==0||previous!==1)throw Error(`Binding map must span normalized 0..1: ${link.id}`);
    }
  }
  const visited=new Set(),visiting=new Set();
  function visit(id){if(visiting.has(id))throw Error(`Binding/attachment dependency cycle: ${id}`);if(visited.has(id))return;visiting.add(id);for(const dep of dependencies.get(id)||[])visit(dep);visiting.delete(id);visited.add(id);}
  for(const id of layers.keys())visit(id);
  return true;
}

export function sampleBinding(link,signals,readState,time,duration){
  const s=link.source;
  let raw,active,kind;
  if(s.signal!==undefined){raw=sampleSignal(signals.get(s.signal),readState,time,duration);active=raw>0;kind='intensity';}
  else{const state=readState(s.layer);raw=state.channels[s.channel];active=state.visible&&state.opacity>0;kind=s.channel==='cell'?'state':'pose';}
  const input=kind==='state'?raw:raw<=s.range[0]?0:raw>=s.range[1]?1:clamp((raw-s.range[0])/(s.range[1]-s.range[0]));
  let value=link.off;
  if(active){
    if(kind==='state')value=link.map.values[input];
    else{
      const keys=link.map.keys;let i=0;while(i<keys.length-2&&input>=keys[i+1][0])i++;
      const [a,x]=keys[i],[b,y]=keys[i+1];let u=(input-a)/(b-a);
      if(input===b)value=y;
      else{if(link.map.interpolation==='hold')u=0;else if(link.map.interpolation==='smoothstep')u=u*u*(3-2*u);value=x+(y-x)*u;}
    }
  }
  return {id:link.id,source:{kind,raw,value:input,active},target:structuredClone(link.target),value};
}
