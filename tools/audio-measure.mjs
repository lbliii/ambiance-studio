// 48 kHz ITU-R BS.1770-5 Annex 1 (integrated loudness), Annex 2 (4x FIR).
// File-backed measurement only. No source edits, resampling, normalization or decoding.
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';

// Annex 2's 12 coefficients for each of four polyphase branches.
const FIR = [
  [0.001708984375,0.010986328125,-0.0196533203125,0.033203125,-0.0594482421875,0.1373291015625,0.97216796875,-0.102294921875,0.047607421875,-0.026611328125,0.014892578125,-0.00830078125],
  [-0.0291748046875,0.029296875,-0.0517578125,0.089111328125,-0.16650390625,0.465087890625,0.77978515625,-0.2003173828125,0.1015625,-0.0582275390625,0.0330810546875,-0.0189208984375],
  [-0.0189208984375,0.0330810546875,-0.0582275390625,0.1015625,-0.2003173828125,0.77978515625,0.465087890625,-0.16650390625,0.089111328125,-0.0517578125,0.029296875,-0.0291748046875],
  [-0.00830078125,0.014892578125,-0.026611328125,0.047607421875,-0.102294921875,0.97216796875,0.1373291015625,-0.0594482421875,0.033203125,-0.0196533203125,0.010986328125,0.001708984375]
];
const db = x => x > 0 ? 20 * Math.log10(x) : null;
const loudness = x => x > 0 ? -0.691 + 10 * Math.log10(x) : null;

class Channel {
  constructor() {
    this.shelf = [0,0]; this.highpass = [0,0]; this.history = new Float64Array(12);
    this.peak = 0; this.truePeak = 0; this.sum = 0; this.hopSum = 0; this.hops = []; this.blocks = [];
  }
  peakSample(x) {
    this.history.copyWithin(1,0,11); this.history[0] = x;
    for (const phase of FIR) {
      let y = 0;
      for (let k = 0; k < 12; k++) y += phase[k] * this.history[k];
      this.truePeak = Math.max(this.truePeak, Math.abs(y));
    }
  }
  sample(x, n) {
    if (!Number.isFinite(x)) throw Error('Non-finite PCM sample');
    this.peak = Math.max(this.peak, Math.abs(x)); this.sum += x*x;
    this.peakSample(x);
    // Transposed direct form II, double precision, initially zero state.
    const a = this.shelf, b = this.highpass;
    let y = 1.53512485958697*x + a[0];
    a[0] = -2.69169618940638*x + 1.69065929318241*y + a[1];
    a[1] = 1.19839281085285*x - 0.73248077421585*y;
    const z = y + b[0];
    b[0] = -2*y + 1.99004745483398*z + b[1];
    b[1] = y - 0.99007225036621*z;
    this.hopSum += z*z;
    if ((n+1)%4800 === 0) {
      this.hops.push(this.hopSum); this.hopSum = 0;
      if (this.hops.length > 4) this.hops.shift();
      if (this.hops.length === 4) this.blocks.push(this.hops.reduce((a,b)=>a+b,0)/19200);
    }
  }
}

function integrated(blocks, peak, frames) {
  const abs = blocks.filter(x => loudness(x) !== null && loudness(x) > -70);
  const relative = abs.length ? loudness(abs.reduce((a,b)=>a+b,0)/abs.length)-10 : null;
  const gated = abs.filter(x => loudness(x) > relative);
  return {value: gated.length ? loudness(gated.reduce((a,b)=>a+b,0)/gated.length) : null,
    units:'LUFS', status: peak === 0 ? 'silence' : frames < 19200 ? 'insufficient_duration' : !gated.length ? 'below_gate' : 'measured',
    block_frames:19200, hop_frames:4800, complete_blocks:blocks.length, absolute_gated_blocks:abs.length,
    relative_gated_blocks:gated.length, absolute_gate_lufs:-70, relative_gate_lufs:relative,
    trailing_frames_excluded: frames < 19200 ? frames : (frames-19200)%4800};
}

