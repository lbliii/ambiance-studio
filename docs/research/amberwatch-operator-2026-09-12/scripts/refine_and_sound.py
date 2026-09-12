import json,hashlib,subprocess,shutil
from pathlib import Path
P=Path(__file__).resolve().parents[1];ROOT=P.parents[1]
def save(p,d):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(d,indent=2)+'\n')
def cli(*args):
 r=subprocess.run([str(ROOT/'ambiance'),'--project',str(P),*map(str,args)],capture_output=True,text=True);d=json.loads(r.stdout)
 if r.returncode:raise RuntimeError(str(d)[:2000])
 return d['data']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
s=json.loads((P/'scene/scene.json').read_text());ops=[]
fr=s['framing'];fr['views']['landscape']['rect_scene_px'][1]=30;ops.append({'op':'framing','value':fr})
for l in s['layers']:
 values={}
 if l['id'].startswith('pumpkin-right'):values.update(x=l['x']-35/1448,y=l['y']-25/1086)
 if l['id'] in ['lantern-post','lantern-post-flame']:values['y']=l['y']-12/1086
 if l['id'].endswith('-flame'):
  values.update(width=l['width']*.78,height=l['height']*.78)
 if l['id'].startswith('leaf-'):
  v=l['tracks']['visible']['keys'];start=v[1][0];end=v[-2][0]
  times=sorted(set([0,start,min(start+.3,end-.3),max(start+.3,end-.3),end,16]))
  fade=[[t,0 if t in [0,start,end,16] else .88] for t in times]
  tracks=l['tracks'];tracks['opacity']={'interpolation':'smoothstep','keys':fade};values['tracks']=tracks
 if values:ops.append({'op':'set','layer':l['id'],'values':values})
look=s['finishing']
for light in look['lights']:
 if light['id']=='pumpkin-right-stones':light['rect'][0]-=35/1448;light['rect'][1]-=25/1086
 if light['id']=='lantern-post-receiver':light['rect'][1]-=12/1086
ops.append({'op':'finishing','value':look})
save(P/'plans/refine-v2.json',{'version':1,'operations':ops});cli('scene','apply',P/'plans/refine-v2.json')
# Preserve existing studio media and its evidence. Historical scripts are never executed.
archive=Path('/Users/lb/Developer/ambiance-studio/archive/session-2026-09-10/outputs/soundtrack')
dest=P/'audio/sources/last-lantern';dest.mkdir(parents=True,exist_ok=True)
for name in ['music','woodland','leaves','hearth']:shutil.copy2(archive/'stems'/(name+'-48s.wav'),dest/(name+'-48s.wav'))
for src,dst in [(archive/'source/generation-log.json','generation-log.json'),(archive/'README.md','source-notes.md'),(archive/'source/mix-validation.json','original-mix-validation.json')]:shutil.copy2(src,dest/dst)
sources=[{'id':name,'path':str((dest/(name+'-48s.wav')).relative_to(P)),'sha256':sha(dest/(name+'-48s.wav')),'origin':'Preserved prepared stem from the studio Last Lantern source set; provider prompts and original preparation evidence copied beside it.','audition':'Pending current-film listening; selection based on matching source direction and preserved source provenance.'} for name in ['music','woodland','leaves','hearth']]
session={'format':'ambiance-audio-session','schema_version':1,'id':'amberwatch-score-v1','sample_rate':48000,'frames':2304000,'master_gain_db':0,'sources':sources,'stems':[{'id':'music','gain_db':-1.5,'role':'Sparse piano, strings and celesta; warm nocturnal identity'},{'id':'woodland','gain_db':0,'role':'Soft distant autumn air'},{'id':'leaves','gain_db':0,'role':'Quiet dry leaf passes across nearby stone'},{'id':'hearth','gain_db':-6,'role':'Muffled fire behind the illuminated cottage windows'}],'clips':[{'id':a['id'],'source':a['id'],'stem':a['id'],'at_frame':0,'source_start_frame':0,'frames':2304000} for a in sources],'notes':'48-second circular prepared sources preserve existing tails and phrase join; no new provider generation. Cat has no added vocalization. Current-film audition remains open.'}
save(P/'audio/session.json',session)
effects=json.loads(json.dumps(session));effects['id']='amberwatch-effects-v1';effects['stems']=[s for s in effects['stems'] if s['id']!='music'];effects['sources']=[s for s in effects['sources'] if s['id']!='music'];effects['clips']=[s for s in effects['clips'] if s['id']!='music'];effects['master_gain_db']=4
save(P/'audio/effects-session.json',effects)
print(json.dumps({'ok':True,'scene':str(P/'scene/scene.json'),'audio_sources':len(sources)}))
