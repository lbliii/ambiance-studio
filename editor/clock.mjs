// mc/1 clock. Exact conversion boundaries; one evaluated host time per sample.
const MAX=BigInt(Number.MAX_SAFE_INTEGER), contexts=new WeakMap();
const abs=n=>n<0n?-n:n;
const gcd=(a,b)=>{a=abs(a);while(b){[a,b]=[b,a%b];}return a;};
function pair(n,d=1n){if(!d)throw Error('Rational denominator must be positive');if(d<0n){n=-n;d=-d;}const g=gcd(n,d);return [n/g,d/g];}
function integer(n){if(!Number.isSafeInteger(n))throw Error('Expected a safe integer');return BigInt(n);}
function component(n){if(typeof n==='string'&&/^-?(0|[1-9][0-9]{0,399})$/.test(n))return BigInt(n);return integer(n);}
function read(v){
  if(typeof v==='number'){
    if(!Number.isFinite(v)||Math.abs(v)>Number.MAX_SAFE_INTEGER)throw Error('Time must be finite and safe');
    const [digits,exponent='0']=String(v).split('e'),[whole,decimal='']=digits.split('.'),e=Number(exponent)-decimal.length;
    const n=BigInt(whole+decimal);return e>=0?pair(n*10n**BigInt(e)):pair(n,10n**BigInt(-e));
  }
  if(!v||typeof v!=='object'||Array.isArray(v)||Object.keys(v).some(k=>!['numerator','denominator'].includes(k))||v.denominator<=0)throw Error('Expected numerator/positive denominator');
  return pair(component(v.numerator),component(v.denominator));
}
// Exact decimal seconds can require more than 53 bits; serialize those integers
// as decimal strings, never as rounded JSON numbers.
function json([n,d]){return Object.freeze({numerator:abs(n)>MAX?String(n):Number(n),denominator:d>MAX?String(d):Number(d)});}
const mul=([a,b],[c,d])=>pair(a*c,b*d),div=([a,b],[c,d])=>pair(a*d,b*c);
const add=([a,b],[c,d])=>pair(a*d+c*b,b*d),sub=([a,b],[c,d])=>pair(a*d-c*b,b*d);
const number=([n,d])=>Number(n)/Number(d),positive=v=>{const r=read(v);if(r[0]<=0n)throw Error('Rate/period must be positive');return r;};
const mod=([n,d],[a,b])=>pair(((n*b)%(a*d)+a*d)%(a*d),d*b);
export const rational=value=>json(read(value));
export function roundRational(value,rounding='exact'){
  const [n,d]=read(value);let q=n/d,r=n%d;
  if(rounding==='exact'){if(r)throw Error('Exact conversion falls between integer samples/frames');}
  else if(rounding==='floor'){if(r<0n)q--;}
  else if(rounding==='ceil'){if(r>0n)q++;}
  else if(rounding==='nearest-half-away-from-zero'){if(abs(r)*2n>=d)q+=n<0n?-1n:1n;}
  else throw Error('Unknown rounding policy');
  if(abs(q)>MAX)throw Error('Rounded result exceeds safe integer range');
  return {value:Number(q),exact:json([n,d]),rounding,residual:json(pair(q*d-n,d))};
}
export const frameToSeconds=(frame,fps)=>json(div([integer(frame),1n],positive(fps)));
export const framesToSamples=(frame,fps,rate,rounding='exact')=>roundRational(json(mul(read(frameToSeconds(frame,fps)),positive(rate))),rounding);
export const samplesToFrames=(sample,rate,fps,rounding='exact')=>roundRational(json(mul(div([integer(sample),1n],positive(rate)),positive(fps))),rounding);
export const secondsToFrames=(seconds,fps,rounding='exact')=>roundRational(json(mul(read(seconds),positive(fps))),rounding);
export const wrapTime=(time,duration)=>((time%duration)+duration)%duration;
const object=v=>v&&typeof v==='object'&&!Array.isArray(v);
function fields(v,allowed,label){if(!object(v)||Object.keys(v).some(k=>!allowed.includes(k)))throw Error(`Invalid ${label} fields`);}
export function compileClock(scene){
  const canvas=scene.canvas,c=scene.clock,mode=c?.mode??'loop',fps=positive(canvas.fps);
  const N=c===undefined?canvas.fps*canvas.loop_seconds:c?.duration_frames;
  if(!Number.isSafeInteger(N)||N<1)throw Error('Clock needs a safe positive frame count');
  const duration=c===undefined?positive(canvas.loop_seconds):div([integer(N),1n],fps);
  if(c!==undefined){
    fields(c,['version','mode','id','revision','duration_frames','local_cycles'],'clock');
    if(c.version!==1||!['loop','finite'].includes(mode)||typeof c.id!=='string'||!c.id||typeof c.revision!=='string'||!c.revision||canvas.loop_seconds!==N/canvas.fps)throw Error('Clock requires version, mode, id, revision and duration_frames matching canvas');
  }
  if(c?.local_cycles!==undefined)fields(c.local_cycles,Object.keys(c.local_cycles),'local cycles');
  const cycles=Object.entries(c?.local_cycles??{}).sort(([a],[b])=>a.localeCompare(b)).map(([id,cycle])=>{
    if(!id)throw Error('Local cycle needs an ID');fields(cycle,['period_seconds','phase_turns'],'local cycle');
    const period=positive(cycle.period_seconds),phase=read(cycle.phase_turns??0);
    json(period);json(phase);
    if(mode==='loop'&&div(duration,period)[1]!==1n)throw Error(`Local cycle must divide the visual loop: ${id}`);
    return [id,period,phase];
  });
  const definition=Object.freeze({version:1,mode,id:c?.id??scene.id??null,revision:c?.revision??null,fps:json(fps),duration_frames:N,duration_seconds:canvas.loop_seconds});
  const signature=JSON.stringify([definition,cycles.map(([id,p,h])=>[id,json(p),json(h)])]);
  function evaluate(request,requestedFrame=null){
    const original=read(request),n=typeof request==='number'?request:number(original),T=canvas.loop_seconds;
    if(!Number.isFinite(n)||Math.abs(n)>Number.MAX_SAFE_INTEGER)throw Error('Time must be finite and safe');
    const declaredEnd=typeof request==='number'&&n===T;
    const region=original[0]<0n?'before':declaredEnd||original[0]*duration[1]>=duration[0]*original[1]?'at-or-after-end':'inside';
    const effective=mode==='finite'?(region==='before'?[0n,1n]:region==='at-or-after-end'?duration:original):
      requestedFrame===null&&typeof request==='number'?read(wrapTime(n,T)):mod(original,duration);
    // Seconds callers retain legacy modulo arithmetic; frame callers use the
    // exact effective frame time so a wrapped double cannot fall below a key.
    const seconds=mode==='loop'?(requestedFrame===null?wrapTime(n,T):number(effective)):
      region==='inside'&&typeof request==='number'?n:number(effective);
    const local=Object.fromEntries(cycles.map(([id,period,phase])=>{
      const progress=mod(add(div(effective,period),phase),[1n,1n]);
      return [id,Object.freeze({progress:number(progress),progress_exact:json(progress),seconds:number(mul(progress,period)),period_seconds:number(period)})];
    }));
    const context=Object.freeze({...definition,requested_seconds:json(original),effective_seconds:json(effective),seconds,region,
      requested_frame:requestedFrame,effective_frame:requestedFrame===null?null:mode==='finite'?Math.max(0,Math.min(N,requestedFrame)):((requestedFrame%N)+N)%N,
      local_cycles:Object.freeze(local)});
    contexts.set(context,signature);return context;
  }
  return Object.freeze({...definition,accept:context=>{if(contexts.get(context)!==signature)throw Error('Evaluated context belongs to a different clock');return context;},seconds:request=>evaluate(request),frame:frame=>evaluate(frameToSeconds(frame,json(fps)),frame)});
}
export const isClockContext=value=>object(value)&&contexts.has(value);
export function consumerTime(context,cycle){
  if(!isClockContext(context))throw Error('Expected evaluated clock context');
  if(cycle===undefined)return {seconds:context.seconds,duration:context.duration_seconds,progress:context.seconds/context.duration_seconds};
  if(typeof cycle!=='string'||!Object.hasOwn(context.local_cycles,cycle))throw Error(`Unknown local cycle: ${cycle}`);
  const c=context.local_cycles[cycle];return {seconds:c.seconds,duration:c.period_seconds,progress:c.progress};
}
export function cycleCell(context,cycle,count,phase=0){
  consumerTime(context,cycle);
  const [n,d]=read(context.local_cycles[cycle].progress_exact);
  return Number((n*integer(count)/d+integer(phase))%integer(count));
}
export function validateCycleReference(scene,consumer){return consumerTime(compileClock(scene).seconds(0),consumer.local_cycle);}