export function measure(spec) {
  const {path, frames, channels, bits, codec, sample_rate: rate, data_offset: offset = 0} = spec;
  if (rate !== 48000 || ![1,2].includes(channels) || !Number.isSafeInteger(frames) || frames < 1 || frames > 48000*3600 ||
      ![8,16,24,32].includes(bits) || !['pcm_integer','pcm_float'].includes(codec) || (codec==='pcm_float' && bits!==32) || !Number.isSafeInteger(offset) || offset<0)
    throw Error('Unsupported measurement format/interval');
  const width=bits/8, align=channels*width, buffer=Buffer.alloc(4096*align);
  const meters=Array.from({length:channels},()=>new Channel()), mono=channels===2 ? new Channel() : meters[0];
  const fd=fs.openSync(path,'r'); let cross=0;
  try {
    for(let start=0; start<frames; start+=4096) {
      const count=Math.min(4096,frames-start), bytes=count*align;
      if(fs.readSync(fd,buffer,0,bytes,offset+start*align)!==bytes) throw Error('Truncated PCM measurement interval');
      for(let i=0;i<count;i++) {
        const values=[];
        for(let ch=0;ch<channels;ch++) {
          const at=i*align+ch*width;
          const x=codec==='pcm_float' ? buffer.readFloatLE(at) : bits===8 ? (buffer[at]-128)/128 : buffer.readIntLE(at,width)/2**(bits-1);
          values.push(x); meters[ch].sample(x,start+i);
        }
        if(channels===2) {mono.sample((values[0]+values[1])/2,start+i); cross+=values[0]*values[1];}
      }
    }
  } finally {fs.closeSync(fd);}
  // Zero extension flushes only the FIR support (11 frames); no extra loudness blocks.
  for(const meter of new Set([...meters,mono])) for(let i=0;i<11;i++) meter.peakSample(0);
  const peak=Math.max(...meters.map(m=>m.peak)), tp=Math.max(...meters.map(m=>m.truePeak));
  const rms=Math.sqrt(meters.reduce((s,m)=>s+m.sum,0)/(frames*channels));
  const blocks=meters[0].blocks.map((x,i)=>meters.reduce((sum,m)=>sum+m.blocks[i],0));
  return {backend:{id:'ambiance-bs1770',version:1,runtime:process.version,arithmetic:'IEEE 754 double'},
    method:{standard:'ITU-R BS.1770-5', loudness:'Annex 1; 48 kHz table 1/2 K-weighting, independent unit-weight mono/stereo channels; 400 ms/75% overlap; absolute -70 and relative -10 LU gates',
      true_peak:'Annex 2 published 4-phase 12-tap FIR; 4x to 192 kHz; zero extension before/after interval, full filter tail; floating point without attenuation',
      rms:'Unweighted channel-mean energy',mono:channels===2?'(L+R)/2, treated as one mono channel':'One original channel; never duplicated'},
    integrated_lufs:integrated(blocks,peak,frames),
    true_peak:{linear:tp,dbtp:db(tp),status:tp===0?'silence':'measured',oversample:4},
    sample_peak:{linear:peak,dbfs:db(peak)},rms_dbfs:db(rms),
    channels:meters.map(m=>({sample_peak_dbfs:db(m.peak),true_peak_dbtp:db(m.truePeak),rms_dbfs:db(Math.sqrt(m.sum/frames))})),
    mono_fold_down:{integrated_lufs:integrated(mono.blocks,mono.peak,frames),rms_dbfs:db(Math.sqrt(mono.sum/frames)),
      rms_ratio: rms ? Math.sqrt(mono.sum/frames)/rms : null,
      cancellation:channels===1?'not_applicable':!peak?'silent_input':mono.peak===0?'complete':'none_or_partial',
      correlation:channels===2 && meters.every(m=>m.sum>0) ? cross/Math.sqrt(meters[0].sum*meters[1].sum) : null}};
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try { process.stdout.write(JSON.stringify(measure(JSON.parse(fs.readFileSync(0,'utf8'))))+'\n'); }
  catch(error) {process.stdout.write(JSON.stringify({ok:false,error:error.message})+'\n');process.exitCode=2;}
}
