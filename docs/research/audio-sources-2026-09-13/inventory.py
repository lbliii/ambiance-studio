"""Bounded read-only BASE-01 survey; writes only its explicitly chosen report."""
import hashlib, json, sys, subprocess, wave
from pathlib import Path
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from PIL import Image
from ambiance_studio import deliveries, views
ROOT=Path(__file__).resolve().parents[3]
PROJECTS=[Path('/Users/lb/.codex/worktrees/e31d/ambiance-studio/projects/amberwatch'),Path('/Users/lb/Developer/ambiance-studio/projects/last-lantern'),Path('/Users/lb/Developer/ambiance-studio/projects/the-midnight-collection')]
def identity(p):
 r={'path':str(p),'available':p.is_file()}
 if r['available']:
  with p.open('rb') as f:r.update(sha256=hashlib.file_digest(f,'sha256').hexdigest(),bytes=p.stat().st_size)
 return r
def read(p):return json.loads(p.read_text())
def image(p):
 r=identity(p)
 if r['available']:
  try:
   with Image.open(p) as im:r.update(dimensions=list(im.size),mode=im.mode);im.verify()
  except Exception as e:r['error']=str(e)
 return r
def probe(p):
 r=identity(p)
 if not r['available']:return r
 try:
  x=subprocess.run(['/usr/bin/afinfo','-x','-r',str(p)],capture_output=True,text=True)
  if x.returncode:raise ValueError(x.stderr.strip())
  tree=ET.fromstring(x.stdout)
  for e in tree.iter():e.tag=e.tag.split('}')[-1]
  r['format']={e.tag:e.text for e in tree.find('.//track') if e.tag not in ['alerts','pcm_info','source_info','packet_table_info']}
  r['format']['container']=tree.findtext('.//file_type')
  pt=tree.find('.//packet_table_info')
  if pt is not None:r['format']['packet_table']={e.tag:e.text for e in pt}
  if p.suffix=='.wav':
   with wave.open(str(p),'rb') as f:
    n=0
    while b:=f.readframes(65536):n+=len(b)
    r['decode']={'backend':'python-wave','complete':n==f.getnframes()*f.getnchannels()*f.getsampwidth(),'frames':f.getnframes()}
  else:r['decode']={'complete':False,'note':'afinfo packet inspection only; conversion validation follows in AUDIO-01'}
 except Exception as e:r['error']=str(e)
 return r
def scan(p):
 conf=read(p/'ambiance-project.json');scene=read(p/conf['scene']);catalog=read(p/conf['catalog'])
 r={'project':str(p),'scene':identity(p/conf['scene']),'catalog':identity(p/conf['catalog']),'canvas':scene.get('canvas'),'saved_views':scene.get('views'),'selected':{},'art':[],'audio':[],'records':[],'risks':[]}
 for channel in ['review','release']:
  try:
   selected=deliveries.current(p,channel);r['selected'][channel]={'selection':selected}
   if selected:
    d=deliveries.load(p,selected['delivery']);r['selected'][channel].update(record=identity(p/'deliveries'/f'{d["id"]}.json'),entries=deliveries.entries(d),working_inputs=d.get('working_inputs'),notes=d.get('notes'))
    for e in r['selected'][channel]['entries'].values():e['actual_movie']=identity(p/e['movie']['path'])
  except Exception as e:r['selected'][channel]={'error':str(e)}
 try:r['view_summary']=views.project_summary(p)
 except Exception as e:r['view_summary']={'error':str(e)}
 used={x.get('asset') for x in scene.get('layers',[])}
 for a in catalog['assets']:
  row={'id':a['id'],'used_by_working_layer':a['id'] in used,'prepared':image(p/a['file']),'declared_sha256':a.get('sha256'),'atlas':a.get('atlas'),'registration_mapping':a.get('registration_mapping'),'provenance':a.get('provenance'),'sources':[]}
  prov=a.get('provenance',{});base=(p/prov['recipe']).parent if prov.get('recipe') else p
  for source in prov.get('sources',[]):row['sources'].append(image((base/source['file']).resolve()))
  row['native_original_detail']='unknown beyond recorded immediate source mappings; full camera/rig motion envelope not evaluated'
  if not row['registration_mapping']:r['risks'].append(a['id']+': no registration mapping')
  if row['registration_mapping'] and row['registration_mapping'].get('shared_scale',1)>1:r['risks'].append(a['id']+': prepared art was enlarged')
  r['art'].append(row)
 # Original/reference surfaces, not all intermediate proofs.
 original_paths=set()
 for folder in ['inputs','assets/source','assets/sources','reference']:
  original_paths.update(x for x in (p/folder).rglob('*') if x.suffix.lower() in ['.png','.jpg','.jpeg','.webp'])
 r['original_art']=[image(x) for x in sorted(original_paths)]
 for f in sorted((p/'audio').rglob('*')):
  if f.suffix.lower() in ['.wav','.mp3','.m4a','.mp4','.audio','.aiff','.flac','.pcm']:
   row=probe(f);row['usage']='run/master/stem derivative' if any(k in f.parts for k in ['runs','masters','stems','proofs','previews']) else 'candidate source';row['audition']='unknown unless explicitly linked by records below';r['audio'].append(row)
  elif f.suffix=='.json' and f.name not in ['report.json','technical-check.json']:
   r['records'].append({'identity':identity(f),'data':read(f)})
 for name in ['plans/source-ledger.json','plans/sound-generation-ledger.json','plans/production-plan.json']:
  f=p/name
  if f.exists():r['records'].append({'identity':identity(f),'data':read(f)})
 r['risks']+=['Native source detail is not established by atlas size or successful encode.','Saved view dimensions are intent; selected edition dimensions are separate.','No fresh audition, physical-device observation, full-resolution visual review or provider entitlement check was performed.']
 return r
if __name__=='__main__':
 data={'format':'ambiance-base-source-inventory','schema_version':1,'baseline':'00c64436543d0252fc0850f3ef58e686badda1b6','scope':'three available projects plus repository reference records; source media read-only','method':'Existing read-only deliveries.current/load and views.project_summary; overview/latest avoided because baseline delivery scope/coverage can persist reports. Full WAV payload reads and Core Audio real packet probes. No selection/review writes.','projects':[scan(p) for p in PROJECTS],'reference_records':[{'identity':identity(p),'data':read(p)} for p in sorted((ROOT/'reference').glob('*.json'))],'unavailable_projects':['a-quieter-tomorrow-fresh','midnight-reading-room'],'provider_facts':{'scope':'historical local records only','current_entitlement':'unknown','current_public_api_formats':'not verified in this bounded local inventory','connected_route':'generation ledger records actual model/output IDs; retrieved bytes take precedence over filename or requested format','no_new_generation':True}}
 # Historical selected source paths are not assumed relative to this checkout.
 ledger=read(ROOT/'reference/audio-generation-log.json')
 data['historical_source_resolution']=[{'selected_source':g.get('selected_source'),'available_matches':[x['path'] for p in data['projects'] for x in p['audio'] if x['path'].endswith(g.get('selected_source','__missing'))],'status':'unresolved when no exact suffix match; no regeneration'} for g in ledger['generations']]
 Path(sys.argv[1]).write_text(json.dumps(data,indent=2)+'\n')
 print(json.dumps({'out':sys.argv[1],'sha256':identity(Path(sys.argv[1]))['sha256'],'projects':[{'project':p['project'],'art':len(p['art']),'audio':len(p['audio'])} for p in data['projects']]}))
