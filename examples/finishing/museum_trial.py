#!/usr/bin/env python3
"""Reproducible read-only source import and public CLI museum look comparison."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2)+'\n')
def run(out, *args):
    command = [str(ROOT/'ambiance'), '--project', str(out), *map(str, args)]
    proc = subprocess.run(command, text=True, capture_output=True)
    data = json.loads(proc.stdout)
    if proc.returncode or not data.get('ok'): raise RuntimeError(data)
    return {'argv': command, 'exit_code': proc.returncode, 'result': data['data']}

def build(source, out):
    source, out = source.resolve(), out.resolve()
    if out.exists(): raise ValueError('Choose a fresh trial directory')
    source_scene = source/'scene/scene.json'; source_catalog = source/'assets/catalog.json'
    scene = json.loads(source_scene.read_text()); catalog = json.loads(source_catalog.read_text())
    used = {l['asset'] for l in scene['layers']}
    protected = {source_scene: sha(source_scene), source_catalog: sha(source_catalog)}
    subprocess.run([str(ROOT/'ambiance'), 'project', 'init', str(out), '--title', 'Museum finishing trial'], check=True, capture_output=True)
    imported = []
    for a in catalog['assets']:
        if a['id'] not in used: continue
        src = (source/a['file']).resolve()
        if not src.is_relative_to(source): raise ValueError('Source artwork escapes museum project')
        digest = sha(src)
        if digest != a['sha256']: raise ValueError('Museum asset changed: '+a['id'])
        protected[src] = digest
        dest = out/'assets/imported'/a['id']/'atlas.png'; dest.parent.mkdir(parents=True)
        shutil.copyfile(src, dest)
        item = {k: copy.deepcopy(a[k]) for k in ['id','width','height','sha256','atlas','pivot','sockets'] if k in a}
        item.update(file=str(dest.relative_to(out)), provenance={'kind':'exact-source-copy','source_project':str(source),'source_file':a['file'],'source_sha256':digest})
        imported.append(item)
    write(out/'scene/scene.json', scene); write(out/'assets/catalog.json', {'version':1,'assets':imported})
    baseline = {'version':1,'working_space':'linear-srgb','output_space':'srgb'}
    corrected = {**baseline,'layers':{name:{'exposure':-.25,'saturation':.82,'balance':[.7,.9,1.2]} for name in ['rat-near','rat-far']}}
    lit = {**corrected,'lights':[{'id':'moonlight-floor','receivers':['rat-near','rat-far'],'rect':[.48,.25,.5,.4],'color':'#668dff','gain':1.35,'feather':.2}]}
    write(out/'look.json', {'kind':'ambiance-look','version':1,'finishing':lit})
    write(out/'comparison.json', {'version':1,'title':'Museum rat: correction and moonlight','time':110/30,'selected_layer':'rat-near','finishing':lit,
          'variants':[{'id':'identity','label':'Linear pipeline only','finishing':baseline},{'id':'corrected','label':'Baseline correction','finishing':corrected}]})
    receipts = [run(out,'render','look-proof',out/'comparison.json','--width',360,'--supersample',2,'--out',out/'look-proof')]
    receipts.append(run(out,'look','apply',out/'look.json'))
    receipts.append(run(out,'render','proof','--start',2,'--seconds',3.1,'--width',360,'--supersample',2,'--out',out/'moving-rat-proof'))
    receipts.append(run(out,'render','frame','--time',110/30,'--width',1080,'--supersample',2,'--out',out/'portrait-frame'))
    after = {str(path): {'before':digest,'after':sha(path)} for path,digest in protected.items()}
    if any(row['before'] != row['after'] for row in after.values()): raise RuntimeError('Source changed during trial')
    write(out/'source-preservation.json', {'ok':True,'files':after})
    write(out/'trial-receipts.json', receipts)
    print(json.dumps({'ok':True,'trial':str(out),'protected_inputs':len(after),'look_workbench':str(out/'look-proof/index.html'),'note':'Candidate look, not a revised museum edition or artistic approval.'},indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('out',type=Path)
    parser.add_argument('--source',type=Path,default=ROOT/'projects/the-midnight-collection')
    args=parser.parse_args();build(args.source,args.out)
