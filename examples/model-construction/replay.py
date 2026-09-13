"""Public CLI replay and exact evidence ledger; fresh directory required."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ambiance_studio.file_identity import digest
from create_fixture import create


def replay(out):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    source=create(out/'source');steps=[]
    def run(argv):
        full=[str(ROOT/'ambiance'),*map(str,argv)]
        result=subprocess.run(full,cwd=ROOT,capture_output=True,text=True)
        data=json.loads(result.stdout)
        steps.append({'argv':full,'returncode':result.returncode,'result':data,'stderr':result.stderr})
        (out/'replay.json').write_text(json.dumps({'steps':steps},indent=2)+'\n')
        if result.returncode:raise RuntimeError(data)
        return data
    package=out/'package';proof=out/'proof';entry=out/'entry';lowered=out/'lowered'
    run(['model','build',source/'models/lantern.json','--source-root',source,'--out',package])
    run(['model','inspect',package,'--out',out/'inspect.json'])
    run(['model','lower',package,'--state',source/'rest.json','--out',lowered])
    run(['--project',lowered,'scene','check','--out',out/'scene-check.json'])
    run(['model','proof',package,'--recipe',source/'proof.json','--out',proof])
    run(['model','check',proof,'--package',package,'--recipe',source/'proof.json'])
    run(['model','admit',package,'--proof',proof,'--recipe',source/'proof.json','--out',entry])
    # Remove the independently built package/proof/source from their original paths.
    # Retain them under evidence so byte provenance remains inspectable.
    (out/'unavailable').mkdir()
    for p in [source,package,proof]:shutil.move(str(p),str(out/'unavailable'/p.name))
    run(['model','inspect',entry,'--out',out/'entry-inspect.json'])
    run(['model','check',entry/'proof','--package',entry/'package','--recipe',entry/'proof-recipe.json'])
    run(['model','lower',entry/'package','--state',out/'unavailable/source/rest.json','--out',out/'reopened'])
    for name in ['scene/scene.json','assets/catalog.json','mapping.json']:
        if digest(lowered/name)!=digest(out/'reopened'/name):raise RuntimeError('Portable lowering changed '+name)
    (out/'evidence.json').write_text(json.dumps({'format':'model-public-cli-replay','schema_version':1,'steps':steps,
        'files':{p.relative_to(out).as_posix():digest(p) for p in sorted(out.rglob('*')) if p.is_file()},
        'observations':[], 'limitations':['Geometric raster-root specimen; no production painting, receiver behavior, animation, scene instances or artistic acceptance.']},indent=2)+'\n')
    return {'ok':True,'evidence':str(out/'evidence.json'),'sha256':digest(out/'evidence.json'),'proof':str(entry/'proof/index.html')}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args();print(json.dumps(replay(args.out),indent=2))
